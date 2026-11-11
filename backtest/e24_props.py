"""Task B2 step 4: QB props share. 2026 only (bt/props_hist). Shipped QB formula h0 blended with a props estimate at weights
0-.5: app formula (pass yds x .04 + flat 1.6 TD x 4 + rush yds x .1 + anytime TD x 6) vs pass-TD line (passtd x 4 - INT
allowance .8 when the line exists). Matching as backtest/e14_props.py. Week-block bootstrap of the gain."""
import os, json, gzip, csv, re, sys, io, runpy, numpy as np
B = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(B)
_o = sys.stdout; sys.stdout = io.StringIO(); ns = runpy.run_path(f"{B}/e24_fit.py"); sys.stdout = _o
df = ns["df"]; d = df[df.season == 2026].copy()
norm = lambda s: re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s.lower()))
nm = {}
for r in csv.DictReader(open(f"{B}/dl/ids.csv")):
    s = str(r["sleeper_id"]).split(".")[0]
    if s not in ("", "NA") and r["position"] == "QB": nm.setdefault(norm(r["name"]), []).append(s)
P = json.load(gzip.open(f"{R}/bt/props_hist.json.gz", "rt")); names = P["names"]
sched = {}
for r in csv.DictReader(gzip.open(f"{R}/bt/nfl/schedules.csv.gz", "rt")):
    if r["season"] == "2026" and r["game_type"] == "REG": sched[(r["home_team"], r["away_team"])] = int(r["week"])
FIX = {"LA": "LAR", "WSH": "WAS"}; props = {}
for g in P["games"].values():
    w = sched.get((FIX.get(g["home"], g["home"]), FIX.get(g["away"], g["away"])))
    if not w: continue
    for oid, pr in g["p"].items():
        n = names.get(oid)
        if not n: continue
        last, _, first = n.partition(", "); c = nm.get(norm(first + " " + last)) or []
        if len(c) == 1: props[(w, c[0])] = pr
def mk(pr, ptd):
    if pr.get("passyd") is None: return None
    td = 1.6 if (not ptd or pr.get("passtd") is None) else pr["passtd"]
    return pr["passyd"] * .04 + td * 4 + (pr.get("rushyd") or 0) * .1 + (pr.get("td") or 0) * 6 - (.8 if ptd else 0)
d["pa"] = [mk(props[(w, p)], False) if (w, p) in props else None for w, p in zip(d.week, d.pid)]
d["pt"] = [mk(props[(w, p)], True) if (w, p) in props else None for w, p in zip(d.week, d.pid)]
d["haspt"] = [((w, p) in props and props[(w, p)].get("passtd") is not None) for w, p in zip(d.week, d.pid)]
e = d[d.pa.notna()].copy(); M = lambda p: round(float(np.mean(np.abs(e.actual - p))), 3)
out = {"n": len(e), "n_with_passtd_line": int(e.haspt.sum()), "weeks": sorted(map(int, e.week.unique())), "sleeper": M(e.base), "shipped_no_props": M(e.h0),
       "props_only_app": M(e.pa), "props_only_passtd": M(e.pt)}
for col in ("pa", "pt"):
    for wt in (0, .1, .2, .3, .4, .5): out[f"{col}_{wt}"] = M(e.h0 * (1 - wt) + e[col] * wt)
print(json.dumps(out, indent=1))
rng = np.random.default_rng(0)
def ci(p1, p0):
    g = np.abs(e.actual - p0) - np.abs(e.actual - p1); wk = sorted(e.week.unique()); gs = [g[e.week == w].values for w in wk]
    bs = [np.mean(np.concatenate([gs[i] for i in rng.integers(0, len(gs), len(gs))])) for _ in range(2000)]
    return round(float(g.mean()), 3), np.round(np.percentile(bs, [2.5, 97.5]), 3).tolist()
for lab, p1, p0 in [("pt .1 vs pa .1 (shipped)", e.h0 * .9 + e.pt * .1, e.h0 * .9 + e.pa * .1), ("pt .3 vs pa .1", e.h0 * .7 + e.pt * .3, e.h0 * .9 + e.pa * .1),
                    ("pa .1 vs none", e.h0 * .9 + e.pa * .1, e.h0)]:
    out["gain " + lab] = ci(p1, p0); print(lab, out["gain " + lab])
json.dump(out, open(f"{B}/e24_props.json", "w"), indent=1)
