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
- Pushing: `git pull --rebase && git push` (workflows commit data to `main` often).

## Engine status (see the "Hashmark analytics engine review" doc for the original audit)
1. Projections — done (weights fitted on Sleeper projections vs results).
2. Win odds / playoff odds — done (fitted on 44k Sleeper matchups).
3. Value engine — done (fitted on 2020-24 dynasty markets vs production; measured age curves; pick values).
4. Trades — done. Grades from 7,656 real trades; redraft graded on championship odds; keeper leagues blend this season
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
6. **NFL team ratings and matchups — next, awaiting "go".** Plan: Elo + EPA with opponent adjustment and a
   last-season prior, blended ~65% with closing spreads (`data/odds.json`); opponent-adjusted, shrunk
   defense-vs-position (raw DVP only ~15-33% real, see `backtest/e10_dvp.py`); matchup effect into projections;
   streaming view for QB/TE/DST/K; schedule strength in expected points incl. fantasy playoffs; prediction log.
   Target: Brier ≤ 0.218 (current power rank 0.230, Vegas 0.218).
7. College prospect (devy) score — untested, hand-set weights; fit on 2015-23 classes incl. draft capital.
8. Confidence labels + live model report card.

## Open items
- Done: `bt/rosters.json.gz` (900 leagues, exact weekly rosters). Waiver test 2024-25, 516 leagues / 62,616 team-weeks,
  and the v65 fixes from it (see engine 5 above and HANDOFF.md).
- Waivers still to improve: WR adds gain least (no WR-specific fix held across seasons, see HANDOFF.md);
  dynasty test can't replay the app's value-protected drops (no historical dynasty values in the archive).
- Retest IDP trade grades with a few more weeks of 2026 data (owner asked); if still below offense, keep IDP out of trade ideas.

## Owner's leagues
Sleeper username `jackdixon`. One keeper league: 8 keepers (6 regular + 2 taxi); taxi keepers must have 0-1 years of
experience and not have started in a lineup that season; no keeper pick cost. Co-manages one team with another owner.
