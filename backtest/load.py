import pandas as pd, numpy as np, os
D = os.path.join(os.path.dirname(__file__), "dl")

def weekly(seasons):
    fr = []
    for y in seasons:
        p = f"{D}/ps_{y}.csv"
        if os.path.exists(p) and os.path.getsize(p) > 1000:
            d = pd.read_csv(p, low_memory=False).rename(columns={"recent_team": "team"})
        else:
            d = pd.read_csv(f"{D}/spw_{y}.csv", low_memory=False)
        d = d[d.season_type == "REG"]
        if "interceptions" in d.columns and "passing_interceptions" not in d.columns: d = d.rename(columns={"interceptions": "passing_interceptions"})
        keep = ["passing_interceptions", "player_id", "player_display_name", "position", "team", "opponent_team", "season", "week", "fantasy_points_ppr", "target_share"]
        fr.append(d[[c for c in keep if c in d.columns]])
    w = pd.concat(fr, ignore_index=True)
    w = w[w.position.isin(["QB", "RB", "WR", "TE"])]
    w = w.rename(columns={"fantasy_points_ppr": "fp"})
    if os.environ.get("SLEEPER_INT"): w["fp"] = w.fp + w.passing_interceptions.fillna(0)  # Sleeper default: -1 per INT, nflverse uses -2
    return w

def games():
    g = pd.read_csv(f"{D}/games.csv", low_memory=False)
    return g[g.game_type == "REG"]

def xfp(seasons):
    fr = []
    for y in seasons:
        p = f"{D}/ep_{y}.csv"
        if os.path.exists(p):
            d = pd.read_csv(p, low_memory=False)
            fr.append(d[["season", "week", "player_id", "total_fantasy_points_exp"]].rename(columns={"total_fantasy_points_exp": "xfp"}))
    return pd.concat(fr, ignore_index=True) if fr else None
