"""x22 (owner: value-over-time for young players looked too pessimistic; "run the test"). Value paths as x9 (bt/hv.json.gz
FantasyPros dynasty consensus, app curves, start rank <= 250, off-list = rank 450), horizons 1/2/3 years.
Models for the median of log(value later / value now):
  A  shipped x9 cells: fmt x pos x age band x tier (<=36/37-100/101-250) x phase, every snapshot a row, fallback n < 30
  B  smooth: same group without the tier; Gaussian kernel on log(rank) (bandwidth .4), each PLAYER weighted once per group
     (1 / his snapshots), shrunk toward the fmt x pos x horizon kernel by effective players (w = n / (n + 15))
  C  B + player signals for the residual (per position x horizon, least squares): young (<= 3rd NFL season) x log(draft
     pick) (undrafted 300), last COMPLETED season's PPR points per game percentile within position (6+ games; none = flag)
Honest splits: (1) leave-one-start-season-out 2020-2023 (season = Mar-Feb); (2) strict x9 split: fit on paths that END
before 2023, test paths that START 2023+ (1 and 2 years only; 3-year paths cannot be split strictly). Scores: value error
(model median vs actual), rank correlation of predicted vs actual later value, young players (rookie/<=23) separately;
real keeper/dynasty trades (bt/rosters.json.gz, player-only): which side holds more value later (5%+ apart).
Season stats: nflverse stats_player_reg_<y>.csv in $X22_DL (default /tmp/x22)."""
import gzip, json, csv, datetime as dt, collections, math, re, os, sys
import numpy as np
exec(open("backtest/x9_paths.py").read().split("paths = []")[0])    # loaders, curve, info, FM, RK, val, near, cellkey
DL = os.environ.get("X22_DL", "/tmp/x22")
HZ = [365, 730, 1095]
g2s = {}; pick = {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s not in ("", "NA") and r.get("gsis_id") not in ("", "NA", None): g2s[r["gsis_id"]] = s
for r in csv.DictReader(gzip.open("bt/nfl/draft_picks.csv.gz", "rt")):
    s = g2s.get(r["gsis_id"])
    if s and r["pick"] not in ("", "NA"): pick[s] = int(r["pick"])
PCT = {}   # (season, sid) -> PPG percentile within position (6+ games)
for y in range(2016, 2026):
    rows = []
    for r in csv.DictReader(open(f"{DL}/reg_{y}.csv", encoding="utf-8")):
        s = g2s.get(r["player_id"]); g = float(r["games"] or 0)
        if s and g >= 6 and r["position"] in ("QB", "RB", "WR", "TE"): rows.append((r["position"], s, float(r["fantasy_points_ppr"] or 0) / g))
    for p in ("QB", "RB", "WR", "TE"):
        xs = sorted(v for q, s, v in rows if q == p)
        for q, s, v in rows:
            if q == p: PCT[(y, s)] = sum(1 for x in xs if x <= v) / len(xs)
def fseason(d): return d.year if d.month >= 3 else d.year - 1
paths = []
for f in FM:
    for i in range(len(D)):
        R = RK[f][i]
        if not R: continue
        for pid, rank in R.items():
            if rank > 250 or pid not in info or info[pid][0] not in ("QB", "RB", "WR", "TE"): continue
            ck = cellkey(f, pid, i, rank); v0 = curve(rank, FM[f][1]); d0 = D[i]
            last = d0.year - 1 if d0.month < 9 else d0.year - 1          # last COMPLETED season before the start date
            if d0.month <= 2: last = d0.year - 2 if d0.month < 2 else d0.year - 1
            dy = info[pid][2]; young = dy not in ("", "NA", None) and int(float(dy)) >= fseason(d0) - 2
            pc = PCT.get((last, pid))
            x = [1.0 if young else 0.0, (math.log(pick.get(pid, 300)) if young else 0.0), pc if pc is not None else 0.0, 1.0 if pc is None else 0.0]
            for h in HZ:
                j = near(d0 + dt.timedelta(days=h))
                if j is None or j <= i or not RK[f][j]: continue
                paths.append(dict(f=f, pos=ck[1], ab=ck[2], ti=ck[3], ph=ck[4], h=h, rank=rank, lr=math.log(val(f, j, pid) / v0), v0=v0, v1=val(f, j, pid),
                                  pid=pid, d0=d0, d1=D[j], s=fseason(d0), x=x, i=i))
print("paths", len(paths))
# ---------- A: x9 cells
def fitA(rows):
    G = collections.defaultdict(list)
    for p in rows:
        ck = (p["f"], p["pos"], p["ab"], p["ti"], p["ph"])
        for lvl, key in enumerate((ck + (p["h"],), ck[:4] + (p["h"],), ck[:3] + (p["h"],), (ck[0], ck[1], p["h"]), (ck[0], p["h"]))): G[(lvl,) + key].append(p["lr"])
    return {k: float(np.median(v)) for k, v in G.items() if len(v) >= 30}
def predA(M, p):
    ck = (p["f"], p["pos"], p["ab"], p["ti"], p["ph"])
    for lvl, key in enumerate((ck + (p["h"],), ck[:4] + (p["h"],), ck[:3] + (p["h"],), (ck[0], ck[1], p["h"]), (ck[0], p["h"]))):
        if (lvl,) + key in M: return M[(lvl,) + key]
    return 0.0
# ---------- B: kernel on log rank, player-weighted, shrunk
BW = .4
def fitB(rows):
    G = collections.defaultdict(list)
    for p in rows:
        G[("g", p["f"], p["pos"], p["ab"], p["ph"], p["h"])].append(p); G[("c", p["f"], p["pos"], p["h"])].append(p)
    M = {}
    for k, xs in G.items():
        cnt = collections.Counter(p["pid"] for p in xs)
        lr = np.array([p["lr"] for p in xs]); lk = np.log([p["rank"] for p in xs]); w = np.array([1.0 / cnt[p["pid"]] for p in xs]); o = np.argsort(lr)
        M[k] = (lr[o], lk[o], w[o]);
    return {"G": M, "memo": {}}
def kmed(arr, x):
    lr, lk, w = arr; ww = w * np.exp(-((lk - x) ** 2) / (2 * BW * BW)); tot = ww.sum()
    if tot <= 0: return 0.0, 0.0
    c = np.cumsum(ww); return float(lr[np.searchsorted(c, tot / 2)]), float(tot)
def predB(M, p):
    key = (p["f"], p["pos"], p["ab"], p["ph"], p["h"], p["rank"])
    if key in M["memo"]: return M["memo"][key]
    x = math.log(p["rank"]); g = M["G"].get(("g", p["f"], p["pos"], p["ab"], p["ph"], p["h"])); c = M["G"].get(("c", p["f"], p["pos"], p["h"]))
    mc, _ = kmed(c, x) if c else (0.0, 0)
    if g: mg, n = kmed(g, x); w = n / (n + 15); m = w * mg + (1 - w) * mc
    else: m = mc
    M["memo"][key] = m; return m
# ---------- C: B + residual regression per pos x h
def fitC(rows, MB):
    out = {}
    for pos in ("QB", "RB", "WR", "TE"):
        for h in HZ:
            xs = [p for p in rows if p["pos"] == pos and p["h"] == h]
            if len(xs) < 200: continue
            cnt = collections.Counter(p["pid"] for p in xs)
            X = np.array([[1.0] + p["x"] for p in xs]); y = np.array([p["lr"] - predB(MB, p) for p in xs]); w = np.sqrt(np.array([1.0 / cnt[p["pid"]] for p in xs]))
            A_ = X * w[:, None]; b_ = y * w; lam = np.eye(X.shape[1]) * 2.0; lam[0, 0] = 0
            out[(pos, h)] = np.linalg.solve(A_.T @ A_ + lam, A_.T @ b_)
    return out
def predC(MB, MC, p):
    b = MC.get((p["pos"], p["h"])); return predB(MB, p) + (float(np.dot(b, [1.0] + p["x"])) if b is not None else 0.0)
def spear(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b)); return float(np.corrcoef(ra, rb)[0, 1])
def score(test, preds):
    out = {}
    for name, sel in (("all", lambda p: True), ("young", lambda p: p["ab"] in ("R", "23"))):
        T = [(p, q) for p, q in zip(test, preds) if sel(p)]
        if not T: continue
        pv = [p["v0"] * math.exp(q) for p, q in T]; av = [p["v1"] for p, q in T]
        out[name] = (len(T), float(np.mean(np.abs(np.array(pv) - np.array(av)))), spear(pv, av), float(np.median([q - p["lr"] for p, q in T])))
    return out
