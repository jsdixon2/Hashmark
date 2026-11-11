"""Engine 6, part 5: does the implied-team-total signal add anything on top of Sleeper's own weekly projection
(which Hashmark's projection engine starts from)? residual = actual PPR - Sleeper projection; feature = projection *
(implied team points / team avg points to date - 1). Fit 2021-2023, test 2024-2025."""
import pandas as pd, numpy as np, json, os, gzip
B = os.path.dirname(os.path.abspath(__file__)); H = os.path.join(B, "..", "bt")
SP = json.load(gzip.open(f"{H}/sleeper_proj.json.gz", "rt"))["w"]
ids = pd.read_csv(f"{B}/dl/ids.csv", low_memory=False, usecols=["gsis_id", "sleeper_id"]).dropna(); ids["sleeper_id"] = ids.sleeper_id.astype(int).astype(str)
g2s = dict(zip(ids.gsis_id, ids.sleeper_id))
G = pd.read_csv(f"{B}/dl/games.csv", low_memory=False); G = G[(G.season >= 2021) & (G.game_type == "REG")]
rows = []
for g in G.itertuples():
    if g.spread_line != g.spread_line or g.total_line != g.total_line: continue
    rows += [(g.season, g.week, g.home_team, g.total_line / 2 + g.spread_line / 2, g.home_score), (g.season, g.week, g.away_team, g.total_line / 2 - g.spread_line / 2, g.away_score)]
T = pd.DataFrame(rows, columns=["season", "week", "team", "imp", "pts"]).sort_values(["season", "team", "week"])
T["avg"] = T.groupby(["season", "team"]).pts.transform(lambda s: s.shift().expanding().mean())
fr = [pd.read_csv(f"{B}/dl/pw_{y}.csv", low_memory=False, usecols=["player_id", "position", "season", "week", "season_type", "team", "fantasy_points_ppr"]) for y in range(2021, 2026) if os.path.exists(f"{B}/dl/pw_{y}.csv")]
P = pd.concat(fr); P = P[(P.season_type == "REG") & P.position.isin(["QB", "RB", "WR", "TE"])].copy()
P["sid"] = P.player_id.map(g2s); P = P.dropna(subset=["sid"])
P["proj"] = [((SP.get(f"{s}-{w}") or {}).get(i) or {}).get("pts_ppr") for s, w, i in zip(P.season, P.week, P.sid)]
P = P.dropna(subset=["proj"]); P = P[P.proj >= 5]
M = P.merge(T, on=["season", "week", "team"]).dropna(subset=["avg"]); M["x"] = M.proj * (M.imp / M.avg.clip(lower=10) - 1)
res = {"by_position": {}}
for pos in ["QB", "RB", "WR", "TE"]:
    q = M[M.position == pos]; fit = q[q.season <= 2023]; test = q[q.season >= 2024]
    yf = (fit.fantasy_points_ppr - fit.proj).values; beta = float(np.dot(fit.x, yf) / np.dot(fit.x, fit.x))
    y = test.fantasy_points_ppr; base = float(np.mean(np.abs(y - test.proj))); new = float(np.mean(np.abs(y - (test.proj + beta * test.x))))
    res["by_position"][pos] = {"beta_on_top_of_sleeper": round(beta, 3), "test_n": int(len(test)), "mae_sleeper": round(base, 3), "mae_sleeper_plus_env": round(new, 3)}
print(json.dumps(res, indent=1)); json.dump(res, open(f"{B}/e12_env_vs_sleeper.json", "w"), indent=1)
