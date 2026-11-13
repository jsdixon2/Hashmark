# Hashmark — working notes for Claude

Sleeper-connected fantasy football PWA. The whole app is one file, `index.html`, served by GitHub Pages from `main`.
Data files in `data/` and backtest archives in `bt/` are rebuilt by GitHub Actions (`.github/workflows/`).

## How the owner works
- Rebuild the analytics engines one at a time to *dominate* (not just beat) public benchmarks; measure on real outcomes,
  give a breakdown of weaknesses and fixes, then **stop and wait for "go"** before building each engine.
- Pull as much free, legal data as helps accuracy. Never scrape sportsbooks or KeepTradeCut directly.
- Never ask for API keys in chat. Keys live in repo secrets: CFBD_API_KEY, ROSTERAUDIT_KEY, ODDS_API_KEY,
  APISPORTS_KEY, HIGHLIGHTLY_KEY, MSF_KEY, ODDSPAPI_KEY.
- Repo is public: archives store numbers only (hashed league ids; no usernames, team or league names).
- No real player photos or NFL logos.
- Design: black/greys, rounded, Apple-like mobile UI; no repetition; clear, concise, data-driven.

## Code conventions
- Changes are layered blocks inserted before `/* ===== boot ===== */`, newest last (v50 … v64). Sources kept in `.build/vNN.js`.
- Wrapper pattern: `fn=(function(prev){return function(...a){... prev(...a) ...}})(fn)`.
- In-place edits via small Python scripts with exact-match counts asserted.
- Syntax check: extract all inline `<script>` blocks into one file and run `node --check`.
- QA: `python3 -m http.server 8765` in the repo, then Playwright (Chromium is preinstalled in the cloud sessions);
  the demo league ("Open demo league") works offline.
- Pushing: `git pull --rebase && git push` (workflows commit data to `main` often). data/report.json conflicts on merge
  are normal (data.yml rebuilds it): keep the newer-code version or rebuild it with `python3 scripts/build_report.py`.
- Fix agents (2026-11-11/12): brief in `.build/AGENT_BRIEF.md`; tools `.build/tools/mkapp.sh NAME PORT` (private app copy)
  and `.build/tools/asplice.py NAME vNNN`. Agents never edit index.html/CLAUDE.md/HANDOFF/data; the coordinator splices.
  Owner: run ONE agent at a time (several Opus agents at once hit the 5-hour usage limit twice). Agent reports are kept
  in `.build/agents/<name>/REPORT.md` (git-ignored, local to the session).

## Engine status (see the "Hashmark analytics engine review" doc for the original audit)
1. Projections — done. v108 refit (`backtest/e14_data.py` -> `e14_fit.py`, `e14_props.py`): median regression per position
   on the app's own inputs (Sleeper proj, PPG, last-3, xFP, last-3 xFP, DvP rank, implied total, has-PPG/has-xFP), fitted
   2021-24: 2025 MAE 4.961 vs Sleeper 5.199 (16/18 weeks), 2026 5.071 vs 5.185 (7/9); a gradient-boosted ceiling did no
   better (4.977 / 5.075). Shipped weights refit on 2021-25 (2026: 5.059); QB keeps the old PJC (refit worse for QBs both
   years). Props share by position `PJ_PROPS_POS` QB .1 / RB-WR-TE .3 (2026, 1,214 player-weeks: .2 -> 5.322, .3 -> 5.31).
   Full replay incl. props, 2026: Hashmark 5.037 vs Sleeper 5.186, 8 of 9 weeks.
   2026-11-12 audit fixes (each tested on held-out seasons; see HANDOFF.md "2026-11-11/12 engine audit"):
   - e15 (no change): PPR weights already beat Sleeper in half-PPR (2025 4.60 vs 4.90, 2026 4.69 vs 4.88) and standard
     (4.40 vs 4.73; 4.45 vs 4.67); format-specific weights gained <0.3%, not shipped. proj_panel `build(seasons,
     scoring="ppr"|"half"|"std", C=None, feats=False)`; report key `projections_fmt` (scripts/rpt_formats.py).
   - e24 (no change): nothing beat the QB formula on both 2025 and 2026; on clean 2026 it only ties Sleeper (5.94 vs
     6.00, CI includes 0). QB props: keep PJ_PROPS_POS.QB .1 and the flat 1.6 pass TDs (pass-TD line tested worse).
   - p111 (e28): hand-set multipliers measured. Questionable x.88 -> x.97 (Sleeper itself discounts Q tags since 2025, so
     .88 double counted); doubtful x.35 -> x.02 (1 of 278 doubtful players played); limited-practice x.97 removed;
     did-not-practice x.9 kept (.888 held out); wind x.94 and rain x.97 kept (fitted .928; rain only from gamebook
     text). Patched in BOTH hmProj definitions. proj_panel reads the questionable factor from index.html.
   - e28 K and D/ST (no change): the app shows Sleeper's number (kdPts / hmProj wrapper); no correction beat Sleeper on
     both seasons. Report key `projections_kd` (scripts/rpt_kd.py). 71 kicker-weeks had no Sleeper projection (shows 0).
   - v114 (e26) rest-of-season points/wk: `ROS114` = 25% shipped rosPPG + 75% per-position fitted model (Sleeper proj,
     PPG, last 3, xFP, last-3 xFP, last season, games, injury, depth chart, missed games, age, week); held out 2025
     3.82 -> 3.50 pts per team game (best simple method 4.51), 2026 4.24 -> 3.94. wvRate kept (wins its 4-week horizon).
     Report key `ros` (scripts/rpt_ros.py). Shipped estimate ran 1-4 pts/wk high for starters before.
