"""Data test (owner "test 1 and 2"), test 1: do contracts add to dynasty value? x17 setup (e16 rows: early-November
2021-24, FantasyPros dynasty ECR, shipped blend market/this season/model, v118 taper). Contract at the date
(bt/nfl/contracts.csv.gz, OverTheCap via nflverse; latest contract signed in or before that season):
share of the cap (apy_cap_pct), years left after this season, guaranteed share, rookie deal, no contract.
Per-position least squares on [shipped value, model value] vs the same + contract features; fit 2021-22 dates, test
2023 (real points over the next 2 seasons) and 2023-24 (market value 1 year later). Also: cut-risk group (age 28+,
<= 1 year left, guaranteed share < .35) vs others, residual vs the shipped value."""
import csv, gzip, math, statistics as st
exec(open("backtest/x17_value.py").read().split("R = {}")[0])
C = {}
for r in csv.DictReader(gzip.open("bt/nfl/contracts.csv.gz", "rt")):
    s = g2s.get(r["gsis_id"])
    if not s or r["year_signed"] in ("", "NA"): continue
    try: C.setdefault(s, []).append((int(r["year_signed"]), int(float(r["years"] or 0)), float(r["value"] or 0), float(r["guaranteed"] or 0), float(r["apy_cap_pct"] or 0), r["draft_year"]))
    except ValueError: pass
def cfeat(s, y):
    cs = [c for c in C.get(s, []) if c[0] <= y]
    if not cs: return [0, 0, 0, 0, 1]
    ys, n, v, g, cap, dy = max(cs)
    left = max(0, min(6, ys + n - (y + 1))); rook = 1 if dy not in ("", "NA") and str(ys) == str(dy).split(".")[0] else 0
    return [cap, left, g / v if v > 0 else 0, rook, 0]
for fmt in ("sf", "1q"):
    F = FMT[fmt]; c = F["curve"]; rows = build(fmt); out = run(rows, fmt, "taper 23->26", R=0)
    X = [dict(x=x, ship=p, mdv=x["m_v"], pos=x["pos"], cf=cfeat(x["s"], x["y"])) for x, p in out]
    fitP = [z for z in X if z["x"]["y"] <= 2022]; teP = [z for z in X if z["x"]["y"] == 2023]; teM = [z for z in X if z["x"]["y"] >= 2023]
    def ev(xs, f, tgt):
        p = [f(z) for z in xs]; t = [z["x"]["par_v"] if tgt == "p" else z["x"]["nxv"] for z in xs]
        return st.mean(abs(a - b) for a, b in zip(p, t)), spear(p, t)
    print(f"\n===== {fmt}: {len(X)} player-dates; contract found for {sum(1 for z in X if not z['cf'][4])}")
    base = lambda z: [1, z["ship"], z["mdv"]]; withc = lambda z: base(z) + [z["cf"][0] * 1e4, z["cf"][1] * 300, z["cf"][2] * 3000, z["cf"][3] * 3000, z["cf"][4] * 3000]
    for tgt, fit, te in (("p", fitP, teP), ("m", fitP, teM)):
        res = {}
        for nm, fe in (("refit, no contract", base), ("with contract", withc)):
            W = {}
            for pos in ("QB", "RB", "WR", "TE"):
                f_ = [z for z in fit if z["pos"] == pos]; A = np.array([fe(z) for z in f_]); y = np.array([z["x"]["par_v"] if tgt == "p" else z["x"]["nxv"] for z in f_])
                W[pos] = np.linalg.lstsq(A, y, rcond=None)[0]
            res[nm] = ev(te, lambda z, W=W, fe=fe: float(np.dot(W[z["pos"]], fe(z))), tgt)
        print("  %-10s shipped MAE %4.0f rank %.3f | refit MAE %4.0f rank %.3f | + contract MAE %4.0f rank %.3f" % ("production" if tgt == "p" else "market", *ev(te, lambda z: z["ship"], tgt), *res["refit, no contract"], *res["with contract"]))
    # cut-risk group, all years, production residual
    for tgt in ("p", "m"):
        rr = lambda z: (z["x"]["par_v"] if tgt == "p" else z["x"]["nxv"]) - z["ship"]
        pool = [z for z in X if (tgt == "m" or z["x"]["prodok"]) and z["x"]["ai"] >= 28]
        cr = [rr(z) for z in pool if not z["cf"][4] and z["cf"][1] <= 1 and z["cf"][2] < .35]; ot = [rr(z) for z in pool if not (not z["cf"][4] and z["cf"][1] <= 1 and z["cf"][2] < .35)]
        if cr and ot: print("  age 28+, <=1 yr left, <35%% guaranteed: n %d median miss vs %s %+.0f | other 28+: n %d %+.0f" % (len(cr), "production" if tgt == "p" else "market 1 yr later", st.median(cr), len(ot), st.median(ot)))
