# Hashmark — session handoff (updated 2026-11-12)

What this session did, so the next Claude agent can carry on. Read `CLAUDE.md` first: it has the owner's standing
instructions, code conventions and the status of every engine. This file adds the detail behind the latest changes.
Newest session at the top.

---

## 2026-11-11/12: engine audit and fixes (v109-v123, p111/p112), on main
Owner asked: "Find all issues with existing engines and report here. Give plan for fixing each", then "Do them all",
then (after usage limits) "one agent at a time", then "Run 2-12. Be detailed, check your work, ask questions if needed".
Every fix was tested on seasons the fit never saw; nothing ships unless it beats what was live. Per-fix numbers are in
CLAUDE.md under each engine; agent reports with full tables are in `.build/agents/<name>/REPORT.md` (local only).

### Owner decisions this session
- Confidence labels (HIGH/MEDIUM/LOW): REMOVED. Shown a side-by-side (player card with and without the chip); chose
  "drop labels, keep ranges". Reason: past steadiness, games played and the questionable tag did not predict how far
  off a projection would be (checked by the coordinator too: at the same projection level "steady" players missed as
  much as volatile ones); the only thing that separated labels was projection size, and in points HIGH missed MORE
  (6.3) than LOW (4.2).
- Run ONE fix agent at a time (parallel Opus agents hit the 5-hour usage limit twice).
- App icon: files renamed `icon-180-p2.png` / `icon-192-p2.png` / `icon-512-p2.png` and sw.js cache `hashmark-v13` so
  phones fetch the Pylon mark; a saved home-screen bookmark must be deleted and re-added (iOS copies the icon once).

### Audit list and status (A = wrong now, B = never tested, C = smaller)
| Item | What | Result |
|---|---|---|
| A1 | Waiver line mixed two tests ("+8.8" set-before-games with "73% helped" hindsight) | Fixed in v115 (one test) |
| A2 | Win odds overconfident after refit | p112 WP.b .918 |
| A3 | Labels restated projection size | v113: labels removed (owner), ranges refit |
| A4 | Young-player value cliff at 24 | v118 taper; v107 removed (its this-season cut was an artifact) |
| A5 | NFL picks log stored only the first prediction | v120 early + final |
| B1 | Projections in half-PPR/standard | Already beat Sleeper; report section only |
| B2 | QB projection | No change (nothing beat it on both seasons) |
| B3 | K/DST + hand-set multipliers | p111 injury multipliers; K/DST = Sleeper |
| B4 | Rest-of-season never graded | v114 blend (miss -8%) |
| B5 | Playoff odds never graded | TO DO |
| B6 | Trade grades on old value scale + IDP | TO DO (agent paused) |
| B7 | Waivers on new projections; WR/dynasty hurt rates | v115 one-big-game WR rule |
| B8 | Risk / breakout hand-set | v121 fitted (AUC .72 -> .92) |
| B9 | Streamers D/ST/K factors | Kept (match the fit); text fixed (v122) |
| B10 | Live in-game projections/odds | v123 score term + live spread |
| B11 | Devy score | TO DO |
| C1 | Locker trade/draft ranks are noise | TO DO |
| C2 | Dead FFC ADP feeds | build_values keeps last good board or drops |
| C3 | Matchup team range | v113 from starters (82% inside on 2026) |
| C4 | Report replays projections instead of recording them | TO DO (also leak check) |
| C5 | 1QB young-player + props weights on thin evidence | 1QB tested in e16 (helps); QB props in e24 (keep .1) |

### Things found along the way (check before relying on old numbers)
- e13_young.py is superseded: bt/hv.json.gz has NO Superflex redraft list ("rsf") at November dates, so its
  "this-season share" variants were artifacts. Use e16_taper.py.
- The report card graded a simplified stand-in projection until v108; since then scripts/proj_panel.py replays the
  full formula (and since p111 reads the questionable factor from index.html).
- Replayed TEAM totals run 8-11% below real team scores (median-regression projections + scoring the archive lacks).
  Head-to-head odds are unaffected; v113's team range is asymmetric to absorb it.
- Demo league deals rosters by player value: value changes reshuffle demo teams (the demo matchup went 49% -> 82%
  after v118; not a bug).
- `e8Chip` is a const (v108): reassigning it throws "Assignment to constant variable" and blanks the app. Wrap or
  replace the callers instead.
- data/report.json conflicts on every merge (data.yml rebuilds it twice daily): keep the newer-code build.

