"""e9_exact2: same test as e9_exact, but logs the top 3 add/drop pairs per add position (with the drop's own 4-week value)
so add-calibration, drop-risk and threshold rules can be fitted on 2024 and checked on 2025 without rerunning. Runs leagues in parallel.
Team-level waiver test: for every team in every rebuilt redraft league each week, pick the one add each method recommends
(dropping that method's least useful bench player) and measure the real lineup points it added over the next 4 weeks."""
import json, gzip, os, collections, numpy as np, pandas as pd, pickle
B = os.path.dirname(os.path.abspath(__file__)); H = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bt")
ST = json.load(gzip.open(f"{H}/sleeper_stats.json.gz", "rt"))["w"]
D = pd.read_pickle(B + "/e9_Dfit.pkl")
L = json.load(gzip.open(f"{H}/leagues.json.gz", "rt"))["leagues"]
G = pd.read_csv(B + "/dl/games.csv", low_memory=False); G = G[G.game_type == "REG"]
OFF = ("QB", "RB", "WR", "TE")
ELIG = {"QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"}, "FLEX": {"RB", "WR", "TE"}, "WRRB_FLEX": {"RB", "WR"}, "REC_FLEX": {"WR", "TE"}, "SUPER_FLEX": set(OFF)}
SEAS = [int(x) for x in os.environ.get("SEAS", "2024,2025").split(",")]
pred = {}; posd = {}; projd = {}; ownd = {}; playd = {}; teamd = {}
for r in D[D.s.isin(SEAS)].sort_values("w").itertuples():
    pred[(r.s, r.w, r.pid)] = max(0.0, r.lin); posd[r.pid] = r.pos; projd[(r.s, r.w, r.pid)] = r.proj; ownd[(r.s, r.w, r.pid)] = r.own; playd[(r.s, r.w, r.pid)] = r.play; teamd[(r.s, r.pid)] = r.team
TW = collections.defaultdict(set)
for g in G.itertuples(): TW[(g.season, g.week)] |= {g.home_team, g.away_team}
def carry(s, w, pid, d):
    for ww in (w, w - 1, w - 2):
        if (s, ww, pid) in d: return d[(s, ww, pid)]
    return 0.0
def plays(s, w, pid):
    t = teamd.get((s, pid)); return [1 if (t is None or t in TW[(s, k)]) else 0 for k in range(w, w + 4)]
def vec(s, w, pid, mode):
    pl = plays(s, w, pid); r = carry(s, w, pid, pred); j = projd.get((s, w, pid), 0.0); jr = carry(s, w, pid, projd)
    if mode == "proj": return [jr * pl[i] if i else j for i in range(4)]
    if mode == "lin": return [r * pl[i] for i in range(4)]
    if mode == "hyb": return [j if i == 0 else r * pl[i] for i in range(4)]
    if mode == "hybinj":
        out_now = (s, w, pid) not in projd and pl[0] == 1  # on a roster, team plays, but no projection this week = out
        return [j if i == 0 else r * pl[i] * (.6 if out_now else 1) for i in range(4)]
    if mode == "blend": return [(.5 * j + .5 * r) if i == 0 else (.5 * jr + .5 * r) * pl[i] for i in range(4)]
def actual(s, k, pid, key):
    st = ST.get(f"{s}-{k}", {}).get(pid)
    return (st or {}).get(key, 0.0) if st else 0.0
def opt(players, val, slots):
    pool = sorted(players, key=lambda p: -val(p)); used = set(); tot = 0.0
    for sl in sorted(slots, key=lambda x: len(ELIG[x])):
        for p in pool:
            if p not in used and posd.get(p) in ELIG[sl]: used.add(p); tot += max(0.0, val(p)); break
    return tot
