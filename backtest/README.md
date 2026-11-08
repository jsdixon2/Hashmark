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
| e10_dvp.py | NFL teams (engine 6) | How much defense-vs-position actually predicts |
