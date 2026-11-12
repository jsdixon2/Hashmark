"""Engine 8 plug-in (A3/C3, backtest e30): smooth projection ranges, honest labels, team ranges. Standard library only.

The constants below were fitted by backtest/e30_fit.py and backtest/e30_team.py (numpy/sklearn) on 2021-25 player-weeks
and league lineups; this script only re-measures them on the seasons after FIT_END each run and writes `ranges.model`,
`ranges.team`, `ranges.labels` (+ coverage) into data/report.json (merged into build_report's `ranges`; the v108 `table`
and `cuts` stay as the app's fallback).
Player model (QB/RB/WR/TE, PPR, players who played): 10/25/75/90th percentile, mean and sd of actual points as
piecewise-linear functions of the Hashmark projection (value at each knot; below the first and above the last knot the
value scales with the projection); lo/hi never fall as the projection rises. Week-to-week volatility, games played and
the questionable tag were tested as inputs and did not improve held-out pinball loss or separate realised misses, so the
range depends on position and projection only. Labels: relative half-width of the 80% range (HIGH/MEDIUM/LOW, global cuts).
Team: mean = sum of starters' means (median projections summed run ~8-10% under real scores); variance = sum var +
2 sum rho sd sd (QB with his WR/TE .23, QB-RB .07, opponents .04, other pairs ~0); K/D-ST sd linear in the projection;
asymmetric z (TZ) because real team scores land above more often than below."""
import json, gzip, math, os, csv, collections, importlib.util

MODEL = {"QB":{"k":[8,14,20,26],"q10":[0.0,5.147,10.151,14.998],"q25":[1.133,9.479,14.034,22.683],"q75":[11.825,18.652,24.761,29.204],"q90":[16.73,23.41,29.677,37.641],"mu":[6.666,14.351,19.557,25.979],"sd":[6.755,6.882,7.825,8.084]},"RB":{"k":[4,8,12,16,20],"q10":[0.0,2.035,4.865,7.039,7.787],"q25":[1.444,4.254,8.332,10.595,11.87],"q75":[7.78,13.093,18.344,21.799,24.655],"q90":[13.569,18.625,23.557,27.86,31.563],"mu":[5.46,9.461,13.573,16.827,19.179],"sd":[5.27,6.727,7.469,8.247,9.663]},"WR":{"k":[4,8,12,16,20],"q10":[0.0,1.745,3.679,6.052,6.813],"q25":[0.786,4.34,7.264,9.983,13.953],"q75":[8.816,12.986,18.246,21.693,26.427],"q90":[14.892,18.604,23.384,30.916,31.545],"mu":[5.796,9.19,13.243,16.913,20.006],"sd":[5.798,6.626,7.831,9.666,9.666]},"TE":{"k":[4,8,12,16],"q10":[0.0,1.952,4.919,4.919],"q25":[1.301,4.477,8.145,9.762],"q75":[8.22,12.235,19.018,19.018],"q90":[13.374,16.757,25.347,25.347],"mu":[5.495,9.043,13.93,14.499],"sd":[5.207,6.132,8.231,8.231]}}
CUT = [0.736, 1.164]   # relative half-width (hi-lo)/2/proj: HIGH <= .736 < MEDIUM <= 1.164 < LOW (25/50/25 of 2021-25 player-weeks)
RHO = {"all_pairs": 0.007, "same_team": -0.002, "QB-WR/TE": 0.231, "opponents": 0.039, "QB-RB": 0.067}
KD = {"K": {"bias": -0.068, "var": [20.938, 0.062]}, "DEF": {"bias": 0.22, "var": [8.185, 3.896]}}
TZ = [-1.086, 1.735]   # team range = mean + TZ x sd (fitted: 10% of 2021-25 team-weeks below, 10% above)
FIT_END = 2025
POS4 = ("QB", "RB", "WR", "TE")

