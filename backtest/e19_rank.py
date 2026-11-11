"""e19: rank free-agent D/ST and K streamers each week under different rules; score the top 3.
Pool: projection > 0 and outside the top 12 at the position by season-to-date points (weeks before), weeks 4-18.
Outcomes: points that week; points over that week + next 2 calendar weeks (bye = 0).
Fit 2021-24, test 2025 and 2026 (2026 weeks 4-9 / 4-7 for the 3-week horizon)."""
import json, os, collections
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(ROOT, ".build/agents/b9/e19_rows.json")))
rows = D["rows"]; G = D["G"]; done = {tuple(x) for x in D["done"]}
IDX = {(r["y"], r["w"], r["id"]): r for r in rows}
TR = (2021, 2022, 2023, 2024)
LAST = {y: max(w for yy, w in done if yy == y) for y in range(2021, 2027)}

def games(y, w, t, n):
    out = []
    for ww in range(w, 19):
        g = G.get(f"{y}-{ww}-{t}")
        if g: out.append((ww, g))
        if len(out) == n: break
    return out

def xval(pos, g): return g["oimp"] if pos == "DEF" else g["imp"]

# ---- fitted coefficients (2021-24) for horizon k = 0,1,2: pts_{w+k} = a + b*proj_w + c*(x_{w+k}-22)
def fit():
    C = {}
    for pos in ("DEF", "K"):
        for k in range(3):
            X, Y = [], []
            for r in rows:
                if r["pos"] != pos or r["y"] not in TR or not r["proj"] or r["proj"] <= 0: continue
                f = IDX.get((r["y"], r["w"] + k, r["id"]))
                if not f: continue
                X.append([1, r["proj"], xval(pos, f) - 22]); Y.append(f["pts"])
            C[(pos, k)] = np.linalg.lstsq(np.array(X), np.array(Y), rcond=None)[0]
    # multiplicative elasticity this week: pts = proj*(1 + e*(x/22-1)) (scale free)
    E = {}
    for pos in ("DEF", "K"):
        X, Y = [], []
        for r in rows:
            if r["pos"] == pos and r["y"] in TR and r["proj"] and r["proj"] > 0:
                X.append([r["proj"], r["proj"] * (xval(pos, r) / 22 - 1)]); Y.append(r["pts"])
        E[pos] = np.linalg.lstsq(np.array(X), np.array(Y), rcond=None)[0]
    return C, E
C, E = fit()

def shipped(pos, r):
    gs = games(r["y"], r["w"], r["team"], 3)
    fs = [(1 + (21.5 - g["oimp"]) / 21.5 * .6) if pos == "DEF" else (1 + (g["imp"] / 22 - 1) * .5) for _, g in gs] or [1]
    return r["proj"] * (.6 + .4 * sum(fs) / len(fs))

def fit_wk(pos, r):  # this week only
    a, b, c = C[(pos, 0)]; return a + b * r["proj"] + c * (xval(pos, r) - 22)

def fit_3(pos, r):  # this + next 2 calendar weeks, bye = 0
    s = 0
    for k in range(3):
        g = G.get(f"{r['y']}-{r['w']+k}-{r['team']}")
        if g and r["w"] + k <= 18:
            a, b, c = C[(pos, k)]; s += a + b * r["proj"] + c * (xval(pos, g) - 22)
    return s

def mult_wk(pos, r, e=None):
    e = E[pos][1] if e is None else e
    return r["proj"] * (1 + e * (xval(pos, r) / 22 - 1))

RULES = {"shipped": shipped, "fitted (this wk)": fit_wk, "fitted (3 wk)": fit_3, "proj only": lambda pos, r: r["proj"],
         "implied only": lambda pos, r: -r["oimp"] if pos == "DEF" else r["imp"], "proj x fitted e": mult_wk}

def run(seasons, extra=None):
    rules = dict(RULES, **(extra or {}))
    res = collections.defaultdict(lambda: collections.defaultdict(list))
    for pos in ("DEF", "K"):
        for y in seasons:
            for w in range(4, LAST[y] + 1):
                std = collections.Counter()
                for r in rows:
                    if r["pos"] == pos and r["y"] == y and r["w"] < w: std[r["id"]] += r["pts"]
                top = {i for i, _ in sorted(std.items(), key=lambda kv: (-kv[1], kv[0]))[:12]}
                pool = [r for r in rows if r["pos"] == pos and r["y"] == y and r["w"] == w and r["proj"] and r["proj"] > 0 and r["id"] not in top]
                if len(pool) < 6: continue
                h3 = w + 2 <= min(LAST[y], 18)
                def p3(r): return sum((IDX.get((y, w + k, r["id"])) or {"pts": 0})["pts"] for k in range(3))
                res[pos]["pool avg"].append((np.mean([r["pts"] for r in pool]), np.mean([p3(r) for r in pool]) if h3 else None))
                for name, f in rules.items():
                    pk = sorted(pool, key=lambda r: (-f(pos, r), r["id"]))[:3]
                    res[pos][name].append((np.mean([r["pts"] for r in pk]), np.mean([p3(r) for r in pk]) if h3 else None, pk[0]["pts"] - np.mean([r["pts"] for r in pool])))
    return res

def show(res, label):
    print(f"\n### {label}")
    for pos in ("DEF", "K"):
        print(f"{pos}: rule | weeks | top-3 pts this wk | top-3 pts wk..wk+2 | #1 beat pool avg %")
        for name, v in res[pos].items():
            a = np.mean([x[0] for x in v]); b = [x[1] for x in v if x[1] is not None]
            hit = f"{100*np.mean([x[2] > 0 for x in v]):.0f}%" if len(v[0]) > 2 else ""
            print(f"  {name:18s} {len(v):3d}  {a:6.2f}  {np.mean(b):6.2f} (n={len(b)})  {hit}")

if __name__ == "__main__":
    print("fitted C:", {f"{k[0]} k{k[1]}": np.round(v, 3).tolist() for k, v in C.items()})
    print("fitted e:", {k: np.round(v, 3).tolist() for k, v in E.items()})
    show(run(TR), "train 2021-24 (in sample)")
    show(run((2025,)), "test 2025")
    show(run((2026,)), "test 2026")
    show(run((2025, 2026)), "test 2025+2026")
