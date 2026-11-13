"""Value test C: value players in each league's own scoring instead of the app's fixed multipliers (fmtMult)?
Dynasty leagues (bt/leagues.json.gz, type 2, no IDP), 2-team trades 2021-2024 with players only (picks left out so the
scoring effect isn't diluted), every player ranked in FantasyPros dynasty consensus on the trade date (bt/hv.json.gz).
Value at the trade: app curve of the consensus rank (SF or 1QB list) x
  app : fmtMult (TE premium bonus x .25 capped .3; RB +3.5/7% and WR/TE -3.5/7% in half/standard; league size)
  lg  : (player's prior-season points per game in THIS league's scoring / his PPR points per game) ^ g, clamped .6-1.6,
        players without a prior season keep the app multiplier.
Outcome: points above replacement in the league's scoring, from the trade week to the end of the NEXT season
(nflverse weekly stat lines rescored with the league's settings; replacement per week = k-th best at the position:
QB 13 (25 superflex), RB 30, WR 42, TE 14). Score: share of trades where the side valued higher scored more (gaps > 5%),
and Brier of a logistic fitted on the value gap. g fitted on 2021-22 trades, tested on 2023-24."""
import gzip, json, csv, math, collections, datetime as dt, re, statistics as st
import numpy as np
H = json.load(gzip.open("bt/hv.json.gz", "rt")); DD = [dt.date.fromisoformat(x) for x in H["d"]]; IDS = H["ids"]
src = open("index.html", encoding="utf-8").read(); VAN = {k: json.loads(re.search(r"const %s=(\[\[.*?\]\]);" % k, src).group(1)) for k in ("VAN1", "VANS")}
def curve(r, A):
    if r <= 1: return A[0][1]
    for (r1, v1), (r2, v2) in zip(A, A[1:]):
        if r <= r2: t = (math.log(r) - math.log(r1)) / (math.log(r2) - math.log(r1)); return math.exp(math.log(v1) + t * (math.log(v2) - math.log(v1)))
    return 5
RK = {f: [({IDS[j]: n + 1 for n, j in enumerate(T)} if T else None) for T in H["t"][k]] for f, k in (("1qb", "do"), ("sf", "dsf"))}
def near(d):
    i = min(range(len(DD)), key=lambda i: abs((DD[i] - d).days)); return i if abs((DD[i] - d).days) <= 21 else None