2. Win odds / playoff odds — done (fitted on 44k Sleeper matchups).
   p112 (e29, 99,975 league matchups 2021-26, fit 2021-24): `const WP={k:.16,c:5,b:.918}` (b was 1.01: favourites were
   overconfident after the projection refit). Held out: 2025 Brier .2138 -> .2135, 2026 .2105 -> .2103; top decile 2026
   said .937 won .927 (was said .939 won .916). k/c kept so season/playoff simulations (use k,c only) are unchanged.
   build_report grades every league in its own scoring (half/std panels + `sc_adj` from Sleeper's projected stat line).
   v123 (e20, play-by-play 2023-25, fit 2023-24, test 2025): live player projection = shipped rule x (1 + g x team
   margin/10), g QB -.14 RB -.06 WR/TE -.2, held .4-1.6 (MAE 3.62 -> 3.56); live spread `LV123` {p 1.2, s .909} (s was
   1.1; changed with p112 so live odds stay as tested). Only when ESPN supplies live scores. Report key `live`.
   v112/v113 matchup "likely X-Y": v113 builds each team's 80% range from its starters (E30.player per position, measured
   correlations QB-WR/TE .23, QB-RB .07, opponents .04, K/DST fitted sd, asymmetric z -1.086/+1.735): 2026 lineups 82.1%
   inside (was 76.1%, 21.8% above). Note: replayed team totals run 8-11% below real scores (median projections +
   scoring the archive lacks); head-to-head odds are unaffected, the range's skew absorbs it.
   v116 (e32, 617 finished leagues 2022-25, fit 2022-23, held out 2024-25): playoff/title odds. PO.u/PO.sh refit kept
   .04/.5; three live bugs fixed (`po116Weeks`, `po116Med`): this week's game was never simulated while the record lagged,
   the last regular week played 6 random weeks (L.remWeeks||6), median wins were not simulated. Playoff Brier .1170 ->
   .1165 (standings rank .129), last week .057 -> .046; said 60-75% made it 68%. v127 uses the week's real result once
   every starter's game is final. Report key `playoff_odds` (scripts/rpt_playoffs.py reads backtest/e32_fix.json,
   force-added to git). v127 half-PPR pregame b .849 (`HB127`; build_report matches: rec == .5).
3. Value engine — done (fitted on 2020-24 dynasty markets vs production; measured age curves; pick values).
   v106: Value card breakdown (`vb106`): Dynasty market 60% / This season 20% / Hashmark model 20% (SF; 1QB .6/.25/.15),
   keeper = keeper value 50% + this season 50%, redraft = experts 62% + model 38%; footer names the adjustment (league
   size, TE premium, catch scoring, injury, smoothing; `vb106Why`). Young-player retest `backtest/e13_young.py`
   (owner: Germie Bernard 955 vs market ~1,250): see HANDOFF.
   v107 (removed) -> v118 (e16): young-player adjustment fades with age: production model looks 4 seasons ahead at .8
   discount with weight 1 at <= 23, 2/3 at 24, 1/3 at 25, 0 from 26 (`YW118`, hmModelVal wrapper); NO this-season cut.
   e13's Superflex this-season input was empty (bt/hv.json.gz "rsf" has no November lists), so v107's cut was an
   artifact. Held out 2023-24: SF all 722/1,178 -> 722/1,174 (miss vs next-year market / 2-season production), <= 23
   697/1,162 -> 694/1,136; 1QB helps too (713/1,169 -> 711/1,165). Largest one-year value step 9% -> 3%.
   Demo league deals rosters by value, so value changes reshuffle demo teams (matchup odds there move; not a bug).
   C2: FFC ADP feeds (adp_ppr/dyn/rook) are near-empty in-season; build_values keeps the last good board (same season,
   <= 150 days, `carried:true`) or drops the source; nothing in the app reads those keys.
   v121 (e18, nflverse 2016-26, fit 2017-21, held out 2022+): breakout odds = logistic model (next season for
   dynasty/keeper, rest of season for redraft), capped 60%; AUC .72 -> .92, 30%+ calls came true 5.5% -> 30% (old odds
   said 18% on average for a 2.6% event). `p.broke` = top-12 QB/TE or top-24 RB/WR this or last season. Risk = within-
   position percentile of predicted bust share (rank corr .26 -> .36; top tier busts 60%, safest 30%). Players without
   adv data and IDP keep old numbers. Trend lists show 10%+ breakout odds only. Report key `signals`.
4. Trades — done. v119 (e25, owner approved after before/after examples): TC d .75 -> .9, g 1.3 -> 1.0 (smaller
   consolidation premium). 18,221 real dynasty/keeper trades; scored on points above replacement only in weeks the
   players STARTED for the team holding them: shipped constants worst of 20 on 2021-24; 2025 Brier .2258 -> .2242,
   2-for-1 said 70 won 67% -> 74%. Young-player value bump made grades worse (no age term). IDP: 30 trades, stays out.
   Report key tested.trade_grades (scripts/rpt_trades.py). Original grades from 7,656 real trades; redraft graded on championship odds; keeper leagues blend this season
   with next season's keeper value (weight fitted on 1,657 keeper trades: ~25% at 1 keeper per 10 roster spots,
   ~35% at 2, levelling near 38%; contender ×0.75, rebuilder ×1.3); keeper pick costs; IDP kept out of trade ideas.
