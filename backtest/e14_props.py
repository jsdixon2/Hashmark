"""Engine 1 refit, step 3: does blending betting props (bt/props_hist.json.gz, 2026 closing lines, median of DK/FD/Caesars)
into the refit projection help? Compares the app's props formula (yards only, receptions = rec yards / 11.5, QB 1.6 TD) with a
full one (receptions and pass-TD lines), at blend weights 0-0.5. Same population as e14_fit (Sleeper proj 3+, played)."""
import os, json, gzip, csv, re, numpy as np, pandas as pd
B = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(B)
import importlib.util
spec = importlib.util.spec_from_file_location("f", f"{B}/e14_fit.py")
df = pd.read_pickle(f"{B}/e14_panel.pkl"); df = df[(df.base >= 3) & (df.season == 2026)].copy()
newC = json.load(open(f"{B}/e14_fit.json"))["new_PJC"]
src = open(f"{B}/e14_fit.py").read(); ns = {"__file__": f"{B}/e14_fit.py"}; exec(src.split("tr = df[")[0].replace('df = pd.read_pickle(f"{B}/e14_panel.pkl"); df = df[df.base >= 3].copy()', ""), ns)
PJC = ns["PJC"]; C = dict(newC); C["QB"] = PJC["QB"]
df["m"] = ns["app"](df, C)
norm = lambda s: re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s.lower()))
nm = {}
for r in csv.DictReader(open(f"{B}/dl/ids.csv")):
    s = str(r["sleeper_id"]).split(".")[0]
    if s in ("", "NA") or r["position"] not in ("QB", "RB", "WR", "TE"): continue
    nm.setdefault(norm(r["name"]), []).append(s)
P = json.load(gzip.open(f"{R}/bt/props_hist.json.gz", "rt")); names = P["names"]
sched = {}
for r in csv.DictReader(gzip.open(f"{R}/bt/nfl/schedules.csv.gz", "rt")):
    if r["season"] == "2026" and r["game_type"] == "REG": sched[(r["home_team"], r["away_team"])] = int(r["week"])
FIX = {"LA": "LAR", "WSH": "WAS"}
props = {}
for g in P["games"].values():
    h, a = g["home"], g["away"]; w = sched.get((h, a)) or sched.get((FIX.get(h, h), FIX.get(a, a)))
    if not w: continue
    for oid, pr in g["p"].items():
        n = names.get(oid)
        if not n: continue
        last, _, first = n.partition(", "); c = nm.get(norm(first + " " + last)) or []
        if len(c) == 1: props[(w, c[0])] = pr
def app_mk(pr):
    mk = k = 0
    if pr.get("recyd") is not None: mk += pr["recyd"] * .1 + pr["recyd"] / 11.5; k += 1
    if pr.get("rushyd") is not None: mk += pr["rushyd"] * .1; k += 1
    if pr.get("passyd") is not None: mk += pr["passyd"] * .04 + 1.6 * 4; k += 1
    if pr.get("td") is not None: mk += pr["td"] * 6
    return mk if k else None
def full_mk(pr):
    mk = k = 0
    if pr.get("recyd") is not None: mk += pr["recyd"] * .1 + (pr.get("rec") if pr.get("rec") is not None else pr["recyd"] / 11.5); k += 1
    if pr.get("rushyd") is not None: mk += pr["rushyd"] * .1; k += 1
    if pr.get("passyd") is not None: mk += pr["passyd"] * .04 + (pr.get("passtd") if pr.get("passtd") is not None else 1.6) * 4 - .8; k += 1
    if pr.get("td") is not None and pr.get("passyd") is None: mk += pr["td"] * 6
    elif pr.get("td") is not None: mk += pr["td"] * 6
    return mk if k else None
df["pa"] = [app_mk(props[(w, p)]) if (w, p) in props else None for w, p in zip(df.week, df.pid)]
df["pf"] = [full_mk(props[(w, p)]) if (w, p) in props else None for w, p in zip(df.week, df.pid)]
d = df[df.pa.notna()].copy(); print("player-weeks with props:", len(d), "of", len(df), "weeks", sorted(d.week.unique()))
out = {"n": len(d), "sleeper": round(float(np.mean(np.abs(d.actual - d.base))), 3), "refit": round(float(np.mean(np.abs(d.actual - d.m))), 3)}
for col in ("pa", "pf"):
    for wt in (.1, .2, .3, .5, 1):
        p = d.m * (1 - wt) + d[col] * wt; out[f"{col}_{wt}"] = round(float(np.mean(np.abs(d.actual - p))), 3)
by = {}
for pos in ("QB", "RB", "WR", "TE"):
    e = d[d.pos == pos]
    if len(e): by[pos] = {"n": len(e), "refit": round(float(np.mean(np.abs(e.actual - e.m))), 3), **{f"pf_{wt}": round(float(np.mean(np.abs(e.actual - (e.m * (1 - wt) + e.pf * wt)))), 3) for wt in (.2, .3, .5)}}
out["by_pos"] = by; print(json.dumps(out, indent=1)); json.dump(out, open(f"{B}/e14_props.json", "w"), indent=1)
