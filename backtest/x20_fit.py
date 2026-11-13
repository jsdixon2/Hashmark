"""Data test 3: does CFBD usage / play value add to the shipped devy model (pwr = production + recruiting)? Same split as
e23 (fit draft classes 2016-20, test 2021-23, plus devy snapshots 1-2 seasons before the final college season).
Features from the player's final college season (snapshots: the snapshot season): usage overall, pass+rush share,
PPA per play, total PPA (missing = 0 + flag). Ship only if pwu beats pwr on test AND both snapshots (AUC and log loss)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import e23_fit_rec as RC
E = RC.E
U = json.load(open(os.environ.get("X20_OUT", "/tmp/x20_cfbd.json")))
_f = E.feats
def usage(r):
    y = r.get("cur", r["D"] - 1)
    for yy in (y, y - 1):
        v = U.get(f'{r["id"]}|{yy}')
        if v and v.get("uo") is not None: return v
    return None
def feats(r, kind):
    if kind != "pwu": return _f(r, kind)
    x = _f(r, "pwr"); v = usage(r) or {}
    for k in ("uo", "pa", "pt"): x["u_" + k] = float(v.get(k) or 0)
    x["u_none"] = 0.0 if v else 1.0
    return x
E.feats = feats
R = E.R; tr = [r for r in R if r["D"] <= 2020]; te = [r for r in R if r["D"] >= 2021]
print("usage found: train %.2f test %.2f" % (sum(1 for r in tr if usage(r)) / len(tr), sum(1 for r in te if usage(r)) / len(te)))
S = json.load(open(os.environ.get("E23_OUT", "/tmp/b11/e23_rows.json").replace(".json", "_snap.json"))); S.sort(key=lambda r: (r["cur"], r["id"]))
byid = {r["id"]: r for r in R}
for r in S: r["cls"] = max(3, r["cls_now"]); r["n"] = byid.get(r["id"], {}).get("n")
for kind in ("pwr", "pwu"):
    M = E.fit(tr, kind, 1.0); out = {}
    for name, rows in (("test", te), ("snap1", [r for r in S if r["ahead"] == 1 and r["D"] >= 2021]), ("snap2", [r for r in S if r["ahead"] == 2 and r["D"] >= 2021])):
        ev = E.evaluate(rows, E.pred(M, rows, kind), ""); out[name] = {"auc": ev["auc"], "ll": ev["ll"], "n": len(rows)}
    print(kind, json.dumps(out)); print("  coef", json.dumps({k: round(c, 3) for k, c in zip(M["names"], M["coef"]) if k.startswith("u_")}))