5. Waivers / FAAB / buy-sell / usage risers — done (v64). Adds ranked by 4-week lineup lift with best drop; fitted
   rate `wvRate` (coefficients `WVC`); FAAB bid tables `FAABQ` + league calibration `faabLeague`; trending top 100;
   buy/sell from fitted rate vs season pace; Hot streaks tab; weekly track record (localStorage `hm_tags_<league>`).
   v65 (from the redraft retest, `backtest/e9_exact2.py` + `e9_fix.py`): each add/drop pair scored g' = lift − 0.25 ×
   drop's own 4-week points (`WV_DROPW`); shown from g' ≥ 4, ≥ 6 in dynasty (`wvBar()`); "close call" flag when the drop
   projects ≥ 45% of the add. Redraft shown moves +10.8 real pts / 73% helped / 20% hurt (was +8.7 / 68% / 25%);
   managers' claims +7.6 / 66% / 17%. No position correction: position effects flip between seasons. See HANDOFF.md.
   v67: free agents' outlook trimmed 1.5 pts/game when picking (`WV_FAH`, winner's-curse guard). With lineups set before
   games (`r3s`), redraft shown moves +8.8 / 25% hurt (v65 +7.2 / 32%); keeper +7.3 / 25%; dynasty +4.3 / 34%.
   v115 (e31, 516 leagues 2024-25, lineups set by today's projection, real points over the next 3 weeks): a WR add whose
   best game is >= 45% of his season points (`WV_SPIKE`, `wvSpike`) no longer counts as a move ("One big game" tier).
   Chosen on 2024, checked 2025: all formats +6.75 -> +7.51 pts, hurt 24.0% -> 22.3%; redraft +8.38 helped 62% hurt 23%;
   keeper +7.18 59/23; dynasty +6.08 50/21; WR dynasty -1.1 -> +8.4. Managers' own claims (honest measure) redraft +3.79,
   keeper +3.08, dynasty +1.16. The old "73% helped" and "managers +7.6" were hindsight-lineup numbers: both waiver lines
   now read report.json `tested.waivers` (scripts/rpt_waivers.py, by_fmt). No 2026 check (roster archive lacks 2026).
4a. Trade finder (v68): ideas must fit BOTH teams' plans. Plan from record + playoff odds (dynasty/keeper: rebuilding if
   po<=.15 or win%<=.3 after 4 games; contender if po>=.5 with win%>=.45, or win%>=.65), user can set Contend/Rebuild
   (localStorage `hm_plan_<league>`). Contender side: starting lineup +0.3 pts/wk or more; rebuilder side: no players at
   age cliff-1+, and 1.5+ years younger or adds a pick. Market within -15%/+20%; you gain value to your roster, they lose
   at most 8% of theirs. Redraft: their lineup must improve too. Card explains the fit for each side.
   Tested (`backtest/e11_trades.py` + `e11_an.py`, 3,413 real in-season dynasty/keeper trades 2022-25): contender sides
   that fit raised their real lineup 80% vs 44%; rebuilders gained dynasty market value 1 yr later 73% vs 40%; both sides
   benefited 48% (fit both + fair) vs 19%. Caveat: rebuilders' NEXT-season production favours veterans; two seasons out,
   player-only fits +58 pts vs +25 (n=103) - the rebuild rule is backed by market value more than near-term production.
4b. v69: owner asked for ideas that are "not egregious" for the other side rather than strictly win-win, and targets
   beyond breakouts. Redraft has its own search (`rdFinder`): your lineup +0.5 pts/wk, title odds not down; theirs at
   most -1.5 pts/wk and -3 title pts; market: they give up 15% or less. Keeper/dynasty: your side must fit your plan;
   theirs only `okForThem` (contender lineup >= -1, rebuilder no ageing vet unless with a pick); full fits rank first.
   Trade targets (`targetsAll`): breakout -> buy-low -> lineup upgrades at fair price (young players when rebuilding).
6a. Live games (v66): in-game projection = points so far + pregame projection × share of game left (ESPN scoreboard
   clock, fallback kickoff time); win odds narrow with the share of lineup points left (`gameState`, `lineupLeft`).
