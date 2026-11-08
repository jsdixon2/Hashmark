"""FAAB: what it takes to win a claim (winning bid as a share of the budget) by demand and time of season,
and whether paying more bought more points."""
import pandas as pd, numpy as np, json, os
B = os.path.dirname(os.path.abspath(__file__))
A = pd.read_pickle(B + "/e9_adds.pkl"); D = pd.read_pickle(B + "/e9_Dfit.pkl")
A = A[A.w.between(2, 16)]
# demand: how many archive leagues added him that week, ranked like Sleeper's trending list
cnt = A.groupby(["s", "w", "pid"]).size().rename("c").reset_index()
cnt["rk"] = cnt.groupby(["s", "w"]).c.rank(ascending=False, method="first")
cnt["tier"] = pd.cut(cnt.rk, [0, 5, 15, 30, 50, 100, 1e9], labels=["top 5", "6-15", "16-30", "31-50", "51-100", "not trending"])
W = A[(A.typ == "waiver") & A.bid.notna()].copy()
bud = W.groupby("lg").bid.max().rename("mx").reset_index()
bud["budget"] = np.select([bud.mx <= 100, bud.mx <= 200, bud.mx <= 500], [100, 200, 500], 1000)
W = W.merge(bud[["lg", "budget"]], on="lg").merge(cnt, on=["s", "w", "pid"], how="left")
W = W[W.groupby("lg").bid.transform("count") >= 5]  # leagues that actually use FAAB
W["pct"] = W.bid / W.budget
W["phase"] = pd.cut(W.w, [0, 5, 10, 18], labels=["weeks 2-5", "weeks 6-10", "weeks 11+"])
out = {"n_bids": len(W), "budgets": W.drop_duplicates("lg").budget.value_counts().to_dict()}
q = W.groupby(["tier", "phase"], observed=True).pct.quantile([.5, .7, .85, .95]).unstack().round(3)
out["winning bid % of budget (median/70th/85th/95th)"] = {f"{a} | {b}": list(v) for (a, b), v in q.iterrows()}
out["n by tier/phase"] = {f"{a} | {b}": int(v) for (a, b), v in W.groupby(["tier", "phase"], observed=True).size().items()}
# points bought: next-4-week points by bid within the same demand tier
M = W.merge(D[["s", "w", "pid", "y4", "lin", "games"]], on=["s", "w", "pid"], how="left").dropna(subset=["y4"])
M["over"] = M.pct > M.groupby(["tier", "phase"], observed=True).pct.transform("median")
out["pts next 4 wks: paid above vs at/below tier median"] = {str(t): [round(float(g[g.over].y4.mean()), 1), round(float(g[~g.over].y4.mean()), 1), int(g.over.sum()), int((~g.over).sum())] for t, g in M.groupby("tier", observed=True)}
# did our predicted rate explain bids? and does value per dollar fall with price?
M["b"] = pd.cut(M.pct, [-.01, 0, .02, .05, .1, .2, 1.01], labels=["$0", "1-2%", "3-5%", "6-10%", "11-20%", "21%+"])
out["by bid size: n, pts next 4 wks, predicted pts"] = {str(k): [int(len(g)), round(float(g.y4.mean()), 1), round(float((g.lin * g.games).mean()), 1)] for k, g in M.groupby("b", observed=True)}
# tiers for players not on the trending list, split by our own value rank
print(json.dumps(out, indent=1)); json.dump(out, open(B + "/e9_faab.json", "w"), indent=1)
# compact table for the app: tier -> phase -> [q50,q70,q85,q95]
T = {}
for (a, b), v in q.iterrows(): T.setdefault(str(a), {})[str(b)] = [float(x) for x in v]
json.dump(T, open(B + "/e9_faab_table.json", "w"))
