#!/usr/bin/env python3
"""Build data/sched.json: this season's NFL schedule with betting lines, from nflverse (CC-BY 4.0).
Fields per game: week, away, home, kickoff text, spread (home-favored positive), total, roof, final flag."""
import csv, io, json, os, datetime, urllib.request
URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
FIX = {"LA": "LAR", "OAK": "LV", "SD": "LAC", "STL": "LAR"}
def num(x):
    try: return float(x)
    except Exception: return None
def kick(day, t):
    try:
        h, m = map(int, t.split(":")); ap = "AM" if h < 12 else "PM"; h = h % 12 or 12
        return f"{day[:3]} {h}:{m:02d} {ap}"
    except Exception:
        return day[:3]
raw = urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "hashmark-build"}), timeout=60).read().decode()
rows = list(csv.DictReader(io.StringIO(raw)))
season = max(int(r["season"]) for r in rows if r.get("game_type") == "REG")
games = []
for r in rows:
    if int(r["season"]) != season or r.get("game_type") != "REG": continue
    a, h = FIX.get(r["away_team"], r["away_team"]), FIX.get(r["home_team"], r["home_team"])
    games.append({"wk": int(r["week"]), "a": a, "h": h, "day": r.get("gameday"), "when": kick(r.get("weekday") or "", r.get("gametime") or ""),
                  "sp": num(r.get("spread_line")), "tot": num(r.get("total_line")), "roof": r.get("roof") or "", "venue": r.get("stadium") or "",
                  "final": r.get("result") not in (None, "", "NA"), "as": num(r.get("away_score")), "hs": num(r.get("home_score"))})
os.makedirs("data", exist_ok=True)
json.dump({"built": datetime.datetime.utcnow().isoformat() + "Z", "season": season, "games": games}, open("data/sched.json", "w"), separators=(",", ":"))
print(f"{len(games)} games for {season}; lines on {sum(1 for g in games if g['tot'] is not None)}")
