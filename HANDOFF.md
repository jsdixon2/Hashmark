# Hashmark — session handoff (2026-11-08)

What this session did, so the next Claude agent can carry on. Read `CLAUDE.md` first: it has the owner's standing
instructions, code conventions and the status of every engine. This file adds the detail behind the latest changes.
Newest session at the top.

---

## 2026-11-09: v70, start/sit advice respects locks (on main)
- **Owner's report:** "Start Quentin Johnston over DeMario Douglas" appeared while both were LIVE.
- **Cause:**
  - `alertsFor` (Needs attention, home Urgent/Lineup moves, matchup card) had no lock check at all.
  - `locked()` (used by the Start/Sit page) only saw games within 4 hours of kickoff in `data/sched.json`.
- **Fix (`.build/v70.js`):**
  - `locked` is wrapped to also use `gameState`, so a game counts as locked from kickoff to final.
  - `alertsFor` is rewritten: locked starters get no swap advice (finished ones read "has played · X points banked" from
    live points, and only Thursday games say "played Thursday"), and locked bench players are never suggested.
- **QA (simulated live demo):**
  - A pregame swap (Brissett over Rodgers) disappears once Brissett's game is final.
  - It stays when neither player has kicked off.
  - No page errors.

- **v71:** v70 made every finished starter an info alert. The matchup page lists info alerts under "Needs attention", so
  the list grew to the whole lineup. Two or more finished starters now fold into one line ("N starters have played ·
  X points banked").

- **v72 (owner said yes to the three display fixes):**
  - `pc()` now shows "<1%" / ">99%".
  - Seven win-chance texts switched from `${PCT(x)}%` to `${pc(x)}`; style widths untouched.
  - The home ring skips its count-up for `<`/`>` values.
  - `myMatchup` holds `wpA` to 0.001-0.999 while any lineup has points left. Before this, 1 − 1e-47 rounded to "100%".
  - The "Projected edge by position" heading says "live projection" during games.
  - The `liveSet` wrapper keeps the LIVE badge number only for players rostered in `S.L`.

- **v73 (owner: "limit grading and analysis context to what the user needs; add an info button"):**
  - `CONDENSE` rules match long paragraphs by their opening words. `condense(root)` runs after `decorate`, moves the full
    text into `DEFS["cx_<title>"]` (merged when two paragraphs share a title), and adds `info(k)` to the section's tag pill
    or heading, never inside team-name headings or cards. When there's no heading it leaves a "Title ⓘ" line.
  - Trade-finder cards are compact:
    - Redraft: "Title odds a → b · lineup +x/wk · theirs ±y/wk · drop Z".
    - Dynasty/keeper: "You · fit · +v% value / Them (rec, plan) · fit · +v% · market".
  - Trends: "-2.3 pts/g ahead of his pace" now reads "usage says 2.3 pts/g below his pace".
  - **Audit (all 22 pages in the demo):** no paragraph over 160 characters except the legal page, no horizontal
    overflow, and no page errors.

- **v74 (owner: fix items 1, 3-6 of the UI report, consolidate headers, clean up the matchup page, add game stats):**
  - **Matchup lineups:** the bold number is real league points (`W.ls.pp`) once a game starts. Before kickoff it shows
    a grey projection plus "proj".
  - **Status line:** Final, or "Q4 13:06 · proj X", or opponent and kickoff time.
  - **Stat line:** built from Sleeper `/stats/nfl/regular/{season}/{week}` (`loadWkStats`, refreshed every 90 s with
    live scores). Example: "22/31, 284 yds, 2 TD, 1 INT · 4 car, 21 yds".
  - **Bench:** uses the same rules.
  - **Needs attention:** only your own problems. "Their problems" no longer carries fix advice, and "N starters have
    played" is a footer line.
  - **Headers:** `pageChrome()` in a final render wrapper removes the `.pgtitle .eyebrow` and replaces the h1 with
    `h2.pgsub` when one exists.
  - **Other:**
    - Info buttons in one row merge into one (`mx_*` keys).
    - Waiver rows: tier pill under the number, "13.4/wk".
    - Trade cards: "+1,947 value" instead of "+94%".
    - Inline links get a ±8px tap area via `::after`; War Room ▲▼☆ are 36px.
  - **Known limit:** links inside boxes that clip overflow (trade-card team names, roster names) still have small tap
    areas.
  - **QA:** simulated live demo with final, live and pregame players plus stats; page audit with no errors or overflow.

- **v75 (owner: initials in player boxes aren't helpful; show "RB/26/PHI"):**
  - The `mono` wrapper draws small tiles (44px) as three stacked lines: position, jersey number (`p.num` from Sleeper's
    `number`, "–" if missing) and team. The stripe is replaced by a bottom team-colour edge.
  - The large player-page tile shows the number big with "QB · PIT" at the top.
  - The demo league has no jersey numbers; live leagues do.

- **v76 (owner: drop the team under the name, take position out of the box and put the tag before the name; small live
  projection beside live score; real K and D/ST names on the matchup):**
  - **List rows:** five templates edited in place (prow, exploit card, value list, players list, waiver row) so the
    position tag comes before the name and the team text goes.
  - **Inline tag:** the `tmTagEl` wrapper reduces it to age only when a row has a box.
  - **Matchup:** live cells show "21.0  23.7 proj". Status lines use a red dot plus the clock, and "Not started" when
    the schedule gives only the team.
  - **K/DEF:** the K + DEF total row is replaced by per-slot rows from `L.allSlots` with live starters, or `kdLineup`
    otherwise.

- **v77 (owner: Joe Milton, a healthy backup QB signed 2 weeks ago, showed "Missed 8 of his team's games", Health 95,
  Injury watch):**
  - **Cause:** `rawRisk` counted every team game without a stat line as missed.
  - **Fix:**
    - `missedInjured(p)` uses `VAL.v[id].injh[2]`: weeks Out/Doubtful on nflverse's official injury reports this season,
      built in `scripts/build_values.py`. It returns 0 when the player isn't on any report.
    - Without values data, it counts only gaps between appearances, for regulars (snap share 50%+, or a QB starter).
  - **Text:** "Listed out for N games this season".
  - **Value breakdown:** shows "Not projected above a replacement QB, now or in future seasons" instead of a 100%/0%
    split of zeros.
  - **Test:** a backup QB went from Health 95 to 47 ("Role in flux: 9% of snaps"). A starter with 3 report weeks still
    shows Injury watch.

- **v78 (owner: the live indicator is hard to see):** the `mxLive()` wrapper on `mxCell`/`kdCell` adds class `mxlive`
  (red-tinted card, 3px red edge on the outer side, extended with negative margins so names don't truncate) and a red
  "LIVE" before the clock. The dot pulses, except with reduced motion. "proj" stays inline with its number.

- **v79 (owner: TB@CHI heading to overtime showed as final):**
  - `loadGameClock` and `gameState` are redefined.
  - **ESPN:** "post" counts only with `type.completed` or a FINAL status name. End of regulation, end of a period and
    OT stay "in", labelled "End of regulation" / "OT 6:52".
  - **Kickoff-time estimate:** live up to 5.5 h ("Late" after 3.1 h), was 4.2 h.
  - **`liveSet` windows:** 4 / 4.2 h raised to 5.5 h.
  - **Tested** with mocked ESPN payloads for each case.
  - **Not confirmed:** which path closed the game on the owner's phone (ESPN payload or the time estimate). Both are
    fixed.

- **v80 (owner: show final score vs Hashmark's weekly projection):** wrappers on `mxCell`/`kdCell` add
  `vsProj(pts, proj)` after final scores ("22.4 ▲5.9 vs 16.5"). Arrows come from the existing .good/.bad classes.

- **v81 (owner: add the NFL final score and opponent next to "Final"):**
  - `loadGameClock` stores `opp`, `home`, `pf` and `pa` per team from ESPN.
  - `nflResult(team)` builds "W 27–24 @ CHI", falling back to sched.json `as`/`hs`.
  - Wrappers on `mxCell`/`kdCell` add it after "Final".

- **v82 (owner: what is "151 points banked" with 145.2 live; rows misaligned when only one side has stats):**
  - **Banked total:** it summed `livePtsMap` (max points across all the owner's leagues). The v70 `alertsFor` now
    prefers `W.ls.pp` (this matchup, league scoring).
  - **Wording:** "N of M starters finished · X pts scored".
  - **Rows:** `.slotrow` stretches, cells are flex columns, and `.mxv` sits at `margin-top:auto`.
  - **Bench:** `mxBench` puts the result and stat line in the meta under the name, with "Final", "LIVE", "proj" or "Bye"
    under the score.

- **v83 (owner: bench final-vs-projection; roster tab "bland and useless": more manager tools, less repetition, small
  boxes):**
  - **Bench:** the `mxBench` wrapper adds `vsProj` after "Final".
  - **`vRoster` rebuilt:** at-a-glance boxes, To do with action buttons, one depth chart (replacing Lineup, Full roster,
    Strength vs league and Underlying value), a 4-week bye/injury planner, IR/taxi moves, the keeper plan, and start/sit
    in a collapsed `<details>`.
  - **Holes:** permanent holes (no player at the position) are counted once, not per week.
  - **QA:** demo league, no errors.

- **v84 (owner: after TB@CHI ended, the cell kept switching between "LIVE · Late" and "Final · W 27–24"):**
  - **Cause:** ESPN's default scoreboard can switch to the next day's games after midnight, so some responses lacked
    the game. `GCLK.m` was replaced on every refresh, and the game fell back to the kickoff-time estimate.
  - **Fix:**
    - Request the scoreboard for this week (`GCLK_URL`).
    - Merge each response into what we already have.
    - A final never reverts, and `gameState` trusts a known final regardless of age.
  - **Test:** a mocked final, followed by two responses without the game, stays final.

- **v85 (owner: after v84 the finished game stayed "LIVE · Late"):**
  - **Likely cause:** the v84 week-specific URL failed. The last ESPN reading ("in", taken just before the official
    final) went stale after 15 minutes, and the kickoff estimate took over.
  - **Fix:**
    - Fetch both ESPN's default and week scoreboards, and merge whichever succeed.
    - Treat a game as final if ESPN is answering but no longer lists it and it kicked off 3.4+ h ago.
    - Kickoff-only estimate and `liveSet` windows: 4.5 h.
  - **Test:** mocked combinations (week fails, default fails, both lack the game, both fail, in → final) all resolve to
    final.

- **v86 (owner: sell-high "Build this trade" should be several optimized options incl. 2-for-1 / 1-for-2; "Love for
  Nabers" is unrealistic because Nabers is their top WR):**
  - **`tradeOpts(L, p, "sell"|"buy")`:**
    - **Types:** builds 1-for-1, 1-for-2 and 2-for-1 around the player.
    - **Redraft:** your lineup +0.3 or more, theirs −1 at worst.
    - **Keeper/dynasty:** implied value plus `fitsPlan` for you, `okForThem` for them.
    - **Market:** they lose at most 10%, you overpay at most 25%.
    - **Output:** at least one of each type when available, at most 4 options, at most 2 per team.
  - **`realOK`:** asking for their single most valuable player needs a 5%+ market edge for them and their lineup not
    worse; asking for their top player at a position needs their lineup change ≥ −0.3. Also applied as a `finder`
    filter.
  - **Cards:** the `sigCard` wrapper replaces "Build this trade" with the options list and drops "Best buyer" when
    options exist.

---

## 2026-11-08, night: v69, trade ideas and targets never empty (on main)
- **Owner's report:** a redraft league showed 0 trade ideas and "No pre-breakout trade targets". Their guidance: ideas
  don't need to be win-win, just not egregious for the other team; targets don't need to be breakout candidates.
- **Redraft:** `rdFinder` is a new search for 1-for-1, 2-for-1 and 1-for-2 trades with roster-limit drops.
  - **Your side:** starting lineup gain of 0.5 pts/wk or more.
  - **Their side:** starting lineup loss of 1.5 pts/wk at most.
  - **Market:** they give up 15% or less.
  - **Title odds** (top 24 candidates): yours must not fall, and theirs may fall by 3 points at most.
  - It replaces the v51/v57 redraft pipeline, whose win-probability filter required you to gain far more than them.
- **Keeper/dynasty:** reruns v68 with the other side's test relaxed to `okForThem`. `fitOf` is tagged with the team and
  `fitsPlan` is swapped during the call. Ideas that also fit their plan get +0.15 score.
- **Targets:** `targetsAll`, shown on the Pre-breakout page. Order: breakout candidates, then buy-low, then players who
  add 1+ pts/wk to your lineup with value at most 1.1× your best player (or players 24 and under when rebuilding).
- **QA (demo):** redraft 4 ideas (was 0), dynasty 14-15, 8 targets per scenario, no errors.

---

## 2026-11-08, evening: trade finder fits both teams (v68, on main)
- **Owner's report** (screenshots):
  - Rebuilding at 1-7 in a league with picks, but offered trades like sending Marvin Harrison Jr. (young) plus a 3rd for
    Jaylen Warren, and Makai Lemon for Stefon Diggs plus a 2nd.
  - The cards read "championship odds go – → ▲ –".
  - A calculator trade graded A+ against F.
- **Causes:**
  1. Team status came from playoff odds plus lineup-strength rank, so a 1-7 team with a strong roster on paper could
     land in "balanced" or "contender". There was no way to set it.
  2. The keeper/dynasty finder (v50/v51) required YOU to gain 10% or more in raw value, while the other side only had to
     look fair on the market. Their fit wasn't required, so ideas were lopsided "edges".
  3. In keeper/dynasty, `x.title` held the trade's name as text, but the card read `x.title.pre`/`.post` as
     championship odds, which gave the dashes. In redraft the GM tile showed the odds object as text.
- **Fix (`.build/v68.js`):**
  - `teamStatus` wrapper adds record-based status plus your own override, `planBar()` (Auto / Contend / Rebuild), and
    `fitOf` / `fitsPlan` / `fitWhy`.
  - A new keeper/dynasty finder applies the same enumeration with these rules:
    - **Market:** within −15% / +20%.
    - **Value:** you gain value to your roster (implied value); they lose at most 8% of theirs.
    - **Contender side:** starting lineup improves by 0.3 pts/wk or more.
    - **Rebuilder side:** no players at their position's age cliff minus 1 or older, and at least 1.5 years younger on
      average (a pick counts as 21.5) or adds a pick.
  - **Redraft:** the other team's lineup gain must be greater than 0.
  - **Cards:** say why the trade works "For you" and "For them".
- **QA (demo league, records set by hand):**
  - At 1-7 (auto rebuilding) you get ideas like Amon-Ra St. Brown for Drake Maye plus a 2028 1st with a contender whose
    lineup gains 18.7 pts/wk.
  - At 7-1 (contender) you get Ashton Jeanty for Zay Flowers plus Derrick Henry with a rebuilder.
  - The override works, and no page errors.
- **Tested** (`backtest/e11_trades.py` builds the panel, `e11_an.py` analyses it): 3,413 real in-season (weeks 2-13),
  2-team, offense-only trades in dynasty and keeper leagues, 2022-25, with exact rosters.
  - **Plans:** each side's plan at the time comes from its record and points-for rank. This approximates the app, which
    also uses playoff odds.
  - **Rule replicated:** projected lineup gain from Sleeper's weekly projections, ages from birthdates, market value
    from FantasyPros dynasty ECR history.
  - **Results:**

    | Check | Fits the rule | Doesn't fit |
    |---|---|---|
    | Contender: real rest-of-season starting lineup improved | 80.0% (+4.3 pts/wk) | 43.6% (−0.2) |
    | Rebuilder: dynasty market value 1 year later improved | 72.9% (+27%) | 39.7% (−15%) |
    | Rebuilders who took on ageing veterans (value 1 yr later) | — | 43% benefited, −12% |
    | Both sides benefited, whole trade (fit both + fair market) | 47.9% | 19.1% |
    | Contender ↔ rebuilder trades, both benefited | 63.2% | 30.3% |

  - **By season:** the same in 2022, 2023 and 2024.
  - **Thresholds:** a lineup gain of ≥1–3 pts/wk is only slightly better than ≥0.3. An age margin of 0–3 years changes
    little.
  - **Caveat:**
    - NEXT-season production favours veterans: rebuilders who fit got −84 pts net, against +37 for those who didn't.
      Most of that is picks, whose players this test doesn't count. Player-only trades: +11 vs +57.
    - TWO seasons out, player-only trades that fit: +58 vs +25 (n=103, small).
    - So the rebuild rule is backed mainly by market value (resale), not near-term points.
  - **App text:** the finder page now quotes the 80%/44% and 73%/40% results.

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
