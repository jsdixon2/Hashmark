"""Trade value over time: can we forecast where a player's (and a trade side's) dynasty value goes?
Data: bt/hv.json.gz FantasyPros dynasty consensus 2019-26 (1QB 'do', SF 'dsf' from 2020-10), app value curves VAN1/VANS.
Off-list (rank > list length) = value of rank 450. Start = any archive date, player ranked <= 250.
Horizons 60/180/300/365/730/1095 days (end date within 21 days of an archive date).
Cell = fmt x pos x age band (rookie/<=23/24-26/27-29/30+) x tier (<=36/37-100/101-250) x phase (Sep-Dec / Jan-Apr /
May-Aug) x horizon; stores deciles of log(value later / value now); falls back to coarser cells when n < 30.
STRICT split: train paths END before 2023-01-01; test paths START on/after 2023-01-01.
Tests: player band coverage (10-90%), value error of the model median vs "value stays the same"; real trades from
bt/rosters.json.gz (player-only, every player listed): which side holds more value later, and coverage of the band for
the side difference (independent draws from each player's cell)."""
import gzip, json, csv, datetime as dt, collections, statistics as st, math, re, random, sys
random.seed(7)
H = json.load(gzip.open("bt/hv.json.gz", "rt")); D = [dt.date.fromisoformat(x) for x in H["d"]]; IDS = H["ids"]
src = open("index.html", encoding="utf-8").read()
VAN = {k: json.loads(re.search(r"const %s=(\[\[.*?\]\]);" % k, src).group(1)) for k in ("VAN1", "VANS")}
def curve(r, A):
    if r <= 1: return A[0][1]
    for (r1, v1), (r2, v2) in zip(A, A[1:]):
        if r <= r2: t = (math.log(r) - math.log(r1)) / (math.log(r2) - math.log(r1)); return math.exp(math.log(v1) + t * (math.log(v2) - math.log(v1)))
    return 5
