"""e30 (A3/C3): smooth projection ranges, honest labels, team ranges from the starters. Fit 2021-24, test 2025 and 2026.
Needs backtest/e30_data.py output (.build/agents/a3/work/e30_panel.json.gz). numpy + sklearn (fitting only); the fitted
constants go into scripts/rpt_ranges.py. Writes .build/agents/a3/work/e30_model.json and prints the result tables."""
import gzip, json, os, sys, math, collections, importlib.util
import numpy as np
from sklearn.linear_model import QuantileRegressor
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
W = ".build/agents/a3/work/"
D = json.load(gzip.open(W + "e30_panel.json.gz", "rt")); R = [dict(zip(D["cols"], r)) for r in D["rows"]]
R = [r for r in R if r["hm"] >= 1 and r["base"] >= 1]
POS4 = ("QB", "RB", "WR", "TE")
KN = {"QB": [8, 14, 20, 26], "RB": [4, 8, 12, 16, 20], "WR": [4, 8, 12, 16, 20], "TE": [4, 8, 12, 16]}   # finer knots (every 2 pts) tested: noisier, WR 84.7% held out
FIT_END = int(os.environ.get("E30_FIT_END", "2024"))   # 2024: test 2025 and 2026; 2025: the shipped refit, test 2026
QS = (.1, .25, .75, .9)

def hat(m, k):
    """piecewise-linear (hat) basis: coefficient j = value at knot j; outside the knots the curve scales with m"""
    out = np.zeros(len(k)); s = 1.0
    if m >= k[-1]: s = m / k[-1]; m = k[-1]
    elif m < k[0]: s = m / k[0]; m = k[0]
    j = max(0, min(len(k) - 2, int(np.searchsorted(k, m, side="right") - 1))); t = (m - k[j]) / (k[j + 1] - k[j])
    out[j] = (1 - t) * s; out[j + 1] = t * s; return out
def ev(c, k, m): return float(hat(m, k) @ np.array(c))

def fit_player(rows, half=None):
    """half: recency weighting, a season counts half as much as the next one (None = equal weights)"""
    M = {}
    for pos in POS4:
        tr = [r for r in rows if r["pos"] == pos]; k = KN[pos]
        X = np.array([hat(r["hm"], k) for r in tr]); y = np.array([r["a"] for r in tr]); e = {}
        sw = np.array([.5 ** (max(x["s"] for x in tr) - r["s"]) if half else 1.0 for r in tr])
        for q in QS:
            c = QuantileRegressor(quantile=q, alpha=0, fit_intercept=False, solver="highs").fit(X, y, sample_weight=sw).coef_
            c = np.maximum.accumulate(np.maximum(c, 0))   # lo/hi never fall as the projection rises
            e[str(q)] = [round(float(v), 3) for v in c]
        mu = np.linalg.lstsq(X, y, rcond=None)[0]; mu = np.maximum.accumulate(np.maximum(mu, 0))
        res2 = (y - X @ mu) ** 2; v = np.maximum(np.linalg.lstsq(X, res2, rcond=None)[0], 1); sd = np.maximum.accumulate(np.sqrt(v))
        e["mean"] = [round(float(x), 3) for x in mu]; e["sd"] = [round(float(x), 3) for x in sd]; e["knots"] = k
        M[pos] = e
    return M

def rng(M, pos, m):
    e = M[pos]; k = e["knots"]; return ev(e["0.1"], k, m), ev(e["0.9"], k, m)

# ---------- the v108 cells (same recipe as build_report.py) for comparison ----------
def vol(r):
    if r["n"] < 4: return "new"
    if r["mu"] is None or r["mu"] <= 0: return "lo"
    cv = r["sd"] / r["mu"]; return "lo" if cv < .45 else "mid" if cv < .7 else "hi"
def tier(h): return 0 if h < 8 else 1 if h < 14 else 2
def qt(xs, p):
    xs = sorted(xs); i = (len(xs) - 1) * p; lo = int(i); hi = min(len(xs) - 1, lo + 1); return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)
