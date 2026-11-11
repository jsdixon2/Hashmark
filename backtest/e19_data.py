"""e19: D/ST and K weekly rows 2021-2026 for the streamer test.
Points = Sleeper's archived pts_std (Sleeper default scoring; K and D/ST are the same in std/half/ppr).
Projection = Sleeper's archived weekly projection (pts_std). Implied points from the closing line in
bt/nfl/schedules.csv.gz: home = total/2 + spread/2, away = total/2 - spread/2.
Writes .build/agents/b9/e19_rows.json (not committed)."""
import csv, gzip, json, os, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *a: os.path.join(ROOT, *a)
FIX = {"LA": "LAR", "OAK": "LV", "SD": "LAC", "STL": "LAR"}
fx = lambda t: FIX.get(t, t)

def load():
    P = json.load(gzip.open(J("bt/sleeper_proj.json.gz")))["w"]
    S = json.load(gzip.open(J("bt/sleeper_stats.json.gz")))["w"]
    ids = list(csv.DictReader(open(J("backtest/dl/ids.csv"))))
    s2g = {r["sleeper_id"]: r["gsis_id"] for r in ids if r["position"] == "PK" and r["sleeper_id"] not in ("", "NA")}
    # games
    G = {}  # (season, week, team) -> dict(opp, imp, opp_imp)
    for r in csv.DictReader(gzip.open(J("bt/nfl/schedules.csv.gz"), "rt")):
        if r["game_type"] != "REG": continue
        y, w = int(r["season"]), int(r["week"])
        if y < 2021: continue
        try: sp, tot = float(r["spread_line"]), float(r["total_line"])
        except ValueError: continue
        h, a = fx(r["home_team"]), fx(r["away_team"])
        ih, ia = tot / 2 + sp / 2, tot / 2 - sp / 2
        G[(y, w, h)] = {"o": a, "imp": ih, "oimp": ia}
        G[(y, w, a)] = {"o": h, "imp": ia, "oimp": ih}
    # kicker team per season-week from nflverse weekly stats (last known team carried forward/back)
    kteam = {}
    for y in range(2021, 2027):
        f = J(f"backtest/dl/pw_{y}.csv")
        if not os.path.exists(f): continue
        for r in csv.DictReader(open(f)):
            if r["position"] == "K" and r.get("season_type", "REG") == "REG":
                kteam[(y, r["player_id"], int(r["week"]))] = fx(r["team"])
    return P, S, s2g, G, kteam

def team_of_k(kteam, y, gid, w):
    if (y, gid, w) in kteam: return kteam[(y, gid, w)]
    best = None
    for d in range(1, 19):
        for ww in (w - d, w + d):
            if (y, gid, ww) in kteam: return kteam[(y, gid, ww)]
    return best

def build():
    P, S, s2g, G, kteam = load()
    rows = []
    teams = sorted({k[2] for k in G})
    for key in P:
        y, w = map(int, key.split("-"))
        if w > 18: continue
        pw, sw = P[key], S.get(key, {})
        for t in teams:  # D/ST
            g = G.get((y, w, t))
            if not g: continue
            pid = t
            pr = (pw.get(pid) or {}).get("pts_std")
            st = sw.get(pid)
            if st is None: continue  # no result logged (game not played yet)
            rows.append({"y": y, "w": w, "id": pid, "pos": "DEF", "team": t, "proj": pr, "pts": st.get("pts_std", 0.0) or 0.0,
                         "imp": g["imp"], "oimp": g["oimp"]})
        for pid, gid in s2g.items():  # K
            pr = (pw.get(pid) or {}).get("pts_std")
            st = sw.get(pid)
            if pr is None and st is None: continue
            t = team_of_k(kteam, y, gid, w)
            if not t: continue
            g = G.get((y, w, t))
            if not g: continue
            played = (y, gid, w) in kteam
            pts = (st or {}).get("pts_std", 0.0) or 0.0
            rows.append({"y": y, "w": w, "id": pid, "pos": "K", "team": t, "proj": pr, "pts": pts, "played": played,
                         "imp": g["imp"], "oimp": g["oimp"]})
    # weeks with results present (season-weeks in stats)
    done = sorted({tuple(map(int, k.split("-"))) for k in S})
    return rows, G, done

if __name__ == "__main__":
    rows, G, done = build()
    os.makedirs(J(".build/agents/b9"), exist_ok=True)
    json.dump({"rows": rows, "done": done, "G": {f"{k[0]}-{k[1]}-{k[2]}": v for k, v in G.items()}}, open(J(".build/agents/b9/e19_rows.json"), "w"))
    c = collections.Counter((r["pos"], r["y"], r["proj"] is not None) for r in rows)
    for k in sorted(c): print(k, c[k])
