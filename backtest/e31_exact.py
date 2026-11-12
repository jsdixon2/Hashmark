"""e31: waiver advice re-tested on today's projections (engine 5, task A1/B7).

Same team-week replay as e9_exact2 (bt/rosters.json.gz exact weekly rosters, 2024-25; the archive has no 2026 leagues),
with the app's CURRENT waiver code path:
  - outlook per player = wvVec: this week Sleeper's projection, later weeks the fitted rate wvRate (WVC; e9_Dfit `lin`),
    out players 0 now and x.6 later; every free agent trimmed WV_FAH = 1.5 pts/game (v67);
  - drops: cost <= 25, the 8 cheapest by cost + WV_DROPW x drop's own 4-week points (v65); 24 best free agents;
    each add keeps the drop with the best g' = lift - .25 x drop's 4-week points; top 3 adds per position are logged.
New measure r3h: before each of weeks w+1..w+3 the lineup is set by Hashmark's CURRENT weekly projection for that week
(scripts/proj_panel.py build(): PJC refit v108, questionable multiplier p111, props blend), in the league's scoring,
and scored on actual points; gain = that minus the same for the roster without the move. r3s (old: lineups set by the
week-w waiver outlook) and r3 (hindsight-best lineups) are kept for comparison. Managers' own single-add claims too.
Output: backtest/e31_exact.pkl (REC, MGR). Run: python3 backtest/e31_exact.py (4 processes, ~10 min)."""
import json, gzip, os, sys, collections, pickle, re
import numpy as np, pandas as pd
B = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(B); H = ROOT + "/bt"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/scripts")
ST = json.load(gzip.open(f"{H}/sleeper_stats.json.gz", "rt"))["w"]
D = pd.read_pickle(B + "/e9_Dfit.pkl")
G = pd.read_csv(B + "/dl/games.csv", low_memory=False); G = G[G.game_type == "REG"]
OFF = ("QB", "RB", "WR", "TE")
ELIG = {"QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"}, "FLEX": {"RB", "WR", "TE"}, "WRRB_FLEX": {"RB", "WR"}, "REC_FLEX": {"WR", "TE"}, "SUPER_FLEX": set(OFF)}
SEAS = [2024, 2025]
WV_FAH, WV_DROPW = 1.5, .25

# Hashmark's weekly projection for EVERY projected player-week (proj_panel.build skips players who did not play; a lineup
# setter must not know that in advance, so that filter is lifted here; the formula itself is untouched).
src = open(ROOT + "/scripts/proj_panel.py", encoding="utf-8").read()
a_ = '            if not stt or not stt.get("gp"): continue\n'; assert src.count(a_) == 1
src = src.replace(a_, '            stt = stt or {}\n')
NS = {"__name__": "proj_panel_all"}; exec(compile(src, "proj_panel_all", "exec"), NS)
HM = {}
for sc in ("ppr", "half", "std"):
    for r in NS["build"](seasons=SEAS, scoring=sc): HM[(sc, r["s"], r["w"], r["pid"])] = r["hm"]
print("hm rows", len(HM), flush=True)

pred = {}; posd = {}; projd = {}; teamd = {}
for r in D[D.s.isin(SEAS)].sort_values(["w", "pid"]).itertuples():
    pred[(r.s, r.w, r.pid)] = max(0.0, r.lin); posd[r.pid] = r.pos; projd[(r.s, r.w, r.pid)] = r.proj; teamd[(r.s, r.pid)] = r.team
TW = collections.defaultdict(set)
for g in G.itertuples(): TW[(g.season, g.week)] |= {g.home_team, g.away_team}
def carry(s, w, pid, d):
    for ww in (w, w - 1, w - 2):
        if (s, ww, pid) in d: return d[(s, ww, pid)]
    return 0.0
def plays(s, w, pid):
    t = teamd.get((s, pid)); return [1 if (t is None or t in TW[(s, k)]) else 0 for k in range(w, w + 4)]
def vec(s, w, pid):  # app wvVec (hybinj in e9): this week Sleeper's projection, then the rate; out now -> later weeks x.6
    pl = plays(s, w, pid); r = carry(s, w, pid, pred); j = projd.get((s, w, pid), 0.0)
    out_now = (s, w, pid) not in projd and pl[0] == 1
    return [j if i == 0 else r * pl[i] * (.6 if out_now else 1) for i in range(4)]
def actual(s, k, pid, key):
    st = ST.get(f"{s}-{k}", {}).get(pid)
    return (st or {}).get(key, 0.0) if st else 0.0
def opt(players, val, slots):
    pool = sorted(players, key=lambda p: (-val(p), p)); used = set(); tot = 0.0
    for sl in sorted(slots, key=lambda x: len(ELIG[x])):
        for p in pool:
            if p not in used and posd.get(p) in ELIG[sl]: used.add(p); tot += max(0.0, val(p)); break
    return tot
def hist(s, w, pid):  # the add's own season so far (PPR): games, total, best single week, last week
    xs = [(ST.get(f"{s}-{k}", {}).get(pid) or {}) for k in range(1, w)]
    xs = [x.get("pts_ppr", 0.0) for x in xs if x.get("gp")]
    return len(xs), sum(xs), max(xs) if xs else 0.0, xs[-1] if xs else 0.0
