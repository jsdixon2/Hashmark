"""Build A fit: expected November -> May (and -> September) dynasty value change by position x age band x rank tier,
from FantasyPros dynasty 1QB/SF consensus (bt/hv.json.gz). Fit Novembers 2019-22, test 2023-24 (Nov -> May).
Value = app curve (VAN1 / VANS). Output backtest/x7_fit.json with the cells refit on all years."""
import gzip, json, csv, datetime as dt, collections, statistics as st, math, re
H = json.load(gzip.open("bt/hv.json.gz", "rt")); D = [dt.date.fromisoformat(x) for x in H["d"]]; IDS = H["ids"]
src = open("index.html", encoding="utf-8").read()
VAN = {k: json.loads(re.search(r"const %s=(\[\[.*?\]\]);" % k, src).group(1)) for k in ("VAN1", "VANS")}
def val(r, A):
    if r <= 1: return A[0][1]
    for (r1, v1), (r2, v2) in zip(A, A[1:]):
        if r <= r2: t = (math.log(r) - math.log(r1)) / (math.log(r2) - math.log(r1)); return math.exp(math.log(v1) + t * (math.log(v2) - math.log(v1)))
    return 5
info = {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s not in ("", "NA"): info[s] = (r.get("position"), r.get("birthdate"), r.get("draft_year"))
def near(d):
    i = min(range(len(D)), key=lambda i: abs((D[i] - d).days)); return i if abs((D[i] - d).days) <= 20 else None
def band(pos, age, rookie): return "R" if rookie else ("23" if age < 24 else "26" if age < 27 else "29" if age < 30 else "30")
def tier(r): return "a" if r <= 60 else "b"
rows = []
for fmt, key, A in (("1qb", "do", VAN["VAN1"]), ("sf", "dsf", VAN["VANS"])):
    T = H["t"][key]
    for Y in range(2019, 2026):
        a, b, c = near(dt.date(Y, 11, 12)), near(dt.date(Y + 1, 5, 15)), near(dt.date(Y + 1, 9, 5))
        if a is None or b is None or not T[a] or not T[b]: continue
        rk = lambda i: {IDS[k]: j + 1 for j, k in enumerate(T[i])}
        RA, RB = rk(a), rk(b); RC = rk(c) if c is not None and T[c] else None
        for pid, r in RA.items():
            if r > 200 or pid not in info: continue
            pos, bd, dy = info[pid]
            if pos not in ("QB", "RB", "WR", "TE") or not bd or bd == "NA": continue
            age = (dt.date(Y, 11, 12) - dt.date.fromisoformat(bd[:10])).days / 365.25; v0 = val(r, A)
            rows.append(dict(fmt=fmt, y=Y, pid=pid, cell=(fmt, pos, band(pos, age, dy == str(Y)), tier(r)), r=r,
                             may=math.log(val(RB.get(pid, 600), A) / v0), sep=math.log(val(RC.get(pid, 600), A) / v0) if RC else None))
def fit(rs, k="may"):
    g = collections.defaultdict(list)
    for x in rs:
        if x[k] is not None: g[x["cell"]].append(x[k])
    # shrink each cell's median toward the format-wide median with n/(n+10)
    allm = {f: st.median(x[k] for x in rs if x["fmt"] == f and x[k] is not None) for f in ("1qb", "sf")}
    return {c: (len(v) * st.median(v) + 10 * allm[c[0]]) / (len(v) + 10) for c, v in g.items()}, allm
tr = [x for x in rows if x["y"] <= 2022]; te = [x for x in rows if x["y"] in (2023, 2024)]
M, allm = fit(tr)
def spear(a, b):
    ra = {i: r for r, i in enumerate(sorted(range(len(a)), key=lambda i: a[i]))}; rb = {i: r for r, i in enumerate(sorted(range(len(b)), key=lambda i: b[i]))}
    n = len(a); return 1 - 6 * sum((ra[i] - rb[i]) ** 2 for i in range(n)) / (n * (n * n - 1))
for f in ("1qb", "sf"):
    T = [x for x in te if x["fmt"] == f and x["cell"] in M]
    pr = [M[x["cell"]] - allm[f] for x in T]; ac = [x["may"] for x in T]
    flag = [x for x, p in zip(T, pr) if p <= -.25]; rest = [x for x, p in zip(T, pr) if p > -.25]
    print(f, "held-out 2023-24 n", len(T), "rank corr predicted vs real Nov->May %.2f" % spear(pr, ac),
          "| flagged (expected 25%%+ worse than market): real median %+.0f%% (n %d) vs others %+.0f%%" % (100 * (math.exp(st.median(x["may"] for x in flag)) - 1), len(flag), 100 * (math.exp(st.median(x["may"] for x in rest)) - 1)),
          "| flagged that fell more than the others' median: %.0f%%" % (100 * sum(x["may"] < st.median(y["may"] for y in rest) for x in flag) / len(flag)))
Mall, alla = fit(rows); Sall, alls = fit(rows, "sep")
out = {"note": "log value change Nov->May / Nov->Sep, cell = fmt|pos|ageband(R,23,26,29,30)|tier(a<=60,b)", "may": {"|".join(c): round(v, 3) for c, v in Mall.items()},
       "sep": {"|".join(c): round(v, 3) for c, v in Sall.items()}, "mkt_may": {k: round(v, 3) for k, v in alla.items()}, "mkt_sep": {k: round(v, 3) for k, v in alls.items()}}
json.dump(out, open("backtest/x7_fit.json", "w"), indent=0)
for c in sorted(Mall): print("|".join(c), "%+.0f%%" % (100 * (math.exp(Mall[c] - alla[c[0]]) - 1)), end="  ")
print()
for f in ("1qb", "sf"):
    T = [x for x in te if x["fmt"] == f and x["cell"] in M]; pr = [M[x["cell"]] - allm[f] for x in T]
    up = [x for x, p in zip(T, pr) if p >= .15]; mid = [x for x, p in zip(T, pr) if -.25 < p < .15]
    print(f, "held-out expected +15%%+: real median %+.0f%% (n %d) vs middle %+.0f%%" % (100 * (math.exp(st.median(x["may"] for x in up)) - 1), len(up), 100 * (math.exp(st.median(x["may"] for x in mid)) - 1)))