# real trades
R_ = json.load(gzip.open("bt/rosters.json.gz", "rt"))["leagues"]; TR = []
for l in R_.values():
    f = "sf" if "SUPER_FLEX" in l["pos"] or l["pos"].count("QB") > 1 else "1qb"
    if l["type"] not in (1, 2): continue
    for t in l["tx"]:
        if t[0] != "trade" or len(t[2]) != 2 or t[5]: continue
        d0 = dt.datetime.utcfromtimestamp(t[8] / 1000).date(); i = near(d0)
        if i is None or not RK[f][i]: continue
        sides = {r: [p for p, rr in t[3].items() if rr == r] for r in t[2]}; ps = [p for v in sides.values() for p in v]
        if not ps or any(p not in RK[f][i] or p not in info or RK[f][i][p] > 250 for p in ps) or any(not v for v in sides.values()): continue
        TR.append((f, i, list(sides.values())))
PIDX = {(p["f"], p["i"], p["pid"], p["h"]): p for p in paths}
def trades(sel_i, preds_fn):
    res = {}
    for h in HZ:
        n = r = 0
        for f, i, (A, B) in TR:
            if not sel_i(D[i]): continue
            pa = [PIDX.get((f, i, x, h)) for x in A]; pb = [PIDX.get((f, i, x, h)) for x in B]
            if any(q is None for q in pa + pb): continue
            la = sum(q["v1"] for q in pa); lb = sum(q["v1"] for q in pb)
            if abs(la - lb) < .05 * max(la, lb): continue
            ma = sum(q["v0"] * math.exp(preds_fn(q)) for q in pa); mb = sum(q["v0"] * math.exp(preds_fn(q)) for q in pb)
            n += 1; r += (ma > mb) == (la > lb)
        res[h] = (n, r / n if n else None)
    return res