6b. v70: no start/sit advice for locked players. `locked(p)` = his game has kicked off (`gameState` from v66, else schedule
   final flag / 4-hour kickoff window). `alertsFor` (feeds matchup "Needs attention", home moves, start/sit) skips locked
   starters (finished ones show "has played · X points banked") and never suggests a locked bench player.
   v71: 2+ finished starters fold into one line ("N starters have played · X points banked").
   v72: `pc()` shows "<1%"/">99%" (never 0/100 unless certain); live win odds held to 0.1-99.9% until all games final;
   win-chance texts use pc (bar widths still PCT); edge-by-position says "live projection" during games; LIVE badge
   number only for players rostered in the league being viewed.
   v73: methodology paragraphs move behind info buttons (`CONDENSE` rules matched by opening words, applied in `decorate`;
   full text goes to `DEFS["cx_*"]`, button in the section's tag pill or heading, never inside team-name headings);
   trade cards are one compact line per side. Add a rule to CONDENSE when a new long explanation is added. Legal stays.
   v74: matchup lineup cells (`mxCell`/`mxBench`): bold = real league points once a game starts (from matchup
   players_points), grey "proj" before kickoff; status Final / Q4 13:06 · proj / opponent+time; Sleeper weekly stat line
   (`loadWkStats`, `statLine`, refreshed with live scores). Needs attention: opponents' problems without advice, "played"
   line as footer. Page chrome (`pageChrome`, final render wrapper): no breadcrumb eyebrow, sub-title replaces title.
   One info button per row. Waiver rows: tier pill under the number. Trade cards show value in points, not %.
   Wider tap areas for inline links (::after); War Room buttons 36px.
   v75: player tiles (`mono`) show POS / jersey number / TEAM stacked (small) or big number with "POS · TEAM" (large);
   "–" when Sleeper has no number. No initials.
   v76: small box = number + team only; list rows put the position tag before the name and drop the team text (inline
   tag keeps only age in dynasty/keeper); matchup live cells "21.0  23.7 proj" with a red dot + clock in the status line;
   K and D/ST get their own named rows (`kdMatchRows`/`kdCell`, names from `kdMeta`).
   v77: risk "missed games" = weeks listed Out/Doubtful on this season's injury reports (`values.json` injh[2]), not team
   games minus games played (that branded backups / new signings injury-prone). Fallback without data: gaps between a
   regular's appearances only. Value breakdown hides the win-now/future split when both are 0.
   v78: live lineup cells (players and K/DST) get a tinted card with a red edge, pulsing dot and red "LIVE" label.
   v79: overtime-safe game state. Final only when ESPN `type.completed` or name contains FINAL (end of regulation/period
   and OT stay live, labelled); time-only estimate keeps a game live up to 5.5 h (was 4.2); liveSet windows 5.5 h.
   v80: final matchup cells show ▲/▼ difference vs Hashmark's pregame projection (`preProjOf` = hmProj, else Sleeper proj;
   K/DST via kdPts with no live data), green/red, grey within 0.5.
   v81: "Final · W 27–24 vs TB" (`nflResult`): scores/opponent/home from the ESPN scoreboard (GCLK.m pf/pa/opp/home),
   fallback sched.json as/hs.
   v82: lineup rows align (names on one line, scores pinned to a shared bottom line); "N of M starters finished · X pts
   scored" uses this matchup's own players_points (was max across leagues -> inflated); bench rows: short right column,
   result + stats under the name.
   v83: bench finals get the vs-projection marker. Roster tab (`vRoster` override; other teams still use `vTeam`):
   3x2 at-a-glance boxes (this week + win%, power, playoffs, roster spots/IR/taxi, bye/injury holes next 4 wks, risk);
   To do (`rosTodo`: lineup alerts, best waiver add, cut candidates <4 pts/4 wks not value-protected, sell-high, week
   holes); Depth chart per position (`rosRow`: slot chip/BN/IR/TX, age, ROS/wk, value or rank, injury + SELL tags,
   this-week proj) incl. K/DST; Next 4 weeks planner (`rosHoles`, week-specific holes beyond permanent ones); roster
   moves + keeper plan; start/sit breakdown collapsed.
   v84: no Final/Live flip-flop. ESPN scoreboard requested for this week (`GCLK_URL`: seasontype=2&week=&dates=); each
   response merges into GCLK.m (teams missing from a response keep their last state); a "post" never reverts, and
   gameState returns a known final regardless of age.
   v85: game clock fetches ESPN's default AND week-specific scoreboards (`gcParse`), merges every success (finals never
   revert); if ESPN answered in the last 5 min without the game and kickoff was 3.4+ h ago, it's final. Kickoff-only
   estimate and liveSet windows: 4.5 h.
   v86: Sell-high / Buy-low cards list up to 4 built trade options (`tradeOpts`: 1-for-1, 2-for-1, 1-for-2, at least one
   of each type when available; same scoring as the finder; max 2 per team) with Build buttons. Realism (`realOK`, also
   filters finder): asking for a team's most valuable player needs the market to favour them 5%+ and their lineup not
   to drop; asking for their top player at a position needs their lineup not to drop more than 0.3 pts/wk.
   v87: bigger deals (`bigDeals` in the finder; `tradeOpts` wrapper on cards): 2-for-2, 3-for-2, 2-for-3 from each side's
   top 7, shared `dealEval`, higher bar (redraft +1.5 pts/wk; keeper/dynasty +5% value, and non-rebuilders' lineup
   ≥ -2 pts/wk); redraft big deals must not lower your title odds. New finder filter tabs.
   v88: Sleeper-wide manager percentiles on My stats ("All leagues"): "Top X%" / "Bottom X%" / "Average" (`topTxt`),
   `mrPanel` + `mrOpen` breakdown sheet, `mrSeasons`/`mrCareer`. Reference `data/mgr_ref.json` from
   `scripts/build_mgr.py` (run by leagues.yml after the crawl): 9,357 team-seasons / 828 leagues after outlier filters.
   Season score = all-play z .45 + finish value z .40 + lineup efficiency z .15, per format bucket (type x size, min 150).
   Career: title seasons 1.25x, below-average keeper/dynasty season before a title within 2 seasons 0.5x, shrunk toward
   average by k=(1-tau2)/tau2 (tau2 assumed .25 until the archive has 300+ repeat owners, then measured).
   Crawler now stores hashed owner ids (`uhash`, "hmu:" salt) + hashed previous league id; backfills old leagues;
   seasons 2019+; leagues.yml MAX 1500 / GROW 250, push trigger limited to main. League views keep league-mate ranks.
   v89 (owner: weigh titles, playoff records and points titles enough that off years don't make everyone average):
   "out" is now hardware = finish value + .1 per playoff win + .3 points title (ref v2: PT/PW); weights ap .40 /
   hardware .45 / lineups .15; title seasons 1.5x, points-title seasons 1.15x; once a career has a title or points title,
   below-average seasons count .75x; rebuild-before-title .5x. Panel shows letter grade (SKG), titles, finals, points
   titles, playoff record.
   v90-v98 rebrand + rebuild (see HANDOFF.md for the brand decisions): v90 Pylon palette/fonts/P2 mark/icons, dock
   Huddle·Team·GM·Scout, `#menuBtn` -> Locker (route `stats`); v91 Huddle (`vHuddle`, `hdPhase`, `hdMove`, `hdMatchups`);
   v92 Locker Records/Almanac (`STB.records`, `STB.almanac`); v93 Sleeper-wide waivers/trades/drafts (`mrTrans`, ref
   metrics wv/tr/dr from `trans_metrics` in build_mgr.py; waiver = pickup QUALITY, volume tested ~0 vs winning);
   v94 Scouting report (`scButton`/`scOpen`, button under the matchup page); v95 Voices (`VOICES`, `VOICE_FX`, LS
   `hm_voice`, default numbers) + Huddle "Last week" personal lines (`pvLines`); v96 weekly awards + share images
   (`awData`, `awImage`); v97 The Wire (`wireStories`, route `wire` in the Team hub, top story on Huddle); v98
   notifications (`nfCheck`, LS `hm_notif`, quiet hours; local/background only, no push server yet).
   v99 motion + polish (owner: skip sounds and haptics): directional page transitions (`m99Dir`: tab cross-fade, deeper
   slide-in, back slide-out), count-up on first view / tick on change keyed by the number's label (`m99Nums`; Top/Bottom
   ranks never count), bars fill once per screen (`m99Bars`), press spring on every tappable thing, pylon loader +
   skeletons (`HM_LOADER`, `m99Skel`), empty states in the voice (`EMPTY99`), pull to refresh (Huddle, Matchup, Wire),
   instant open from the last Huddle snapshot (LS `hm_snap`, `S._snapOn` blocks demo renders until live data arrives).
   v100 consistency audit: Locker tile grades come from the Sleeper-wide percentile on "All leagues" (no A+ next to
   "Bottom 48%"); Luck/Activity ungraded; Skills radar labelled "vs league mates"; Sleeper-wide card's titles block is
   one line; `pageChrome` keeps info buttons out of h1 text; League page one tab row (`ltMerge`); Huddle eyebrow above
   the greeting, awards top 3 + "All awards" sheet, tiles that duplicated tabs removed ("More"); "you" tag in Pylon, no ▲;
   tab names Huddle · News · Gameday and Team "Player news"; search PAGES renamed (+ The Wire, Records, Almanac);
   position chips neutral everywhere (specificity override); My teams card shows projections pregame, not 0.0-0.0.
   v101 release detection (owner: "Jordan Love was released" came from the headline "Jordan Love Makes The Cut"):
   `relMatch` only counts transaction phrasing (team verb + name, "was/has been released|waived|cut", "released by/from",
   "cut ties with"); and if Sleeper still lists the player on a team, a release story only counts for 36 hours.
   v102 The Wire in depth (`wxCtx`, `wGameStory`, new `wireStories`/`wireStory(s,brief)`): lead + fact panel + details;
   game stories (kickoff chance, top 3 starters, loser's biggest miss vs average, zero-point starters, bench left and
   whether the best lineup would have won, records/odds after, lifetime H2H); trades (each player: team, age, pts/g,
   ROS/wk, value; picks; points started since; ROS and value balance only when every piece has a number, no value
   verdict when picks are involved); waiver bids vs the league's median winning bid; standings (rank, PF rank,
   all-play, luck, odds, next opponent, core, track-record notes); playoff race table; Week in review; Injury report;
   Who's hot (last 3 weeks). Huddle shows the top story brief with "Full story".
   v103 lighter launches: data files go through the service worker (`sw.js` `dataFetch`: keeps each file with its
   ETag/Last-Modified, sends If-None-Match, reuses the copy on 304, works offline); app fetches use fixed URLs with
   cache:"no-cache" (no more ?t= busting with no-store); the 1.6 MB college file only loads in Scout; finished Sleeper
   weeks (>= 2 weeks old) cached in IndexedDB for good, last week for 6 h (`hxGet` wrapper, key hxw1:<path>).
   Note for QA: Playwright disables the HTTP cache whenever page.route is used; test caching without routes.
   Cleanup: 21 provably dead items removed (superseded definitions never called before being replaced, captures of
   old versions never used; acorn analysis, see HANDOFF). Only ~2% of the code was dead; most size is live features.
   v105 (owner: scrolling Players, the app "timed out", closed See all and jumped to the top): background renders
   keep the page. The 45 s live poll (`pollQuiet`, S.quiet) and the 3 min transactions / game-clock timers (`bgRender`)
   only redraw live pages (`UI105_LIVE`: home, matchup, league, team, roster, gameday, tx); they wait 1.5 s after the last
   touch/scroll; every same-route redraw restores expanded `.lmore` lists (marked data-open), open details, table
   side-scroll and scrollY. New timers that redraw must call `bgRender()`, never `render()`.
   v130 (owner: 30 s live, 3 min otherwise): one scheduler (`LV130`, 5 s tick) refreshes scores every 30 s while any game
   is live (liveSet or ESPN st "in"), every 180 s otherwise, and on return to the app (15 s+). The old 45 s / 60 s timers
   and the forced ESPN-clock timer still exist but their automatic calls are skipped; pull to refresh (touch event) runs.
   New refresh logic must go through lv130Refresh(), not new setIntervals.
