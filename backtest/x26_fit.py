"""x26 (owner: "cross check head coaches and coordinators for scheme trends and defensive profiles"; test only).
Data: bt/nfl/coaches.json (Wikipedia infobox HC/OC/DC, scripts/fetch_coaches.py), backtest/x26_profiles.json
(x26_profiles.py), Sleeper projections + stat lines 2018-26 (bt/sleeper_proj[_old], bt/sleeper_stats[_old]).
A. Does a coordinator's scheme follow him? For team-seasons where the DC (or OC) changed to someone who coordinated
   (or head-coached, for offense) elsewhere the season before, predict this season's profile (season z-scores) from
   (1) the team's own last season, (2) the coach's last team-season, (3) a blend fit on 2019-2022, tested 2023-25.
   Also weeks 1-4 profile. Control: teams that kept their coordinator.
B. Does it move fantasy points? Weeks 1-4 residual (real PPR - Sleeper projection) on the scheme shift a new coordinator
   brings (coach-prior minus team-prior, z units): own OC change (pass rate over expected, plays, top-RB carry share,
   top target share) by position; opponent DC change (man rate, single-high rate, pressure, pass/rush EPA allowed).
   Per-position least squares fit on 2018-2023, tested on 2024-26 vs Sleeper alone; MAE + paired bootstrap CI."""