def report(tag, train, test, sel_i):
    MA = fitA(train); MB = fitB(train); MC = fitC(train, MB)
    fns = {"A shipped": lambda p: predA(MA, p), "B smooth": lambda p: predB(MB, p), "C +signals": lambda p: predC(MB, MC, p), "flat": lambda p: 0.0}
    print(f"\n=== {tag}: train {len(train)} test {len(test)}")
    for h in HZ:
        T = [p for p in test if p["h"] == h]
        if not T: continue
        print(f"  {h // 365} yr")
        for nm, fn in fns.items():
            sc = score(T, [fn(p) for p in T])
            print("    %-11s all: n %6d err %5.0f rank %.3f bias %+.2f | young: n %5d err %5.0f rank %.3f bias %+.2f" % (nm, *sc["all"], *sc.get("young", (0, 0, 0, 0))))
    for nm, fn in fns.items():
        tr = trades(sel_i, fn); print("    trades %-11s " % nm + "  ".join(f"{h // 365}yr {v[1] * 100:.1f}% (n {v[0]})" for h, v in tr.items() if v[0]))
    return MC
# (1) leave one start season out
for S in (2020, 2021, 2022, 2023):
    test = [p for p in paths if p["s"] == S]; train = [p for p in paths if p["s"] != S]
    MC = report(f"leave season {S} out", train, test, lambda d, S=S: fseason(d) == S)
# (2) strict
CUT = dt.date(2023, 1, 1)
MC = report("strict: fit on paths ending before 2023, test starts 2023+", [p for p in paths if p["d1"] < CUT], [p for p in paths if p["d0"] >= CUT], lambda d: d >= CUT)
print("C coefficients (fit on strict train) [1, young, young*log(pick), ppg pct, no ppg]:", {f"{k[0]} {k[1]}": [round(x, 3) for x in v] for k, v in MC.items()})
