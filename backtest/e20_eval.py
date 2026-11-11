#!/usr/bin/env python3
"""e20 step 2b: grade live win odds on the replayed states (e20_live.py). Fit 2023-24, test 2025.
Row: season, window, frac, nwin, y, then per side: final, so_far, rem_shipped, rem_gameScript, lineup share left, pregame total."""
import gzip, json, math, collections, sys
OUT = ".build/agents/b10/"
WP = {"k": .16, "c": 5, "b": 1.01}

def wp(d, va, vb, live):
    sd = math.sqrt(va + vb)
    p = (1.0 if d > 0 else 0.0 if d < 0 else .5) if sd < .25 else 1 / (1 + math.exp(-1.7 * WP["b"] * d / sd))
    return min(.999, max(.001, p)) if live else p

def side(r, o):
    pt, sof, rs, rg, ra, pre = r[o:o + 6]; return pt, sof, rs, rg, ra, pre

def model(r, rule="shipped", p=1.0, s=1.0, base="live"):
    A = side(r, 5); B = side(r, 11)
    pa = A[1] + (A[2] if rule == "shipped" else A[3]); pb = B[1] + (B[2] if rule == "shipped" else B[3])
    xa = pa if base == "live" else A[5]; xb = pb if base == "live" else B[5]
    va = s * (xa * WP["k"] + WP["c"]) ** 2 * A[4] ** p; vb = s * (xb * WP["k"] + WP["c"]) ** 2 * B[4] ** p
    return wp(pa - pb, va, vb, A[4] > 0 or B[4] > 0)

def brier(xs): return sum((p - y) ** 2 for p, y in xs) / len(xs) if xs else None
def ll(xs): return -sum(math.log(p if y else 1 - p) for p, y in xs) / len(xs)

def main():
    R = json.load(gzip.open(OUT + "live_states.json.gz", "rt"))
    live = [r for r in R if 0 < r[9] < 1 or 0 < r[15] < 1 or (r[9] < 1 and r[15] < 1 and (r[9] > 0 or r[15] > 0))]
    # live = some games done or in progress and some points still to play
    live = [r for r in R if (r[9] < .999 or r[15] < .999) and (r[9] > 0 or r[15] > 0)]
    tr = [r for r in live if r[0] <= 2024]; te = [r for r in live if r[0] == 2025]
    print("states live: train", len(tr), "test", len(te), file=sys.stderr)
    # variance shape: residual^2 / (proj k + c)^2 by share left (train)
    vb = collections.defaultdict(lambda: [0, 0.0, 0.0, 0.0])
    for r in tr:
        for o in (5, 11):
            pt, sof, rs, rg, ra, pre = side(r, o)
            if ra >= .999: continue
            b = round(ra * 10) / 10; x = vb[b]; proj = sof + rs
            x[0] += 1; x[1] += (pt - proj) ** 2 / (proj * WP["k"] + WP["c"]) ** 2; x[2] += pt - proj; x[3] += (pt - sof - rg)
    shape = {str(b): {"n": v[0], "ratio": round(v[1] / v[0], 3), "bias_shipped": round(v[2] / v[0], 2), "bias_gs": round(v[3] / v[0], 2)} for b, v in sorted(vb.items())}
    # sample train for fitting speed (deterministic stride)
    trs = tr[::5]
    best = None
    for rule in ("shipped", "gs"):
        for p in (.6, .7, .8, .9, 1.0, 1.1, 1.2):
            for s in (.7, .8, .9, 1.0, 1.1, 1.2, 1.3):
                v = brier([(model(r, rule, p, s), r[4]) for r in trs])
                if best is None or v < best[0] - 1e-12: best = (v, rule, p, s)
    bg = None
    for p in (.6, .7, .8, .9, 1.0, 1.1, 1.2):
        for s in (.7, .8, .9, 1.0, 1.1, 1.2, 1.3):
            v = brier([(model(r, "gs", p, s), r[4]) for r in trs])
            if bg is None or v < bg[0] - 1e-12: bg = (v, p, s)
    bsv = None
    for p in (.6, .7, .8, .9, 1.0, 1.1, 1.2):
        for s in (.7, .8, .9, 1.0, 1.1, 1.2, 1.3):
            v = brier([(model(r, "shipped", p, s), r[4]) for r in trs])
            if bsv is None or v < bsv[0] - 1e-12: bsv = (v, p, s)
    fits = {"best": best, "gs_best": bg, "shipped_var_best": bsv}
    M = {"shipped": lambda r: model(r), "gs": lambda r: model(r, "gs"),
         "shipped+var": lambda r: model(r, "shipped", bsv[1], bsv[2]), "gs+var": lambda r: model(r, "gs", bg[1], bg[2])}
    res = {"fits": fits, "shape_train": shape, "n_train": len(tr), "n_test": len(te), "test": {}, "by_left": {}, "calib": {}}
    for nm, f in M.items():
        xs = [(f(r), r[4]) for r in te]
        res["test"][nm] = {"brier": round(brier(xs), 4), "logloss": round(ll(xs), 4), "acc": round(sum((p > .5) == (y == 1) for p, y in xs) / len(xs), 4)}
        bl = collections.defaultdict(list)
        for r, x in zip(te, xs):
            left = (r[9] * r[10] + r[15] * r[16]) / max(1e-9, r[10] + r[16]); bl[min(9, int(left * 10))].append(x)
        res["by_left"][nm] = {f"{k/10:.1f}-{(k+1)/10:.1f}": [len(v), round(brier(v), 4)] for k, v in sorted(bl.items())}
        cb = []
        for i in range(10):
            v = [x for x in xs if i / 10 <= x[0] < (i + 1) / 10 or (i == 9 and x[0] == 1)]
            if v: cb.append({"said": round(sum(p for p, _ in v) / len(v), 3), "won": round(sum(y for _, y in v) / len(v), 3), "n": len(v)})
        res["calib"][nm] = cb
    pre = [r for r in R if r[0] == 2025 and r[9] >= .999 and r[15] >= .999]
    res["pregame_2025"] = {"n": len(pre), "brier": round(brier([(model(r), r[4]) for r in pre]), 4)}
    json.dump(res, open(OUT + "e20_eval.json", "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("fits", "test", "pregame_2025")}, indent=1))
    print(json.dumps(res["shape_train"]))
    for nm in M: print(nm, res["by_left"][nm])
    print(json.dumps(res["calib"]["shipped"]))

if __name__ == "__main__":
    main()