LG = sorted(json.load(gzip.open(f"{H}/rosters.json.gz", "rt"))["leagues"].values(), key=lambda l: str(l["id"]))
def run(lg):
    REC, MGR, nteam = [], [], 0
    s = lg["season"]
    if s not in SEAS: return REC, MGR, 0
    slots = [x for x in (lg.get("pos") or []) if x in ELIG]
    if not slots: return REC, MGR, 0
    rec = (lg.get("sc") or {}).get("rec", 1); key, sc = ("pts_ppr", "ppr") if rec >= .75 else ("pts_half_ppr", "half") if rec >= .25 else ("pts_std", "std")
    WK = {int(k): v for k, v in (lg.get("weeks") or {}).items()}
    tx = sorted(lg.get("tx") or [], key=lambda t: (t[1], t[8] or 0, str(t)))
    for w in range(3, 14):
        if (w - 1) not in WK: continue
        ro = {str(pid): r[0] for r in WK[w - 1] for pid in (r[4] or [])}
        avail = [pid for pid in posd if (s, w, pid) in pred and pid not in ro]
        teams = collections.defaultdict(list)
        for pid, rid in ro.items():
            if posd.get(pid) in OFF: teams[rid].append(pid)
        ks = list(range(w + 1, min(w + 4, 18)))
        for rid in sorted(teams, key=str):
            mine = sorted(teams[rid])
            if len(mine) < len(slots): continue
            nteam += 1
            V = {p: vec(s, w, p) for p in set(mine) | set(avail)}
            V0 = {p: list(V[p]) for p in V}
            for p in avail: V[p] = [max(0.0, x - WV_FAH) if x > 0 else 0.0 for x in V[p]]
            VV = lambda p: V[p] if p in V else V.setdefault(p, vec(s, w, p))
            tot = lambda ps: sum(opt(ps, lambda p, i=i: VV(p)[i], slots) for i in range(4) if w + i <= 17)
            hmv = lambda p, k: HM.get((sc, s, k, p), 0.0)
            def setl(ps, k, by):  # lineup set before week k, scored on actual points
                if by == "hm": val = lambda p: hmv(p, k)
                else: val = lambda p: (V0[p] if p in V0 else VV(p))[k - w]
                pool = sorted(ps, key=lambda p: (-val(p), p)); used = []
                for sl in sorted(slots, key=lambda x: len(ELIG[x])):
                    for p in pool:
                        if p not in used and posd.get(p) in ELIG[sl]: used.append(p); break
                return sum(actual(s, k, p, key) for p in used)
            B0 = {by: [setl(mine, k, by) for k in ks] for by in ("hm", "old")}
            BH = [opt(mine, lambda p: actual(s, k, p, key), slots) for k in ks]
            def meas(new):
                return dict(r3h=sum(setl(new, k, "hm") for k in ks) - sum(B0["hm"]), r3s=sum(setl(new, k, "old") for k in ks) - sum(B0["old"]),
                            r3=sum(opt(new, lambda p: actual(s, k, p, key), slots) for k in ks) - sum(BH))
            base = tot(mine)
            dv = {d: sum(V[d]) for d in mine}
            drops = []
            for d in mine:
                rest = [x for x in mine if x != d]; c = base - tot(rest)
                if c <= 25: drops.append((c + WV_DROPW * dv[d], d, rest, c))
            drops = sorted(drops)[:8]
            cand = sorted(avail, key=lambda p: (-sum(V[p]), p))[:24]
            byp = collections.defaultdict(list)
            for a in cand:
                best = None
                for _, d, rest, c in drops:
                    raw = tot(rest + [a]) - base; gp = raw - WV_DROPW * dv[d]
                    if best is None or gp > best[0] + .05: best = (gp, raw, d, c)
                if best: byp[posd.get(a)].append((best, a))
            for ap, lst in byp.items():
                lst = sorted(lst, key=lambda x: (-x[0][0], x[1]))[:3]
                for k_, ((gp, raw, d, c), a) in enumerate(lst):
                    hg, ht, hmax, hlw = hist(s, w, a)
                    REC.append(dict(s=s, w=w, lg=lg["id"], t=lg.get("type"), rid=rid, k=k_, gp=gp, g=raw, a=a, d=d, dcost=c, apos=ap, dpos=posd.get(d),
                                    dval=dv[d], aval=sum(V[a]), a0=V[a][0], arate=V[a][1] if len(V[a]) > 1 else 0, dval0=V[d][0],
                                    hg=hg, ht=ht, hmax=hmax, hlw=hlw, nslot=len(slots), nros=len(mine), sc=sc,
                                    **meas([p for p in mine if p != d] + [a])))
            for t in tx:
                if t[1] != w or t[0] not in ("waiver", "free_agent") or len(t[3] or {}) != 1: continue
                (ad, rr), = (t[3] or {}).items()
                if rr != rid or posd.get(str(ad)) not in OFF or str(ad) in mine: continue
                dr = [str(x) for x in (t[4] or {}) if str(x) in mine]
                new = [p for p in mine if p not in dr] + [str(ad)]
                MGR.append(dict(s=s, w=w, lg=lg["id"], t=lg.get("type"), rid=rid, typ=t[0], bid=t[7], a=str(ad), apos=posd.get(str(ad)), ndrop=len(dr), **meas(new)))
    return REC, MGR, nteam
if __name__ == "__main__":
    import multiprocessing as mp
    RA, MA, NT = [], [], 0
    with mp.Pool(int(os.environ.get("NP", "4"))) as P:
        for i, (r_, m_, n_) in enumerate(P.imap(run, LG, chunksize=2)):
            RA += r_; MA += m_; NT += n_
            if i % 50 == 0: print(i, len(RA), len(MA), flush=True)
    pickle.dump((RA, MA, NT), open(B + "/e31_exact.pkl", "wb"))
    print("team-weeks", NT, "pairs", len(RA), "manager adds", len(MA))