6. NFL team ratings and matchups — done (v104, `scripts/build_teams.py` -> `data/teams.json`, run by news.yml every 30 min,
   writes only when something changed). Backtests `backtest/e12_*.py` (games 2002-2025, player weeks 2021-25):
   points-margin Elo (K .08, home 2.0, prior x.7, cap 28, sigma 12.5) Brier .2246 on 1,355 games 2021-25 (old power
   rank .230); closing line .2118 -> odds use the line when posted, the rating otherwise (fitted blend weight on the
   line = 1.0). 1-6 weeks ahead the rating beat market-implied ratings (.220-.227 vs .226-.232). Defense-vs-position,
   opponent-adjusted and shrunk, improves player MAE by only ~0.02 (context only). Implied team total moves players
   (QB best/worst 10% of environments +3.5/-2.5 pts) but Sleeper's projection already prices it (adding it on top
   tested worse) -> this week's projections unchanged; the environment factor (beta QB .577 RB .535 WR .245 TE .224)
   is used only for future weeks: Scout › NFL teams Power rankings + Fantasy playoffs table, GM › Waivers Streamers
   (QB/TE/DST/K), Team › Roster Fantasy playoffs for your starters. Prediction log graded in teams.json `log`/`card`.
7. Devy (see engine 7 below) and C4 snapshots: `scripts/snapshot_proj.py` + `.github/workflows/snapshot.yml` freeze
   Hashmark's projection per game at kickoff into bt/proj_log/<season>-<week>.json.gz; scripts/rpt_snapshot.py grades
   them (`projections_live`, report row "Recorded before kickoff"). e27 leak check: bt/sleeper_proj is fetched after
   games but not revised by results; it reflects inactives (honest for lineups set at kickoff; ~+0.02 MAE earlier).
   v120 (A5): log keeps per game `early` (first prediction, with days before kickoff) and `final` (last pregame, rewritten
   until kickoff, frozen after); card {final, early (7+ days out only), by_src line/rating}. build_teams.py env overrides
   HM_OUT_TEAMS, HM_GAMES_CSV, HM_SCHED, HM_ODDS, HM_NOW for testing. Nothing graded on real games before 2026-11-12.
   v122 (e19): Streamers' D/ST (.6) and K (.5) factors match the fitted elasticities; no rule beat them on 2025-26. Tag
   fixed to "next 3 games"; top-3 D/ST streamers beat the average free agent by 2.6 pts/wk (81% of weeks, 2021-26).