info = {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s not in ("", "NA") and r.get("birthdate") not in ("", "NA", None): info[s] = (r.get("position"), dt.date.fromisoformat(r["birthdate"][:10]), r.get("draft_year"))
FM = {"1qb": ("do", VAN["VAN1"]), "sf": ("dsf", VAN["VANS"])}
RK = {}
for f, (k, A) in FM.items():
    RK[f] = [({IDS[j]: n + 1 for n, j in enumerate(T)} if T else None) for T in H["t"][k]]
def val(f, i, pid):
    R = RK[f][i]; A = FM[f][1]; return curve(R.get(pid, 450), A)
def near(d):
    i = min(range(len(D)), key=lambda i: abs((D[i] - d).days)); return i if abs((D[i] - d).days) <= 21 else None
HZ = [60, 180, 300, 365, 730, 1095]
def cellkey(f, pid, i, rank):
    pos, bd, dy = info[pid]; d = D[i]; season = d.year if d.month >= 5 else d.year - 1
    age = (d - bd).days / 365.25
    ab = "R" if dy == str(season) else "23" if age < 24 else "26" if age < 27 else "29" if age < 30 else "30"
    return (f, pos, ab, "a" if rank <= 36 else "b" if rank <= 100 else "c", "S" if d.month >= 9 else "P" if d.month <= 4 else "U")
paths = []
for f in FM:
    for i in range(len(D)):
        R = RK[f][i]
        if not R: continue
        for pid, rank in R.items():
            if rank > 250 or pid not in info or info[pid][0] not in ("QB", "RB", "WR", "TE"): continue
            v0 = curve(rank, FM[f][1]); ck = cellkey(f, pid, i, rank)
            for h in HZ:
                j = near(D[i] + dt.timedelta(days=h))
                if j is None or j <= i or not RK[f][j]: continue
                paths.append((ck, h, D[i], D[j], pid, v0, val(f, j, pid), f, i))
print("paths", len(paths))
CUT = dt.date(2023, 1, 1)
train = [p for p in paths if p[3] < CUT]; test = [p for p in paths if p[2] >= CUT]
print("train", len(train), "test", len(test))
QS = [.05, .1, .2, .3, .4, .5, .6, .7, .8, .9, .95]
def quant(xs):
    xs = sorted(xs); n = len(xs); return [xs[min(n - 1, int(q * n))] for q in QS]
def fit(rows):
    G = collections.defaultdict(list)
    for ck, h, d0, d1, pid, v0, v1, f, i in rows:
        lr = math.log(v1 / v0)
        for lvl, key in enumerate((ck + (h,), ck[:4] + (h,), ck[:3] + (h,), (ck[0], ck[1], h), (ck[0], h))): G[(lvl,) + key].append(lr)
    return {k: (len(v), quant(v)) for k, v in G.items() if len(v) >= 30}
def look(M, ck, h):
    for lvl, key in enumerate((ck + (h,), ck[:4] + (h,), ck[:3] + (h,), (ck[0], ck[1], h), (ck[0], h))):
        m = M.get((lvl,) + key)
        if m: return m[1]
    return None
M = fit(train)
print("\nPLAYERS (held out, starts 2023-01 on)")
print("horizon  n      inside 10-90%   value error: model median vs value-stays-flat")
for h in HZ:
    T = [p for p in test if p[1] == h]
    if not T: print(h, "no test paths"); continue
    ins = em = ef = 0; n = 0
    for ck, hh, d0, d1, pid, v0, v1, f, i in T:
        q = look(M, ck, h)
        if not q: continue
        n += 1; lr = math.log(v1 / v0); ins += q[1] <= lr <= q[9]; em += abs(v0 * math.exp(q[5]) - v1); ef += abs(v0 - v1)
    print("%5dd %6d   %5.1f%%          %6.0f vs %6.0f  (%+.1f%%)" % (h, n, 100 * ins / n, em / n, ef / n, 100 * (em / ef - 1)))
# real trades
R_ = json.load(gzip.open("bt/rosters.json.gz", "rt"))["leagues"]
trades = []
for l in R_.values():
    f = "sf" if "SUPER_FLEX" in l["pos"] or l["pos"].count("QB") > 1 else "1qb"
    if l["type"] not in (1, 2): continue   # keeper/dynasty only
    for t in l["tx"]:
        if t[0] != "trade" or len(t[2]) != 2 or t[5]: continue
        d0 = dt.datetime.utcfromtimestamp(t[8] / 1000).date()
        if d0 < CUT: continue
        i = near(d0)
        if i is None or not RK[f][i]: continue
        sides = {r: [p for p, rr in t[3].items() if rr == r] for r in t[2]}
        ps = [p for v in sides.values() for p in v]
        if not ps or any(p not in RK[f][i] or p not in info or RK[f][i][p] > 250 for p in ps) or any(not v for v in sides.values()): continue
        trades.append((f, i, list(sides.values())))
print("\nREAL TRADES (keeper/dynasty, player-only, 2023+):", len(trades))
print("horizon  n     side ahead later picked right: model / flat   band for the difference: inside 10-90%")
for h in HZ:
    n = rm = rf = ins = 0
    for f, i, (A, B) in trades:
        j = near(D[i] + dt.timedelta(days=h))
        if j is None or not RK[f][j]: continue
        def side(ps):
            now = sum(curve(RK[f][i][p], FM[f][1]) for p in ps); later = sum(val(f, j, p) for p in ps)
            qs = [look(M, cellkey(f, p, i, RK[f][i][p]), h) for p in ps]; return now, later, qs, ps
        a, b = side(A), side(B)
        if any(q is None for q in a[2] + b[2]): continue
        med = lambda s: sum(curve(RK[f][i][p], FM[f][1]) * math.exp(q[5]) for p, q in zip(s[3], s[2]))
        if abs(a[1] - b[1]) < .05 * max(a[1], b[1]): continue    # near-ties later: skip for "who's ahead"
        n += 1; act = a[1] > b[1]; rm += (med(a) > med(b)) == act; rf += (a[0] > b[0]) == act
        sims = []
        for _ in range(300):
            draw = lambda s: sum(curve(RK[f][i][p], FM[f][1]) * math.exp(random.choice(q)) for p, q in zip(s[3], s[2]))
            sims.append(draw(a) - draw(b))
        sims.sort(); ins += sims[30] <= a[1] - b[1] <= sims[269]
    if n: print("%5dd %5d   %5.1f%% / %5.1f%%                       %5.1f%%" % (h, n, 100 * rm / n, 100 * rf / n, 100 * ins / n))
json.dump({"|".join(map(str, k)): [n, [round(x, 4) for x in q]] for k, (n, q) in fit(paths).items()}, open("backtest/x9_fit.json", "w"))