g2s, POS = {}, {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s not in ("", "NA"):
        POS[s] = r.get("position")
        if r.get("gsis_id") not in ("", "NA", None): g2s[r["gsis_id"]] = s
F = lambda r, k: float(r.get(k) or 0)
W = collections.defaultdict(dict)   # (season, week) -> sid -> stat line
for y in range(2020, 2026):
    for r in csv.DictReader(open(f"backtest/dl/pw_{y}.csv", encoding="utf-8")) if y >= 2021 else []:
        if r["season_type"] != "REG" or r["player_id"] not in g2s: continue
        W[(y, int(r["week"]))][g2s[r["player_id"]]] = r
def pts(r, sc, pos):
    p = (F(r, "passing_yards") * sc.get("pass_yd", .04) + F(r, "passing_tds") * sc.get("pass_td", 4) + F(r, "passing_interceptions") * sc.get("pass_int", -1)
         + F(r, "passing_2pt_conversions") * sc.get("pass_2pt", 2) + F(r, "completions") * sc.get("pass_cmp", 0) + (F(r, "attempts") - F(r, "completions")) * sc.get("pass_inc", 0)
         + F(r, "passing_first_downs") * sc.get("pass_fd", 0) + F(r, "rushing_yards") * sc.get("rush_yd", .1) + F(r, "rushing_tds") * sc.get("rush_td", 6)
         + F(r, "carries") * sc.get("rush_att", 0) + F(r, "rushing_first_downs") * sc.get("rush_fd", 0) + F(r, "rushing_2pt_conversions") * sc.get("rush_2pt", 2)
         + F(r, "receptions") * (sc.get("rec", 0) + (sc.get("bonus_rec_te", 0) if pos == "TE" else sc.get("bonus_rec_rb", 0) if pos == "RB" else sc.get("bonus_rec_wr", 0) if pos == "WR" else 0))
         + F(r, "receiving_yards") * sc.get("rec_yd", .1) + F(r, "receiving_tds") * sc.get("rec_td", 6) + F(r, "receiving_first_downs") * sc.get("rec_fd", 0)
         + F(r, "receiving_2pt_conversions") * sc.get("rec_2pt", 2)
         + (F(r, "sack_fumbles_lost") + F(r, "rushing_fumbles_lost") + F(r, "receiving_fumbles_lost")) * sc.get("fum_lost", -2))
    return p
PPR = {"pass_yd": .04, "pass_td": 4, "pass_int": -2, "rec": 1, "rec_yd": .1, "rec_td": 6, "rush_yd": .1, "rush_td": 6, "fum_lost": -2}
REPL = {"QB": 13, "RB": 30, "WR": 42, "TE": 14}
cacheW = {}
def week_pts(sk, sc, y, w, sf):
    k = (sk, y, w)
    if k in cacheW: return cacheW[k]
    rows = W.get((y, w), {}); P = {}; by = collections.defaultdict(list)
    for sid, r in rows.items():
        pos = POS.get(sid)
        if pos not in REPL: continue
        v = pts(r, sc, pos); P[sid] = v; by[pos].append(v)
    rep = {}
    for pos, xs in by.items():
        xs.sort(reverse=True); n = (25 if sf else 13) if pos == "QB" else REPL[pos]; rep[pos] = xs[n - 1] if len(xs) >= n else 0
    cacheW[k] = (P, rep); return cacheW[k]
def par(sid, sk, sc, sf, wl):
    t = 0.0; pos = POS.get(sid)
    for (y, w) in wl:
        P, rep = week_pts(sk, sc, y, w, sf)
        if sid in P: t += P[sid] - rep.get(pos, 0)
    return t
def prior_ratio(sid, sc, y):
    a = b = 0.0; n = 0; pos = POS.get(sid)
    for w in range(1, 19):
        r = W.get((y - 1, w), {}).get(sid)
        if r is None: continue
        a += pts(r, sc, pos); b += pts(r, PPR, pos); n += 1
    return (a / b) if n >= 6 and b > 30 else None
def fmtmult(pos, rank, sc, n):
    m = 1.0; te = sc.get("bonus_rec_te", 0) or 0
    if pos == "TE" and te > 0: m *= 1 + min(.3, te * .25)
    rec = sc.get("rec", 1)
    if rec is not None and rec < 1:
        k = .07 if rec == 0 else .035
        if pos == "RB": m *= 1 + k
        elif pos in ("WR", "TE"): m *= 1 - k
    if n != 12 and rank > 36: m *= 1 + (n - 12) * .025 * min(1, (rank - 36) / 120)
    return m
L = json.load(gzip.open("bt/leagues.json.gz", "rt"))["leagues"]
T = []
for l in L.values():
    if l["type"] != 2 or not (2021 <= l["season"] <= 2024): continue
    if any(p.startswith("IDP") or p in ("DL", "LB", "DB") for p in l["pos"]): continue
    sc = l["sc"]; sf = "SUPER_FLEX" in l["pos"] or l["pos"].count("QB") > 1; f = "sf" if sf else "1qb"; A = VAN["VANS" if sf else "VAN1"]
    sk = json.dumps(sorted(sc.items())) + str(sf); y = l["season"]; n = l.get("n") or 12
    for t in l.get("tx") or []:
        if t[0] != "trade" or len(t[2]) != 2 or t[5]: continue
        d0 = dt.datetime.fromtimestamp(t[8] / 1000, dt.timezone.utc).date(); i = near(d0)
        if i is None or not RK[f][i]: continue
        a, b = t[2]; got = {a: [], b: []}
        for pid, rid in (t[3] or {}).items():
            if rid in got: got[rid].append(str(pid))
        if not got[a] or not got[b]: continue
        allp = got[a] + got[b]
        if any(POS.get(p) not in REPL or p not in RK[f][i] for p in allp): continue
        w0 = max(1, t[1] or 1); wl = [(y, w) for w in range(w0, 18)] + [(y + 1, w) for w in range(1, 18)]
        out = {r: sum(par(p, sk, sc, sf, wl) for p in got[r]) for r in (a, b)}
        side = {r: [(curve(RK[f][i][p], A), fmtmult(POS[p], RK[f][i][p], sc, n), prior_ratio(p, sc, y if d0 >= dt.date(y, 9, 1) else y)) for p in got[r]] for r in (a, b)}
        T.append(dict(y=y, out=out[a] - out[b], A=side[a], B=side[b], custom=sc.get("pass_td", 4) >= 6 or (sc.get("bonus_rec_te") or 0) > 0 or sc.get("rec", 1) < 1 or any(sc.get(k) for k in ("rush_fd", "rec_fd", "pass_fd", "bonus_rec_rb", "bonus_rec_wr"))))
print("trades", len(T), "in custom-scoring leagues", sum(x["custom"] for x in T))
def vals(side, mode, g):
    s = 0.0
    for v, fm, pr in side:
        m = fm if mode == "app" or pr is None else max(.6, min(1.6, pr ** g)); s += v * m
    return s
def score(xs, mode, g):
    n = right = 0; X = []; Y = []
    for x in xs:
        va, vb = vals(x["A"], mode, g), vals(x["B"], mode, g); gap = (va - vb) / max(va, vb)
        X.append(gap); Y.append(1 if x["out"] > 0 else 0)
        if abs(gap) >= .05 and x["out"] != 0: n += 1; right += (gap > 0) == (x["out"] > 0)
    X = np.array(X); Y = np.array(Y); best = min((np.mean((1 / (1 + np.exp(-k * X)) - Y) ** 2), k) for k in np.arange(.5, 12, .25))
    return right / max(1, n), n, best[0]
tr = [x for x in T if x["y"] <= 2022]; te = [x for x in T if x["y"] >= 2023]
bestg = max([.5, .75, 1.0, 1.25, 1.5], key=lambda g: score(tr, "lg", g)[0])
print("g fitted on 2021-22:", bestg)
for name, xs in (("2021-22 (fit)", tr), ("2023-24 held out", te), ("2023-24 custom-scoring leagues", [x for x in te if x["custom"]])):
    a = score(xs, "app", 1); b = score(xs, "lg", bestg)
    print("%-32s app multipliers: right %.1f%% (n %d) Brier %.4f | league scoring: right %.1f%% Brier %.4f" % (name, 100 * a[0], a[1], a[2], 100 * b[0], b[2]))
