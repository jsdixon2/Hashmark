"""Engine 6, part 2: games 1-6 weeks ahead (no betting line yet). Compares, for 2021-2025 regular seasons:
 elo      - the e12 margin rating as of the prediction week
 market   - team ratings implied by all closing spreads so far this season (ridge least squares, recency-weighted,
            last-season market rating as prior), i.e. what the betting market thinks of each team
 blend    - w*market + (1-w)*elo, w fitted on 2021-2022, tested on 2023-2025."""
import pandas as pd, numpy as np, json, os, math
B = os.path.dirname(os.path.abspath(__file__))
E = json.load(open(f"{B}/e12_teams.json"))["params"]
G = pd.read_csv(f"{B}/dl/games.csv", low_memory=False)
G = G[G.season >= 2019].sort_values(["season", "week", "gameday"]).reset_index(drop=True)
TEAMS = sorted(set(G.home_team) | set(G.away_team)); ix = {t: i for i, t in enumerate(TEAMS)}
def phi(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
SIG, HFA = E["sigma"], E["HFA"]

def market(rows, prior, lam=3.0, half=6.0):
    """ridge fit: spread_line ~ r_home - r_away + hfa; rows=(home,away,spread,weeks_ago,neutral)"""
    n = len(TEAMS); A = []; y = []; wts = []
    for h, a, sp, ago, neu in rows:
        v = np.zeros(n + 1); v[ix[h]] = 1; v[ix[a]] = -1; v[n] = 0 if neu else 1; A.append(v); y.append(sp); wts.append(0.5 ** (ago / half))
    A = np.array(A); y = np.array(y); W = np.diag(wts)
    reg = np.eye(n + 1) * lam; reg[n, n] = 1e-3
    p0 = np.append(prior, HFA)
    sol = np.linalg.solve(A.T @ W @ A + reg, A.T @ W @ y + reg @ p0)
    return sol[:n], sol[n]

def elo_through(season, week):
    r = {}
    for s, gs in G[G.season <= season].groupby("season"):
        r = {t: E["prior_shrink"] * v for t, v in r.items()}
        for g in gs.itertuples():
            if s == season and g.week >= week: break
            if g.home_score != g.home_score: continue
            h, a = r.get(g.home_team, 0.0), r.get(g.away_team, 0.0); hfa = 0 if g.location == "Neutral" else HFA
            err = max(-E["margin_cap"], min(E["margin_cap"], g.home_score - g.away_score)) - (h - a + hfa)
            r[g.home_team] = h + E["K"] * err; r[g.away_team] = a - E["K"] * err
    return r

out = []
mprior = {}
for s in range(2020, 2026):
    S = G[(G.season == s) & (G.game_type == "REG")]
    last_w = int(S.week.max())
    # previous season's final market rating = prior (shrunk)
    prev = G[(G.season == s - 1) & G.spread_line.notna()]
    if len(prev):
        pr, _ = market([(g.home_team, g.away_team, g.spread_line, 0, g.location == "Neutral") for g in prev.itertuples()], np.zeros(len(TEAMS)))
        prior = .6 * pr
    else: prior = np.zeros(len(TEAMS))
    if s == 2020: continue
    for wk in range(3, last_w - 1):
        past = S[(S.week < wk) & S.spread_line.notna()]
        mr, mh = market([(g.home_team, g.away_team, g.spread_line, wk - g.week, g.location == "Neutral") for g in past.itertuples()], prior)
        er = elo_through(s, wk)
        for k in range(1, 7):
            for g in S[S.week == wk + k - 1].itertuples():
                if g.home_score != g.home_score or g.home_score == g.away_score: continue
                neu = g.location == "Neutral"; y = 1.0 if g.home_score > g.away_score else 0.0
                pe = er.get(g.home_team, 0) - er.get(g.away_team, 0) + (0 if neu else HFA)
                pm = mr[ix[g.home_team]] - mr[ix[g.away_team]] + (0 if neu else mh)
                out.append((s, k, pe, pm, y, g.spread_line))
D = pd.DataFrame(out, columns=["s", "k", "pe", "pm", "y", "sp"])
br = lambda mu: ((D.y - mu.apply(lambda v: phi(v / SIG))) ** 2)
fitm = D[D.s <= 2022]
W = min([i / 10 for i in range(11)], key=lambda w: br(fitm.pm * w + fitm.pe * (1 - w)).mean() if len(fitm) else 0)
T = D[D.s >= 2023]
res = {"blend_weight_on_market": W, "test_games": len(T), "by_weeks_ahead": {}}
for k in range(1, 7):
    q = T[T.k == k]
    res["by_weeks_ahead"][k] = {"n": len(q), "elo": round(br(q.pe)[q.index].mean(), 4), "market": round(br(q.pm)[q.index].mean(), 4),
                                "blend": round(br(q.pm * W + q.pe * (1 - W))[q.index].mean(), 4), "closing_line_that_week": round(br(q.sp)[q.index].mean(), 4)}
print(json.dumps(res, indent=1)); json.dump(res, open(f"{B}/e12_ahead.json", "w"), indent=1)
