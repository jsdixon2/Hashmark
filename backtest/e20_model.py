#!/usr/bin/env python3
"""e20 step 1b: remaining points = pre x a[pos] x S(e) x clamp(1 + g[pos] x margin/10, .4, 1.6)
S(e): pooled share of a game's points still to come at elapsed game-clock share e (fit 2023-24); a, g per position for MAE.
Test on 2025 at the checkpoints. Writes .build/agents/b10/e20_model.json."""
import json, sys, collections
sys.path.insert(0, "backtest")
import e20_player as E
OUT = ".build/agents/b10/e20_model.json"

def fitS(rows):
    F = sum(r["c"][20] for r in rows)
    return [round(sum(r["c"][20] - r["c"][i] for r in rows) / F, 3) for i in range(21)]

def rem(r, i, S=None, a=1.0, g=0.0):
    e = i / 20; base = max(.02, 1 - e) if S is None else S[i]
    return r["pre"] * a * base * min(1.6, max(.4, 1 + g * r["m"][i] / 10))

def mae(rs, idx, **kw): return sum(abs(r["c"][20] - r["c"][i] - rem(r, i, **kw)) for r in rs for i in idx) / (len(rs) * len(idx))

def main():
    rows = E.load(); tr = [r for r in rows if r["s"] <= 2024]; te = [r for r in rows if r["s"] == 2025]
    S = fitS(tr); S[0] = 1.0; S[20] = 0.0
    idx = list(E.CK)
    A, G = {}, {}
    for p in E.POSS:
        rs = [r for r in tr if r["pos"] == p]; best = None
        for a in [x / 50 for x in range(40, 71)]:
            for g in [x / 100 for x in range(-30, 6, 2)]:
                v = mae(rs, idx, S=S, a=a, g=g)
                if best is None or v < best[0] - 1e-9: best = (v, a, g)
        A[p], G[p] = best[1], best[2]
        bg = None
        for g in [x / 100 for x in range(-30, 6, 2)]:
            v = mae(rs, idx, S=S, g=g)
            if bg is None or v < bg[0] - 1e-9: bg = (v, g)
        G[p + "_noa"] = bg[1]
    models = {"shipped": lambda r: {}, "S": lambda r: {"S": S}, "S+g": lambda r: {"S": S, "g": G[r["pos"] + "_noa"]},
              "S+g+a": lambda r: {"S": S, "a": A[r["pos"]], "g": G[r["pos"]]}, "lin+g": lambda r: {"g": G[r["pos"] + "_noa"]}}
    tab = {}
    for i in idx:
        tab[str(E.CK[i])] = {m: round(sum(abs(r["c"][20] - r["c"][i] - rem(r, i, **f(r))) for r in te) / len(te), 3) for m, f in models.items()}
    allm = {m: round(sum(tab[k][m] for k in tab) / len(tab), 3) for m in models}
    res = {"S": S, "a": A, "g": G, "n_train": len(tr), "n_test": len(te), "test_mae": tab, "test_mean": allm}
    json.dump(res, open(OUT, "w"), indent=1)
    print(json.dumps({"S": S, "a": A, "g": G}))
    for k, v in tab.items(): print(k, v)
    print("mean", allm)

if __name__ == "__main__":
    main()
