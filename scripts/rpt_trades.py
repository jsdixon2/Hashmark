"""Report card: trade-grade calibration (key tested.trade_grades; tested.trades from e11 is left as it is).

From backtest/e25_data.py + e25_an.py (written to backtest/e25.json). The app's day-one grade replayed on real 2-team
dynasty and keeper trades from the league archive: values = FantasyPros ECR on the trade date through VANS/VAN1 (blended
like the app), picks by round, side value effV (v119: TC d .9 / g 1.0), P(side comes out ahead) = pvTable (PVT).
Outcome = points above replacement received minus sent, rest of that season + next season weeks 1-9; picks = what that
round has produced in real rookie drafts. Favoured side only: "said 70" = grade said 65-75%, "won" = share that came out
ahead. TC chosen on 2021-24 trades; 2025 trades held out. Offense only (IDP: 30 trades, see idp).
Standard library only; numbers are fixed backtest results, not recomputed in Actions."""

FIT = {"n": 11162, "said": .629, "won": .669, "brier": .2176, "said60_won": .643, "said70_won": .752, "said80_won": .785}
HOLD = {"n": 3689, "said": .630, "won": .645, "brier": .2264, "said60_won": .629, "n60": 2094, "said70_won": .693, "n70": 1034,
        "said80_won": .718, "n80": 202,
        "before_v119": {"won": .627, "brier": .2335, "said60_won": .612, "said70_won": .658, "said80_won": .713}}
SPLITS_2025 = {  # held-out season, v119 grade (brier before v119 in brackets)
    "young": {"n": 834, "won": .634, "said": .618, "brier": .2262, "brier_before": .2346},
    "not_young": {"n": 2855, "won": .648, "said": .634, "brier": .2265, "brier_before": .2331},
    "consolidation": {"n": 2135, "won": .681, "said": .625, "brier": .2148, "brier_before": .2271},
    "picks": {"n": 3147, "won": .661, "said": .632, "brier": .2221, "brier_before": .2298},
    "players_only": {"n": 542, "won": .554, "said": .623, "brier": .2516, "brier_before": .2547},
}
STARTED = {  # same trades, PAR counted only in weeks the player started for the team holding him (lineup-slot check)
    "holdout_2025": {"n": 3082, "said": .632, "won": .648, "brier": .2242, "said60_won": .62, "said70_won": .71, "said80_won": .75,
                     "before_v119": {"brier": .2258, "said70_won": .69, "said80_won": .74}},
    "fit_2021_24": {"n": 9795, "brier": .2210, "before_v119": .2243},
    "two_seasons_2021_23": {"n": 6035, "brier": .2095, "before_v119": .2147},
    "2for1_2025": {"n": 883, "brier": .2130, "before_v119": .2161},
    "3for1_2025": {"n": 258, "brier": .2188, "before_v119": .2209},
}
IDP = {"n_idp": 24, "idp_won": .708, "idp_said": .709, "n_off": 2538, "off_won": .578, "off_said": .654,
       "note": "production proxy (no IDP rank history); player-only trades 2021-26; too few IDP trades to change anything"}

def section(ctx=None):
    t = dict(said60_won=HOLD["said60_won"], said70_won=HOLD["said70_won"], said80_won=HOLD["said80_won"], n=HOLD["n"],
             won=HOLD["won"], said=HOLD["said"], brier=HOLD["brier"],
             holdout_2025=HOLD, fit_2021_24=FIT, splits_2025=SPLITS_2025, started=STARTED, idp=IDP,
             src="real dynasty/keeper trades 2021-25, app's day-one grade replayed; 2025 held out", backtest="e25",
             unit="favoured side ahead in points above replacement, rest of season + next season wks 1-9")
    return {"tested": {"trade_grades": t}}

if __name__ == "__main__":
    import json; print(json.dumps(section(), indent=1))
