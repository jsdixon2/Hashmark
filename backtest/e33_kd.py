"""F1 / e33 item 3: kickers with no Sleeper projection (kdPts shows 0). Panel = backtest/e28_kd.py (K rows 2021-26,
Sleeper std scoring). For K rows whose team plays that week but Sleeper has no projection, compare: 0 (shipped), the
kicker's season average so far (>= 2 games, else the week's median kicker projection), and the week's median projection.
Also split by whether he had played for that team earlier in the season (what the app can see: p.ppg / games)."""
import os, sys, json, statistics as st, collections
import numpy as np
B = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, B)
import e28_kd
rows = e28_kd.panel()
K = [r for r in rows if r["pos"] == "K"]
med = collections.defaultdict(list)
for r in K:
    if r["proj"] is not None: med[(r["y"], r["w"])].append(r["proj"])
med = {k: st.median(v) for k, v in med.items()}
none = [r for r in K if r["proj"] is None]
print("K rows", len(K), "no projection", len(none), "played", sum(1 for r in none if r["played"]))
out = {}
def grade(tag, R):
    if not R: return
    y = np.array([r["pts"] for r in R])
    zero = np.zeros(len(R)); md = np.array([med.get((r["y"], r["w"]), 8.0) for r in R])
    avg = np.array([r["avg"] if r["avg"] is not None else med.get((r["y"], r["w"]), 8.0) for r in R])
    avg_only = np.array([r["avg"] if r["avg"] is not None else 0.0 for r in R])
    o = {"n": len(R), "played_share": round(float(np.mean([bool(r["played"]) for r in R])), 3), "mean_pts": round(float(y.mean()), 2),
         "zero": round(float(np.abs(y - zero).mean()), 3), "median": round(float(np.abs(y - md).mean()), 3),
         "avg_else_median": round(float(np.abs(y - avg).mean()), 3), "avg_else_zero": round(float(np.abs(y - avg_only).mean()), 3)}
    out[tag] = o; print(tag, o)
for s in range(2021, 2027): grade(f"{s} all", [r for r in none if r["y"] == s])
grade("2021-26 all", none)
grade("2021-26 has season avg (2+ games)", [r for r in none if r["avg"] is not None])
grade("2021-26 no season avg", [r for r in none if r["avg"] is None])
for s in (2025, 2026): grade(f"{s} has season avg", [r for r in none if r["y"] == s and r["avg"] is not None])
json.dump(out, open(os.path.join(B, "e33_kd.json"), "w"), indent=1)
