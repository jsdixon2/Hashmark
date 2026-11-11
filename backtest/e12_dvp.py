"""Engine 6, part 3: matchups. Opponent-adjusted, shrunk defense-vs-position.
For every player-game (2021-2025, REG), a defense's 'points over expected allowed' (POE) at a position = the player's
PPR points minus his own average in his OTHER games that season (so a defense isn't blamed for facing stars).
Defense rating at a position before week w = sum of POE in weeks < w / (games + k)  (shrinks small samples to 0).
Test: does player points = own average-to-date + beta * defense rating beat own average alone?
k and beta fitted on 2021-2023, tested on 2024-2025 (MAE and correlation)."""
import pandas as pd, numpy as np, json, os, glob
B = os.path.dirname(os.path.abspath(__file__))
fr = []
for y in range(2021, 2026):
    p = f"{B}/dl/pw_{y}.csv"
    if os.path.exists(p): fr.append(pd.read_csv(p, low_memory=False, usecols=["player_id", "position", "season", "week", "season_type", "team", "opponent_team", "fantasy_points_ppr"]))
P = pd.concat(fr); P = P[(P.season_type == "REG") & P.position.isin(["QB", "RB", "WR", "TE"])].copy()
P = P.sort_values(["player_id", "season", "week"])
g = P.groupby(["player_id", "season"]).fantasy_points_ppr
P["tot"], P["n"] = g.transform("sum"), g.transform("count")
P["avg_other"] = np.where(P.n > 1, (P.tot - P.fantasy_points_ppr) / (P.n - 1), np.nan)
P["avg_todate"] = g.transform(lambda s: s.shift().expanding().mean()); P["gp"] = g.cumcount()
P["poe"] = P.fantasy_points_ppr - P.avg_other
# defense POE per game-position (sum over the players at that position that game)
D = P.dropna(subset=["poe"]).groupby(["season", "week", "opponent_team", "position"]).poe.sum().reset_index()
D = D.sort_values(["season", "opponent_team", "position", "week"])
gg = D.groupby(["season", "opponent_team", "position"]).poe
D["cum"] = gg.transform(lambda s: s.shift().fillna(0).cumsum()); D["ng"] = gg.cumcount()
M = P[(P.gp >= 3) & (P.avg_todate >= 5)].merge(D[["season", "week", "opponent_team", "position", "cum", "ng"]], on=["season", "week", "opponent_team", "position"], how="left").fillna({"cum": 0, "ng": 0})
# player's share of his position's opportunity: use his avg relative to position group total via simple scaling
res = {"by_position": {}}
for pos in ["QB", "RB", "WR", "TE"]:
    q = M[M.position == pos]; fit = q[q.season <= 2023]; test = q[q.season >= 2024]
    best = None
    for k in [2, 4, 6, 8, 12]:
        rat = fit.cum / (fit.ng + k)
        # scale per player: defense POE is per position-game, so a player gets his share ~ avg / position-team average
        share = fit.avg_todate / fit.groupby(["season", "week", "opponent_team"]).avg_todate.transform("sum").clip(lower=1)
        x = (rat * share).values; y = (fit.fantasy_points_ppr - fit.avg_todate).values
        beta = float(np.dot(x, y) / max(1e-9, np.dot(x, x)))
        mae = float(np.mean(np.abs(y - beta * x)))
        if best is None or mae < best[0]: best = (mae, k, beta)
    _, k, beta = best
    rat = test.cum / (test.ng + k); share = test.avg_todate / test.groupby(["season", "week", "opponent_team"]).avg_todate.transform("sum").clip(lower=1)
    adj = beta * rat * share; y = test.fantasy_points_ppr
    base_mae = float(np.mean(np.abs(y - test.avg_todate))); new_mae = float(np.mean(np.abs(y - (test.avg_todate + adj))))
    base_c = float(np.corrcoef(y, test.avg_todate)[0, 1]); new_c = float(np.corrcoef(y, test.avg_todate + adj)[0, 1])
    soft = rat >= rat.quantile(.9); hard = rat <= rat.quantile(.1)
    res["by_position"][pos] = {"k_shrink_games": k, "beta": round(beta, 3), "test_n": int(len(test)),
        "mae_own_avg": round(base_mae, 3), "mae_with_matchup": round(new_mae, 3), "corr_own_avg": round(base_c, 4), "corr_with_matchup": round(new_c, 4),
        "softest_10pct_defenses_pts_vs_avg": round(float((y - test.avg_todate)[soft].mean()), 2), "toughest_10pct_defenses_pts_vs_avg": round(float((y - test.avg_todate)[hard].mean()), 2)}
print(json.dumps(res, indent=1)); json.dump(res, open(f"{B}/e12_dvp.json", "w"), indent=1)
