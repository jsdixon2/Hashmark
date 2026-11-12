#!/usr/bin/env python3
"""e23 step 2: test the shipped devy score and fit a replacement on draft classes 2016-2020, test on 2021-2023.

Outcome: hit3 = a top-24 RB/WR or top-12 QB/TE PPR season in the first 3 NFL seasons (hit4 = 4 seasons, classes <= 2022).
Population: every class member the app's pool would hold (drafted in D or left college after season D-1).
Models (logistic, L2, pooled across positions with position intercepts; features standardised on the train years):
  shipped   score only (the hand-set score), per-position intercept
  pre       pre-draft: app-available inputs only (score parts, seasons in college, breakout class, conference, weight)
  cap       with real draft capital: log(pick) (undrafted = 300) [+ pre]  -> for drafted rookies
Reads $E23_OUT (default /tmp/b11/e23_rows.json). Writes $E23_FIT (default /tmp/b11/e23_fit.json).
"""
import json, math, os, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss

R = json.load(open(os.environ.get("E23_OUT", "/tmp/b11/e23_rows.json")))
R.sort(key=lambda r: (r["D"], r["id"]))
POS = ["QB", "RB", "TE", "WR"]
KEYS = {"QB": ["ypa", "tdint", "cmp", "rush", "att"], "RB": ["scrim", "ts", "ypc", "x15", "rtd"], "WR": ["dom", "yptpa", "ts", "x20"], "TE": ["dom", "yptpa", "ts", "x20"]}
IDEAL = {"QB": 220, "RB": 210, "WR": 200, "TE": 245}


def bo_v(r):
    c = (r["bo"] or {}).get("cls")
    return 1.0 if c and c <= 1 else .8 if c == 2 else .55 if c == 3 else .3 if r["bo"] else 0


def feats(r, kind):
    """kind 'pre': inputs the app has for every college player in cfb.json."""
    pos = r["pos"]; x = {}
    for p in POS:
        x["i_" + p] = 1.0 if pos == p else 0.0
    if kind in ("shipped", "sy"):
        x["score"] = r["score"] / 100
        if kind == "sy":  # shipped score + seasons in college at the draft: both computable in the app from cfb.json
            x["yrs"] = min(5, r["cls"])
        return x
    pc = r["pct"]
    if kind in ("pw", "cpw"):  # production reconstructed from the shipped score (the app can do this from score, bo, conf, wt)
        W_ = {"WR": .8, "TE": .8, "RB": .85, "QB": .85}[pos]
        cm = 1.0 if r["p5"] else .9 if r["fbs"] else .8
        wm = 1 - min(.08, abs(r["wt"] - IDEAL[pos]) / 400) if (pos != "QB" and r["wt"]) else 1
        x["prod"] = (r["score"] / 100 / cm / wm - (1 - W_) * bo_v(r)) / W_
        x["bo"] = bo_v(r); x["yrs"] = min(5, r["cls"]); x["p5"] = 1.0 if r["p5"] else 0.0
        x["g5"] = 1.0 if (r["fbs"] and not r["p5"]) else 0.0; x["wtd"] = abs((r["wt"] or IDEAL[pos]) - IDEAL[pos]) / 25
        if kind == "cpw":
            x["lpick"] = math.log(r["pick"] or 300)
        return x
    # production: mean of the position's share/efficiency percentiles (one number keeps the fit small)
    x["prod"] = sum(pc.get(k, 0) for k in KEYS[pos]) / len(KEYS[pos])
    x["top"] = max(pc.get(k, 0) for k in KEYS[pos][:2])  # best of the two lead metrics
    x["bo"] = bo_v(r)
    x["yrs"] = min(5, r["cls"])  # seasons since first roster year (early declare = fewer)
    x["p5"] = 1.0 if r["p5"] else 0.0
    x["g5"] = 1.0 if (r["fbs"] and not r["p5"]) else 0.0
    x["wtd"] = abs((r["wt"] or IDEAL[pos]) - IDEAL[pos]) / 25
    if kind == "cap":
        x["lpick"] = math.log(r["pick"] or 300)
    return x


def mat(rows, kind):
    F = [feats(r, kind) for r in rows]; names = sorted(F[0]); return np.array([[f[k] for k in names] for f in F]), names


def fit(rows, kind, C=1.0):
    X, names = mat(rows, kind); y = np.array([r["o3"]["hit"] for r in rows], int)
    mu = X.mean(0); sd = X.std(0); sd[sd == 0] = 1
    for i, k in enumerate(names):
        if k.startswith("i_"):
            mu[i], sd[i] = 0, 1
    m = LogisticRegression(C=C, max_iter=5000, fit_intercept=False).fit((X - mu) / sd, y)
    return {"names": names, "mu": mu.tolist(), "sd": sd.tolist(), "coef": m.coef_[0].tolist()}


def pred(M, rows, kind):
    X, names = mat(rows, kind); assert names == M["names"]
    z = ((X - np.array(M["mu"])) / np.array(M["sd"])) @ np.array(M["coef"])
    return 1 / (1 + np.exp(-z))


