"""e19: grid over the app-shaped rule score = proj * (m + (1-m) * avg factor over next n games), factor 1 + e*(x/22-1)
(x = opponent implied pts for D/ST, own implied pts for K). Choose on 2021-24, confirm on 2025-26."""
import collections, numpy as np
import e19_rank as R
from scipy.stats import spearmanr
rows, IDX, LAST = R.rows, R.IDX, R.LAST
def weeks(pos, seasons):
    for y in seasons:
        for w in range(4, LAST[y] + 1):
            std = collections.Counter()
            for r in rows:
                if r["pos"] == pos and r["y"] == y and r["w"] < w: std[r["id"]] += r["pts"]
            top = {i for i, _ in sorted(std.items(), key=lambda kv: (-kv[1], kv[0]))[:12]}
            pool = [r for r in rows if r["pos"] == pos and r["y"] == y and r["w"] == w and r["proj"] and r["proj"] > 0 and r["id"] not in top]
            if len(pool) >= 6: yield pool
def score(pos, r, e, m, n):
    gs = R.games(r["y"], r["w"], r["team"], n); fs = [1 + e * (R.xval(pos, g) / 22 - 1) for _, g in gs] or [1]
    return r["proj"] * (m + (1 - m) * sum(fs) / len(fs))
def evalr(pos, pools, e, m, n):
    t, rh = [], []
    for pool in pools:
        sc = [score(pos, r, e, m, n) for r in pool]
        pk = sorted(range(len(pool)), key=lambda i: (-sc[i], pool[i]["id"]))[:3]
        t.append(np.mean([pool[i]["pts"] for i in pk])); rh.append(spearmanr(sc, [r["pts"] for r in pool])[0])
    return np.mean(t), np.nanmean(rh)
for pos, es in (("DEF", (0, -.3, -.6, -.9, -1.2, -1.8)), ("K", (-.5, 0, .25, .5, 1.0))):
    tr, te = list(weeks(pos, (2021, 2022, 2023, 2024))), list(weeks(pos, (2025, 2026)))
    print(f"\n{pos}: train weeks {len(tr)}, test weeks {len(te)}   (e, m, n): train top3/rho | test top3/rho")
    for n in (1, 3):
        for m in (0, .6):
            for e in es:
                a, b = evalr(pos, tr, e, m, n), evalr(pos, te, e, m, n)
                print(f"  e={e:+.2f} m={m} n={n}: {a[0]:.2f}/{a[1]:.3f} | {b[0]:.2f}/{b[1]:.3f}")