7. College prospect (devy) — v124 (e23, cfbfastR-data rosters/stats + nflverse outcomes; classes 2016-20 fit, 2021-23
   held out; hit = top-24 RB/WR or top-12 QB/TE PPR season within 3 NFL seasons): fitted "starter odds" (`dvOdds`,
   `DVM124`): AUC .903 -> .918 final season, .839 -> .865 one season earlier, .697 -> .743 two earlier, vs the hand-set
   score (kept for board order). Recruiting rating (CFBD, Actions only via manual .github/workflows/devy-test.yml) wins
   everywhere (.930 / .880 / .772, log loss better too): `DVM124.pwr` shipped (undrafted prospects; rating = p.rec.rating,
   else unrated flag); pre-draft odds display capped at "40%+" (35%+ bin said 42%, happened 31%, n 16). Note: TEs lead the
   40%+ group (top-12 TE is an easier bar; few TE hits behind it). Rated share train 62% / test 51% / app 2027 62%. build_cfb: position
   fallback for '?'/'NA' rosters; recruiting classes cur-7..cur.
8. Confidence labels + live model report card — done (v108). `scripts/build_report.py` -> `data/report.json` (data.yml,
   twice daily) grades the app's full projection replayed by `scripts/proj_panel.py` (stdlib; downloads nflverse weekly +
   ffopportunity to /tmp/hm_dl, reads PJC/PJ_PROPS_POS from index.html), win odds (Brier .211, calibration), NFL picks,
   ranges (cells pos x tier x volatility x questionable, fitted 2021-24, 80% range held 81% on 2025-26). App: `e8Range`
   (hmProj wrapper sets lo/hi/sd/conf), labels HIGH/MEDIUM/LOW (`e8Chip`), player card "Week N projection" (stat tile
   relabelled "Sleeper's Wk N projection"), matchup "likely X-Y" under team totals (sd = .16m+5), start/sit "Coin flip"
   under 58%, Report card page (route `report`, `vReport`, link card at the bottom of the Locker, in search), track-record
   lines on Waivers (Best adds) and Trade finder (dynasty/keeper).
   v126 report card rows: rest of season, half-PPR/standard, breakout odds, risk score, kickers and D/ST, trade grades,
   playoff odds, recorded-before-kickoff (appears once graded). v128: Clutch tile ungraded on All leagues.
   v125 (owner decision): Locker Sleeper-wide ranks need reliability n/(n+k) (k=(1-tau2)/tau2 from mgr_ref.json): grade
   from .5, muted "small sample" from .25, record only below; trades and drafts HIDDEN from the Sleeper-wide panel
   (tau2 .06/.035: ~16/~28 seasons needed); tiles say "mostly luck season to season". "How repeatable" line per skill.
   v127 (e33): verdict "expected" = v114 model refit per GAME PLAYED (`ROS127`, `exp127`; net right buy/sell 2025
   133 -> 148, 2026 78 -> 101, sell precision 78 -> 91% / 74 -> 78%); questionable play-rate line (practice x position)
   on start/sit, roster To do, Needs attention (projection unchanged). Replacement levels and kicker 0-fallback tested:
   no change.
   v113 (e30, owner decision 2026-11-12): ranges from per-position piecewise-linear quantile curves (RPT.ranges.model,
   `E30`, new `e8Range`; old cell table = fallback): held out 2025-26 80.1% inside (9.7% below / 10.1% above). Past
   volatility, games played and questionable did NOT predict misses, so HIGH/MEDIUM/LOW labels were REMOVED (owner chose
   "drop labels" after a side-by-side). Player card: projection + range + "lands inside 8 times in 10". Report card
   "Projection ranges" table by position (inside/below/above). Start/sit keeps "Coin flip" (<58%).
   Report plug-ins: scripts/rpt_*.py each `section(ctx)` merged into report.json by build_report.py (HM_OUT env to test).

## Open items
- Audit list 2026-11-11/12: all items done (see HANDOFF.md).
- Watch the first real runs: snapshot.yml (first call to Sleeper from Actions), build_cfb with cur-7 recruiting.
- Not verifiable here (no Sleeper/ESPN access): v121 breakout/risk and v123 live-score term in a real league; Sleeper's
  practice-status field format for the v127 questionable line.
- v129: topTxt "Average" = 45th-55th percentile; QB range top x1.03 (chosen 2024-25, held out 2026 77.1% -> 80.4%);
  TE left as is (78-80% every season 2021-25 on the report population, 2026 75% at n 271 = edge of noise; recheck as
  2026 fills in); Skills tile ungraded on All leagues.
- WR waiver adds largely fixed by v115; dynasty waiver test still can't replay value-protected drops.
- v131 + p131 (outside new-user review, owner said fix 1-5): Huddle tiles skip the hero's move (`hd131Same`: same t + go;
  Moves tile shows "Next: …"); hero for Sell high/Buy low reads "Sell high: X"; insights lead with the call ("Running
  hot: scoring X a game more than his usage supports", "TD rate likely to cool: …", "Due to rise", "More TDs likely");
  "105.3 vs 82.0" on Huddle; "You're contending in …"; empty Trade Lab hub tiles say "None right now" + what appears
  there (`TL131`). Review item 1 (dock covering the last tile) was a full-page-screenshot artifact: main already pads
  96px + --dockb. Review items 6-12 (44% vs 0% win check, sign-in pitch/theme, contrast, roster rank vs value, jargon
  explanations, trust line, greeting): done in v132-v135 below; tagline (7) being brainstormed with the owner.
- v132: leagueSummary cache (Huddle/My teams win chance) lives one redraw only (1.5 s); it used to survive projection
  changes until a score changed, so Home could show 79% while Team showed 29% (review item 6, reproduced and fixed).
- v133: light-mode text contrast to WCAG AA: --good #08795B, --bad #B8253F; small orange text (.hdk, .stcmp, .tag.good,
  .wtag.w-acc, devy .dvo/.dvp/.dvr .up, active dock label) #BF4706; fills/buttons keep #E85A0C. Grey meta text already
  passed. Contrast checker false positives: gradient pills (.pill.hot) and translucent pill backgrounds.