def fit_cells(rows):
    cells = collections.defaultdict(list)
    for r in rows:
        if r["hm"] < 4 or r["base"] < 3: continue
        cells[(r["pos"], tier(r["hm"]), vol(r), r["q"])].append(r["a"] / r["hm"])
    return {k: (qt(v, .1), qt(v, .9)) for k, v in cells.items() if len(v) >= 60}
def cell_rng(T, r):
    k = (r["pos"], tier(r["hm"]), vol(r), r["q"])
    for kk in (k, k[:3] + (0,), (k[0], k[1], "mid", 0)):
        if kk in T: return T[kk][0] * r["hm"], T[kk][1] * r["hm"]
    return None

def pin(y, q, t): d = y - q; return max(t * d, (t - 1) * d)

def calibrate(M, rows):
    """per position, stretch the lower and upper side (distance from the knot projection) so exactly 10% of the training
    player-weeks (proj 4+, Sleeper 3+) fall below and 10% above; then keep lo/hi monotone"""
    for pos in POS4:
        e = M[pos]; k = e["knots"]; xs = [r for r in rows if r["pos"] == pos]
        for q, side in (("0.1", -1), ("0.9", 1)):
            c0 = np.array(e[q]); kk = np.array(k, float)
            def share(f):
                c = kk + f * (c0 - kk); v = [ev(c, k, r["hm"]) for r in xs]
                return np.mean([r["a"] < x for r, x in zip(xs, v)]) if side < 0 else np.mean([r["a"] > x for r, x in zip(xs, v)])
            lo_, hi_ = .5, 2.0
            for _ in range(30):
                mid = (lo_ + hi_) / 2
                if share(mid) > .1: lo_ = mid   # too many outside -> widen (bigger f)
                else: hi_ = mid
            # widening = larger f for both sides (c0 - kk is negative below, positive above)
            f = (lo_ + hi_) / 2; c = np.maximum.accumulate(np.maximum(kk + f * (c0 - kk), 0))
            e[q] = [round(float(v), 3) for v in c]; e["f" + q] = round(f, 3)
    return M
dom = lambda r: r["hm"] >= 4 and r["base"] >= 3
tr = [r for r in R if r["s"] <= FIT_END]; T = fit_cells(tr)
M = fit_player([r for r in tr if r["base"] >= 3])   # calibrate() tested: factors ~1, the zero floor makes it jumpy; not used
# label: relative half-width of the 80% range; cuts at the 25th / 75th percentile of training player-weeks (proj 4+, global)
def relw(pos, m): lo, hi = rng(M, pos, m); return (hi - lo) / 2 / m
ws = sorted(relw(r["pos"], r["hm"]) for r in tr if dom(r)); CUT = [round(qt(ws, .25), 3), round(qt(ws, .75), 3)]
def lab(pos, m): w = relw(pos, m); return "HIGH" if w <= CUT[0] else "MEDIUM" if w <= CUT[1] else "LOW"

print("== player ranges: 80% range, held out (proj 4+, Sleeper 3+) ==")
def cov_table(rows, name):
    g = collections.defaultdict(lambda: [0, 0, 0, 0.0, 0.0, 0.0, 0.0])   # n, below, above, pin10 new, pin90 new, pin10 cells, pin90 cells
    for r in rows:
        lo, hi = rng(M, r["pos"], r["hm"]); c = cell_rng(T, r)
        if not c: continue
        for key in ("all", r["pos"], lab(r["pos"], r["hm"]), "q" if r["q"] else "-", "new" if r["n"] < 4 else "est"):
            x = g[key]; x[0] += 1; x[1] += r["a"] < lo; x[2] += r["a"] > hi
            x[3] += pin(r["a"], lo, .1); x[4] += pin(r["a"], hi, .9); x[5] += pin(r["a"], c[0], .1); x[6] += pin(r["a"], c[1], .9)
    out = {}
    for k, x in g.items():
        n = x[0]; out[k] = {"n": n, "inside": round(1 - (x[1] + x[2]) / n, 3), "below": round(x[1] / n, 3), "above": round(x[2] / n, 3),
                            "pinball": round((x[3] + x[4]) / n, 3), "pinball_cells": round((x[5] + x[6]) / n, 3)}
    print(name); [print("  ", k, v) for k, v in out.items()]; return out
