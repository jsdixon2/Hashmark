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
                  "time": r.get("gametime"), "final": r.get("result") not in (None, "", "NA"), "as": num(r.get("away_score")), "hs": num(r.get("home_score"))})

# ---- kickoff weather from Open-Meteo (free, no key) for this week's open-air games ----
STAD = {"ARI":(33.528,-112.263,1),"ATL":(33.755,-84.401,1),"BAL":(39.278,-76.623,0),"BUF":(42.774,-78.787,0),"CAR":(35.226,-80.853,0),"CHI":(41.862,-87.617,0),
 "CIN":(39.095,-84.516,0),"CLE":(41.506,-81.700,0),"DAL":(32.748,-97.093,1),"DEN":(39.744,-105.020,0),"DET":(42.340,-83.046,1),"GB":(44.501,-88.062,0),
 "HOU":(29.685,-95.411,1),"IND":(39.760,-86.164,1),"JAX":(30.324,-81.637,0),"KC":(39.049,-94.484,0),"LV":(36.091,-115.184,1),"LAC":(33.953,-118.339,1),
 "LAR":(33.953,-118.339,1),"LA":(33.953,-118.339,1),"MIA":(25.958,-80.239,0),"MIN":(44.974,-93.258,1),"NE":(42.091,-71.264,0),"NO":(29.951,-90.081,1),
 "NYG":(40.814,-74.074,0),"NYJ":(40.814,-74.074,0),"PHI":(39.901,-75.168,0),"PIT":(40.447,-80.016,0),"SF":(37.403,-121.970,0),"SEA":(47.595,-122.332,0),
 "TB":(27.976,-82.503,0),"TEN":(36.166,-86.771,0),"WAS":(38.908,-76.864,0)}
def weather(games):
    import datetime as dt
    today = dt.date.today()
    for g in games:
        if g["final"] or not g.get("day"):
            continue
        try:
            d = dt.date.fromisoformat(g["day"])
        except Exception:
            continue
        if not (0 <= (d - today).days <= 7):
            continue
        st = STAD.get(g["h"])
        if not st or st[2] or "dome" in g.get("roof", "") or "closed" in g.get("roof", ""):
            continue
        try:
            hh = int((g.get("time") or "13:00").split(":")[0])
        except Exception:
            hh = 13
        u = (f"https://api.open-meteo.com/v1/forecast?latitude={st[0]}&longitude={st[1]}&hourly=temperature_2m,precipitation_probability,wind_speed_10m,wind_gusts_10m"
             f"&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=America%2FNew_York&start_date={g['day']}&end_date={g['day']}")
        try:
            j = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "hashmark-build"}), timeout=30).read())
            H = j["hourly"]; i = min(range(len(H["time"])), key=lambda k: abs(int(H["time"][k][11:13]) - hh))
            g["wx"] = {"t": H["temperature_2m"][i], "w": H["wind_speed_10m"][i], "gust": H["wind_gusts_10m"][i], "pop": H["precipitation_probability"][i], "src": "Open-Meteo"}
        except Exception as e:
            print("  weather skip", g["h"], e)
weather(games)
os.makedirs("data", exist_ok=True)
json.dump({"built": datetime.datetime.utcnow().isoformat() + "Z", "season": season, "games": games}, open("data/sched.json", "w"), separators=(",", ":"))
print(f"{len(games)} games for {season}; lines on {sum(1 for g in games if g['tot'] is not None)}")
