"""Value tests B, D, E (owner: "test all"). Base = backtest/e16_taper.py rows (early-November dates 2021-24, FantasyPros
dynasty ECR market, November redraft ECR this-season part, app production model with the shipped v118 taper 23->26).
Shipped blend: SF market .6 / this season .2 / model .2, 1QB .6/.25/.15.
Targets: real points above replacement over the next two seasons (dates 2021-23, on the app curve) = honest target;
dynasty market value one year later (dates 2021-24). Fit on 2021-22 dates, test on 2023 (production) / 2023-24 (market).
B: blend weights by position x age band (<=23 / 24-26 / 27+), grid .05 steps, fitted on production.
D: role signals (weeks 1-8 snap share, target share, WOPR) added to the value: per-position least squares on
   [shipped value, model value] vs the same plus role signals; held-out MAE / rank corr on production.
E: source accuracy. Only one value source has history (FantasyPros ECR); data/values.json's 16 sources exist from
   2026-11-07 only. Tested what can be: when experts disagree (ECR sd / rank), should the market weigh less?"""
import csv, gzip, math, statistics as st, os, itertools
from collections import defaultdict
src = open("backtest/e16_taper.py").read().split("res={}")[0]; exec(src)
import numpy as np
def spear(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b)); return float(np.corrcoef(ra, rb)[0, 1])
# role signals, weeks 1-8 of the date's season
pfr2s = {r["pfr_id"]: r["sleeper_id"] for r in csv.DictReader(open("backtest/dl/ids.csv")) if r["pfr_id"] not in ("", "NA") and r["sleeper_id"] not in ("", "NA")}
fp2s = {r["fantasypros_id"]: r["sleeper_id"] for r in csv.DictReader(open("backtest/dl/ids.csv")) if r["fantasypros_id"] not in ("", "NA") and r["sleeper_id"] not in ("", "NA")}
role = defaultdict(lambda: defaultdict(list))
for y in range(2021, 2025):
    for r in csv.DictReader(open(f"backtest/dl/pw_{y}.csv")):
        if r["season_type"] != "REG" or int(r["week"]) > 8: continue
        s = g2s.get(r["player_id"])
        if not s: continue
        for k in ("target_share", "wopr"):
            try: role[(s, y)][k].append(float(r[k]))
            except (ValueError, KeyError): pass
    for r in csv.DictReader(open(f"backtest/dl/snap_{y}.csv")):
        if r["game_type"] != "REG" or int(r["week"]) > 8: continue
        s = pfr2s.get(r["pfr_player_id"])
        if s:
            try: role[(s, y)]["snap"].append(float(r["offense_pct"]))
            except ValueError: pass
def rf(s, y, k): v = role.get((s, y), {}).get(k); return st.mean(v) if v else 0.0
# expert disagreement (ECR sd) from the monthly FantasyPros files nearest each date
def sdmap(date, typ):
    f = f"bt/nfl/ecr/{date[:7]}.csv.gz"; out = {}
    for r in csv.DictReader(gzip.open(f, "rt")):
        if r["ecr_type"] == typ and r["id"] in fp2s:
            try: out[fp2s[r["id"]]] = (float(r["sd"]), float(r["ecr"]))
            except ValueError: pass
    return out