TY = [y for y in (2025, 2026) if y > FIT_END]; TEST = lambda r: r["s"] > FIT_END and dom(r)
COV = {y: cov_table([r for r in R if r["s"] == y and dom(r)], y) for y in TY}
COV["test"] = cov_table([r for r in R if TEST(r)], "test " + "-".join(map(str, TY)))
# old cells coverage for reference
oc = [r for r in R if TEST(r) and cell_rng(T, r)]
print("cells coverage test", round(np.mean([cell_rng(T, r)[0] <= r["a"] <= cell_rng(T, r)[1] for r in oc]), 3), len(oc))

print("== realised error by label within projection tier, held out (abs pts | % of proj) ==")
ERR = {}
for t, (a, b) in enumerate([(4, 8), (8, 14), (14, 99)]):
    for L_ in ("HIGH", "MEDIUM", "LOW"):
        xs = [r for r in R if TEST(r) and a <= r["hm"] < b and lab(r["pos"], r["hm"]) == L_]
        if xs: ERR[f"{t}|{L_}"] = {"n": len(xs), "abs": round(np.mean([abs(r["a"] - r["hm"]) for r in xs]), 2), "rel": round(np.mean([abs(r["a"] - r["hm"]) / r["hm"] for r in xs]), 3)}
for k, v in ERR.items(): print("  tier", k, v)
LABS = {}
for L_ in ("HIGH", "MEDIUM", "LOW"):
    xs = [r for r in R if TEST(r) and lab(r["pos"], r["hm"]) == L_]
    LABS[L_] = {"n": len(xs), "share": None, "inside": COV["test"][L_]["inside"], "rel_err": round(np.mean([abs(r["a"] - r["hm"]) / r["hm"] for r in xs]), 3),
                "abs_err": round(np.mean([abs(r["a"] - r["hm"]) for r in xs]), 2)}
nT = sum(v["n"] for v in LABS.values())
for v in LABS.values(): v["share"] = round(v["n"] / nT, 3)
print("labels", LABS); print("label share by position", {p: collections.Counter(lab(p, r["hm"]) for r in R if TEST(r) and r["pos"] == p) for p in POS4})

print("== does the player's own volatility / games / questionable separate misses? (norm-relative test, held out) ==")
# full linear quantile model with volatility, games, questionable; label = width vs same-level norm (avg player)
def feat(r):
    cv = (r["sd"] / max(r["mu"], 1)) if r["n"] >= 4 and r["sd"] is not None else .6
    return [r["hm"], math.sqrt(r["hm"]), r["hm"] * (min(cv, 1.5) - .6), r["hm"] * r["q"], r["hm"] * (r["n"] < 4)]
VT = {}
for pos in POS4:
    X = np.array([feat(r) for r in tr if r["pos"] == pos]); y = np.array([r["a"] for r in tr if r["pos"] == pos]); cf = {}
    for q in (.1, .9): f = QuantileRegressor(quantile=q, alpha=0, solver="highs").fit(X, y); cf[q] = (f.intercept_, f.coef_)
    te = [r for r in R if TEST(r) and r["pos"] == pos]
    def w_(f): return (cf[.9][0] + f @ cf[.9][1]) - (cf[.1][0] + f @ cf[.1][1])
    ratio = np.array([w_(np.array(feat(r))) / w_(np.array([r["hm"], math.sqrt(r["hm"]), 0, 0, 0])) for r in te])
    q1, q3 = np.quantile(ratio, [.25, .75])
    for t, (a, b) in enumerate([(4, 8), (8, 14), (14, 99)]):
        for nm, sel in (("tighter", ratio <= q1), ("norm", (ratio > q1) & (ratio < q3)), ("wider", ratio >= q3)):
            xs = [r for r, s_, in zip(te, sel) if s_ and a <= r["hm"] < b]
            if len(xs) >= 30: VT[f"{pos}|{t}|{nm}"] = {"n": len(xs), "rel": round(np.mean([abs(r["a"] - r["hm"]) / r["hm"] for r in xs]), 3)}
