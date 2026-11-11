"""Report card: kickers and team defenses (key projections_kd). Standard library only.
The app shows Sleeper's weekly K and D/ST projection scored with the league's scoring (index.html kdPts / the hmProj
wrapper for positions without PJC), so app = Sleeper here; graded in Sleeper default scoring (pts_std).
backtest/e28_kd.py: no correction (implied points, spread, season average, home, dome/wind) beat Sleeper on both
held-out seasons (fit 2021-24; 2025 and 2026), so nothing is layered on top.
Population: player (K) or team (D/ST) played that week (gp) and Sleeper projected more than 0. K = position PK in ids.csv."""
import gzip, json, csv

def _rows(season, weeks, PP):
    SP = json.load(gzip.open("bt/sleeper_proj.json.gz", "rt"))["w"]; ST = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]
    pk = set()
    for r in csv.DictReader(open(PP._get("ids.csv", PP.IDS), encoding="utf-8")):
        s = str(r.get("sleeper_id") or "").split(".")[0]
        if s not in ("", "NA") and r.get("position") == "PK": pk.add(s)
    out = []; noproj = {"K": 0, "DEF": 0}
    for w in sorted(weeks):
        key = f"{season}-{w}"; P = SP.get(key) or {}; S = ST.get(key)
        if not S: continue
        for pid in sorted(S):
            st = S[pid]
            if not st or not st.get("gp"): continue
            pos = "DEF" if pid.isalpha() and pid.isupper() and 2 <= len(pid) <= 3 else ("K" if pid in pk else None)
            if not pos: continue
            pr = (P.get(pid) or {}).get("pts_std")
            if not pr or pr <= 0: noproj[pos] += 1; continue
            out.append({"w": w, "pos": pos, "sl": pr, "app": pr, "a": st.get("pts_std") or 0.0})
    return out, noproj

def section(ctx):
    season, weeks, PP = ctx["season"], list(ctx["weeks"]), ctx["PP"]
    rows, noproj = _rows(season, weeks, PP)
    res = {}
    for pos in ("K", "DEF"):
        R = [r for r in rows if r["pos"] == pos]
        if not R: continue
        mae = lambda k, xs: round(sum(abs(x["a"] - x[k]) for x in xs) / len(xs), 3)
        wk = {}
        for w in sorted({r["w"] for r in R}):
            xs = [r for r in R if r["w"] == w]
            wk[w] = {"n": len(xs), "app": mae("app", xs), "sl": mae("sl", xs)}
        res[pos] = {"n": len(R), "mae_app": mae("app", R), "mae_sleeper": mae("sl", R), "no_proj": noproj[pos],
                    "mean_proj": round(sum(r["sl"] for r in R) / len(R), 2), "mean_pts": round(sum(r["a"] for r in R) / len(R), 2), "weeks": wk}
    if not res: return {}
    res["method"] = ("app shows Sleeper's K and D/ST projection in league scoring; graded in Sleeper default scoring, played and "
                     "projected > 0. Corrections tested 2021-24 -> 2025/2026 (implied points, spread, season average, home, dome/wind) "
                     "did not beat Sleeper on both seasons, so none is applied")
    return {"projections_kd": res}

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import proj_panel
    s = max(int(k.split("-")[0]) for k in json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"])
    print(json.dumps(section({"season": s, "weeks": range(1, 19), "PP": proj_panel}), indent=1)[:1500])
