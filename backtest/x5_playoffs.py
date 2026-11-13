"""Edge test 5. (a) Leverage: how much one week's result moves playoff chances, from 900 real leagues 2022-25
(P(made playoffs | won week w) - P(... | lost) for teams with the same record entering week w).
(b) Playoff schedules: as of week 10, does the fantasy-points-allowed of a player's week 15-17 opponents (to his
position, through week 10) predict his week 15-17 points beyond his week 1-10 PPG? nflverse weekly 2021-25."""
import gzip, json, csv, collections, statistics as st
R = json.load(gzip.open("bt/rosters.json.gz", "rt"))["leagues"]
lev = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0, 0]))
for l in R.values():
    pws = l.get("pws", 15); W = sorted(int(w) for w in l["weeks"] if int(w) < pws)
    if len(W) < 12: continue
    rec = collections.defaultdict(lambda: [0, 0]); res = {}; pts = collections.Counter()
    for w in W:
        bym = collections.defaultdict(list)
        for t in l["weeks"][str(w)]: bym[t[1]].append(t)
        for pr in bym.values():
            if len(pr) == 2:
                a, b = pr; res[(w, a[0])] = a[2] > b[2]; res[(w, b[0])] = b[2] > a[2]
        for t in l["weeks"][str(w)]: pts[t[0]] += t[2]
    teams = list(pts); recs = {r: sum(res.get((w, r), 0) for w in W) for r in teams}
    nplay = 6 if len(teams) >= 10 else 4
    made = set(sorted(teams, key=lambda r: (-recs[r], -pts[r]))[:nplay])
    for w in W:
        for r in teams:
            if (w, r) not in res: continue
            wb = sum(res.get((x, r), 0) for x in W if x < w); k = (len(teams), w, wb)
            c = lev[w - 1][k]; i = 0 if res[(w, r)] else 2; c[i] += 1; c[i + 1] += r in made
for gw in (3, 8, 11, 13):
    xs = []
    for k, c in lev[gw].items():
        if c[0] >= 15 and c[2] >= 15: xs.append((c[1] / c[0] - c[3] / c[2], c[0] + c[2], k[2]))
    xs.sort(key=lambda x: x[0]); n = sum(x[1] for x in xs)
    if xs: print("week %d: one game moves playoff odds by %.0f pts on average, range %.0f-%.0f pts across records" % (gw + 1, 100 * sum(a * m for a, m, _ in xs) / n, 100 * xs[0][0], 100 * xs[-1][0]))
# (b)
pw = collections.defaultdict(dict); allowed = collections.defaultdict(list); opp = {}
for y in range(2021, 2026):
    for r in csv.DictReader(open(f"backtest/dl/pw_{y}.csv", encoding="utf-8")):
        if r["season_type"] != "REG" or r["position"] not in ("QB", "RB", "WR", "TE"): continue
        w = int(r["week"]); p = float(r.get("fantasy_points_ppr") or 0); pw[(y, r["player_id"])][w] = (p, r["position"], r["team"])
        if w <= 10: allowed[(y, r["opponent_team"], r["position"])].append((w, p))
    for g in csv.DictReader(open("backtest/dl/games.csv", encoding="utf-8")):
        if g["season"] == str(y) and g["game_type"] == "REG" and 15 <= int(g["week"]) <= 17:
            opp[(y, int(g["week"]), g["home_team"])] = g["away_team"]; opp[(y, int(g["week"]), g["away_team"])] = g["home_team"]
A = {}
for (y, t, pos), xs in allowed.items():
    wk = collections.defaultdict(float)
    for w, p in xs: wk[w] += p
    A[(y, t, pos)] = st.mean(wk.values())
avg = {(y, pos): st.mean(v for (yy, t, pp), v in A.items() if yy == y and pp == pos) for y in range(2021, 2026) for pos in ("QB", "RB", "WR", "TE")}
X = []
for (y, pid), ws in pw.items():
    early = [ws[w][0] for w in ws if w <= 10]; late = [w for w in (15, 16, 17) if w in ws]
    if len(early) < 6 or len(late) < 2: continue
    ppg = st.mean(early); pos = ws[late[0]][1]
    if ppg < 8: continue
    sched = st.mean(A.get((y, opp.get((y, w, ws[w][2])), pos), avg[(y, pos)]) / avg[(y, pos)] - 1 for w in late)
    X.append((sched, st.mean(ws[w][0] for w in late) - ppg, ppg, pos))
X.sort(); n = len(X) // 5
print("players %d (8+ PPG weeks 1-10)" % len(X))
for name, part in (("easiest fifth of playoff schedules", X[-n:]), ("middle", X[2 * n:3 * n]), ("hardest fifth", X[:n])):
    print("  %-34s opponents allow %+.0f%%  -> weeks 15-17 vs own PPG %+.2f pts" % (name, 100 * st.mean(x[0] for x in part), st.mean(x[1] for x in part)))
mx, my = st.mean(x[0] for x in X), st.mean(x[1] for x in X)
b = sum((x[0] - mx) * (x[1] - my) for x in X) / sum((x[0] - mx) ** 2 for x in X)
r2 = (sum((x[0] - mx) * (x[1] - my) for x in X) ** 2) / (sum((x[0] - mx) ** 2 for x in X) * sum((x[1] - my) ** 2 for x in X))
print("  slope %.2f pts per +100%% easier; schedule explains %.1f%% of playoff-week swings" % (b, 100 * r2))
