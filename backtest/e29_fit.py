#!/usr/bin/env python3
"""e29: refit the pregame win-odds spread WP (k, c, b) on 2021-24, test on 2025 and 2026 separately.
P(A wins) = logistic(1.7 b (pa - pb) / sqrt((pa k + c)^2 + (pb k + c)^2)). k, c and b are not separately identified
(scaling k and c by s equals dividing b by s), so b stays 1.01 and (k, c) are fitted; "widen" = one multiplier s on both
team sds (k=.16 s, c=5 s). Input: .build/agents/a2/e29_rows.json from e29_data.py. Usage: e29_fit.py [old|new]
(which team totals: old = build_report's grading, new = full projection in each league's scoring; default new)."""
import json, math, random, sys, collections
R = json.load(open(".build/agents/a2/e29_rows.json"))
TOT = sys.argv[1] if len(sys.argv) > 1 else "new"
I = (5, 6) if TOT == "old" else (7, 8)
rows = [(r[0], r[1], r[2], r[3], r[4], r[I[0]], r[I[1]], r[9]) for r in R]
OLD = (.16, 5, 1.01)

def prob(pa, pb, p):
    k, c, b = p; sd = math.sqrt((pa * k + c) ** 2 + (pb * k + c) ** 2) or 1
    return 1 / (1 + math.exp(-1.7 * b * (pa - pb) / sd))
def ll(p, y): p = min(1 - 1e-9, max(1e-9, p)); return -math.log(p if y else 1 - p)
def score(xs, p):
    if not xs: return None
    ps = [prob(r[5], r[6], p) for r in xs]
    return sum((q - r[7]) ** 2 for q, r in zip(ps, xs)) / len(xs), sum(ll(q, r[7]) for q, r in zip(ps, xs)) / len(xs)
def calib(xs, p):
    out = []
    for i in range(10):
        b = [(q, r[7]) for r in xs for q in [prob(r[5], r[6], p)] if i / 10 <= q < (i + 1) / 10 or (i == 9 and q == 1)]
        if len(b) >= 20: out.append((round(sum(q for q, _ in b) / len(b), 3), round(sum(y for _, y in b) / len(b), 3), len(b)))
    return out
def fav(xs, p):   # favourite side: mean said vs won (symmetrised so both sides count once)
    s = w = 0
    for r in xs:
        q = prob(r[5], r[6], p); y = r[7]
        if q < .5: q, y = 1 - q, 1 - y
        s += q; w += y
    return round(s / len(xs), 4), round(w / len(xs), 4)

tr = [r for r in rows if r[0] <= 2024]
# grid fit on log loss (coarse then fine, deterministic)
best = None
for k in [x / 100 for x in range(8, 31)]:
    for c in [x / 2 for x in range(0, 21)]:
        v = score(tr, (k, c, 1.01))[1]
        if best is None or v < best[0] - 1e-12: best = (v, k, c)
_, k0, c0 = best
for k in [k0 + x / 1000 for x in range(-10, 11)]:
    for c in [c0 + x / 10 for x in range(-5, 6)]:
        if c < 0: continue
        v = score(tr, (k, c, 1.01))[1]
        if v < best[0] - 1e-12: best = (v, round(k, 3), round(c, 2))
FIT = (best[1], best[2], 1.01)
bs = None
for s in [x / 1000 for x in range(900, 1301, 5)]:
    v = score(tr, (.16 * s, 5 * s, 1.01))[1]
    if bs is None or v < bs[0] - 1e-12: bs = (v, s)
WID = (round(.16 * bs[1], 4), round(5 * bs[1], 3), 1.01)
print(f"totals={TOT}  train 2021-24 n={len(tr)}  fit k={FIT[0]} c={FIT[1]} b=1.01 | widen s={bs[1]} -> k={WID[0]} c={WID[1]}")
M = {"old": OLD, "fit": FIT, "widen": WID}
fmt = lambda rec: "ppr" if rec >= .75 else "half" if rec >= .25 else "std"
size = lambda n: "<=10" if n <= 10 else "12" if n <= 12 else "14+"
wkb = lambda w: "1-4" if w <= 4 else "5-10" if w <= 10 else "11+"
res = {"fit": FIT, "widen": WID, "seasons": {}}
for S in ("2021-24", 2025, 2026):
    xs = tr if S == "2021-24" else [r for r in rows if r[0] == S]
    d = {"n": len(xs)}
    for nm, p in M.items():
        b, l = score(xs, p); d[nm] = {"brier": round(b, 5), "logloss": round(l, 5), "fav_said_won": fav(xs, p), "calib": calib(xs, p)}
        for lab, f in (("size", lambda r: size(r[3])), ("scoring", lambda r: fmt(r[4])), ("week", lambda r: wkb(r[1]))):
            g = collections.defaultdict(list)
            for r in xs: g[f(r)].append(r)
            d[nm][lab] = {key: {"n": len(v), "brier": round(score(v, p)[0], 4), "fav_said_won": fav(v, p)} for key, v in sorted(g.items())}
    if S != "2021-24":   # bootstrap by league: fitted - old
        lg = collections.defaultdict(list)
        for r in xs: lg[r[2]].append(r)
        keys = sorted(lg); per = {}
        for kk in keys:
            v = lg[kk]
            per[kk] = [(sum((prob(r[5], r[6], p) - r[7]) ** 2 for r in v), sum(ll(prob(r[5], r[6], p), r[7]) for r in v)) for p in (OLD, FIT, WID)] + [len(v)]
        rnd = random.Random(29); wins = collections.Counter(); B = 1000
        for _ in range(B):
            smp = [per[keys[rnd.randrange(len(keys))]] for _ in keys]; n = sum(x[3] for x in smp)
            for j, nm in ((1, "fit"), (2, "widen")):
                if sum(x[j][0] for x in smp) < sum(x[0][0] for x in smp): wins[nm + "_brier"] += 1
                if sum(x[j][1] for x in smp) < sum(x[0][1] for x in smp): wins[nm + "_ll"] += 1
        d["bootstrap_leagues"] = len(keys); d["bootstrap_better_of_1000"] = dict(sorted(wins.items()))
    res["seasons"][str(S)] = d
    print(f"\n== {S}  n={len(xs)}" + (f"  leagues={d['bootstrap_leagues']}  bootstrap (of 1000) better than old: {d['bootstrap_better_of_1000']}" if S != "2021-24" else ""))
    for nm in M:
        e = d[nm]; print(f"  {nm:6s} Brier {e['brier']:.4f}  logloss {e['logloss']:.4f}  favourite said/won {e['fav_said_won']}")
    print("  calibration said->won (old | fit | widen):")
    for a, b_, c_ in zip(d["old"]["calib"], d["fit"]["calib"], d["widen"]["calib"]):
        print(f"    {a[0]:.3f}->{a[1]:.3f} n{a[2]:5d} | {b_[0]:.3f}->{b_[1]:.3f} n{b_[2]:5d} | {c_[0]:.3f}->{c_[1]:.3f} n{c_[2]:5d}")
    for lab in ("size", "scoring", "week"):
        for key in d["old"][lab]:
            o, f_ = d["old"][lab][key], d["fit"][lab][key]
            print(f"    {lab:7s} {key:5s} n{o['n']:6d}  old Brier {o['brier']:.4f} fav {o['fav_said_won']}  | fit {f_['brier']:.4f} fav {f_['fav_said_won']}")
json.dump(res, open(f".build/agents/a2/e29_{TOT}.json", "w"), indent=1)
