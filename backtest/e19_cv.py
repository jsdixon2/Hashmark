"""e19: forward-chained test (fit on seasons before y, test y = 2022..2026) of streamer rules.
Per week and pool (projection > 0, outside top 12 season-to-date, weeks 4+): top-3 points that week and over 3 calendar
weeks, Spearman of rule score vs points within the pool; paired difference vs the shipped rule with standard errors."""
import json, os, collections
import numpy as np
import e19_rank as R
from scipy.stats import spearmanr

rows, G, IDX, LAST = R.rows, R.G, R.IDX, R.LAST
xval = R.xval

def fit(seasons):
    C, E = {}, {}
    for pos in ("DEF", "K"):
        for k in range(3):
            X, Y = [], []
            for r in rows:
                if r["pos"] != pos or r["y"] not in seasons or not r["proj"] or r["proj"] <= 0: continue
                f = IDX.get((r["y"], r["w"] + k, r["id"]))
                if f: X.append([1, r["proj"], xval(pos, f) - 22]); Y.append(f["pts"])
            C[(pos, k)] = np.linalg.lstsq(np.array(X), np.array(Y), rcond=None)[0]
        X, Y = [], []
        for r in rows:
            if r["pos"] == pos and r["y"] in seasons and r["proj"] and r["proj"] > 0:
                X.append([r["proj"], r["proj"] * (xval(pos, r) / 22 - 1)]); Y.append(r["pts"])
        E[pos] = np.linalg.lstsq(np.array(X), np.array(Y), rcond=None)[0][1]
    return C, E

def mix(pos, r, e, wnow, n=3):
    """app-shaped rule: proj * ((1-wnow-ish) ...): proj * (m + (1-m)*avg factor over next n games), factor 1+e*(x/22-1)"""
    gs = R.games(r["y"], r["w"], r["team"], n)
    fs = [1 + e * (xval(pos, g) / 22 - 1) for _, g in gs] or [1]
    return r["proj"] * (wnow + (1 - wnow) * sum(fs) / len(fs))

def rules_for(C, E):
    def fw(pos, r):
        a, b, c = C[(pos, 0)]; return a + b * r["proj"] + c * (xval(pos, r) - 22)
    def f3(pos, r):
        s = 0
        for k in range(3):
            g = G.get(f"{r['y']}-{r['w']+k}-{r['team']}")
            if g and r["w"] + k <= 18:
                a, b, c = C[(pos, k)]; s += a + b * r["proj"] + c * (xval(pos, g) - 22)
        return s
    return {"shipped": R.shipped, "proj only": lambda pos, r: r["proj"],
            "implied only": lambda pos, r: -r["oimp"] if pos == "DEF" else r["imp"],
            "fitted linear (this wk)": fw, "fitted linear (3 wk)": f3,
            "proj x (1+e(x/22-1)) this wk": lambda pos, r: r["proj"] * (1 + E[pos] * (xval(pos, r) / 22 - 1)),
            "proj x fitted e, 1 game, no mix": lambda pos, r: mix(pos, r, E[pos], 0, 1),
            "proj x e=-.6/.5, this wk only": lambda pos, r: mix(pos, r, -.6 * 22 / 21.5 if pos == "DEF" else .5, 0, 1)}

def main():
    out = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
    coef = {}
    for y in range(2022, 2027):
        C, E = fit(tuple(range(2021, y)))
        coef[y] = ({f"{k[0]}{k[1]}": np.round(v, 3).tolist() for k, v in C.items()}, {k: round(float(v), 3) for k, v in E.items()})
        rules = rules_for(C, E)
        for pos in ("DEF", "K"):
            for w in range(4, LAST[y] + 1):
                std = collections.Counter()
                for r in rows:
                    if r["pos"] == pos and r["y"] == y and r["w"] < w: std[r["id"]] += r["pts"]
                top = {i for i, _ in sorted(std.items(), key=lambda kv: (-kv[1], kv[0]))[:12]}
                pool = [r for r in rows if r["pos"] == pos and r["y"] == y and r["w"] == w and r["proj"] and r["proj"] > 0 and r["id"] not in top]
                if len(pool) < 6: continue
                h3 = w + 2 <= min(LAST[y], 18)
                p3 = lambda r: sum((IDX.get((y, w + k, r["id"])) or {"pts": 0})["pts"] for k in range(3))
                for name, f in rules.items():
                    sc = [f(pos, r) for r in pool]
                    pk = sorted(range(len(pool)), key=lambda i: (-sc[i], pool[i]["id"]))[:3]
                    d = out[pos][name]
                    d["wk"].append(np.mean([pool[i]["pts"] for i in pk]))
                    d["rho"].append(spearmanr(sc, [r["pts"] for r in pool])[0])
                    if h3:
                        d["h3"].append(np.mean([p3(pool[i]) for i in pk]))
                        d["rho3"].append(spearmanr(sc, [p3(r) for r in pool])[0])
                    d["seas"].append(y)
    return out, coef

if __name__ == "__main__":
    out, coef = main()
    for y, c in coef.items(): print(y, c)
    for pos in ("DEF", "K"):
        print(f"\n{pos}  (held-out weeks 2022-26, n weeks = {len(out[pos]['shipped']['wk'])}, 3-wk n = {len(out[pos]['shipped']['h3'])})")
        print(f"  {'rule':34s} top3 wk  diff vs shipped (se) | top3 3wk  diff (se) | rho wk | rho 3wk")
        b = out[pos]["shipped"]
        for name, d in out[pos].items():
            dw = np.array(d["wk"]) - np.array(b["wk"]); d3 = np.array(d["h3"]) - np.array(b["h3"])
            se = lambda a: a.std(ddof=1) / np.sqrt(len(a)) if a.any() else 0
            print(f"  {name:34s} {np.mean(d['wk']):6.2f}  {dw.mean():+.2f} ({se(dw):.2f}) | {np.mean(d['h3']):6.2f}  {d3.mean():+.2f} ({se(d3):.2f}) | {np.nanmean(d['rho']):.3f} | {np.nanmean(d['rho3']):.3f}")
        # 2025-26 only
        print("  2025-26 only:")
        for name, d in out[pos].items():
            m = [i for i, s in enumerate(d["seas"]) if s >= 2025]
            print(f"    {name:34s} top3 wk {np.mean([d['wk'][i] for i in m]):.2f}  rho {np.nanmean([d['rho'][i] for i in m]):.3f}")