def ev(c, k, m):
    s = 1.0
    if m >= k[-1]: s = m / k[-1]; m = k[-1]
    elif m < k[0]: s = m / k[0]; m = k[0]
    j = 0
    while j < len(k) - 2 and m >= k[j + 1]: j += 1
    t = (m - k[j]) / (k[j + 1] - k[j]); return s * ((1 - t) * c[j] + t * c[j + 1])

def rng(pos, m): e = MODEL[pos]; return ev(e["q10"], e["k"], m), ev(e["q90"], e["k"], m)
def label(pos, m):
    lo, hi = rng(pos, m); w = (hi - lo) / 2 / m if m > 0 else 9; return "HIGH" if w <= CUT[0] else "MEDIUM" if w <= CUT[1] else "LOW"
def player(pos, m):
    if pos in MODEL: e = MODEL[pos]; return ev(e["mu"], e["k"], m), ev(e["sd"], e["k"], m)
    if pos in KD: v = KD[pos]["var"]; return m + KD[pos]["bias"], math.sqrt(max(1.0, v[0] + v[1] * m))
    return m, max(1.5, .16 * m + 3)
def rho(a, b):
    (pa, ta, oa), (pb, tb, ob) = a, b
    if ta and ta == tb:
        if "QB" in (pa, pb):
            o = pb if pa == "QB" else pa
            return RHO["QB-WR/TE"] if o in ("WR", "TE") else RHO["QB-RB"] if o == "RB" else RHO["all_pairs"]
        return RHO["same_team"]
    if ta and ta == ob: return RHO["opponents"]
    return RHO["all_pairs"]