- p134: roster rows show value rank ("WR6 value") instead of the raw number; Next 4 weeks lists slots empty every week
  once ("Empty every week: FLEX").
- v134: confidence notes in plain words (`CF134`); "Value to you" says why ("you'd start him less than most teams
  would"); roster glance boxes explained behind one info button (DEFS.rosglance).
- v135: proof line under the Huddle's top move (`hd135Proof`: waiver track record / sell 91% / buy 69% held-out 2025 /
  projections vs Sleeper weeks); greeting uses the Sleeper display name in live mode; live note says 30 seconds.
- v136 (owner: Luther Burden, concussion + questionable before a bye, showed Long term LOW "Uncertain injury
  (Undisclosed)"): Sleeper's "Undisclosed" no longer counts as an uncertain (heart/spine-type) injury unless the player is
  on IR/PUP/NFI with no named injury in 3 weeks of news; otherwise minor, named from the news (concussion, ankle ...).
  Short term is capped at Medium while a player carries any injury tag ("but listed questionable (concussion)").
  Matchup page win bar (.wp) now orange for you / plain track for them, like the other win bars (was mint/rose).
- v137 (owner: Burden "worth less to me" on his rebuilding keeper team; the card said REDRAFT): the player card values
  for the league selected in the app. The Value tag now names the league and "Value to you" starts "On / Not on your
  roster here." Value to you = market x (your lineup loss or gain / average other team's)^.6, clamped .5-1.6 (-34% is
  the floor). Known asymmetry, not changed: valIn adds a breakout bonus for contenders that valOut never gets.
- Edge tests x1-x8 (2026-11-13, HANDOFF "outside the box"): win-max lineups and playoff schedules dead; owner said go on
  4 builds, one at a time: A offseason sells, B crowd add/drop in projections, C league-mate profiles, D injury types.
- v138 (build A, backtest/x7_fit.py -> x7_fit.json): `OFS138` Nov->May dynasty value drift vs the market by fmt x pos x
  age band (rookie/<=23/24-26/27-29/30+) x rank tier (top 60 / 61-200). Held out 2023-24: flagged (-25%+) lost 41/46%
  by May vs 23/20% others (70% fell more); expected +15%+ held -3/-7% vs -26/-21%. Dynasty/keeper only, Oct 1-Mar 1:
  roster To do "Sell before the offseason" (owned, -20%+, value >= 800) and an "Offseason:" line on the Value card.
- Build B (backtest/x3_fit.py, NOT shipped): crowd add/drop rank (900 leagues, window Monday -> first kickoff, no
  post-game leak) did not improve Hashmark's projection held out 2024-25 (MAE 4.822 -> 4.828; 3-week residuals flat).
  The x3 crowd edge was vs Sleeper's projection only; Hashmark's inputs already carry it.
- v139 (build C, backtest/x2_fit.py): trade habits persist (2+ trades in weeks 1-8 -> 43% trade again in 9-17, 1 -> 26%,
  0 -> 12%; previous partner 45% vs 34% chance). Trade partners + Trade finder cards: "Open to trades: N trades this
  season · traded with you" (`tr139`, from L.tx); partners with equal fit sorted by trades. League-only FAAB bid style
  does not persist (r .11) -> no bid profiling.
- Build D (backtest/x6_fit.py, NOT shipped): injury-type multipliers on Hashmark's projection (questionable / first game
  back / games 2-3 back, fit 2021-23) made held-out 2024-25 worse: per type 4.103 -> 4.142 MAE (900 rows), pooled worse
  too (Q 4.366 -> 4.426, R1 3.871 -> 4.084); per-type patterns flip between periods. x6's effect was vs Sleeper only.
  Untested idea: injury type in the v127 questionable play-rate line (hamstring played 59% vs 63-73% others).
