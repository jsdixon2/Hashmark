# Hashmark — session handoff (2026-11-08)

What this session did, so the next Claude agent can carry on. Read `CLAUDE.md` first: it has the owner's standing
instructions, code conventions and the status of every engine. This file adds the detail behind the latest changes.
Newest session at the top.

---

## 2026-11-08, later: live in-game projections (v66, on main) and the WR investigation (not shipped)

### v66: live projections and win odds (on `main`, commit 45cbfef)
- **Problem the owner reported:** live points showed during games, but projections and win probability stayed at their
  pregame values.
- **Fix:** a started player's projection is now `points so far + pregame projection × share of his game left`, and a
  finished game counts actual points. Kicker and DEF (`kdPts`) follow the same rule.
- **Win probability:** uses the live projections. Each side's variance is scaled by the share of its lineup's pregame
  projection still to play (`lineupLeft`), so the odds tighten as games finish and reach 100% or 0% once all are final.
- **Game clock:** comes from ESPN's public scoreboard (`site.api.espn.com/.../nfl/scoreboard`), refreshed every 60 s
  while games are on. If it can't be reached, the clock is estimated from kickoff time in `data/sched.json` (game ≈ 3.1 h).
  ESPN couldn't be tested from the cloud sandbox, so the estimate is the safety net. Check in a real browser that the
  scoreboard call succeeds.
- **Code:** functions `gameState`, `livePtsMap`, `wkPre` (the old `wkProj`), `lineupLeft`. Wrappers on `wkProj`,
  `kdPts`, `myMatchup`, `gameTag`, `refreshLive`. Source in `.build/v66.js`.
- **QA:** a simulated live demo league. A mid-game player at 12 pts with 38% of his game left on a 16.5 projection
  showed 18.3. Win odds went from 92% to 94% mid-game and to 100% at the end, with no page errors.

### WR adds: what was tried (owner asked to optimize WR adds; explain before committing to main)
- **New measure** (`r3s` in `e9_exact2.py`): lineups set by our projections before each game and scored on actual
  points, the way a manager would play it. The old `r3` scored hindsight-best lineups.
- **What the new measure shows:** on `r3s`, v65's shown moves gain +5.9 (2024) and +4.9 (2025), with 35% hurt. WR adds
  are the weakest: +2.8 and 43% hurt.
- **Receiving-role features** (air-yards share, WOPR, average depth of target, targets, TD luck; `e9_wr.py`): no
  improvement. Rank correlation on the wire was 0.563–0.565 against 0.564 now; boosted trees were worse. The WR rate is
  already calibrated (0.98 on the wire), so the player model isn't the problem.
- **WR-only discount on the lift:** didn't hold across seasons (fitted on 2025, the best discount is none).
- **Haircut on every wire player's outlook before choosing** (`ADDH` in `e9_exact2.py`, compared in `e9_wrfix.py`):
  1.5 pts/game at all positions cut the hurt rate in all 6 season × league-type cells (30→26, 32→26, 39→34, 27→25,
  28→25, 39→34). Against simply raising v65's bar to the same number of moves, the change in gain was mixed (−0.2 to
  +0.4). Larger haircuts (3, or 3 at WR only) were inconsistent.
- **Conclusion:** WR can't be fixed reliably with the free data available. The only defensible change is the 1.5
  all-position haircut, which means fewer moves that backfire.
- **Shipped as v67** after the owner said "go": `WV_FAH = 1.5`. `wireRecs` sets `S._wvH` to the league's rostered ids,
  and the `wvVec` wrapper trims everyone else. Shown moves, both seasons, lineups set before games (hindsight in
  brackets):

  | League type | Before (v65) | After (v67) |
  |---|---|---|
  | Redraft | +7.2, 32% hurt (10.8 / 73% helped) | +8.8, 25% hurt (11.7 / 75%) |
  | Keeper | +5.5, 33% hurt | +7.3, 25% hurt |
  | Dynasty | +2.7, 40% hurt | +4.3, 34% hurt |

  About 30% fewer moves are suggested.

---

## Session of 2026-11-08: redraft waiver retest and v65 fixes

### What the owner asked
1. Re-test the waiver advice on redraft leagues once `bt/rosters.json.gz` landed (open item from the previous session).
2. Then: "Push all current fixes and apply fixes to all weaknesses you located. Put all changes in the readable file for
   other agent to view." This file is that readable file.

### Setup (needed in a fresh cloud container)
The backtests need nflverse files in `backtest/dl/` (gitignored). These URLs work through the sandbox proxy:
```
cd backtest/dl
R=https://github.com/nflverse/nflverse-data/releases/download
curl -sSfLo games.csv $R/schedules/games.csv
curl -sSfLo ids.csv https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv
for y in 2021 2022 2023 2024 2025; do
  curl -sSfLo ep_$y.csv   https://github.com/ffverse/ffopportunity/releases/download/latest-data/ep_weekly_$y.csv
  curl -sSfLo snap_$y.csv $R/snap_counts/snap_counts_$y.csv
  curl -sSfLo inj_$y.csv  $R/injuries/injuries_$y.csv
done
pip install scipy scikit-learn
```
Note: `github.com/<org>/<repo>/raw/...` links return 403 here. Use `raw.githubusercontent.com` instead.

Then run `python3 backtest/e9_data.py`, then `python3 backtest/e9_fit.py`. The second one writes `e9_Dfit.pkl`, which
the waiver tests read.

