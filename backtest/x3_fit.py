"""Build B: does the crowd's add/drop activity improve Hashmark's projection? Crowd = 900 real leagues (bt/rosters).
Window per week w: transactions from the Monday before week w's first game to that first kickoff (no post-game leak).
Feature: player's rank among that window's most-added (and most-dropped) players, buckets 1-10 / 11-25 / 26-60.
Model: projection + additive shift per position group x bucket, fitted as the median residual (real - Hashmark) on
2022-23, tested on 2024-25 (MAE, same player-weeks). proj_panel gives Hashmark's full projection `hm`."""
import gzip, json, csv, collections, statistics as st, sys, datetime as dt
sys.path.insert(0, "scripts"); import proj_panel as PP
rows = [r for r in PP.build(range(2022, 2026)) if r["hm"] >= 1]
R = json.load(gzip.open("bt/rosters.json.gz", "rt"))["leagues"]
first = {}
for g in csv.DictReader(open("backtest/dl/games.csv", encoding="utf-8")):
    if g["game_type"] != "REG": continue
    y, w = int(g["season"]), int(g["week"]); t = dt.datetime.fromisoformat(g["gameday"] + "T" + (g["gametime"] or "13:00")) + dt.timedelta(hours=4)  # ET -> UTC approx
    if (y, w) not in first or t < first[(y, w)]: first[(y, w)] = t
win = {k: ((v - dt.timedelta(days=3)).timestamp() * 1000, v.timestamp() * 1000) for k, v in first.items()}
A = collections.Counter(); D = collections.Counter(); nl = collections.Counter()
for l in R.values():
    y = l["season"]; nl[y] += 1
    for t in l["tx"]:
        if t[0] not in ("waiver", "free_agent"): continue
        for w in (t[1], t[1] + 1):
            ws = win.get((y, w))
            if ws and ws[0] <= t[8] < ws[1]:
                for p in t[3]: A[(y, w, p)] += 1
                for p in t[4]: D[(y, w, p)] += 1
def rankmap(C):
    by = collections.defaultdict(list)
    for (y, w, p), n in C.items(): by[(y, w)].append((n, p))
    out = {}
    for k, xs in by.items():
        for i, (n, p) in enumerate(sorted(xs, reverse=True)[:60]): out[(k[0], k[1], p)] = i + 1
    return out
RA, RD = rankmap(A), rankmap(D)
def bk(r): return None if r is None else "1-10" if r <= 10 else "11-25" if r <= 25 else "26-60"
def feat(r):
    a, d = bk(RA.get((r["s"], r["w"], r["pid"]))), bk(RD.get((r["s"], r["w"], r["pid"])))
    g = "QB" if r["pos"] == "QB" else "RB" if r["pos"] == "RB" else "WRTE"
    return (g, "add", a) if a else (g, "drop", d) if d else None
tr = [r for r in rows if r["s"] <= 2023]; te = [r for r in rows if r["s"] >= 2024]
cell = collections.defaultdict(list); base = collections.defaultdict(list)
for r in tr:
    f = feat(r); g = "QB" if r["pos"] == "QB" else "RB" if r["pos"] == "RB" else "WRTE"; base[g].append(r["a"] - r["hm"])
    if f: cell[f].append(r["a"] - r["hm"])
B = {g: st.median(v) for g, v in base.items()}
SH = {f: (len(v) * (st.median(v) - B[f[0]])) / (len(v) + 30) for f, v in cell.items()}   # shrunk shift vs the group's usual residual
for f in sorted(SH): print("|".join(f), "n", len(cell[f]), "shift %+.2f" % SH[f])
def mae(rs, use):
    return st.mean(abs(r["a"] - (r["hm"] + (SH.get(feat(r), 0) if use and feat(r) else 0))) for r in rs)
for name, rs in (("2024-25 all", te), ("2024-25 flagged only", [r for r in te if feat(r)])):
    print(name, "n", len(rs), "MAE Hashmark %.3f -> with crowd %.3f" % (mae(rs, False), mae(rs, True)))
for y in (2024, 2025):
    rs = [r for r in te if r["s"] == y]; print(y, "MAE %.3f -> %.3f" % (mae(rs, False), mae(rs, True)))
json.dump({"|".join(f): round(v, 2) for f, v in SH.items()}, open("backtest/x3_fit.json", "w"))
idx = {(r["s"], r["w"], r["pid"]): r for r in rows}
for per, rs in (("2022-23", tr), ("2024-25", te)):
    G = collections.defaultdict(list)
    for r in rs:
        f = feat(r)
        if not f or f[2] == "26-60": f = ("all", "none", "") if not f else None
        if not f: continue
        xs = [idx.get((r["s"], r["w"] + k, r["pid"])) for k in (0, 1, 2)]; xs = [x for x in xs if x]
        G[(f[1], f[0] if f[1] != "none" else "")].append(st.mean(x["a"] - x["hm"] for x in xs))
    print(per, " ".join("%s %s %+.2f (n %d)" % (k[0], k[1], st.mean(v), len(v)) for k, v in sorted(G.items())))
