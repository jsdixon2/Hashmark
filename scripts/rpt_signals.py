"""Report-card section `signals`: held-out test of breakout odds and the risk score (backtest/e18_data.py + e18_fit.py).

Numbers are fixed results of the backtest (fit on 2017-21 seasons, tested on later seasons the fit never saw);
rerun the backtest to refresh them. Breakout = not yet a top-12 QB/TE / top-24 RB/WR in PPR points per game (this
season so far or last season) and finishes there next season (min 8 games) or over the rest of this season (min 4).
Risk outcome = share of his team's remaining games he missed or scored under half his season-to-date average.
"""

SIGNALS = {
    "src": "nflverse weekly stats 2016-2026; cuts at weeks 4/6/8/10/12 and season end",
    "backtest": "e18",
    "breakout_next": {
        "held_out": "2022-2024", "n": 12437, "base_rate": 0.026,
        "old": {"auc": 0.718, "brier": 0.063, "avg_said": 0.176, "calls30_n": 2909, "calls30_hit": 0.055},
        "new": {"auc": 0.921, "brier": 0.0222, "avg_said": 0.030, "calls30_n": 249, "calls30_hit": 0.297},
        "calib": [["0-5%", 10678, 0.007, 0.007], ["5-10%", 708, 0.072, 0.062], ["10-20%", 538, 0.143, 0.132],
                  ["20-30%", 264, 0.241, 0.231], ["30-50%", 211, 0.384, 0.303], ["50%+", 38, 0.554, 0.263]],
    },
    "breakout_ros": {
        "held_out": "2022-2026", "n": 14320, "base_rate": 0.031,
        "old": {"auc": 0.643, "brier": 0.0684, "avg_said": 0.178, "calls30_n": 3403, "calls30_hit": 0.053},
        "new": {"auc": 0.925, "brier": 0.0244, "avg_said": 0.030, "calls30_n": 266, "calls30_hit": 0.398},
        "calib": [["0-5%", 12147, 0.007, 0.005], ["5-10%", 842, 0.073, 0.083], ["10-20%", 745, 0.142, 0.14],
                  ["20-30%", 320, 0.242, 0.291], ["30-50%", 231, 0.371, 0.394], ["50%+", 35, 0.568, 0.429]],
    },
    "risk": {
        "held_out": "2022-2026", "n": 4458, "avg_bust": 0.426,
        "old": {"rank_corr": 0.255, "top_tier_bust": 0.554, "safe_bust": 0.355},
        "new": {"rank_corr": 0.359, "top_tier_bust": 0.599, "safe_bust": 0.318},
        "tiers_new": [["Bubble-wrapped", 873, 0.303], ["Sunday nap", 707, 0.337], ["Coin flip", 718, 0.378],
                      ["Spicy nugget", 675, 0.434], ["Hold my beer", 659, 0.515], ["Full-send fireworks", 826, 0.599]],
        "per_season_rank_corr": {"2022": [0.24, 0.327], "2023": [0.286, 0.377], "2024": [0.288, 0.348], "2025": [0.207, 0.383], "2026": [0.24, 0.354]},
    },
    "lines": [
        "Breakout calls of 30%+ came true 30% of the time next season (old formula: 5.5%), 40% over the rest of the season.",
        "Top risk tier busted in 60% of remaining games vs 30% for the safest tier (old score: 55% vs 34%).",
    ],
}


def section(ctx):
    return {"signals": SIGNALS}
