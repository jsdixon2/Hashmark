"""e30 C3: matchup team range from the starters' own ranges, tested on real league lineups (bt/leagues.json.gz).
Per starter: mean mu(m) and sd(m) from the e30 player model (QB/RB/WR/TE, knots in e30_model_<FIT_END>.json), K and D/ST a
fitted linear sd (Sleeper projection vs result, 2021-24). Team mean = sum mu; variance = sum var + 2 sum rho sd sd with rho
from e30_fit (QB with his WR/TE, QB-RB, same team, opponents, any pair). Range = mean -/+ z sd; z per side fitted on 2021-24
team-weeks so 10% fall below and 10% above. Compared with v112 (sd = (proj k + c)/b around the summed projection).
usage: python3 backtest/e30_team.py  (needs e30_data.py + e30_fit.py outputs)"""
import gzip, json, os, math, collections, importlib.util, statistics as st
import numpy as np
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
W = ".build/agents/a3/work/"; FIT_END = int(os.environ.get("E30_FIT_END", "2024"))
MD = json.load(open(W + f"e30_model_{FIT_END}.json")); M = MD["M"]; RHO = MD["RHO"]
spec = importlib.util.spec_from_file_location("br", "scripts/build_report.py"); BR = importlib.util.module_from_spec(spec); spec.loader.exec_module(BR)
PP = BR.__dict__.get("PP")
spec = importlib.util.spec_from_file_location("pp", "scripts/proj_panel.py"); PP = importlib.util.module_from_spec(spec); spec.loader.exec_module(PP)
def hat_ev(c, k, m):
    s = 1.0
    if m >= k[-1]: s = m / k[-1]; m = k[-1]
    elif m < k[0]: s = m / k[0]; m = k[0]
    j = max(0, min(len(k) - 2, int(np.searchsorted(k, m, side="right") - 1))); t = (m - k[j]) / (k[j + 1] - k[j])
    return s * ((1 - t) * c[j] + t * c[j + 1])
SP = json.load(gzip.open("bt/sleeper_proj.json.gz", "rt"))["w"]; ST = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]
POS = {}
import csv
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s not in ("", "NA"): POS[s] = r["position"]
def pos_of(x): return "DEF" if x.isalpha() and x.isupper() and 2 <= len(x) <= 3 else ("K" if POS.get(x) == "PK" else POS.get(x))
# ---- K / DEF: sd of (actual - Sleeper projection) linear in the projection, fitted 2021-24 ----
KD = {}
for P_ in ("K", "DEF"):
    xs = []
    for key, P in SP.items():
        y = int(key.split("-")[0])
        if y > FIT_END: continue
        S_ = ST.get(key) or {}
        for x, pr in P.items():
            if pos_of(x) != P_ or not (pr.get("pts_ppr") or 0) > 2: continue
            a = S_.get(x)
            if a is None or not a.get("gp", 1): continue
            xs.append((pr["pts_ppr"], (a.get("pts_ppr") or 0)))
    m = np.array([x[0] for x in xs]); a = np.array([x[1] for x in xs]); X = np.c_[np.ones(len(m)), m]
    b = np.linalg.lstsq(X, a, rcond=None)[0]; v = np.linalg.lstsq(X, (a - X @ b) ** 2, rcond=None)[0]
    KD[P_] = {"bias": round(float(np.mean(a - m)), 3), "var": [round(float(v[0]), 3), round(float(v[1]), 3)], "n": len(xs)}
