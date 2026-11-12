#!/usr/bin/env python3
"""e23: does recruiting rating add to the fitted devy model (pw)? Consumes $E23_REC from e23_cfbd_pull.py and the rows
from e23_data.py. Same split as e23_fit.py: fit 2016-2020 draft classes, test 2021-2023 (and devy snapshots 1-2 seasons
earlier). Recruit features: rating (0-1, 247 composite; unrated = 0) + unrated flag. Joined by CFBD athleteId = roster
athlete_id, else by name + school of the player's first college team. Prints test AUC / log loss with and without.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import e23_fit as E

REC = json.load(open(os.environ.get("E23_REC", "/tmp/e23_recruit.json")))
_feats = E.feats


def first_school(r):
    return ((r.get("first_school") or r.get("school") or "")).lower()


def rating(r):
    v = REC.get(str(r["id"])) or REC.get(f'n:{E_norm(r.get("n"))}|{first_school(r)}')
    return (v or {}).get("rating")


def E_norm(n):
    import re
    n = (n or "").lower().replace(".", "").replace("'", "").replace("’", "")
    n = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", n.strip())
    return re.sub(r"[^a-z ]", "", n).strip()


def feats(r, kind):
    if kind not in ("pwr", "cpwr"):
        return _feats(r, kind)
    x = _feats(r, "pw" if kind == "pwr" else "cpw")
    rt = rating(r)
    x["rec"] = float(rt) if rt else 0.0
    x["unrated"] = 0.0 if rt else 1.0
    return x


E.feats = feats


def main():
    R = E.R
    tr = [r for r in R if r["D"] <= 2020]; te = [r for r in R if r["D"] >= 2021]
    print("rated share train", round(sum(1 for r in tr if rating(r)) / len(tr), 3), "test", round(sum(1 for r in te if rating(r)) / len(te), 3))
    S = json.load(open(os.environ.get("E23_OUT", "/tmp/b11/e23_rows.json").replace(".json", "_snap.json")))
    S.sort(key=lambda r: (r["cur"], r["id"]))
    byid = {r["id"]: r for r in R}
    for r in S:
        r["cls"] = max(3, r["cls_now"]); r["n"] = byid.get(r["id"], {}).get("n")
    out = {}
    for kind in ("pw", "pwr"):
        M = E.fit(tr, kind, 1.0)
        out[kind] = {"test": E.evaluate(te, E.pred(M, te, kind), ""),
                     "snap1": E.evaluate([r for r in S if r["ahead"] == 1 and r["D"] >= 2021], E.pred(M, [r for r in S if r["ahead"] == 1 and r["D"] >= 2021], kind), ""),
                     "snap2": E.evaluate([r for r in S if r["ahead"] == 2 and r["D"] >= 2021], E.pred(M, [r for r in S if r["ahead"] == 2 and r["D"] >= 2021], kind), ""),
                     "coef": dict(zip(M["names"], [round(c, 3) for c in M["coef"]]))}
    print(json.dumps(out, indent=1))
    print("SHIP recruiting only if pwr beats pw on test AND both snapshots (AUC and log loss).")


if __name__ == "__main__":
    main()
