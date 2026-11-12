"""F1 / e33 item 5: half-PPR-specific win-odds widening. Rows from e29 (.build/agents/a2/e29_rows.json: season, week,
league hash, size, rec, ..., full-projection totals A/B in each league's scoring [7, 8], A won [9]). Shipped p112:
k .16 c 5 b .918 for every format. Fit b for half-PPR leagues (rec .5) on 2021-24 by log loss (grid .001), test 2025 and
2026 separately; bootstrap over leagues. Ships only if better on BOTH held-out seasons."""
import json, math, random, collections, os
R = json.load(open("/home/user/Hashmark/.build/agents/a2/e29_rows.json"))
rows = [r for r in R if abs(r[4] - .5) < 1e-6]
def prob(pa, pb, b, k=.16, c=5):
    sd = math.sqrt((pa * k + c) ** 2 + (pb * k + c) ** 2) or 1; return 1 / (1 + math.exp(-1.7 * b * (pa - pb) / sd))
def ll(q, y): q = min(1 - 1e-9, max(1e-9, q)); return -math.log(q if y else 1 - q)
def sc(xs, b):
    ps = [prob(r[7], r[8], b) for r in xs]
    return sum((q - r[9]) ** 2 for q, r in zip(ps, xs)) / len(xs), sum(ll(q, r[9]) for q, r in zip(ps, xs)) / len(xs)
tr = [r for r in rows if r[0] <= 2024]
B = min(((sc(tr, b / 1000)[1], b / 1000) for b in range(700, 1011)), key=lambda t: (t[0], t[1]))[1]
print("half-PPR rows", len(rows), "train", len(tr), "b fit on 2021-24:", B)
res = {"b_half": B, "n_train": len(tr), "seasons": {}}
for S in (2025, 2026):
    xs = [r for r in rows if r[0] == S]; d = {"n": len(xs)}
    for nm, b in (("shipped b .918", .918), (f"half b {B}", B)):
        br, l = sc(xs, b); fs = fw = 0
        for r in xs:
            q = prob(r[7], r[8], b); f = q if q >= .5 else 1 - q; fs += f; fw += r[9] if q >= .5 else 1 - r[9]
        d[nm] = {"brier": round(br, 4), "logloss": round(l, 4), "fav_said": round(fs / len(xs), 3), "fav_won": round(fw / len(xs), 3)}
    lg = collections.defaultdict(list)
    for r in xs: lg[r[2]].append(r)
    keys = sorted(lg); per = {k: [sum((prob(r[7], r[8], b) - r[9]) ** 2 for r in lg[k]) for b in (.918, B)] for k in keys}
    rnd = random.Random(33); w = 0
    for _ in range(1000):
        smp = [per[keys[rnd.randrange(len(keys))]] for _ in keys]; w += sum(x[1] for x in smp) < sum(x[0] for x in smp)
    d["leagues"] = len(keys); d["bootstrap_half_better_brier_of_1000"] = w
    res["seasons"][S] = d; print(S, json.dumps(d))
json.dump(res, open("/home/user/Hashmark/backtest/e33_half.json", "w"), indent=1)