res = collections.defaultdict(list); nteam = 0; REC = []; MGR = []
SRC = os.environ.get("SRC", "keepers")
if SRC == "keepers": LG = [pr["s"] for pr in json.load(gzip.open(f"{H}/keepers.json.gz", "rt"))["pairs"].values()]
else: LG = list(json.load(gzip.open(f"{H}/rosters.json.gz", "rt"))["leagues"].values())
NL = collections.Counter()
def run(lg):
    global nteam
    REC.clear(); MGR.clear(); nteam = 0
    s = lg["season"]
    if s not in SEAS: return [], [], 0
    slots = [x for x in (lg.get("pos") or []) if x in ELIG]
    if not slots: return [], [], 0
    rec = (lg.get("sc") or {}).get("rec", 1); key = "pts_ppr" if rec >= .75 else "pts_half_ppr" if rec >= .25 else "pts_std"
    WK = {int(k): v for k, v in (lg.get("weeks") or {}).items()}
    tx = sorted(lg.get("tx") or [], key=lambda t: (t[1], t[8] or 0))
    NL[(lg.get("type"), s)] += 1
    for w in range(3, 14):
        if (w - 1) not in WK: continue
        # exact rosters as they stood after week w-1 (the pool waivers for week w are claimed from)
        ro = {str(pid): r[0] for r in WK[w - 1] for pid in (r[4] or [])}
        avail = [pid for pid in posd if (s, w, pid) in pred and pid not in ro]
        teams = collections.defaultdict(list)
        for pid, rid in ro.items():
            if posd.get(pid) in OFF: teams[rid].append(pid)
        ks = range(w + 1, min(w + 4, 18))  # week w left out: some real adds were made after that week's games
        for rid, mine in teams.items():
            if len(mine) < len(slots): continue
            nteam += 1
            pr = lambda p: pred.get((s, w, p), 0.0)
            base_act = sum(opt(mine, lambda p: actual(s, k, p, key), slots) for k in ks)
            def realized(add, drop):
                new = [p for p in mine if p != drop] + [add]
                return sum(opt(new, lambda p: actual(s, k, p, key), slots) for k in ks) - base_act
            def worst_bench(val):
                st = set(); pool = sorted(mine, key=lambda p: -val(p)); used = set()
                for sl in sorted(slots, key=lambda x: len(ELIG[x])):
                    for p in pool:
                        if p not in used and posd.get(p) in ELIG[sl]: used.add(p); break
                bench = [p for p in mine if p not in used]
                return min(bench, key=val) if bench else min(mine, key=val)
            ks4 = list(range(w, w + 4))
            for mode in ("hybinj",):
                V = {p: vec(s, w, p, mode) for p in set(mine) | set(avail)}
                VV = lambda p: V[p] if p in V else V.setdefault(p, vec(s, w, p, mode))
                tot = lambda ps: sum(opt(ps, lambda p, i=i: VV(p)[i], slots) for i in range(4) if w + i <= 17)
                base = tot(mine)
                cand = sorted(avail, key=lambda p: -sum(V[p]))[:20]
                pairs = []
                for d in mine:
                    rest = [x for x in mine if x != d]; b0 = tot(rest)
                    if base - b0 > float(os.environ.get("DL", "25")): continue
                    for a in cand:
                        pairs.append((tot(rest + [a]) - base, a, d, base - b0))
                byp = collections.defaultdict(list)
                for pr_ in sorted(pairs, key=lambda x: -x[0]):
                    lst = byp[posd.get(pr_[1])]
                    if len(lst) < 3 and all(pr_[1] != x[1] for x in lst): lst.append(pr_)
                for ap, lst in byp.items():
                    for k_, (g, a, d, dc) in enumerate(lst):
                        REC.append(dict(s=s, w=w, lg=lg["id"], t=lg.get("type"), rid=rid, k=k_, g=g, a=a, d=d, dcost=dc, r3=realized(a, d), apos=ap, dpos=posd.get(d), dval=sum(V[d]), aval=sum(V[a]), nslot=len(slots), nros=len(mine)))
            for t in tx:
                if t[1] != w or t[0] not in ("waiver", "free_agent") or len(t[3] or {}) != 1: continue
                (ad, rr), = (t[3] or {}).items()
                if rr != rid or posd.get(str(ad)) not in OFF or str(ad) in mine: continue
                dr = [str(x) for x in (t[4] or {}) if str(x) in mine]
                new = [p for p in mine if p not in dr] + [str(ad)]
                MGR.append(dict(s=s, w=w, lg=lg["id"], rid=rid, typ=t[0], bid=t[7], r3=sum(opt(new, lambda p: actual(s, k, p, key), slots) for k in ks) - base_act,
                                g=tot(dr and [p for p in mine if p not in dr] + [str(ad)] or mine + [str(ad)]) - base if True else 0, a=str(ad)))
    return list(REC), list(MGR), nteam
if __name__ == "__main__":
    import multiprocessing as mp
    RA, MA = [], []
    with mp.Pool(4) as P:
        for i, (r_, m_, n_) in enumerate(P.imap_unordered(run, LG, chunksize=4)):
            RA += r_; MA += m_; nteam += n_
            if i % 100 == 0: print(i, len(RA), flush=True)
    REC, MGR = RA, MA
    pickle.dump((REC, MGR), open(B + f"/e9_exact2_{SRC}.pkl", "wb"))
    out = {"teams_weeks": nteam}
    print(json.dumps(out, indent=1))