R = {}
for fmt in ("sf", "1q"):
    F = FMT[fmt]; c = F["curve"]; rows = build(fmt); out = run(rows, fmt, "taper 23->26", R=0)   # shipped
    SD = {y: sdmap(DATES[y], "dsf" if fmt == "sf" else "do") for y in DATES if y <= 2024}
    X = []
    for x, p in out:
        X.append(dict(x=x, ship=p, mkv=c(x["mk"]), rdv=c(x["rd"]) if x["rd"] else c(450), mdv=x["m_v"], pos=x["pos"],
                      band="<=23" if x["ai"] <= 23 else "24-26" if x["ai"] <= 26 else "27+",
                      ts=rf(x["s"], x["y"], "target_share"), wo=rf(x["s"], x["y"], "wopr"), sn=rf(x["s"], x["y"], "snap"),
                      sd=SD[x["y"]].get(x["s"], (None, None))))
    fitP = [z for z in X if z["x"]["y"] <= 2022]; teP = [z for z in X if z["x"]["y"] == 2023]
    fitM = fitP; teM = [z for z in X if z["x"]["y"] >= 2023]
    def ev(xs, f, tgt):
        p = [f(z) for z in xs]; t = [z["x"]["par_v"] if tgt == "p" else z["x"]["nxv"] for z in xs]
        return st.mean(abs(a - b) for a, b in zip(p, t)), spear(p, t)
    ship = lambda z: z["ship"]
    print(f"\n===== {fmt}: {len(X)} player-dates (market top 300)")
    b0p, b0m = ev(teP, ship, "p"), ev(teM, ship, "m")
    print("shipped           test production MAE %4.0f rank %.3f | test market MAE %4.0f rank %.3f" % (*b0p, *b0m))
    # ---- B
    grid = [(a, b, round(1 - a - b, 2)) for a in np.arange(0, 1.01, .05) for b in np.arange(0, 1.01, .05) if a + b <= 1.0001]
    W = {}
    for pos in ("QB", "RB", "WR", "TE"):
        for band in ("<=23", "24-26", "27+"):
            cell = [z for z in fitP if z["pos"] == pos and z["band"] == band]
            if len(cell) < 40: W[(pos, band)] = F["W"]; continue
            W[(pos, band)] = min(grid, key=lambda w: st.mean(abs(w[0] * z["mkv"] + w[1] * z["rdv"] + w[2] * z["mdv"] - z["x"]["par_v"]) for z in cell))
    fB = lambda z: (lambda w: w[0] * z["mkv"] + w[1] * z["rdv"] + w[2] * z["mdv"])(W[(z["pos"], z["band"])])
    # one global refit for comparison (same freedom per format)
    wg = min(grid, key=lambda w: st.mean(abs(w[0] * z["mkv"] + w[1] * z["rdv"] + w[2] * z["mdv"] - z["x"]["par_v"]) for z in fitP))
    fG = lambda z: wg[0] * z["mkv"] + wg[1] * z["rdv"] + wg[2] * z["mdv"]
    print("B global refit %s  test production MAE %4.0f rank %.3f | market MAE %4.0f rank %.3f" % (tuple(round(v, 2) for v in wg), *ev(teP, fG, "p"), *ev(teM, fG, "m")))
    print("B pos x age    test production MAE %4.0f rank %.3f | market MAE %4.0f rank %.3f" % (*ev(teP, fB, "p"), *ev(teM, fB, "m")))
    print("   cell weights (market/this season/model):", {f"{k[0]} {k[1]}": tuple(round(v, 2) for v in w) for k, w in W.items()})
    for band in ("<=23", "24-26", "27+"):
        s = [z for z in teP if z["band"] == band]
        print("   test %-5s n %3d  shipped MAE %4.0f rank %.3f  pos x age MAE %4.0f rank %.3f" % (band, len(s), *ev(s, ship, "p"), *ev(s, fB, "p")))
    # ---- D
    def ols(xs, feats, tgt):
        A = np.array([[1] + [f(z) for f in feats] for z in xs]); y = np.array([z["x"]["par_v"] if tgt == "p" else z["x"]["nxv"] for z in xs])
        return np.linalg.lstsq(A, y, rcond=None)[0]
    base = [lambda z: z["ship"], lambda z: z["mdv"]]
    roles = base + [lambda z: z["ts"] * 1e4, lambda z: z["wo"] * 1e4, lambda z: z["sn"] * 1e4]
    for tgt, fit, te in (("p", fitP, teP), ("m", fitM, teM)):
        pb, pr = {}, {}
        for pos in ("QB", "RB", "WR", "TE"):
            f_ = [z for z in fit if z["pos"] == pos]; pb[pos] = ols(f_, base, tgt); pr[pos] = ols(f_, roles if pos != "QB" else base, tgt)
        fb = lambda z: float(np.dot(pb[z["pos"]], [1] + [f(z) for f in base]))
        fr = lambda z: float(np.dot(pr[z["pos"]], [1] + [f(z) for f in (roles if z["pos"] != "QB" else base)]))
        print("D %-10s refit without roles MAE %4.0f rank %.3f | with snap/target share/WOPR MAE %4.0f rank %.3f" % ("production" if tgt == "p" else "market", *ev(te, fb, tgt), *ev(te, fr, tgt)))
    # ---- E
    have = [z for z in X if z["sd"][0] is not None]
    print("E ECR sd found for %d of %d" % (len(have), len(X)))
    def fE(k):
        def f(z):
            if z["sd"][0] is None: return z["ship"]
            rel = z["sd"][0] / max(1, z["sd"][1]); w0 = F["W"]; wm = w0[0] * math.exp(-k * rel); rest = 1 - wm
            return wm * z["mkv"] + rest * (w0[1] * z["rdv"] + w0[2] * z["mdv"]) / (w0[1] + w0[2])
        return f
    kb = min([0, .25, .5, 1, 1.5, 2, 3], key=lambda k: ev(fitP, fE(k), "p")[0])
    print("E disagreement k fitted %.2f: test production MAE %4.0f rank %.3f | market MAE %4.0f rank %.3f" % (kb, *ev(teP, fE(kb), "p"), *ev(teM, fE(kb), "m")))
    # where do misses come from by disagreement tercile (shipped)?
    hs = sorted([z for z in teP if z["sd"][0] is not None], key=lambda z: z["sd"][0] / max(1, z["sd"][1]))
    for i, part in enumerate((hs[:len(hs) // 3], hs[len(hs) // 3:2 * len(hs) // 3], hs[2 * len(hs) // 3:])):
        print("   disagreement %s: shipped MAE %4.0f, market-only MAE %4.0f, model-only MAE %4.0f" % (("low", "mid", "high")[i], ev(part, ship, "p")[0], ev(part, lambda z: z["mkv"], "p")[0], ev(part, lambda z: z["mdv"], "p")[0]))
