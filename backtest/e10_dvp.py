"""Engine 6 check: does 'points allowed to a position' (DVP) so far predict what a defense allows next, and do players score more against soft DVP opponents beyond their own level?"""
import pandas as pd, numpy as np, json, os
B = os.path.dirname(os.path.abspath(__file__))
P = pd.concat([pd.read_csv(f"{B}/dl/ps_{y}.csv", low_memory=False, usecols=["player_id", "position", "recent_team", "opponent_team", "week", "season", "season_type", "fantasy_points_ppr"]) for y in range(2015, 2025)])
P = P[(P.season_type == "REG") & P.position.isin(["QB", "RB", "WR", "TE"])]
A = P.groupby(["season", "week", "opponent_team", "position"]).fantasy_points_ppr.sum().rename("allowed").reset_index()
A = A.sort_values(["season", "opponent_team", "position", "week"])
g = A.groupby(["season", "opponent_team", "position"]).allowed
A["todate"] = g.transform(lambda s: s.shift().expanding().mean()); A["n"] = g.cumcount()
out = {}
for pos in ["QB", "RB", "WR", "TE"]:
    q = A[(A.position == pos) & (A.n >= 4)].dropna()
    q = q.assign(dev=q.allowed - q.groupby(["season", "week"]).allowed.transform("mean"), tdev=q.todate - q.groupby(["season", "week"]).todate.transform("mean"))
    out[pos] = {"corr: points allowed so far vs next game": round(float(np.corrcoef(q.tdev, q.dev)[0, 1]), 3),
                "slope (pts of next-game difference per pt of DVP difference)": round(float(np.polyfit(q.tdev, q.dev, 1)[0]), 3)}
# player level: does opponent DVP explain the player's game beyond his own season average?
P = P.sort_values(["player_id", "season", "week"])
P["ppg"] = P.groupby(["player_id", "season"]).fantasy_points_ppr.transform(lambda s: s.shift().expanding().mean()); P["gp"] = P.groupby(["player_id", "season"]).cumcount()
M = P[(P.gp >= 4) & (P.ppg >= 6)].merge(A[["season", "week", "opponent_team", "position", "todate", "n"]], on=["season", "week", "opponent_team", "position"])
M = M[M.n >= 4]
for pos in ["QB", "RB", "WR", "TE"]:
    q = M[M.position == pos].copy(); q["rel"] = q.todate / q.groupby(["season", "week"]).todate.transform("mean")
    r = np.corrcoef(q.rel - 1, q.fantasy_points_ppr / q.ppg - 1)[0, 1]
    soft = q.rel >= q.rel.quantile(.8); hard = q.rel <= q.rel.quantile(.2)
    out[pos]["player: corr opp DVP vs game/season ratio"] = round(float(r), 3)
    out[pos]["player: softest-20% opp, pts vs own avg"] = round(float((q.fantasy_points_ppr - q.ppg)[soft].mean()), 2)
    out[pos]["player: toughest-20% opp, pts vs own avg"] = round(float((q.fantasy_points_ppr - q.ppg)[hard].mean()), 2)
    out[pos]["fitted matchup effect (fraction of DVP gap that shows up)"] = round(float(np.polyfit(q.rel - 1, q.fantasy_points_ppr / q.ppg - 1, 1)[0]), 3)
print(json.dumps(out, indent=1)); json.dump(out, open(B + "/e10_dvp.json", "w"), indent=1)
