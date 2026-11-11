# Backtests

Scripts that fit and test Hashmark's engines against real outcomes. They read the archives in `../bt/`
(built by the GitHub Actions in `.github/workflows/`) and nflverse files in `backtest/dl/`
(not committed; download URLs in HANDOFF.md: weekly player stats `ps_YYYY.csv`, ffopportunity `ep_YYYY.csv`, `snap_YYYY.csv`, `inj_YYYY.csv`,
`games.csv`, `ids.csv` from the nflverse data releases on GitHub).

| Script | Engine | What it does |
|---|---|---|
| e7_keeper.py → e7_eval.py, e7_fit.py | Trades (keeper) | 1,657 keeper-league trades vs this-season lineup points + next-season keeper value; fits how much next season counts |
| e8_waiver.py | Waivers | First look: which signals predict next-4-week points; FAAB points per dollar |
| e9_data.py → e9_fit.py | Waivers | Player-week panel and the fitted rest-of-month rate (coefficients in index.html `WVC`) |
| e9_team.py, e9_team3.py, e9_exact.py, e9_an.py | Waivers | Team-level test: suggested add/drop vs real lineup points (e9_exact uses exact weekly rosters: `SRC=keepers` or `SRC=rosters`) |
| e9_exact2.py → e9_fix.py | Waivers (v65) | e9_exact with the top 3 add/drop pairs per add position logged (4 cores, ~6 min); e9_fix fits the drop penalty on one season, tests on the other, and measures the shipped rule (`e9_fix.json`) |
| e9_faab.py, e9_lgfaab.py | FAAB | Winning-bid tables by demand and season phase (`FAABQ`, `FAABP` in index.html); league calibration |
| e9_wr.py, e9_wrfix.py | Waivers (v67) | WR rate variants with receiving-role features; wire-outlook haircut comparison (with e9_exact2 ADDH runs) |
| e11_trades.py → e11_an.py | Trade finder (v68) | 3,413 real in-season dynasty/keeper trades: does fitting both teams' plans predict that both benefited? |
| e13_young.py | Values (v106) | Do young players' dynasty values lag? Blend variants vs market 1 yr later and next-2-season production |
| e14_data.py → e14_fit.py, e14_props.py | Projections (v108) | Player-week panel 2021-26 with the app's inputs; median-regression refit vs Sleeper (2025/2026 held out), boosted-tree ceiling; props blend weight |
| e10_dvp.py | NFL teams (engine 6) | How much defense-vs-position actually predicts |
