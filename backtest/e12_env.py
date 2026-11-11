"""Engine 6, part 4: game environment. Does the betting market's implied team total (from the closing spread and
over/under) move a player's points beyond his own average to date? feature = implied team points / team's average
points scored to date (this season). Fitted on 2021-2023, tested on 2024-2025, per position."""
import pandas as pd, numpy as np, json, os
B = os.path.dirname(os.path.abspath(__file__))
G = pd.read_csv(f"{B}/dl/games.csv", low_memory=False); G = G[(G.season >= 2021) & (G.game_type == "REG")]
rows = []
for g in G.itertuples():
    if g.spread_line != g.spread_line or g.total_line != g.total_line: continue
    home = g.total_line / 2 + g.spread_line / 2; away = g.total_line / 2 - g.spread_line / 2   # spread_line = expected home margin
    rows += [(g.season, g.week, g.home_team, home, g.home_score), (g.season, g.week, g.away_team, away, g.away_score)]
T = pd.DataFrame(rows, columns=["season", "week", "team", "imp", "pts"]).sort_values(["season", "team", "week"])
T["avg"] = T.groupby(["season", "team"]).pts.transform(lambda s: s.shift().expanding().mean())
fr = [pd.read_csv(f"{B}/dl/pw_{y}.csv", low_memory=False, usecols=["player_id", "position", "season", "week", "season_type", "team", "fantasy_points_ppr"]) for y in range(2021, 2026) if os.path.exists(f"{B}/dl/pw_{y}.csv")]
P = pd.concat(fr); P = P[(P.season_type == "REG") & P.position.isin(["QB", "RB", "WR", "TE"])].sort_values(["player_id", "season", "week"])
g = P.groupby(["player_id", "season"]).fantasy_points_ppr; P["avg_todate"] = g.transform(lambda s: s.shift().expanding().mean()); P["gp"] = g.cumcount()
M = P[(P.gp >= 3) & (P.avg_todate >= 5)].merge(T, on=["season", "week", "team"], how="inner").dropna(subset=["avg"])
M["x"] = (M.imp / M.avg.clip(lower=10) - 1)
res = {"by_position": {}}
for pos in ["QB", "RB", "WR", "TE"]:
    q = M[M.position == pos]; fit = q[q.season <= 2023]; test = q[q.season >= 2024]
    xf = (fit.x * fit.avg_todate).values; yf = (fit.fantasy_points_ppr - fit.avg_todate).values; beta = float(np.dot(xf, yf) / np.dot(xf, xf))
    adj = beta * test.x * test.avg_todate; y = test.fantasy_points_ppr
    hi = test.x >= test.x.quantile(.9); lo = test.x <= test.x.quantile(.1)
    res["by_position"][pos] = {"beta": round(beta, 3), "test_n": int(len(test)), "mae_own_avg": round(float(np.mean(np.abs(y - test.avg_todate))), 3),
        "mae_with_env": round(float(np.mean(np.abs(y - (test.avg_todate + adj)))), 3), "corr_own_avg": round(float(np.corrcoef(y, test.avg_todate)[0, 1]), 4),
        "corr_with_env": round(float(np.corrcoef(y, test.avg_todate + adj)[0, 1]), 4),
        "best_10pct_environments_pts_vs_avg": round(float((y - test.avg_todate)[hi].mean()), 2), "worst_10pct_environments_pts_vs_avg": round(float((y - test.avg_todate)[lo].mean()), 2)}
print(json.dumps(res, indent=1)); json.dump(res, open(f"{B}/e12_env.json", "w"), indent=1)
