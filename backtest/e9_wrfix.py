"""WR adds: does a haircut on wire players' outlook (winner's-curse guard) improve real lineup gains?
Inputs: e9_exact2_rosters.pkl (no haircut) and e9_exact2_rosters_<tag>.pkl runs (ADDH env in e9_exact2.py).
Primary measure r3s: lineups set by our own projections before each game (what a manager would do), scored on actual
points over weeks w+1..w+3. r3 (hindsight-best lineups) shown too. Pair chosen by g' = g - 0.25 * drop's 4-week points."""
import pickle, os, sys, numpy as np, pandas as pd
B = os.path.dirname(os.path.abspath(__file__))
BAR = {"redraft": 4, "keeper": 4, "other": 4, "dynasty": 6}
key = ["s", "w", "lg", "rid"]
def load(tag):
    R, _ = pickle.load(open(B + f"/e9_exact2_rosters{tag}.pkl", "rb")); R = pd.DataFrame(R)
    R["tn"] = R.t.map({0: "redraft", 1: "keeper", 2: "dynasty", 3: "other"}); R["gp"] = R.g - .25 * R.dval
    return R.loc[R.groupby(key).gp.idxmax()]
runs = {"none": ""}
for t in sys.argv[1:] or ["_wr15", "_wr3", "_all15"]:
    if os.path.exists(B + f"/e9_exact2_rosters{t}.pkl"): runs[t.strip("_")] = t
P = {k: load(v) for k, v in runs.items()}
def f(q, c="r3s"): return f"{q[c].mean():5.2f} ({(q[c] > 0).mean():.0%}/{(q[c] < 0).mean():.0%}) n={len(q)}"
for s in (2024, 2025):
    print(f"\n== {s}: shown moves (g' >= bar). set-by-projection gain (helped/hurt) | hindsight gain")
    for k, d in P.items():
        q = d[(d.s == s)]; q = q[q.gp >= q.tn.map(BAR)]
        k0 = P["none"]; k0 = k0[(k0.s == s)]; n0 = int((k0.gp >= k0.tn.map(BAR)).sum())
        same = d[d.s == s].nlargest(n0, "gp")
        print(f"  {k:6s} shown {f(q)} | {f(q, 'r3')} || same count as none: {f(same)} | WR adds {f(q[q.apos == 'WR'])}")
    for tn in ["redraft", "keeper", "dynasty"]:
        print(f"  {tn}: " + " | ".join(f"{k} {f(d[(d.s == s) & (d.tn == tn) & (d.gp >= BAR[tn])])}" for k, d in P.items()))
print("\n== both seasons, by add position (set-by-projection gain, shown moves)")
for k, d in P.items():
    q = d[d.gp >= d.tn.map(BAR)]
    print(f"  {k:6s}", q.groupby("apos").r3s.agg(["size", "mean"]).round(2).to_dict("index"))
