"""Engine 5 check: which signals pick the free agents that actually score, and what FAAB buys.
Every waiver/free-agent add in the league archive (2021-2025): who was added in week w, and their PPR points in weeks w..w+3."""
import json, gzip, os, numpy as np, pandas as pd, collections
from scipy.stats import spearmanr
B = os.path.dirname(os.path.abspath(__file__)); H = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bt")
L = json.load(gzip.open(f"{H}/leagues.json.gz", "rt"))["leagues"]
PJ = json.load(gzip.open(f"{H}/sleeper_proj.json.gz", "rt"))["w"]
ids = pd.read_csv(B + "/dl/ids.csv", low_memory=False)[["sleeper_id", "gsis_id"]].dropna()
ids["sleeper_id"] = ids.sleeper_id.astype(str).str.replace(r"\.0$", "", regex=True); s2g = dict(zip(ids.sleeper_id, ids.gsis_id))
import sys; sys.path.insert(0, B); from load import weekly
W = weekly(range(2021, 2026)); W = W[W.position.isin(["QB", "RB", "WR", "TE"])]
EP = pd.concat([pd.read_csv(f"{B}/dl/ep_{y}.csv", usecols=["season", "week", "player_id", "total_fantasy_points_exp"]) for y in range(2021, 2026)]) if os.path.exists(f"{B}/dl/ep_2021.csv") else None
fp = W.set_index(["player_id", "season", "week"]).fp.to_dict(); pos = dict(zip(W.player_id, W.position))
xe = EP.groupby(["player_id", "season", "week"]).total_fantasy_points_exp.sum().to_dict() if EP is not None else {}
adds = collections.defaultdict(lambda: collections.Counter()); bids = []
for lg in L.values():
    if lg["season"] > 2025: continue
    for t in lg.get("tx") or []:
        if t[0] not in ("waiver", "free_agent") or not t[1]: continue
        for pid in (t[3] or {}):
            g = s2g.get(pid)
            if not g or pos.get(g) is None: continue
            adds[(lg["season"], t[1])][g] += 1
            if t[0] == "waiver" and t[7] is not None: bids.append((lg["season"], t[1], g, t[7]))
rows = []
for (s, w), c in adds.items():
    if w < 3 or w > 15: continue
    for g, n in c.items():
        past = [fp.get((g, s, k)) for k in range(1, w)]; pv = [x for x in past if x is not None]
        xp = [xe.get((g, s, k)) for k in range(1, w)]; xv = [x for x in xp if x is not None]
        nxt = [fp.get((g, s, k), 0.0) for k in range(w, w + 4)]
        sid = next((k for k, v in s2g.items() if v == g), None)
        pj = (PJ.get(f"{s}-{w}", {}).get(sid) or {}).get("pts_ppr") if sid else None
        rows.append(dict(s=s, w=w, g=g, pos=pos[g], n=n, ppg=np.mean(pv) if pv else 0, gp=len(pv), l3=np.mean(pv[-3:]) if pv else 0,
                         xfp=np.mean(xv) if xv else 0, x3=np.mean(xv[-3:]) if xv else 0, proj=pj or 0, y=sum(nxt)))
D = pd.DataFrame(rows); print(len(D), "player-weeks added")
D["app"] = .62 * D.ppg + .38 * D.proj
D["usage"] = .5 * D.x3 + .25 * D.xfp + .25 * D.proj
res = {}
for c in ["n", "proj", "ppg", "l3", "xfp", "x3", "app", "usage"]:
    r = [spearmanr(q[c], q.y).correlation for _, q in D.groupby(["s", "w"]) if len(q) >= 15]
    res[c] = round(float(np.nanmean(r)), 3)
# top-5 per week by each signal: average points they scored next 4 weeks
for c in ["n", "proj", "app", "usage", "x3"]:
    res["top5_" + c] = round(float(np.mean([q.nlargest(5, c).y.mean() for _, q in D.groupby(["s", "w"]) if len(q) >= 15])), 1)
# FAAB: winning bid vs next-4-week points
Bd = pd.DataFrame(bids, columns=["s", "w", "g", "bid"]).merge(D[["s", "w", "g", "y", "n"]], on=["s", "w", "g"], how="left").dropna()
Bd["b"] = pd.cut(Bd.bid, [-1, 0, 3, 10, 25, 50, 1000])
res["faab"] = {str(k): [round(float(v.y.mean()), 1), round(float((v.y / v.bid.clip(lower=1)).median()), 2), len(v)] for k, v in Bd.groupby("b", observed=True)}
res["bid_vs_demand"] = {int(k): round(float(v.bid.median()), 1) for k, v in Bd.assign(dm=pd.cut(Bd.n, [0, 2, 5, 10, 25, 1e9], labels=[1, 2, 3, 4, 5])).groupby("dm", observed=True)}
print(json.dumps(res, indent=1)); json.dump(res, open(B + "/e8.json", "w"), indent=1)
