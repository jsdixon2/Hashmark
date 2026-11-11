"""Engine 6, part 1: NFL team ratings. Fits a margin-based rating (Elo-style updates in points, home edge, last-season
prior shrunk toward 0, capped margins) on 2006-2020 and tests on 2021-2025 regular-season games (Brier, log loss,
accuracy) against the closing spread (Vegas) and a blend of the two.
Usage: python3 backtest/e12_teams.py  (needs backtest/dl/games.csv from nflverse)."""
import pandas as pd, numpy as np, json, os, itertools, math
B = os.path.dirname(os.path.abspath(__file__))
G = pd.read_csv(f"{B}/dl/games.csv", low_memory=False)
G = G[G.home_score.notna() & G.away_score.notna()].sort_values(["season", "week", "gameday"]).reset_index(drop=True)
G["margin"] = G.home_score - G.away_score  # home minus away
def phi(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def run(K, HFA, REG, CAP, SIG, seasons, keep=False):
    r, last, out = {}, None, []
    for s, gs in G[G.season.isin(seasons)].groupby("season", sort=True):
        r = {t: REG * v for t, v in r.items()}  # last-season prior, shrunk toward average
        for g in gs.itertuples():
            h, a = r.get(g.home_team, 0.0), r.get(g.away_team, 0.0)
            hfa = 0.0 if g.location == "Neutral" else HFA
            pred = h - a + hfa
            if keep and g.game_type == "REG" and g.margin != 0:
                out.append((s, g.week, pred, g.spread_line, g.margin, g.home_team, g.away_team))
            err = max(-CAP, min(CAP, g.margin)) - pred
            r[g.home_team] = h + K * err; r[g.away_team] = a - K * err
    return r, out

def score(rows, SIG, w=0.0):
    b = ll = acc = 0.0
    for s, wk, pred, sp, m, *_ in rows:
        mu = (1 - w) * pred + w * (sp if sp == sp else pred)
        p = min(.999, max(.001, phi(mu / SIG))); y = 1.0 if m > 0 else 0.0
        b += (p - y) ** 2; ll -= y * math.log(p) + (1 - y) * math.log(1 - p); acc += (p > .5) == (y == 1)
    n = len(rows); return b / n, ll / n, acc / n

FIT = list(range(2002, 2021)); TEST = list(range(2002, 2026))
best = None
for K, HFA, REG, CAP in itertools.product([.06, .08, .1, .12], [1.0, 1.5, 2.0, 2.5], [.4, .5, .6, .7], [14, 17, 21, 28]):
    _, rows = run(K, HFA, REG, CAP, 13.5, FIT, keep=True)
    rows = [x for x in rows if x[0] >= 2006]
    b = score(rows, 13.5)[0]
    if best is None or b < best[0]: best = (b, K, HFA, REG, CAP)
_, K, HFA, REG, CAP = best
_, rows = run(K, HFA, REG, CAP, 13.5, TEST, keep=True)
fit_rows = [x for x in rows if 2006 <= x[0] <= 2020]
SIG = min([11, 12, 12.5, 13, 13.5, 14, 15], key=lambda s: score(fit_rows, s)[0])
test = [x for x in rows if x[0] >= 2021 and x[3] == x[3]]
vegas = [(s, wk, sp, sp, m) for s, wk, pred, sp, m, *_ in test]
# blend weight fitted on 2006-2020 only
fw = [x for x in fit_rows if x[3] == x[3]]
W = min([i / 20 for i in range(21)], key=lambda w: score(fw, SIG, w)[0])
res = {"params": {"K": K, "HFA": HFA, "prior_shrink": REG, "margin_cap": CAP, "sigma": SIG, "blend_weight_on_spread": W},
       "test_2021_2025_games": len(test),
       "ratings_only": dict(zip(["brier", "logloss", "accuracy"], [round(v, 4) for v in score(test, SIG)])),
       "vegas_closing_spread": dict(zip(["brier", "logloss", "accuracy"], [round(v, 4) for v in score(vegas, SIG)])),
       "blend": dict(zip(["brier", "logloss", "accuracy"], [round(v, 4) for v in score(test, SIG, W)])),
       "by_season": {s: {"ratings": round(score([x for x in test if x[0] == s], SIG)[0], 4), "vegas": round(score([x for x in vegas if x[0] == s], SIG)[0], 4),
                         "blend": round(score([x for x in test if x[0] == s], SIG, W)[0], 4)} for s in range(2021, 2026)}}
print(json.dumps(res, indent=1)); json.dump(res, open(f"{B}/e12_teams.json", "w"), indent=1)