### Step 1: retest on the exact-roster archive
`SRC=rosters python3 backtest/e9_exact.py` (≈15 min, single core) → `backtest/e9_an.py`.
- 516 leagues, 62,616 team-weeks, 2024–25. League types in the archive: 163 redraft, 49 keeper, 293 dynasty, 11 type-3
  (best ball or guillotine; too few to act on).
- **Unit:** real lineup points the move added over the next 3 weeks (weeks w+1..w+3, hindsight-best lineup), against
  keeping the roster as it was.

| Before v65 | Redraft | Keeper | Dynasty |
|---|---|---|---|
| Hashmark, all suggestions | +7.2 (64% helped, 28% hurt) | +6.5 | +3.5 |
| Hashmark, rated 8+ | +10.1 (71% / 23%) | +9.8 | +6.8 |
| Managers' own waiver claims | +7.6 (66% / 17%) | +6.5 | +3.9 |

### Weaknesses found, what the data said, and what shipped
Fitting and testing used `backtest/e9_exact2.py` (the same test, but it logs the top 3 add/drop pairs per add position,
runs on 4 cores in about 6 min, and writes `e9_exact2_rosters.pkl`) and `backtest/e9_fix.py` (writes `e9_fix.json`).

1. **Suggestions hurt the lineup more often than managers' claims (28% vs 17%).**
   - **Driver:** the dropped player still had value. At the same rated lift, moves whose drop projects ≥45% of the
     add's 4-week points hurt 33–41% of the time and gained about half as much. This held in both seasons.
   - **Fix:** score each pair by `g' = g − 0.25 × drop's own 4-week points`.
   - **Weight:** fitted on 2024 it came out 0.20, on 2025 it came out 0.30. Tested on the other season both ways, it
     raised gain and cut the hurt rate at the same number of moves in redraft, keeper and dynasty.
   - **App:** shipped as `WV_DROPW = .25`. It also chooses the pair by `g'`. The UI shows "close call: he still
     projects X pts" when the drop projects ≥45% of the add.
2. **WR (and QB) lifts looked overstated next to TE.**
   - **Not a stable effect:** TE adds were the best in 2024 (+13.5) and the worst in 2025 (+4.4). A position correction
     fitted on 2024 made 2025 worse.
   - **No position correction shipped.** WR adds remain the weakest (+6.0 under the new rule, against +9–12 for other
     positions). Still open.
3. **Dynasty suggestions were weak.**
   - **Fix:** a higher bar to show a move in dynasty, `g' ≥ 6` (4 elsewhere): `wvBar()`.
   - **Caveat:** the app already protects dynasty drops by long-term value (`wvProtected`). The test can't replay that,
     because the archive has no historical dynasty values, so the dynasty numbers here are a floor.
4. **Tried and rejected:** re-picking pairs with richer fitted models (Huber or ridge regression with position terms,
   gradient boosting, and a lookup table of lift × drop risk × position). Each one did worse than the app's own pair
   choice at the same number of moves. The only change to pair choice that held up is the drop penalty.

### Result of the shipped rule (both seasons; from `e9_fix.json`)
| Shown moves | Redraft | Keeper | Dynasty |
|---|---|---|---|
| Old rule (g ≥ 4) | +8.7, 68% helped, 25% hurt (n 14,933) | +8.1, 66%, 25% | +5.9, 61%, 21% |
| **New rule (g' ≥ bar)** | **+10.8, 73%, 20% (n 10,227)** | **+10.1, 71%, 20%** | **+7.3, 65%, 17%** |
| New "Strong add" (g' ≥ 12) | +12.8, 76%, 19% | +12.1, 76%, 17% | +9.0, 69%, 16% |
| Managers' waiver claims | +7.6, 66%, 17% | +6.5, 65%, 16% | +3.9, 47%, 10% |

- **By season, redraft:** 2024 +12.0 (was +9.7); 2025 +9.8 (was +7.9).
- **Trade-off:** about a third fewer moves are suggested. The ones that remain are better.
- **Still behind managers:** the hurt rate is 20% against managers' 17%. Managers' claims often drop players who were
  scoring nothing, so they rarely lose points, but they gain less.

### App changes (`index.html`)
- **New block** `v65` before `/* ===== boot ===== */` (source in `.build/v65.js`; `.build/` is gitignored).
  - `wireRecs` is rewrapped with the same logic plus the drop penalty. `r.g` is now the penalised lift; `r.raw`,
    `r.dv` and `r.risky` were added.
  - `wvRow` is wrapped to add the close-call note.
- **In-place edits (exact-match asserted):** the four `r.g>=4` checks (waiver page "best adds", track-record tags, the
  home moves list, the home summary) now use `wvBar()`. The "nothing on the wire" message shows the bar. The "Tested on"
  sentence on the waiver page now carries the new numbers.
- **QA:**
  - All inline scripts passed `node --check`.
  - Playwright on the demo league showed redraft and dynasty bars of 4 and 6, the drop pairing on a full roster and
    the close-call label, with no page errors. The demo league is tiny (6 free agents), so live leagues are the real
    test.

### Still open (for the next agent)
- **Waivers:** the hurt rate is still above managers'; WR adds are the weakest. Possible next step: a rate model aware
  of the WR role (route participation, if a free source exists) and drop choice that weighs injury cover.
- **IDP trade grades:** retest once a few more weeks of 2026 data are in.
- **Engine 6 (NFL team ratings and matchups):** the plan is in `CLAUDE.md`. Wait for the owner's "go".

### Earlier history
The previous session's full handoff (briefing, the original engine review, transcript) was given to this session by the
owner as `hashmark-handoff.md`. It isn't committed, because the repo is public. `CLAUDE.md` holds its essentials.