### To-do list, fully explained (in order)
5. **Trades + IDP (B6).** Trade grades (`TC` d .75 / g 1.3; win odds .5 + .21 tanh(gap/.25)) were fitted on 7,656
   trades 2021-24 on the value scale of that time; values since changed (v118, v121 risk feeds stability()). Replay
   grade calibration on trades it can be replayed on, hold out 2025, split by young players / 2-for-1 / picks; refit
   only if miscalibrated 3+ pts with n >= 200. IDP retest with 2026 data; keep IDP out of trade ideas unless it caught
   up. Deliver scripts/rpt_trades.py (tested.trade_grades) and v119 if constants change.
6. **Playoff/title odds (B5).** Never graded. Replay 2021-25 from weeks 4, 8, 11 with the app's season simulation
   (draws use WP.k/WP.c, `PO` constants) on archived leagues; calibration "said X% made playoffs / won title". Fix the
   draw spread if off. Report key + report-card row.
7. **Snapshot + leak check (C4).** First check when scripts/fetch_bt.py captures each week's Sleeper projection: if
   after kickoff/inactives, projections in bt/sleeper_proj.json.gz are cleaner than what a manager saw, and every
   projection backtest (e14, e15, e24, e26, e28, e30, e31) is optimistic. Report to the owner immediately if so. Then
   snapshot Hashmark's projection before each kickoff in Actions (scripts/snapshot_proj.py, frozen per game) and grade
   it (scripts/rpt_snapshot.py); coordinator adds the workflow step.
8. **Locker ranks (C1).** Repeatability tau2: trades .06, drafts .035, waivers .21. Show "Top X%" + grade only when
   reliability n/(n+k) >= .5 (k = (1-tau2)/tau2), "small sample" tag between .25 and .5, raw record below; read tau2
   from mgr_ref.json. One line per skill in the breakdown sheet on how repeatable it is.
9. **Devy (B11, engine 7).** Fit the prospect score on 2015-23 draft classes against NFL fantasy hits (top-24 RB/WR,
   top-12 QB/TE within 4 years). College stats need CFBD_API_KEY (Actions only): build what is testable now (draft
   capital, age, athleticism, recruiting) and a ready Actions script for the rest.
10. **Report card rows** for ros, projections_fmt, projections_kd, signals, live, trade grades, playoff odds.
11. **Follow-ups:** verdict card "expected" (`neutral(p)`) worse than season PPG; `repl()` levels after v114;
    kickers with no Sleeper projection show 0; verify v121/v123 in a real league; QB/TE range coverage 77%/75% in 2026;
    half-PPR odds slightly overconfident.
12. **Final pass:** QA, docs, merge, report to the owner.

---

