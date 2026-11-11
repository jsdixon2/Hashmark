"""e19: fit D/ST and K points on Sleeper projection + implied points (closing line). Fit 2021-24, test 2025, 2026."""
import json, os, sys, collections
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(ROOT, ".build/agents/b9/e19_rows.json")))
rows = [r for r in D["rows"] if r["proj"] is not None and r["proj"] > 0]
IDX = {(r["y"], r["w"], r["id"]): r for r in D["rows"]}
TR, TE = (2021, 2022, 2023, 2024), ((2025,), (2026,))

def feat(r, pos, spec, rr=None):
    rr = rr or r
    x = rr["oimp"] if pos == "DEF" else rr["imp"]
    if spec == "proj": return [1, r["proj"]]
    if spec == "imp": return [1, x - 22]
    if spec == "both": return [1, r["proj"], x - 22]
    if spec == "mult": return [r["proj"], r["proj"] * (x / 22 - 1)]

def ols(X, y):
    X, y = np.array(X, float), np.array(y, float)
    return np.linalg.lstsq(X, y, rcond=None)[0]

def ev(b, X, y):
    p = np.array(X, float) @ b; y = np.array(y, float)
    return np.sqrt(np.mean((p - y) ** 2)), np.mean(np.abs(p - y)), np.corrcoef(p, y)[0, 1] if len(set(p)) > 1 else 0

out = {}
for pos in ("DEF", "K"):
    R = [r for r in rows if r["pos"] == pos]
    print(f"\n== {pos}  train n={sum(r['y'] in TR for r in R)}  mean proj {np.mean([r['proj'] for r in R]):.2f} mean pts {np.mean([r['pts'] for r in R]):.2f}")
    xs = [(r["oimp"] if pos == "DEF" else r["imp"]) for r in R if r["y"] in TR]
    print(f"   implied mean {np.mean(xs):.2f} sd {np.std(xs):.2f}")
    for spec in ("proj", "imp", "both", "mult"):
        tr = [r for r in R if r["y"] in TR]
        b = ols([feat(r, pos, spec) for r in tr], [r["pts"] for r in tr])
        line = f"  {spec:5s} b={np.round(b,3)}"
        for ys in TE:
            te = [r for r in R if r["y"] in ys]
            rm, ma, c = ev(b, [feat(r, pos, spec) for r in te], [r["pts"] for r in te])
            line += f" | {ys[0]} n={len(te)} rmse {rm:.3f} mae {ma:.3f} r {c:.3f}"
        print(line); out[(pos, spec)] = b
    # raw projection as-is
    for ys in TE:
        te = [r for r in R if r["y"] in ys]
        print(f"  raw proj {ys[0]}: rmse {ev(np.array([1.0]), [[r['proj']] for r in te], [r['pts'] for r in te])[:2]}")
    # future weeks: proj of week w, implied of week w+k
    for k in (1, 2):
        tr = []
        for r in R:
            if r["y"] not in TR: continue
            f = IDX.get((r["y"], r["w"] + k, r["id"]))
            if f: tr.append((r, f))
        for spec in ("proj", "both", "mult"):
            b = ols([feat(r, pos, spec, f) for r, f in tr], [f["pts"] for r, f in tr])
            line = f"  wk+{k} {spec:5s} b={np.round(b,3)} n={len(tr)}"
            for ys in TE:
                te = [(r, IDX[(r['y'], r['w'] + k, r['id'])]) for r in R if r["y"] in ys and (r['y'], r['w'] + k, r['id']) in IDX]
                rm, ma, c = ev(b, [feat(r, pos, spec, f) for r, f in te], [f["pts"] for r, f in te])
                line += f" | {ys[0]} rmse {rm:.3f} r {c:.3f}"
            print(line)
