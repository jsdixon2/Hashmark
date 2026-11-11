#!/usr/bin/env python3
"""e20 step 3: 2025 (held out) summary for scripts/rpt_live.py: Brier / calibration by slate moment, shipped vs v123."""
import gzip, json, collections, sys
sys.path.insert(0, "backtest")
import e20_eval as E
OUT = ".build/agents/b10/"
R = json.load(gzip.open(OUT + "live_states.json.gz", "rt"))
te = [r for r in R if r[0] == 2025]
MOM = {("Thu-night", 1.0): "After Thursday", ("Sun-early", .5): "Sunday early games at halftime", ("Sun-early", 1.0): "After Sunday early games",
       ("Sun-late", 1.0): "After Sunday late games", ("Sun-night", 1.0): "After Sunday night", ("Mon-night", .5): "Monday night at halftime"}
res = {}
def cal(xs):
    out = []
    for lo, hi in ((0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)):
        v = [x for x in xs if lo <= x[0] < hi]
        if len(v) >= 50: out.append({"said": round(sum(p for p, _ in v) / len(v), 3), "won": round(sum(y for _, y in v) / len(v), 3), "n": len(v)})
    return out
for (lab, f), name in MOM.items():
    rs = [r for r in te if r[-1] == lab and r[2] == f]
    if not rs: continue
    old = [(E.model(r), r[4]) for r in rs]; new = [(E.model(r, "gs", 1.2, 1.1), r[4]) for r in rs]
    # favourite view: said = favourite's chance, happened = favourite won
    fav = [(max(p, 1 - p), y if p >= .5 else 1 - y) for p, y in new]
    res[name] = {"n": len(rs), "brier_old": round(E.brier(old), 4), "brier": round(E.brier(new), 4),
                 "fav_said": round(sum(p for p, _ in fav) / len(fav), 3), "fav_won": round(sum(y for _, y in fav) / len(fav), 3), "calib": cal(new)}
print(json.dumps(res, indent=1))
json.dump(res, open(OUT + "e20_slate.json", "w"), indent=1)