def evaluate(rows, p, tag):
    y = np.array([r["o3"]["hit"] for r in rows], int)
    out = {"n": len(rows), "hits": int(y.sum()), "auc": round(roc_auc_score(y, p), 3) if 0 < y.sum() < len(y) else None,
           "ll": round(log_loss(y, np.clip(p, 1e-4, 1 - 1e-4), labels=[0, 1]), 4)}
    # within-position AUC, averaged (the app ranks within position)
    au = []
    for ps in POS:
        ix = [i for i, r in enumerate(rows) if r["pos"] == ps]
        yy = y[ix]
        if 0 < yy.sum() < len(yy):
            au.append((ps, round(roc_auc_score(yy, p[ix]), 3), int(yy.sum())))
    out["pos_auc"] = au
    # top-k by position: hits among each class's top 10 RB/WR, top 5 QB/TE
    tk, th = 0, 0
    for D in sorted({r["D"] for r in rows}):
        for ps, k in (("QB", 5), ("RB", 10), ("WR", 10), ("TE", 5)):
            ix = sorted([i for i, r in enumerate(rows) if r["D"] == D and r["pos"] == ps], key=lambda i: (-p[i], rows[i]["id"]))[:k]
            tk += len(ix); th += int(y[ix].sum())
    out["topk_hit"] = f"{th}/{tk}"
    return out


def main():
    tr = [r for r in R if r["D"] <= 2020]; te = [r for r in R if r["D"] >= 2021]
    res = {"n_train": len(tr), "n_test": len(te), "hits_train": sum(r["o3"]["hit"] for r in tr), "hits_test": sum(r["o3"]["hit"] for r in te)}
    models = {}
    for kind in ("shipped", "sy", "pw", "pre", "cap"):
        best = None
        for C in (.03, .1, .3, 1.0):  # C chosen by leave-one-class-out on train years only
            ll = []
            for D in range(2016, 2021):
                a = [r for r in tr if r["D"] != D]; b = [r for r in tr if r["D"] == D]
                ll.append(evaluate(b, pred(fit(a, kind, C), b, kind), "")["ll"] * len(b))
            s = sum(ll) / len(tr)
            if best is None or s < best[0] - 1e-9:
                best = (s, C)
        M = fit(tr, kind, best[1]); M["C"] = best[1]; models[kind] = M
        res[kind] = {"C": best[1], "train": evaluate(tr, pred(M, tr, kind), ""), "test": evaluate(te, pred(M, te, kind), ""),
                     "coef": dict(zip(M["names"], [round(c, 3) for c in M["coef"]]))}
    # draft capital, drafted only (the Devy Lab 'drafted' tab)
    dtr = [r for r in tr if r["drafted"]]; dte = [r for r in te if r["drafted"]]
    for kind in ("cap", "cpw"):
        M = fit(dtr, kind, 1.0); models[kind + "_drafted"] = M
        res[kind + "_drafted"] = {"test": evaluate(dte, pred(M, dte, kind), ""), "test_shipped": evaluate(dte, pred(models["shipped"], dte, "shipped"), ""),
                                  "test_pw": evaluate(dte, pred(models["pw"], dte, "pw"), "")}
    # round-only baseline for drafted players: hit rate by position x round group (shrunk k=4 to the round group)
    rg = lambda r: "1" if r["rd"] == 1 else "2" if r["rd"] == 2 else "3" if r["rd"] == 3 else "4-7"
    T, G = {}, {}
    for r in dtr:
        for key, D_ in (((r["pos"], rg(r)), T), (rg(r), G)):
            D_.setdefault(key, [0, 0]); D_[key][0] += r["o3"]["hit"]; D_[key][1] += 1
    pt = np.array([(T.get((r["pos"], rg(r)), [0, 0])[0] + 4 * G[rg(r)][0] / G[rg(r)][1]) / (T.get((r["pos"], rg(r)), [0, 0])[1] + 4) for r in dte])
    res["round_table_drafted_test"] = evaluate(dte, pt, "")
    # app constants: raw-scale coefficients (z = intercept[pos] + sum coef[k] * x[k])
    app = {}
    for k in ("pw", "cpw_drafted"):
        M = models[k]; c = dict(zip(M["names"], M["coef"])); mu = dict(zip(M["names"], M["mu"])); sd = dict(zip(M["names"], M["sd"]))
        raw = {n: c[n] / sd[n] for n in M["names"] if not n.startswith("i_")}
        b0 = sum(c[n] * mu[n] / sd[n] for n in raw)
        app[k] = {"b": {p: round(c["i_" + p] - b0, 4) for p in POS}, "w": {n: round(v, 4) for n, v in sorted(raw.items())}}
    res["app"] = app
    # devy snapshots (1-2 seasons before the final college season), models fitted on final-season rows above.
    # Seasons in college at the draft use the app's projection (stay through year 3), never the realised value.
    S = json.load(open(os.environ.get("E23_OUT", "/tmp/b11/e23_rows.json").replace(".json", "_snap.json")))
    S.sort(key=lambda r: (r["cur"], r["id"]))
    for r in S:
        r["cls"] = max(3, r["cls_now"])
    for ah in (1, 2):
        st = [r for r in S if r["ahead"] == ah and r["D"] >= 2021]
        res[f"snap{ah}_test"] = {k: evaluate(st, pred(models[k], st, k), "") for k in ("shipped", "sy", "pw", "pre")}
        sa = [r for r in S if r["ahead"] == ah]
        res[f"snap{ah}_all"] = {k: evaluate(sa, pred(models[k], sa, k), "") for k in ("shipped", "sy", "pw", "pre")}
    json.dump({"res": res, "models": models}, open(os.environ.get("E23_FIT", "/tmp/b11/e23_fit.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