for k, v in VT.items(): print("  ", k, v)

# ---------- correlations between starters (standardised residuals, 2021-24) ----------
def z(r):
    e = M[r["pos"]]; k = e["knots"]; return (r["a"] - ev(e["mean"], k, r["hm"])) / ev(e["sd"], k, r["hm"])
for r in R: r["z"] = z(r)
wk = collections.defaultdict(list)
for r in tr: wk[(r["s"], r["w"])].append(r)
def corr(pairs):
    a = np.array(pairs); return round(float(np.sum(a[:, 0] * a[:, 1]) / math.sqrt(np.sum(a[:, 0] ** 2) * np.sum(a[:, 1] ** 2))), 3), len(a)
cats = collections.defaultdict(list); s_all = s2 = n_all = 0
for key, rs in wk.items():
    zz = np.array([r["z"] for r in rs]); s_all += (zz.sum() ** 2 - (zz ** 2).sum()) / 2; s2 += (zz ** 2).sum() * (len(zz) - 1) / 2; n_all += len(zz) * (len(zz) - 1) / 2
    for i in range(len(rs)):
        for j in range(i + 1, len(rs)):
            a, b = rs[i], rs[j]
            if not a["team"] or not b["team"]: continue
            if a["team"] == b["team"]:
                pp = "".join(sorted([a["pos"], b["pos"]])) if "QB" in (a["pos"], b["pos"]) else "same"
                c = "QB-" + ("WR/TE" if any(p in ("WR", "TE") for p in (a["pos"], b["pos"]) if p != "QB") else "RB") if "QB" in (a["pos"], b["pos"]) else "same_team"
                cats[c].append((a["z"], b["z"]))
            elif a["team"] == b["opp"]: cats["opponents"].append((a["z"], b["z"]))
RHO = {"all_pairs": round(s_all / s2, 3)}
for c, v in cats.items(): RHO[c] = corr(v)[0]; print("  rho", c, corr(v))
print("  rho all pairs (week effect)", RHO["all_pairs"], int(n_all))

json.dump({"M": M, "CUT": CUT, "COV": COV, "ERR": ERR, "LABS": LABS, "VT": VT, "RHO": RHO}, open(W + f"e30_model_{FIT_END}.json", "w"))

print("== single factors, held out: realised |miss| / projection, relative to the same position x tier average (1.00 = typical) ==")
te = [r for r in R if TEST(r)]; base_ = collections.defaultdict(list)
for r in te: base_[(r["pos"], tier(r["hm"]))].append(abs(r["a"] - r["hm"]) / r["hm"])
bm = {k: np.mean(v) for k, v in base_.items()}
cvs = sorted(r["sd"] / max(r["mu"], 1) for r in te if r["n"] >= 4 and r["sd"] is not None); c1, c2 = qt(cvs, 1 / 3), qt(cvs, 2 / 3)
def grp(r):
    g = ["questionable" if r["q"] else "not questionable", "under 4 games" if r["n"] < 4 else "4+ games"]
    if r["n"] >= 4 and r["sd"] is not None:
        cv = r["sd"] / max(r["mu"], 1); g.append("steady (CV low third)" if cv <= c1 else "swingy (CV top third)" if cv > c2 else "CV middle third")
    return g
FAC = collections.defaultdict(lambda: collections.defaultdict(list))
for r in te:
    for g in grp(r): FAC[g][tier(r["hm"])].append(abs(r["a"] - r["hm"]) / r["hm"] / bm[(r["pos"], tier(r["hm"]))])
FACT = {g: {str(t): [round(float(np.mean(v)), 3), len(v)] for t, v in sorted(d.items())} for g, d in FAC.items()}
for g, d in FACT.items(): print("  ", g, d)
mj = json.load(open(W + f"e30_model_{FIT_END}.json")); mj["FACT"] = FACT; json.dump(mj, open(W + f"e30_model_{FIT_END}.json", "w"))