## 2026-11-10/11: the rebrand + rebuild (v90+), in progress on `claude/festive-planck-liolqe`, NOT on main yet
Owner asked to build "everything we've discussed" and report before committing to main. Brand decisions (all from the
brand book canvas, https://claude.ai/artifact/A3fXk4HH4m6o2YLAG74QXz):
- **Name:** Hashmark (trademark search still to do). **Logo:** P2 "Pylons and the 50": four orange pylons (14×27 at
  x 20/66 on a 100 grid) around a chalk 50-yard line (76×11). No diagonal crossbar (Hinge's logo is an H with one).
  Chalk ground: line turns Night; Pylon ground: pylons turn Night. Min 16 px; drop the tile below 29 px.
- **Colour:** Pylon #FF6B1A (yours/live/act; #E85A0C on light), mint #3DDBB4 up/good, pink #FF5470 down/bad,
  Night #0B0C0E, Locker #15171B, Line #24272D/#2A2D33, Muted #9BA1A9, Chalk #F2F1EC. Colour only means something.
- **Type:** Space Grotesk (display, numbers) + Inter (text). **Appearance:** Auto (phone) / Dark / Light.
- **Nav:** Huddle · Team · GM · Scout; top-left profile button = Locker (My stats + Settings + Leagues); search top right.
- **Voice:** default "Just the Numbers"; optional Booth Mode, The Heckler (roasts only you), The Headset, Hype Man,
  Back in My Day. Every voice is straight on injuries, deadlines, money. Personal lines: records, rivalries, traits.
- **Manager rank:** "Top X%" / "Bottom X%" / "Average" + letter grade; hardware-weighted (v88/v89).
- **League bulletin:** "The Wire"; stories may cite any manager's track record league-wide ("news is news").
- **Notifications:** game-changers (win odds swing 15+) and urgent roster; quiet hours 11 pm-8 am; batched.
- **No account wall** for now.
- **Recap awards (team):** The Avalanche, Highway Robbery, Wrong Place Wrong Time, Mercy Rule, Photo Finish,
  Benchwarmer's Revenge, Set It and Forget It, Dumpster Diver, The Fleece, Rock Bottom. **(player):** The Franchise,
  Overachiever, Missing Persons Report, Wasted Talent, Off the Scrap Heap, Special Teams Special, The Vulture, Garbage Time Hero.

Built so far:
- **v90 rebrand:** palette tokens (dark + light) injected last so they win; `.good`/`.bad` = mint/pink (was accent);
  position chips neutral; `HM_MARK()` svg + "hashmark" wordmark replaces `.wm`; dock Huddle/Team/GM/Scout with new
  icons, Stats removed from dock; `#menuBtn` opens the Locker (route `stats`); Locker has Settings (`data-profile`)
  and Leagues (`data-open-leagues`) buttons; `pageTitle`/`LABEL`/`openSheet` say "Locker". Fonts link swapped.
  New `icon.svg`, `icon-180/192/512.png` (rendered from the mark), manifest colours, sw cache `hashmark-v10`.
- **v91 Huddle:** `vOverview` wrapper prepends `vHuddle()`: day-of-week greeting/phase (`hdPhase`), "Your move"
  card from `mergedMoves()[0]`, this week's matchups across leagues (`sums()`), then the old tiles under "Everything".
- **v92 Locker:** `STB.records` (high/low score, biggest win/loss, streaks per league chain, best season, playoff
  record) and `STB.almanac` (champions by year, all-time table, biggest blowouts) + tiles; sheets titled Locker.
- **v93 Sleeper-wide waivers / trades / drafts** (owner: "yes please" to Sleeper-wide skills). New metrics in
  `scripts/build_mgr.py` `trans_metrics` and the app's `mrTrans`, same definitions:
  - `wv` pickup quality: points per started week of your waiver/FA pickups minus the league's average starter slot
    (needs 4+ started weeks). First tried volume (pickup points per game): correlation with all-play win % was 0.02,
    because weak teams start more pickups; quality correlates 0.26, so quality ships.
  - `tr` trades: per game, points received players scored in your lineup minus points the players you gave scored in
    theirs (0.20 vs all-play). Picks are not valued (dynasty trades for picks look like losses in year one).
  - `dr` drafts: per pick, points the pick scored in your lineup that season minus the average of the 12 picks around
    it, keepers excluded (0.07 vs all-play; dynasty rookie drafts are noisy in year one).
  - Shown on the Sleeper-wide card and as "Top X% on Sleeper" on the Locker tiles. NOT in the overall score
    (results already contain them). tau2 assumed (.20/.10/.10) until owner ids let build_mgr measure it.
- **v94 Scouting report:** button under the matchup page -> sheet: lifetime H2H, streak, playoff meetings, last
  meeting; this season's bench points left (league rank), starters who scored 0, waiver claims (rank), trades vs
  league average, close games; last 4 weeks vs average, luck; a "This week" note when an opponent's player is
  listed Out/Doubtful/Questionable. Needs the Locker's history (hxLoad starts on demand).
- **v95 Voices:** settings (profile sheet) radio list; Huddle "Last week" lines: rivalry first win (after 3+ losses),
  personal-record score, two straight close losses, 35+ blowout, 25+ bench points, else the result. Voice adds one
  line; Just the Numbers adds nothing. HX history now auto-loads 2.5 s after opening Huddle in live mode.
- **v96 Awards + share:** last finished week of the viewed league; player awards compare with the player's own season
  average (no archived pregame projections; Vulture / Garbage Time Hero not built: no TD or quarter data).
  Share draws a 1080x1350 PNG (league awards or your week) -> share sheet or download.
- **v97 The Wire:** Team › The Wire (+ top story on Huddle): upsets (pregame chance < 30%), 40+ blowouts, photo
  finishes (< 3), trades and big FAAB bids from the last 2 weeks, unbeaten / winless / 3+ streaks with track-record
  notes (league-mate skill ranks), playoff race (clinched > 99.5%, bubble 25-75%, out < 0.5%).
- **v98 Notifications:** Game-changers (15+ point swing in win chance, batched 10 min unless 25+) and Urgent roster;
  quiet hours (default 11 pm-8 am; urgent still on Thu/Sun/Mon). Fires while the app is open/backgrounded
  (service worker `showNotification`). Waiver results, trades and The Wire daily need a push server: not built.
- **leagues.yml fix:** run 6 crawled 2.5 h (archive grew to 14,770 team-seasons; tau2 measured for the first time:
  S .27, ap .27, lineups .17, scoring .29, consistency .24, hardware .16) but its push hit a merge conflict on
  data/mgr_ref.json (my v89 commit changed it meanwhile) and the crawl was lost while the job still showed success.
  The workflow now commits the archive first, rebases onto main, rebuilds calib + mgr_ref on top, and exits 1 if the
  push fails. Never edit data/mgr_ref.json on main while a league-archive run is in progress.
- **v99 motion + polish** (owner asked for high-end UX; skip sounds and haptics). "Motion once": animate the first
  time, never on every refresh; everything off under Reduce Motion. Bugs found in testing and fixed: numbers keyed by
  position ticked from another card's value ("Top 137%"), now keyed by their label; counting "Top 45%" up from 0
  passed through "Top 8%", so ranks never count; background data loads overwrote the cached Huddle with demo numbers
  during restore, so `render` now waits while `S._snapOn`. Bars needed a forced reflow to animate from 0.
  Not built (by choice): sounds; haptics (iPhone web apps can't vibrate anyway).
- **v100 audit (owner: "double check for consistency, redundancy, confusing navigation, inaccurate data, incorrect
  rankings, formatting; fix it first")**. Found and fixed:
  - Rankings contradicting each other: Locker tiles showed league-mate letter grades (Trades A+, Waivers A) next to
    "Bottom 48% / 23% on Sleeper". On All leagues the letter now comes from the Sleeper-wide percentile; the trade
    tile's own grade average is labelled "Hashmark grade"; Luck and Activity lost their grades (not skills).
  - Redundancy: titles/finals/playoff record appeared three times in the Locker (hero, Sleeper-wide card, tile); the
    Sleeper-wide copy is now one line. Huddle tiles that duplicated tabs or cards (Matchups, Updates, Gameday) removed;
    awards on Huddle show 3 with an "All awards" sheet.
  - Navigation: League page had two stacked tab rows -> one; "Updates" named two different tabs -> Huddle "News" and
    Team "Player news"; search still listed "My stats"/"Overview"/"Home" -> Locker/Huddle; The Wire, Records,
    Almanac added to search.
  - Formatting: "Demo league i" (info button text copied into the h1) fixed in `pageChrome`; Huddle's day line sat
    under the greeting; "▲ YOU" tag (the up-arrow means better than expected) -> plain orange "YOU"; position chips
    were still coloured on some lists (specificity) -> neutral; My teams card showed 0.0-0.0 before kickoff -> the
    projection with "proj", win chance below.
  - Data spot checks: Huddle and Matchup win chance agree; last-week line, Week N awards and The Wire agree.
- **v108 Engine 1 refit + Engine 8 screens (owner "Go").** Found that the report card graded a simplified stand-in
  (all inputs = Sleeper proj), not the app's projection; the real formula with the old weights was ~even with Sleeper
  (2026 5.192 vs 5.185). Refit (see CLAUDE.md engine 1): linear median regression matched a boosted-tree ceiling, so the
  simple, explainable formula stays. Report card now replays the full projection (`scripts/proj_panel.py`). Not replayed:
  wind/rain and practice tweaks (no archive). Props archive only covers 2026 (8 weeks): re-check PJ_PROPS_POS as it grows.
  Win odds were fitted with the old projections; graded after the refit: Brier .2114 (was .212), calibration still ~1 pt.
  Report card shows verdict pills (Beats Sleeper / Calibrated / Uses the line / Honest / Tested), not letter grades:
  only rows with a real benchmark get a verdict. Waiver/trade numbers are season-level backtests, labelled "Tested".
- **v106 + young-player value retest (owner: why is Germie Bernard only 955?).** Every dynasty source has him #111-129
  overall (~1,250 on the SF curve). The blend: market 60% (~1,260), this-season 20% (~1,260 avg, but DD rd #217 / FC rd
  #133 / FP ROS #77), production model 20% (near 0: ~7-8 PPR ppg vs WR replacement 11, 2-season horizon). Display fix
  shipped (v106, labelled groups + adjustment footer). Retest `backtest/e13_young.py` (FP dynasty SF ECR history in
  bt/hv.json.gz at early-Nov dates 2021-24, 1,196 player-dates ranked <=300; outcomes = market 1 yr later and real PAR
  over the next 2 seasons, both on the app curve; ties share average rank - without that the results moved between runs):
  | variant | young<=23.5 mkt+1y bias/MAE | young prod MAE | all mkt MAE | all prod MAE |
  | app (.6/.2/.2) | -479 / 871 | 1142 | 695 | 1061 |
  | market only | +124 / 808 | 1382 | 733 | 1204 |
  | young: 4 yrs ahead, disc .8 | -400 / 829 | 1153 | 685 | 1063 |
  | young: this-season .1 | -309 / 803 | 1173 | 681 | 1068 |
  | young: this-season .1 + 4 yrs disc .8 | -221 / 762 | 1193 | 670 | 1072 |
  | young: this-season 0 + 4 yrs disc .8 | +2 / 735 | 1277 | 665 | 1090 |
  Reading: the model does NOT undervalue young players vs real production (it improves production accuracy a lot vs
  market only). Young players are valued ~450 below where the market puts them a year later (older: -26); the
  this-season share causes more of that than the model. Ordering among young players (rho .844) doesn't change with
  any variant: it's a level shift. For Bernard-like players (young WR, market #80-200, n=46) the current blend is
  already the most accurate (690 / 1106 vs market 780 / 1337). The 2-season production outcome can't see years 3+,
  which is exactly where young players' value sits, so it understates the case for youth.
  Recommendation to owner: young (<=23.5) players get a 4-season model horizon at .8 discount and a 10% this-season
  share (rest to market). Owner said go -> shipped as v107 (age <= 23 since Sleeper ages are whole years; 1QB gets the
  same horizon and its 25% this-season share halved to 12.5%).
- **v105 page resets while scrolling (owner bug report).** Live leagues only: `pollQuiet` (45 s) -> `refreshLive` ->
  `render()` redrew any route, incl. GM › Waivers/Players; "See all" is DOM-only (`.lmore.clip` + `[data-more]`), so the
  list collapsed, the page shrank and the scroll jumped. Demo mode never polls, which is why QA missed it. Reproduced on
  the old build (Playwright: expand, scroll 2600, render -> collapsed, height 3901->3065). Fix in `.build/v105.js`.
  Engine 8 screens and the Engine 1 refit were paused for this and still await the owner's go.
- **2026-11-11: owner asked for items 1-4 of the optimization list.**
  1. Launch data (v103): measured ~1.1 MB compressed / 4.7 MB parsed per launch. Causes: every data file fetched with
     no-store + a time-stamped URL (re-download every 2 min-1 h) and Huddle loading the college file for one tile.
     Fix: service-worker conditional requests (verified with an ETag server: second launch = all 304s), fixed URLs,
     college file only in Scout. Launch 1 drops the 1.5 MB college file; later launches download only changed files.
  2. History (v103): finished weeks of the current season cached on the phone (IndexedDB); only the current week and
     (every 6 h) last week are fetched.
  3. Cleanup: my "30-40% smaller" estimate was wrong. Measured: minifying without renaming saves 12% (code is already
     compact); strictly superseded code ~9 KB; captured-but-unused old versions a few KB more. Removed 21 items
     (~14 KB) with an iterative acorn analysis (a definition is dead when the next definition of the same name doesn't
     reference it and nothing references the name in between; unused `const _x=fn` captures). Runtime coverage over a
     full demo tour leaves ~214 KB never run, but much of it is live-mode only (Sleeper connect, live league load),
     so it is NOT safe to delete by coverage. The real size win is code splitting (load Devy Lab, War Room, guillotine,
     trade calculator on demand): a planned project, not done.
  4. Engine 6 (v104): see CLAUDE.md engine 6. Team code map nflverse -> Sleeper (LA->LAR, OAK->LV, SD->LAC).
- **v102 The Wire in depth** (owner: "excerpts are small and useless; be informative"). Every story now has a lead,
  a fact panel and detail bullets; new story types Week in review, Injury report, Who's hot. Guard rails: trade value
  and projection comparisons only when every player has a number; with picks in the deal it says so instead of
  declaring a winner (a pick valued 0 had produced "wins the deal by 100%"). Grammar for team named "You".
- **v101 false release (owner screenshot):** Huddle said "Jordan Love FA was released" from Fox's headline "NFL Week 9
  All-Stars: Jordan Love Makes The Cut". Old `relStatus` matched release/cut/waive within 30 characters after the name.
  It fed three places: the FA team label (`tmLabel`), free-agent lists (`freeAgents` filter) and the "Released" move.
  New `relMatch` needs transaction phrasing; tested on 8 release and 7 non-release headlines (all correct); plus a
  Sleeper cross-check (still on a team after 36 h -> not released). No player in the current feed is flagged.
- **Merge to main (2026-11-11):** run 7 saved its crawl: 14,766 team-seasons, 1,311 leagues (2019-25), 2,256
  managers seen in 2+ seasons, so tau2 is now MEASURED: overall .29, all-play .27, lineups .17, scoring .29,
  consistency .24, hardware .20, waivers .22, trades .06, drafts .03. Trades and drafts barely persist season to
  season, so Sleeper-wide trade/draft ranks stay near average until a manager has many seasons (correct, not a bug).
  build_mgr skips trans metrics for seasons without stat lines (2019-20), which had scored every pickup/trade/pick 0.
- **QA:** every route (24) in dark + light at 360 px: no console errors, no horizontal overflow (Playwright, demo).
- **Demo caveat:** the demo's current league and its history use different ids/teams, so Scouting/Awards/Wire fall
  back to the demo history's latest season; real Sleeper leagues match by league id.
- Block sources in `.build/v90.js` ...; spliced with a helper that delimits each block with `/* /vNN */`.

## 2026-11-10: v88, Sleeper-wide manager percentiles
- **Owner asked:** the overall profile should compare a manager's whole career with every Sleeper manager studied, shown
  as "Top X%", not just against league mates; league profiles stay league-specific. Weight championships so rebuilding
  seasons are balanced; new accounts start near average; drop samples too small to use; outliers must not distort it.
- **Reference (`scripts/build_mgr.py` -> `data/mgr_ref.json`, 3.5 KB):** from `bt/leagues.json.gz` (+ `bt/rosters.json.gz`
  and `bt/sleeper_stats.json.gz` for lineup efficiency). 9,357 team-seasons in 828 leagues (2021-25, finished seasons).
  - Left out: 195 unfinished seasons, 13 leagues under 8 teams, 11 guillotine, 6 unusual scoring (avg team score outside
    40-260), 3 with under 10 scored weeks, 4 dead leagues (25%+ abandoned teams), 13 abandoned teams.
  - Per format bucket (league type x size 10/12/14; under 150 team-seasons falls back to type, then all): winsorized
    mean/sd and the 2.5/97.5% clip bounds for ap, sc, cons, lu, out, luck.
  - Lineup efficiency rebuilt from exact rosters with league scoring on archived stat lines (K/DST Sleeper standard);
    a week counts only when rebuilt starter points match Sleeper's score within 8% (3,716 team-seasons qualify).
    Taxi leagues: players a team never started all season are left out, like the app's v62 rule.
- **Score:** season = (.45 z_allplay + .40 z_finish + .15 z_lineups) / sd of that composite (per set of available parts).
  Finish value: title 1, runner-up .45, 3rd .25, 4th .2, other playoff team .1, minus the league average.
  Career = sum(w·S) / (sum(w) + k), k = (1 - tau2) / tau2; Top % from Phi(career / sqrt(tau2)).
  Weights: finished season 1, live season games/13, title season x1.25, below-average keeper/dynasty season followed
  by a title in that league within 2 seasons x0.5. Under 2 effective seasons = provisional ("Top ~10%").
- **Limitation (being fixed):** the archive had no owner ids, so career persistence (tau2) is assumed (.25 composite).
  `scripts/fetch_leagues.py` now stores hashed owner ids and backfills old leagues; once 300+ owners appear in 2+
  seasons, `build_mgr.py` measures tau2 itself (`tau2_src: "measured"`). This needs the leagues workflow to run on main.
- **To check later:** the app's lineup efficiency (Sleeper players_points) vs the archive's rebuilt version (stat lines):
  compare means once owner ids let us match the owner's own leagues. Waivers/trades/drafting are not Sleeper-wide yet
  (their app definitions need the value model); they stay ranked against league mates.

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

- **v87 (owner: add larger deals, 2-for-2 and 3-for-2):**
  - **`dealEval`:** a shared evaluator for multi-player deals, using the same rules as smaller ones plus a higher bar.
  - **`bigDeals(L)`:** finds 2-for-2, 3-for-2 and 2-for-3 deals for the finder, with at most 2 per team. They're merged
    into `finder()`, redraft title odds are computed for them, and new FDT tabs are added.
  - **`tradeOpts` wrapper:** adds the best 2-for-2 / 3-for-2 deals around the card's player.
  - **Speed (demo):** about 80 ms per run, with lineup sums cached per deal.

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
