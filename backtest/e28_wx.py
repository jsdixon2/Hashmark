"""e28: weather. Actual / replayed Hashmark projection (before multipliers, players who played, pre >= 3) by game wind
(nflverse schedules: game-time wind, roof). Kickers: actual / Sleeper projection (the app shows Sleeper for K).
Rain: optional, from the gamebook weather text in nflverse play-by-play (backtest/dl/wx_YYYY.json if present, built by
e28_wx.py --rain). Fit 2021-24, check 2025-26."""
import csv, gzip, json, os, sys, collections, statistics as stt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT); sys.path.insert(0, os.path.join(ROOT, "backtest")); sys.path.insert(0, os.path.join(ROOT, "scripts"))
import proj_panel as PP
FIX = {"LA": "LAR", "OAK": "LV", "SD": "LAC", "STL": "LAR"}; fx = lambda t: FIX.get(t, t)

def games():
    G = {}
    for r in csv.DictReader(gzip.open("bt/nfl/schedules.csv.gz", "rt")):
        if r["game_type"] != "REG" or int(r["season"]) < 2021: continue
        y, w = int(r["season"]), int(r["week"])
        dome = r["roof"] in ("dome", "closed")
        wind = None if r["wind"] in ("", "NA") else float(r["wind"])
        temp = None if r["temp"] in ("", "NA") else float(r["temp"])
        rain = None
        for t in (fx(r["home_team"]), fx(r["away_team"])): G[(y, w, t)] = {"dome": dome, "roof": r["roof"], "wind": wind, "temp": temp, "gid": r["game_id"]}
    return G

def teams():
    g2s = {}
    for r in csv.DictReader(open(PP._get("ids.csv", PP.IDS), encoding="utf-8")):
        s = str(r.get("sleeper_id") or "").split(".")[0]
        if s not in ("", "NA") and r.get("gsis_id") not in ("", "NA", None): g2s[r["gsis_id"]] = s
    T = {}
    for y in range(2021, 2027):
        for r in csv.DictReader(open(f"backtest/dl/pw_{y}.csv", encoding="utf-8")):
            s = g2s.get(r["player_id"])
            if s and r.get("season_type") == "REG": T[(y, int(r["week"]), s)] = fx(r["team"])
    return T

def band(g):
    if g is None: return None
    if g["dome"]: return "dome"
    if g["wind"] is None: return "outdoor, wind unknown"
    w = g["wind"]
    return "wind 0-9" if w < 10 else "wind 10-14" if w < 15 else "wind 15-19" if w < 20 else "wind 20+"

def wmed(R, k):
    xs = sorted((r["a"] / r[k], r[k]) for r in R if r[k] > 0); tot = sum(w for _, w in xs); c = 0
    for v, w in xs:
        c += w
        if c >= tot / 2: return v

def main():
    import e28_inj as EI, e28_kd as EK
    G = games(); T = teams()
    rows, _ = EI.panel()
    R = [r for r in rows if r["pre"] >= 3]
    rain = {}
    for y in range(2021, 2027):
        f = f".build/agents/b3/wx_{y}.json"
        if os.path.exists(f): rain.update(json.load(open(f)))
    for r in R:
        t = T.get((r["s"], r["w"], r["pid"])); g = G.get((r["s"], r["w"], t)) if t else None
        r["band"] = band(g); r["g"] = g; r["rain"] = rain.get(g["gid"]) if g else None
    K = [dict(r, pre=r["proj"], a=r["pts"], s=r["y"]) for r in EK.panel() if r["pos"] == "K" and r["proj"] and r["played"]]
    for r in K:
        g = G.get((r["y"], r["w"], r["team"])); r["band"] = band(g); r["g"] = g; r["rain"] = rain.get(g["gid"]) if g else None
    out = {}
    bands = ["dome", "wind 0-9", "wind 10-14", "wind 15-19", "wind 20+", "outdoor, wind unknown"]
    for pos in ("QB", "RB", "WR", "TE", "K", "nonRB"):
        S = K if pos == "K" else [r for r in R if (r["pos"] != "RB" if pos == "nonRB" else r["pos"] == pos)]
        print(f"\n{pos}  (weighted-median actual/projection = MAE-optimal multiplier; sum ratio)")
        for b in bands:
            line = f"  {b:22s}"
            for lab, f in (("2021-24", lambda r: r["s"] <= 2024), ("2025-26", lambda r: r["s"] >= 2025)):
                X = [r for r in S if r["band"] == b and f(r)]
                if len(X) >= 10:
                    m = wmed(X, "pre"); s = sum(r["a"] for r in X) / sum(r["pre"] for r in X)
                    line += f" | {lab} n={len(X):5d} wmed {m:.3f} sum {s:.3f}"; out[f"{pos}|{b}|{lab}"] = {"n": len(X), "wmed": round(m, 3), "sum": round(s, 3)}
                else: line += f" | {lab} n={len(X):5d}" + " " * 25
            print(line)
        if any(r["rain"] is not None for r in S):
            for rv in (True, False):
                line = f"  {'rain' if rv else 'no rain (outdoor)':22s}"
                for lab, f in (("2021-24", lambda r: r["s"] <= 2024), ("2025-26", lambda r: r["s"] >= 2025)):
                    X = [r for r in S if r["rain"] is rv and r["band"] != "dome" and f(r)]
                    if len(X) >= 10: line += f" | {lab} n={len(X):5d} wmed {wmed(X,'pre'):.3f} sum {sum(r['a'] for r in X)/sum(r['pre'] for r in X):.3f}"; out[f"{pos}|rain={rv}|{lab}"] = {"n": len(X), "wmed": round(wmed(X, 'pre'), 3)}
                print(line)
    # candidate multipliers for wind >= 15, non-RB skill players and K (K: app applies none today)
    print("\nMAE on wind >= 15 outdoor player-weeks, per season (current app: x.94 for QB/WR/TE, K untouched)")
    for pos in ("nonRB", "K"):
        S = K if pos == "K" else [r for r in R if r["pos"] != "RB"]
        W = lambda r: r["g"] and not r["g"]["dome"] and r["g"]["wind"] is not None and r["g"]["wind"] >= 15
        tr = [r for r in S if W(r) and r["s"] <= 2024]; mfit = wmed(tr, "pre")
        for y in (2021, 2022, 2023, 2024, 2025, 2026):
            X = [r for r in S if W(r) and r["s"] == y]
            if not X: continue
            line = f"  {pos:5s} {y} n={len(X):4d}"
            for m in (1.0, .94, round(mfit, 3)):
                line += f" | x{m}: {sum(abs(r['a'] - r['pre'] * m) for r in X) / len(X):.4f}"
            print(line)
        print(f"  {pos} fitted 2021-24 multiplier (wind>=15 rows only): {mfit:.3f}; calm outdoor (<10) 2021-24 {wmed([r for r in S if r['band']=='wind 0-9' and r['s']<=2024],'pre'):.3f}")
    json.dump(out, open(".build/agents/b3/e28_wx.json", "w"), indent=1)

if __name__ == "__main__": main()