import json, gzip, csv, os, re, random, collections, statistics as st, unicodedata
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = json.load(open(f"{R}/bt/nfl/coaches.json")); PR = json.load(open(f"{R}/backtest/x26_profiles.json"))
FIX = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA"}; fx = lambda t: FIX.get(t, t)
def nm(s): s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower(); return re.sub(r"[^a-z ]", "", re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", s)).strip()
# who held each job (first-listed = season starter; for prior-history use everyone listed)
job = {k: {r: [nm(x) for x in v.get(r, [])] for r in ("hc", "oc", "dc")} for k, v in C.items()}
hist = collections.defaultdict(list)   # coach -> [(season, team, role)]
for k, v in job.items():
    y, t = k.split("|"); y = int(y)
    for r in ("hc", "oc", "dc"):
        for c in v[r]: hist[c].append((y, t, r))
# z-scores per season and scope
METS_D = ["man", "single_high", "pressure", "rushers", "box", "def_pass_epa", "def_rush_epa"]
METS_O = ["proe", "neutral_pass_rate", "plays", "rb1_share", "tgt1_share", "off_motion", "off_pa"]
Z = {}
for sc in ("full", "w14"):
    for y in range(2016, 2026):
        for m in METS_D + METS_O:
            vals = {k.split("|")[1]: PR[k][sc][m] for k in PR if k.startswith(f"{y}|") and sc in PR[k] and m in PR[k][sc]}
            if len(vals) < 20: continue
            mu, sd = st.mean(vals.values()), st.pstdev(vals.values()) or 1
            for t, v in vals.items(): Z[(y, t, sc, m)] = (v - mu) / sd
def coach_prior(c, y, roles):
    """coach's most recent season before y in one of roles, within 2 seasons: (season, team)"""
    best = None
    for (yy, t, r) in hist.get(c, []):
        if r in roles and y - 2 <= yy < y and (best is None or yy > best[0]): best = (yy, t)
    return best
def changes(y, t, side):
    cur, prev = job.get(f"{y}|{t}"), job.get(f"{y-1}|{t}")
    if not cur or not prev: return None
    role = "dc" if side == "D" else "oc"
    if not cur[role]: return None
    c = cur[role][0]
    if c in prev[role]: return ("same", c, None)
    roles = ("dc",) if side == "D" else ("oc", "hc")
    p = coach_prior(c, y, roles)
    if p and p[1] == t: return ("same", c, None)
    return ("travel", c, p) if p else ("new", c, None)
# ---------------- A ----------------
print("A. Does the scheme follow the coordinator? (season z-scores; corr with this season's profile)")
A = {}
for side, mets in (("D", METS_D), ("O", METS_O)):
    for m in mets:
        for sc in ("full", "w14"):
            rows = []
            for y in range(2017, 2026):
                for t in {k.split("|")[1] for k in PR if k.startswith(f"{y}|")}:
                    ch = changes(y, t, side)
                    if not ch: continue
                    tgt, tp = Z.get((y, t, sc, m)), Z.get((y - 1, t, "full", m))
                    if tgt is None or tp is None: continue
                    cp = Z.get((ch[2][0], ch[2][1], "full", m)) if ch[0] == "travel" else None
                    rows.append((y, ch[0], tgt, tp, cp))
            def cor(a, b): return st.correlation(a, b) if len(a) > 4 else float("nan")
            same = [r for r in rows if r[1] == "same"]; tr = [r for r in rows if r[1] == "travel" and r[4] is not None]; new = [r for r in rows if r[1] == "new"]
            # blend weight on coach prior, fit 2019-2022, test 2023-25 (travellers only)
            fit = [r for r in tr if r[0] <= 2022]; test = [r for r in tr if r[0] >= 2023]
            def mse(rs, w): return st.mean((r[2] - (w * r[4] + (1 - w) * r[3]) * k) ** 2 for r in rs) if rs else float("nan")
            k = 1.0
            best = min((mse(fit, w / 10), w / 10) for w in range(11))[1] if fit else 0
            # shrink factor too (prior-season z regresses toward 0)
            ks = [x / 10 for x in range(2, 11)]
            def mse2(rs, w, kk): return st.mean((r[2] - kk * (w * r[4] + (1 - w) * r[3])) ** 2 for r in rs) if rs else float("nan")
            bw, bk = min(((mse2(fit, w / 10, kk), w / 10, kk) for w in range(11) for kk in ks))[1:] if fit else (0, 1)
            tk = min(((mse2(fit, 0, kk), kk) for kk in ks))[1] if fit else 1
            A[(side, m, sc)] = dict(n_same=len(same), n_travel=len(tr), n_new=len(new),
                r_same_team=cor([r[3] for r in same], [r[2] for r in same]),
                r_travel_team=cor([r[3] for r in tr], [r[2] for r in tr]), r_travel_coach=cor([r[4] for r in tr], [r[2] for r in tr]),
                r_new_team=cor([r[3] for r in new], [r[2] for r in new]), w_coach=bw,
                test_n=len(test), test_mse_team=mse2(test, 0, tk), test_mse_blend=mse2(test, bw, bk))
            a = A[(side, m, sc)]
            print(f"  {side} {m:17s} {sc:4s} same-coord r={a['r_same_team']:.2f} (n {a['n_same']}) | new coord from elsewhere (n {a['n_travel']}): "
                  f"team-last-yr r={a['r_travel_team']:.2f} vs coach's-old-team r={a['r_travel_coach']:.2f} | first-time coord r={a['r_new_team']:.2f} (n {a['n_new']}) "
                  f"| blend w_coach {bw:.1f}; test 2023-25 n {a['test_n']} mse team {a['test_mse_team']:.3f} vs blend {a['test_mse_blend']:.3f}")
# ---------------- B ----------------
print("\nB. Weeks 1-4 fantasy residuals vs Sleeper")
load = lambda f: json.load(gzip.open(f"{R}/bt/{f}.json.gz", "rt"))["w"] if os.path.exists(f"{R}/bt/{f}.json.gz") else {}
SP = {**load("sleeper_proj_old"), **load("sleeper_proj")}; ST = {**load("sleeper_stats_old"), **load("sleeper_stats")}
s2g = {}
for r in csv.DictReader(open(f"{R}/backtest/dl/ids.csv")):
    s = str(r["sleeper_id"]).split(".")[0]
    if s not in ("", "NA") and r["gsis_id"] not in ("", "NA"): s2g[s] = r["gsis_id"]
team = {}
for y in range(2018, 2027):
    f = f"{R}/bt/nfl/pbp_player/{y}.csv.gz"
    if not os.path.exists(f): continue
    for r in csv.DictReader(gzip.open(f, "rt")):
        if r["season_type"] == "REG": team[(y, int(r["week"]), r["gsis_id"])] = fx(r["team"])
opp = {}
for r in csv.DictReader(gzip.open(f"{R}/bt/nfl/schedules.csv.gz", "rt")):
    if r["game_type"] != "REG": continue
    y, w = int(r["season"]), int(r["week"]); a, h = fx(r["away_team"]), fx(r["home_team"])
    opp[(y, w, a)] = h; opp[(y, w, h)] = a
def shift(y, t, side, m):
    ch = changes(y, t, side) if y <= 2025 or f"{y}|{t}" in job else None
    if not ch or ch[0] != "travel": return 0.0
    cp, tp = Z.get((ch[2][0], ch[2][1], "full", m)), Z.get((y - 1, t, "full", m))
    return (cp - tp) if cp is not None and tp is not None else 0.0
FO = ["proe", "plays", "rb1_share", "tgt1_share"]; FD = ["man", "single_high", "pressure", "def_pass_epa", "def_rush_epa"]
rows = collections.defaultdict(list)
for key, pw in SP.items():
    y, w = map(int, key.split("-"))
    if w > 4: continue
    stw = ST.get(key, {})
    for sid, v in pw.items():
        pos = v.get("pos"); p = v.get("pts_ppr")
        if pos not in ("QB", "RB", "WR", "TE") or p is None or p < 3 or sid not in stw: continue
        g = s2g.get(sid); t = team.get((y, w, g)) if g else None
        if not t: continue
        o = opp.get((y, w, t))
        if not o: continue
        x = [shift(y, t, "O", m) for m in FO] + [shift(y, o, "D", m) for m in FD]
        rows[pos].append((y, stw[sid].get("pts_ppr", 0) - p, x, any(abs(z) > 0 for z in x)))
def ols(X, yv, lam=5.0):
    k = len(X[0]); A_ = [[sum(r[i] * r[j] for r in X) + (lam if i == j else 0) for j in range(k)] for i in range(k)]
    b = [sum(r[i] * v for r, v in zip(X, yv)) for i in range(k)]
    for i in range(k):  # gauss
        piv = A_[i][i] or 1e-9
        for j in range(i + 1, k):
            f = A_[j][i] / piv
            for c in range(i, k): A_[j][c] -= f * A_[i][c]
            b[j] -= f * b[i]
    beta = [0.0] * k
    for i in reversed(range(k)): beta[i] = (b[i] - sum(A_[i][c] * beta[c] for c in range(i + 1, k))) / (A_[i][i] or 1e-9)
    return beta
random.seed(7); tot = {"base": [], "adj": []}
for pos in ("QB", "RB", "WR", "TE"):
    rs = rows[pos]; fit = [r for r in rs if r[0] <= 2023]; test = [r for r in rs if r[0] >= 2024]
    mu = st.median([r[1] for r in fit])  # Sleeper's mean-vs-median offset, so the adjustment is judged on top of it
    beta = ols([r[2] for r in fit if r[3]], [r[1] - mu for r in fit if r[3]])
    base = [abs(r[1] - mu) for r in test]; adj = [abs(r[1] - mu - sum(b * x for b, x in zip(beta, r[2]))) for r in test]
    d = [a - b for a, b in zip(adj, base)]; aff = [i for i, r in enumerate(test) if r[3]]
    bs = sorted(st.mean(random.choices(d, k=len(d))) for _ in range(400))
    tot["base"] += base; tot["adj"] += adj
    print(f"  {pos}: fit n {len(fit)} ({sum(r[3] for r in fit)} with a coordinator shift), test 2024-26 n {len(test)} ({len(aff)} affected): "
          f"MAE {st.mean(base):.3f} -> {st.mean(adj):.3f} (CI {bs[10]:+.3f}..{bs[389]:+.3f}); affected only "
          f"{st.mean([base[i] for i in aff]) if aff else float('nan'):.3f} -> {st.mean([adj[i] for i in aff]) if aff else float('nan'):.3f}")
    print("     coefs", dict(zip(["own " + m for m in FO] + ["opp " + m for m in FD], [round(b, 2) for b in beta])))
    for yy in (2024, 2025, 2026):
        tb = [base[i] for i, r in enumerate(test) if r[0] == yy]; ta = [adj[i] for i, r in enumerate(test) if r[0] == yy]
        if tb: print(f"     {yy}: {st.mean(tb):.3f} -> {st.mean(ta):.3f} (n {len(tb)})")
print(f"  ALL: {st.mean(tot['base']):.3f} -> {st.mean(tot['adj']):.3f}")
