"""B5 / e32: playoff and title odds replay data. One record per (league, checkpoint c in 4/8/11) from bt/rosters.json.gz
(exact weekly rosters, 2022-25, 900 leagues): record after week c (h2h wins/ties, points for, median-league wins if the
league plays the median), the real schedule for weeks c+1..pws-1, each team's strength as the app computes it
(sum of the best legal QB/RB/WR/TE/FLEX/SF lineup by rest-of-season pts/game; per player the app's shipped ROS estimate
`hm` from backtest/e26_scored.pkl, known before week c+1, rescaled to league scoring like wvScale), the season-to-date
pts/game, and the truth: playoff teams (winners bracket) and champion (bracket place 1).
Also the last regular-season week (c = pws-2, `last`). Output backtest/e32_recs.pkl. Run: python3 backtest/e32_data.py (~1 min)."""
import json, gzip, os, collections, pickle
import numpy as np, pandas as pd
B = os.path.dirname(os.path.abspath(__file__)); H = os.path.join(B, "..", "bt")
ST = json.load(gzip.open(f"{H}/sleeper_stats.json.gz", "rt"))["w"]
LG = json.load(gzip.open(f"{H}/rosters.json.gz", "rt"))["leagues"]
LL = json.load(gzip.open(f"{H}/leagues.json.gz", "rt"))["leagues"]
E = pd.read_pickle(B + "/e26_scored.pkl")
HMV = {(r.s, r.w, r.pid): (r.pos, max(0.0, float(r.hm))) for r in E.itertuples()}
ELIG = {"QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"}, "FLEX": {"RB", "WR", "TE"}, "WRRB_FLEX": {"RB", "WR"},
        "REC_FLEX": {"WR", "TE"}, "SUPER_FLEX": {"QB", "RB", "WR", "TE"}}
CPS = (4, 8, 11)

def lpts(st, sc, key):
    if not st: return 0.0
    b = st.get(key, 0.0) or 0.0
    if sc.get("pass_td") is not None and st.get("pass_td"): b += (sc["pass_td"] - 4) * st["pass_td"]
    if sc.get("pass_int") is not None and st.get("pass_int"): b += (sc["pass_int"] + 1) * st["pass_int"]
    return b

# position fallback factor (league scoring / PPR) like wvRecFactor
RF = collections.defaultdict(lambda: [0.0, 0.0])
def scale(s, c, pid, pos, sc, key):
    num = den = 0.0; g = 0
    for w in range(1, c + 1):
        st = ST.get(f"{s}-{w}", {}).get(pid)
        if not st or not st.get("gp"): continue
        g += 1; num += lpts(st, sc, key); den += st.get("pts_ppr", 0.0) or 0.0
    if g >= 3 and den / g > 3: return max(.55, min(1.3, num / den))
    return {"pts_ppr": 1.0, "pts_half_ppr": {"QB": 1.0, "RB": .9, "WR": .86, "TE": .85}, "pts_std": {"QB": 1.0, "RB": .8, "WR": .72, "TE": .7}}[key][pos] if key != "pts_ppr" else 1.0

def best(players, slots):
    pool = sorted(players, key=lambda x: (-x[2], x[0])); used = set(); tot = 0.0
    for sl in sorted(slots, key=lambda x: len(ELIG[x])):
        for p in pool:
            if p[0] not in used and p[1] in ELIG[sl]: used.add(p[0]); tot += p[2]; break
    return tot

recs = []; skipped = collections.Counter()
for lid in sorted(LG):
    lg = LG[lid]; s = lg["season"]; L2 = LL.get(lid)
    if s > 2025 or not L2 or L2.get("status") != "complete" or L2.get("guillotine"): skipped["meta"] += 1; continue
    br = L2.get("bracket") or []
    champ = [m[4] for m in br if m[6] == 1]
    poset = {t for m in br for t in (m[2], m[3]) if isinstance(t, int)}
    pws, pt = int(L2["pws"]), int(L2["pteams"])
    if len(champ) != 1 or len(poset) != pt: skipped["bracket"] += 1; continue
    slots = [x for x in lg["pos"] if x in ELIG]
    WK = {int(k): v for k, v in lg["weeks"].items()}
    if any(w not in WK for w in range(1, pws)): skipped["weeks"] += 1; continue
    rids = sorted({r[0] for r in WK[1]}); n = len(rids); idx = {r: i for i, r in enumerate(rids)}
    if n < 4 or pt >= n: skipped["size"] += 1; continue
    sc = lg.get("sc") or {}; rec = sc.get("rec", 1)
    key = "pts_ppr" if rec >= .75 else "pts_half_ppr" if rec >= .25 else "pts_std"
    # median league? compare Sleeper's final regular-season wins with head-to-head wins
    h2h = collections.Counter(); pairs = {}
    for w in range(1, pws):
        g = collections.defaultdict(list)
        for r in WK[w]:
            if r[1] is not None: g[r[1]].append(r)
        pairs[w] = [(idx[a[0]], idx[b[0]], a[2], b[2]) for a, b in [v for v in g.values() if len(v) == 2]]
    hw = sum(1 for w in range(1, pws) for p in pairs[w] if p[2] != p[3])
    rw = sum(r[1] for r in L2["rost"])
    med = rw > 1.5 * hw
    # division leagues can't be told apart; rounds per playoff week -> app's playoff_round_type
    rounds = max(m[0] for m in br); pw = int(L2["lws"]) - pws + 1
    prt = 2 if pw >= 2 * rounds else 1 if pw == rounds + 1 else 0
    for c in CPS + (pws - 2,):
        if c >= pws - 1 or (c == pws - 2 and c in CPS): continue
        W = np.zeros(n); PF = np.zeros(n); G = np.zeros(n)
        for w in range(1, c + 1):
            for x, y, a, b in pairs[w]:
                PF[x] += a; PF[y] += b; G[x] += 1; G[y] += 1
                if a > b: W[x] += 1
                elif b > a: W[y] += 1
                else: W[x] += .5; W[y] += .5
            if med:
                sc_ = sorted(r[2] for r in WK[w]); m = (sc_[(n - 1) // 2] + sc_[n // 2]) / 2
                for r in WK[w]:
                    if r[2] > m: W[idx[r[0]]] += 1
                    elif r[2] == m: W[idx[r[0]]] += .5
        stren = np.zeros(n); miss = 0; tot = 0
        for r in WK[c]:
            pl = []
            for pid in (r[4] or []):
                v = HMV.get((s, c + 1, str(pid)))
                if v is None: continue
                pos, hm = v; pl.append((str(pid), pos, hm * scale(s, c, str(pid), pos, sc, key)))
            stren[idx[r[0]]] = best(pl, slots)
        fut = [[(x, y) for x, y, _, _ in pairs[w]] for w in range(c + 1, pws)]
        po = np.array([1 if r in poset else 0 for r in rids]); ch = np.array([1 if r == champ[0] else 0 for r in rids])
        recs.append(dict(lid=lid, s=s, c=c, n=n, pt=pt, prt=prt, med=med, w=W, pf=PF, g=G, st=stren, fut=fut, po=po, ch=ch,
                         nfut=len(fut), last=c not in CPS))
print(len(recs), "records", len({r['lid'] for r in recs}), "leagues", dict(skipped))
print(collections.Counter((r["s"], r["c"]) for r in recs)); print("median leagues", sum(r["med"] for r in recs if r["c"] == 4))
print("prt", collections.Counter(r["prt"] for r in recs if r["c"] == 4))
pickle.dump(recs, open(B + "/e32_recs.pkl", "wb"))