def section(ctx):
    season = ctx["season"]; panel = ctx["panel"]
    out = {"model": MODEL, "rel_cuts": CUT, "fit": f"2021-{FIT_END}", "method": "e30",
           "team": {"rho": RHO, "kd": KD, "z": TZ}}
    # ---- player ranges on the seasons the model never saw (proj 4+, Sleeper 3+, players who played) ----
    te = [r for r in panel if r["s"] > FIT_END and r["hm"] >= 4 and r["base"] >= 3 and r["pos"] in POS4]
    g = collections.defaultdict(lambda: [0, 0, 0, 0.0, 0.0])
    for r in te:
        lo, hi = rng(r["pos"], r["hm"]); a = r["a"]; L_ = label(r["pos"], r["hm"])
        for k in ("all", r["pos"], L_):
            x = g[k]; x[0] += 1; x[1] += a < lo; x[2] += a > hi; x[3] += abs(a - r["hm"]) / r["hm"]; x[4] += abs(a - r["hm"])
    cov = {k: {"n": x[0], "inside": round(1 - (x[1] + x[2]) / x[0], 3), "below": round(x[1] / x[0], 3), "above": round(x[2] / x[0], 3),
               "rel_err": round(x[3] / x[0], 3), "abs_err": round(x[4] / x[0], 2)} for k, x in g.items() if x[0]}
    if cov.get("all"):
        out["test_coverage_80"] = cov["all"]["inside"]; out["test_n"] = cov["all"]["n"]; out["test_seasons"] = str(season) if season == FIT_END + 1 else f"{FIT_END + 1}-{season}"
        out["labels"] = {k: cov[k] for k in ("HIGH", "MEDIUM", "LOW") if k in cov}
        out["coverage"] = {k: cov[k] for k in ("all",) + POS4 if k in cov}
    else:   # no held-out games yet: the e30 test numbers (fit 2021-24, test 2025-26, n 4,835)
        out.update({"test_coverage_80": .801, "test_n": 4835, "test_seasons": "2025-26 (fit 2021-24)",
                    "labels": {"HIGH": {"n": 1301, "inside": .775, "rel_err": .386, "abs_err": 6.35},
                               "MEDIUM": {"n": 2376, "inside": .811, "rel_err": .574, "abs_err": 5.57},
                               "LOW": {"n": 1184, "inside": .812, "rel_err": .805, "abs_err": 4.21}}})
    # ---- team ranges on real lineups (held-out seasons) ----
    try:
        spec = importlib.util.spec_from_file_location("br_e30", "scripts/build_report.py"); BR = importlib.util.module_from_spec(spec); spec.loader.exec_module(BR)
        PP = ctx["PP"]; SP = ctx["SP"]; POS = ctx["POS"]
        HMF = {"ppr": ctx["HM"]}
        for f in ("half", "std"): HMF[f] = {(r["s"], r["w"], r["pid"]): r["hm"] for r in PP.build([season], scoring=f)}
        g2s = {}
        for r in csv.DictReader(open(PP._get("ids.csv", PP.IDS), encoding="utf-8")):
            s_ = str(r.get("sleeper_id") or "").split(".")[0]
            if s_ not in ("", "NA") and r.get("gsis_id") not in ("", "NA", None): g2s[r["gsis_id"]] = s_
        tm = {}
        for r in csv.DictReader(open(PP._get(f"pw_{season}.csv", PP.NV + f"stats_player/stats_player_week_{season}.csv"), encoding="utf-8")):
            s_ = g2s.get(r["player_id"])
            if s_ and r.get("season_type") == "REG": tm[(int(r["week"]), s_)] = (r["team"], r["opponent_team"])
        def pos_of(x): return "DEF" if x.isalpha() and x.isupper() and 2 <= len(x) <= 3 else ("K" if POS.get(x) in ("K", "PK") else POS.get(x))
        res = []
        for lg in ctx["leagues"].values():
            s = int(lg["season"]); sc = lg.get("sc") or {}
            if s != season or s <= FIT_END or lg.get("guillotine") or any(k.startswith("idp") for k in sc): continue
            f = BR.fmt_of(sc); H = HMF[f]; K = BR.FMTK[f][0]; pws = lg.get("pws") or 15
            for wk, rws in lg["weeks"].items():
                w = int(wk); P = SP.get(f"{s}-{w}")
                if not P or w >= pws: continue
                for rid, mid, pt, stt in rws:
                    hit = [x for x in stt if x in P]
                    if not stt or len(hit) / len(stt) < .9 or not pt or pt <= 0: continue
                    tot = mu = 0.0; parts = []
                    for x in hit:
                        p_ = pos_of(x); m = max(0.0, (H[(s, w, x)] if (s, w, x) in H else P[x].get(K) or 0) + BR.sc_adj(P[x], sc, POS.get(x), f))
                        tot += m; a, sd = player(p_, m); mu += a
                        t = tm.get((w, x), (x, None) if p_ == "DEF" else (None, None)); parts.append(((p_, t[0], t[1]), sd))
                    var = sum(sd * sd for _, sd in parts)
                    for i in range(len(parts)):
                        for j in range(i + 1, len(parts)): var += 2 * rho(parts[i][0], parts[j][0]) * parts[i][1] * parts[j][1]
                    sd = math.sqrt(var); lo, hi = mu + TZ[0] * sd, mu + TZ[1] * sd
                    s0 = (tot * BR.WP["k"] + BR.WP["c"]) / BR.WP["b"]
                    res.append((pt < lo, pt > hi, pt < tot - 1.2816 * s0, pt > tot + 1.2816 * s0))
        if res:
            n = len(res); out["team"]["test"] = {"n": n, "season": season, "inside": round(1 - sum(r[0] + r[1] for r in res) / n, 3),
                "below": round(sum(r[0] for r in res) / n, 3), "above": round(sum(r[1] for r in res) / n, 3),
                "v112_inside": round(1 - sum(r[2] + r[3] for r in res) / n, 3), "v112_below": round(sum(r[2] for r in res) / n, 3), "v112_above": round(sum(r[3] for r in res) / n, 3)}
    except Exception as e:
        out["team"]["error"] = str(e)[:160]
    return {"ranges": out}