- v140 (owner): My teams tiles size scores to the tile (container query on .lbx) so "proj" never runs past the edge;
  h1/h2/h3 lowercase (wordmark style) except names (`hnm140Mark` MutationObserver adds .hnm when a heading equals a
  league/team/owner/player name) and The Wire headlines (.wst). Trade calculator redesign (A tug of war / B verdict first
  / C scoreboard) and trade sharing (1 image card / 2 link with trade in # / 3 short link + live preview via a worker)
  shown as mockups. Owner: B for the calculator, add buttons under each side, share = image only.
- v141: two-team calculator = verdict card (`C141V` grade -> "Do it." ... "Don't send this.", value/lineup or title odds/
  comes-out-ahead line), You give + Add / You get from <team> + Add, lineup bars, what changes, Make it fair (`c141Fair`:
  their players that re-grade you to -2%..+12%, each tested with calcEval), Share (`c141Image` 1080x1350 card -> share
  sheet or download), old result under "Full breakdown". 3-4 team trades keep the old layout.
- v142 (owner): every win-chance bar is the orange gradient (tlPaint wrapper: bar whose neighbouring text says win
  chance/odds); other bars keep the green/yellow/red traffic light. Owner asked about a projected-value-over-time graph
  for trades: x9 test run (backtest/x9_paths.py -> x9_fit.json; train paths END before 2023, test starts 2023+):
  players: median beats "value stays flat" by 2% at 6 mo, 6.5% at 1 yr, 17% at 2 yrs, 23.5% at 3 yrs (60 days: tie);
  10-90% bands hold 76-80% (slightly narrow). 1,256 real keeper/dynasty trades 2023+: side ahead later picked 69.3% vs
  67.9% flat at 1 yr, 65.6% vs 59.5% at 2 yrs, 57% vs 52% at 3 yrs (n 126).
- v143 (owner "go": both sides' market value + dotted value to your team): calculator "Value over time" card for
  dynasty/keeper two-team trades (under the lineup bars). data/valpath.json from backtest/x9_ship.py 1.1 (cells x 11
  quantiles, bands widened x1.1: x9_cal.py held-out coverage 81-84%; pick buckets r1e/r1m/r1l/r2/r3/r4 = real 2020-24
  rookies' values .5/1.5/2.5 yrs after the draft). `vp143Sim` 500 seeded draws per side (stable per trade), points
  Now / Draft (or 6 mo) / 1 / 2 / 3 yrs; dotted = median x today's roster-fit ratio (implied() / market); headline names
  who's ahead now and the month the lines cross. Picks: today's value until their draft (May 1 of pick year), r1 uses
  the mid bucket. Not in the share image yet. Rebuild data: python3 backtest/x9_paths.py && python3 backtest/x9_ship.py 1.1.
- x10 (owner: do pick values account for strong/weak draft classes? NO, by design now): backtest/x10_class.py on e23 rows
  (classes 2016-23; run backtest/e23_run.sh first). Hits (top-24 RB/WR, top-12 QB/TE within 3 NFL seasons) among each
  class's top 12 by NFL pick: 5-8 per class, sd 1.05 vs 1.71 expected from luck alone; top 24: 7-15, sd 2.24 vs 2.43.
  Class-to-class differences are no bigger than chance; leave-one-class-out predictions correlate .25-.51 (n 8, not
  significant). Picks stay flat by class. Aside (untested): market pick prices in values.json (dd) fall ~19%/yr
  (2027 1st mid 6,165 -> 2028 4,991 -> 2029 4,235) vs the app's 7%/yr discount (pickVal).
- x11 (backtest/x11_picks.py, 17,554 real keeper/dynasty trades with picks 2019-26, bt/leagues.json.gz; pick entries
  are [season, round, original roster, previous owner, new owner]): implied 1st price (median players paid, app curve)
  next draft 3,490 1QB / 3,246 SF, one more year out 2,870 / 2,672 (-18%), two more 1,985 / 2,133 (-25..-31% more);
  Huber regression on all trades agrees (~-30% then -10..-14%). App: 3,772 / 3,508 / 3,262 (7%/yr) -> future picks
  overvalued ~25-30% one year out, ~55% two out. Who pays: contenders receive 1sts ~10-20% cheaper (regression 1QB
  2,427 vs 2,912 rebuilders / 3,354 middle; SF 2,769 vs 3,064 / 3,094), rebuilders do NOT pay more than middle teams
  (app: contender x.85 supported, rebuilder x1.15 not). Landing: a contender's pick traded 1 draft out landed in the
  late third 55% (avg slot .66), rebuilder's early third 40% (.50); 2 drafts out contender .61 / rebuilder .48 (n 71/29)
  -> strength persists into the second year (app adjusts slot only for the next draft).
- x12 (backtest/x12_picktest.py, owner "go test"): 7,217 dynasty trades with picks traced to the real rookie draft (the
  player actually picked), real value of each side at draft + 180 days. Which pick rule names the side that ended ahead?
  Held out 2023+ (n 4,536): app 7%/yr 65.2% right / log error .922; market-like 20%/yr 64.2% / .933; no discount 65.5% /
  .918; fit on 2019-22 picked .93. Second-year slot lean: no gain. Pick level x1.1-1.2: right 65.8-66.3%, error flat.
  -> KEEP pickVal as is. The market's ~20%/yr discount is an inefficiency: future picks are underpriced (managers,
  contenders most, sell them cheap but they hold their value) = a buy signal, not something to copy.
- v144 (owner "yes do that"): Trade Lab hub (dynasty only) "future picks on sale" card (`fp144`, `fp144Card`): other
  teams' 1sts/2nds 2+ drafts out (picksOf), contenders first then most trades (tr139); price table per pick (Typical ask =
  pickVal x (.8/.93)^years beyond next draft, Worth = pickVal); tap a pick chip -> calculator with that pick on the get
  side. DEFS.fp144 explains x11/x12.
- v145 (owner: Burden for nothing graded B for both, "Gets 3,703 · sends 3,703"): a player added before choosing the other
  team was stored from you to you; choosing the team later didn't re-point it. `calc145Fix` (runs before calcEval and
  vCalc) sends any asset whose destination is its own team or a team not in the trade to the other side.
- p146 (owner: Chuba Hubbard 27 RB ~ same value as Luther Burden in the keeper league): explained (keeper value = 50% keeper
  value + 50% this season; dynasty markets Burden ~5,200 avg vs Hubbard ~3,000 (ECR #31 vs #95), this season Hubbard RB8
  vs Burden WR15 so the halves pull them together). Fixed: (1) questionable + MINOR injury no longer trims long-term value
  x.9 in valueEngine (card already said long-term unchanged); (2) trade finder "▲ +-8 value" -> signed / "about even value".
- v147 (owner: "app is moving a little slow"): profiled (CDP, 10 Huddle redraws, 5 leagues): lostSeason() scanned every
  news story for every player on each filter (players x stories) = top cost before and after today's work. lostSeason
  and injClass now cached per player (key id|inj|offRep|news.rep) until NW.built / NW.items.length changes. Huddle
  redraw with 1,500 stories: 57 -> 6 ms; other pages equal or faster. Perf scripts: scratchpad qa/perf.js, perf3.js
  (old build served on :8766 from git show <commit>:index.html).

## Owner's leagues
Sleeper username `jackdixon`. One keeper league: 8 keepers (6 regular + 2 taxi); taxi keepers must have 0-1 years of
experience and not have started in a lineup that season; no keeper pick cost. Co-manages one team with another owner.