print("K/DEF", KD)
# ---- team/opp per player-week (for correlations) ----
D = json.load(gzip.open(W + "e30_panel.json.gz", "rt")); C = D["cols"]
TM = {(r[0], r[1], r[2]): (r[C.index("team")], r[C.index("opp")]) for r in D["rows"]}
HMF = {"ppr": PP.build(range(2021, 2027))}
for f in ("half", "std"): HMF[f] = PP.build(range(2021, 2027), scoring=f)
HMF = {f: {(r["s"], r["w"], r["pid"]): r["hm"] for r in rows} for f, rows in HMF.items()}
def player(pos, m):
    if pos in M:
        e = M[pos]; k = e["knots"]; mu = hat_ev(e["mean"], k, m); sd = hat_ev(e["sd"], k, m); return mu, sd
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
L = json.load(gzip.open("bt/leagues.json.gz", "rt"))["leagues"]; rows = []
for lg in L.values():
    s = int(lg["season"])
    if lg.get("guillotine") or s < 2021: continue
    sc = lg.get("sc") or {}; pws = lg.get("pws") or 15; f = BR.fmt_of(sc); H = HMF[f]; K = BR.FMTK[f][0]
    if any(k.startswith("idp") for k in sc): continue   # IDP starters have no projection model here (app: fallback formula)
    for wk, rws in lg["weeks"].items():
        w = int(wk); P = SP.get(f"{s}-{w}")
        if not P or w >= pws: continue
        for rid, mid, pt, stt in rws:
            hit = [x for x in stt if x in P]
            if not stt or len(hit) / len(stt) < .9 or not pt or pt <= 0: continue
            tot = 0.0; mus = 0.0; parts = []
            for x in hit:
                p_ = pos_of(x); m = (H[(s, w, x)] if (s, w, x) in H else P[x].get(K) or 0) + BR.sc_adj(P[x], sc, POS.get(x), f)
                m = max(0.0, m); tot += m; mu, sd = player(p_, m); mus += mu
                t = TM.get((s, w, x), (x, None) if p_ == "DEF" else (None, None)); parts.append(((p_, t[0], t[1]), sd))
            var = sum(sd * sd for _, sd in parts)
            for i in range(len(parts)):
                for j in range(i + 1, len(parts)): var += 2 * rho(parts[i][0], parts[j][0]) * parts[i][1] * parts[j][1]
            rows.append((s, tot, mus, math.sqrt(var), pt, f, bool(sc.get("bonus_rec_te"))))
print("team-weeks", collections.Counter(r[0] for r in rows))
tr = [r for r in rows if r[0] <= FIT_END]
zs = sorted((r[4] - r[2]) / r[3] for r in tr)
def qt(xs, p): i = (len(xs) - 1) * p; lo = int(i); return xs[lo] + (xs[min(len(xs) - 1, lo + 1)] - xs[lo]) * (i - lo)
ZL, ZH = round(qt(zs, .1), 3), round(qt(zs, .9), 3)
print("fitted z (2021-24): lo", ZL, "hi", ZH, " (normal: -1.282 / 1.282)")
WPk, WPc, WPb = .16, 5, .918
def evals(rs, name):
    out = {}
    for nm, fn in (("v112", lambda r: (r[1] - 1.2816 * (r[1] * WPk + WPc) / WPb, r[1] + 1.2816 * (r[1] * WPk + WPc) / WPb)),
                   ("starters normal", lambda r: (r[2] - 1.2816 * r[3], r[2] + 1.2816 * r[3])),
                   ("starters fitted z", lambda r: (r[2] + ZL * r[3], r[2] + ZH * r[3]))):
        b = sum(r[4] < fn(r)[0] for r in rs) / len(rs); a = sum(r[4] > fn(r)[1] for r in rs) / len(rs)
        wdt = st.mean(fn(r)[1] - fn(r)[0] for r in rs)
        out[nm] = {"n": len(rs), "inside": round(1 - a - b, 3), "below": round(b, 3), "above": round(a, 3), "width": round(wdt, 1)}
    print(name); [print("  ", k, v) for k, v in out.items()]; return out
TEAM = {str(y): evals([r for r in rows if r[0] == y], y) for y in range(2021, 2027)}
TEAM["2025-26"] = evals([r for r in rows if r[0] > FIT_END], "held out all")
for f in ("ppr", "half", "std"): TEAM["held out " + f] = evals([r for r in rows if r[0] > FIT_END and r[5] == f], "held out " + f)
TEAM["held out TE premium"] = evals([r for r in rows if r[0] > FIT_END and r[6]], "held out TE premium")
TEAM["held out no TE premium"] = evals([r for r in rows if r[0] > FIT_END and not r[6]], "held out no TE premium")
for t, (a_, b_) in enumerate([(0, 100), (100, 120), (120, 999)]):
    TEAM[f"held out proj {a_}-{b_}"] = evals([r for r in rows if r[0] > FIT_END and a_ <= r[1] < b_], f"held out summed proj {a_}-{b_}")
print("actual / summed projection (median player projections):", {y: round(sum(r[4] for r in rows if r[0] == y) / sum(r[1] for r in rows if r[0] == y), 3) for y in range(2021, 2027)})
print("actual / summed player means:", {y: round(sum(r[4] for r in rows if r[0] == y) / sum(r[2] for r in rows if r[0] == y), 3) for y in range(2021, 2027)})
json.dump({"KD": KD, "ZL": ZL, "ZH": ZH, "TEAM": TEAM}, open(W + f"e30_team_{FIT_END}.json", "w"))
