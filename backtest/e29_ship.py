#!/usr/bin/env python3
"""e29 step 2: the shipped candidate = keep k .16 / c 5 (the playoff-odds simulations draw team scores with sd = proj k + c,
so they stay as fitted) and widen only through b, fitted on 2021-24 (log loss, grid .001). Compares old (b 1.01), the b
fit, and the two-parameter (k, c) fit from e29_fit.py on 2025 and 2026 (full projection in each league's scoring), and
checks the matchup page's "likely X-Y" team range (80% interval m +- 1.2816 sd) with sd = .16m+5 (old) vs (.16m+5)/b.
Input .build/agents/a2/e29_rows.json; writes .build/agents/a2/e29_ship.json."""
import json, math, random, collections
R = json.load(open(".build/agents/a2/e29_rows.json"))
rows = [(r[0], r[1], r[2], r[3], r[4], r[7], r[8], r[9], r[10], r[11]) for r in R]
def prob(pa, pb, p):
    k, c, b = p; sd = math.sqrt((pa * k + c) ** 2 + (pb * k + c) ** 2) or 1
    return 1 / (1 + math.exp(-1.7 * b * (pa - pb) / sd))
def ll(q, y): q = min(1 - 1e-9, max(1e-9, q)); return -math.log(q if y else 1 - q)
def sc(xs, p): ps = [prob(r[5], r[6], p) for r in xs]; return sum((q - r[7]) ** 2 for q, r in zip(ps, xs)) / len(xs), sum(ll(q, r[7]) for q, r in zip(ps, xs)) / len(xs)
tr = [r for r in rows if r[0] <= 2024]
best = min(((sc(tr, (.16, 5, b / 1000))[1], b / 1000) for b in range(850, 1011)), key=lambda t: (t[0], t[1]))
B = best[1]
M = {"old": (.16, 5, 1.01), "b_fit": (.16, 5, B), "kc_fit": (.146, 9.0, 1.01)}
print("b fit on 2021-24:", B)
res = {"b": B, "seasons": {}}
for S in (2025, 2026):
    xs = [r for r in rows if r[0] == S]; d = {"n": len(xs)}
    for nm, p in M.items():
        b, l = sc(xs, p); cal = []
        for i in range(10):
            v = [(q, r[7]) for r in xs for q in [prob(r[5], r[6], p)] if i / 10 <= q < (i + 1) / 10]
            if len(v) >= 20: cal.append((round(sum(q for q, _ in v) / len(v), 3), round(sum(y for _, y in v) / len(v), 3), len(v)))
        d[nm] = {"brier": round(b, 4), "logloss": round(l, 4), "calib": cal}
    lg = collections.defaultdict(list)
    for r in xs: lg[r[2]].append(r)
    keys = sorted(lg); per = {k: [(sum((prob(r[5], r[6], p) - r[7]) ** 2 for r in lg[k]), sum(ll(prob(r[5], r[6], p), r[7]) for r in lg[k])) for p in (M["old"], M["b_fit"])] for k in keys}
    rnd = random.Random(29); w = collections.Counter()
    for _ in range(1000):
        smp = [per[keys[rnd.randrange(len(keys))]] for _ in keys]
        w["brier"] += sum(x[1][0] for x in smp) < sum(x[0][0] for x in smp); w["logloss"] += sum(x[1][1] for x in smp) < sum(x[0][1] for x in smp)
    d["bootstrap_b_fit_better_of_1000"] = dict(w); d["leagues"] = len(keys)
    cov = {}
    for nm, f in (("old .16m+5", lambda m: .16 * m + 5), (f"(.16m+5)/{B}", lambda m: (.16 * m + 5) / B)):
        n = h = lo = 0
        for r in xs:
            for m, a in ((r[5], r[8]), (r[6], r[9])):
                if m <= 0: continue
                s = f(m); n += 1; h += m - 1.2816 * s <= a <= m + 1.2816 * s; lo += a < m - 1.2816 * s
        cov[nm] = {"n": n, "inside": round(h / n, 3), "below": round(lo / n, 3)}
    d["team_range_80"] = cov
    res["seasons"][S] = d
    print(f"\n== {S} n={len(xs)} leagues={len(keys)} bootstrap b_fit better than old (of 1000): {dict(w)}")
    for nm in M: print(f"  {nm:7s} Brier {d[nm]['brier']:.4f} logloss {d[nm]['logloss']:.4f}")
    print("  said->won  old | b_fit")
    for a, b_ in zip(d["old"]["calib"], d["b_fit"]["calib"]): print(f"   {a[0]:.3f}->{a[1]:.3f} (n {a[2]}) | {b_[0]:.3f}->{b_[1]:.3f} (n {b_[2]})")
    print("  team 80% range:", cov)
json.dump(res, open(".build/agents/a2/e29_ship.json", "w"), indent=1)
