"""Report card: this season's projection MAE vs Sleeper in half-PPR and standard scoring (key projections_fmt).
Same replay as the PPR grade (scripts/proj_panel.build(scoring=...)): Sleeper projection, PPG, last 3 and actual points
in that scoring, expected points scaled by the player's PPG in that scoring / PPR PPG, the same PJC weights the app uses
in every format (backtest/e15_fit.py: format-specific weights gained <0.3% on held-out 2025-26, not shipped).
Population: Sleeper projected >= 3 in that scoring, player played; weeks with 50+ players."""

def _grade(rows, season, weeks):
    by = {}
    for r in rows:
        if r["s"] == season and r["w"] in weeks and r["base"] >= 3: by.setdefault(r["w"], []).append(r)
    wk = {}
    for w in sorted(by):
        R = by[w]
        if len(R) < 50: continue
        wk[w] = {"n": len(R), "hm": round(sum(abs(x["a"] - x["hm"]) for x in R) / len(R), 3), "sl": round(sum(abs(x["a"] - x["base"]) for x in R) / len(R), 3)}
    cur = [x for w in wk for x in by[w]]
    if not cur: return None
    n = len(cur); mh = sum(abs(x["a"] - x["hm"]) for x in cur) / n; ms = sum(abs(x["a"] - x["base"]) for x in cur) / n
    pos = {p: {"n": len(xs), "hm": round(sum(abs(x["a"] - x["hm"]) for x in xs) / len(xs), 3), "sl": round(sum(abs(x["a"] - x["base"]) for x in xs) / len(xs), 3)}
           for p in ("QB", "RB", "WR", "TE") for xs in [[x for x in cur if x["pos"] == p]] if xs}
    return {"n": n, "mae_hm": round(mh, 3), "mae_sleeper": round(ms, 3), "gain_pct": round((ms - mh) / ms * 100, 1) if ms else None,
            "weeks_beat": sum(1 for v in wk.values() if v["hm"] < v["sl"]), "n_weeks": len(wk), "by_pos": pos, "weeks": wk}

def section(ctx):
    season, weeks, PP = ctx["season"], set(ctx["weeks"]), ctx["PP"]
    out = {}
    for f in ("half", "std"):
        g = _grade(PP.build([season], scoring=f), season, weeks)
        if g: out[f] = g
    if not out: return {}
    out["method"] = "same weights as PPR, inputs in the league's scoring; Sleeper projected 3+ in that scoring, played"
    return {"projections_fmt": out}

if __name__ == "__main__":
    import json, os, sys, importlib.util
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import proj_panel
    s = max(int(k.split("-")[0]) for k in json.load(__import__("gzip").open("bt/sleeper_stats.json.gz", "rt"))["w"])
    print(json.dumps(section({"season": s, "weeks": range(1, 19), "PP": proj_panel}), indent=1)[:2000])
