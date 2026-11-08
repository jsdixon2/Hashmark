"""Engine 5 fixes (v65), from the redraft retest on exact weekly rosters (input: e9_exact2 output, 516 leagues, 2024-25).

Weaknesses in the retest and what the data said:
 1. Suggestions hurt the lineup more often than managers' own claims (28% vs 17%). Driver: the dropped player still
    had value. Within the same rated lift, moves whose drop projects >=45% of the add's points hurt 33-41% of the time.
    Fix: judge every add/drop pair by g' = g - DROP_W * (drop's own 4-week points). DROP_W fitted on one season and
    tested on the other (0.20 from 2024, 0.30 from 2025): raises real gain and cuts the hurt rate at the same number of
    moves in redraft, keeper and dynasty, both directions. App uses 0.25.
 2. WR (and QB) lifts looked overstated next to TE. Not stable: TE adds were best in 2024 (+13.5) and worst in 2025
    (+4.4); a position correction fitted on 2024 made 2025 worse. No position correction shipped.
 3. Dynasty suggestions were weak. Fix: a higher bar to show a move in dynasty (g' >= 6), on top of item 1.
    (The app also protects dynasty drops by long-term value, which this test can't replay, so dynasty here is a floor.)
Picking a different pair with richer fitted models (ridge/boosting with position terms) made results worse; the only
pair-choice change kept is the drop penalty."""
import pickle, sys, os, json, numpy as np, pandas as pd
B = os.path.dirname(os.path.abspath(__file__))
R, M = pickle.load(open(sys.argv[1] if len(sys.argv) > 1 else B + "/e9_exact2_rosters.pkl", "rb"))
R = pd.DataFrame(R); M = pd.DataFrame(M)
R["tn"] = R.t.map({0: "redraft", 1: "keeper", 2: "dynasty", 3: "other"})
M["tn"] = M.lg.map(R.drop_duplicates("lg").set_index("lg").tn)
key = ["s", "w", "lg", "rid"]
def f(q): return dict(n=int(len(q)), gain=round(float(q.r3.mean()), 2), helped=round(float((q.r3 > 0).mean()), 3), hurt=round(float((q.r3 < 0).mean()), 3))
# 1. drop weight: fit on one season, test on the other, at the same number of moves as the old 4+ rule
O = R.loc[R.groupby(key).g.idxmax()]
cv = {}
for trs, tes in [(2024, 2025), (2025, 2024)]:
    t = O[O.s == trs]; k = (t.g >= 4).sum()
    b = max(np.arange(0, 1.01, .05), key=lambda b: t.loc[(t.g - b * t.dval).nlargest(k).index].r3.mean())
    cv[f"fit {trs} -> test {tes}"] = {"drop_w": round(float(b), 2)}
    for tn in ["redraft", "keeper", "dynasty"]:
        q = O[(O.s == tes) & (O.tn == tn)]; k = int((q.g >= 4).sum())
        cv[f"fit {trs} -> test {tes}"][tn] = {"old": f(q[q.g >= 4]), "new": f(q.loc[(q.g - b * q.dval).nlargest(k).index])}
print(json.dumps(cv, indent=1))
# 2. shipped rule: pair chosen by g', shown when g' >= bar (4; 6 in dynasty), tiers 8 / 12 on g'
DROP_W, BAR = .25, {"redraft": 4, "keeper": 4, "other": 4, "dynasty": 6}
R["gp"] = R.g - DROP_W * R.dval
P = R.loc[R.groupby(key).gp.idxmax()]
final = {}
for tn in ["redraft", "keeper", "dynasty", "other"]:
    o, p = O[O.tn == tn], P[P.tn == tn]; m = M[(M.tn == tn) & (M.typ == "waiver")]; bar = BAR[tn]
    final[tn] = {"old: shown (g>=4)": f(o[o.g >= 4]), "new: shown (g'>=%d)" % bar: f(p[p.gp >= bar]),
                 "old Strong add (g>=12)": f(o[o.g >= 12]), "new Strong add (g'>=12)": f(p[p.gp >= 12]),
                 "old Good+ (g>=8)": f(o[o.g >= 8]), "new Good+ (g'>=8)": f(p[p.gp >= 8]),
                 "managers' waiver claims": f(m), "managers' free-agent adds": f(M[(M.tn == tn) & (M.typ == "free_agent")]),
                 "by season, new shown": {int(s): f(p[(p.s == s) & (p.gp >= bar)]) for s in (2024, 2025)},
                 "by season, old shown": {int(s): f(o[(o.s == s) & (o.g >= 4)]) for s in (2024, 2025)}}
    print(f"\n{tn}"); [print(f"  {k:30s}", v) for k, v in final[tn].items()]
pa = P[P.gp >= P.tn.map(BAR)]; oa = O[O.g >= 4]
print("\nby add position, old:", oa.groupby("apos").r3.agg(["size", "mean"]).round(2).to_dict("index"))
print("by add position, new:", pa.groupby("apos").r3.agg(["size", "mean"]).round(2).to_dict("index"))
print("by season x add position (old shown):", oa.groupby(["s", "apos"]).r3.mean().round(2).unstack().to_dict("index"))
json.dump({"drop_w": DROP_W, "bar": BAR, "crossval": cv, "final": final}, open(B + "/e9_fix.json", "w"), indent=1)
