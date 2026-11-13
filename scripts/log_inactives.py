"""Data test 1 (timing): does Sleeper's player list show game-day inactives, and when? Run by .github/workflows/inactives-log.yml
4 times on a Sunday (before inactives, after the 1 pm / 4 pm / night inactives). Each run stores the injury status of every
QB/RB/WR/TE on an NFL team (Sleeper ids + status only) as a snapshot in bt/inactives/<date>.json.gz; MySportsFeeds
injuries too if MSF_KEY is set. backtest/x18_timing.py grades snapshots against who actually played (nflverse)."""
import base64, gzip, json, os, time, urllib.request, datetime as dt
now = dt.datetime.now(dt.timezone.utc); day = (now - dt.timedelta(hours=10)).date().isoformat()   # Monday-night run files under Sunday
OUT = f"bt/inactives/{day}.json.gz"; os.makedirs("bt/inactives", exist_ok=True)
D = json.load(gzip.open(OUT, "rt")) if os.path.exists(OUT) else {"day": day, "snaps": []}
def get(u, h=None): return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=h or {"User-Agent": "hashmark-build"}), timeout=60).read())
snap = {"t": now.isoformat(timespec="seconds"), "sleeper": {}}
P = get("https://api.sleeper.app/v1/players/nfl")
for pid, p in P.items():
    if p.get("team") and p.get("position") in ("QB", "RB", "WR", "TE"):
        snap["sleeper"][pid] = [p.get("injury_status"), p.get("practice_participation"), p.get("status")]
K = os.environ.get("MSF_KEY")
if K:
    try:
        a = "Basic " + base64.b64encode(f"{K}:MYSPORTSFEEDS".encode()).decode()
        j = get("https://api.mysportsfeeds.com/v2.1/pull/nfl/injuries.json", {"Authorization": a})
        snap["msf"] = {str(x["player"].get("externalMappings") or x["player"]["id"]): (x.get("currentInjury") or {}).get("playingProbability") for x in j.get("players", [])}
    except Exception as e: snap["msf_err"] = str(e)[:100]
D["snaps"].append(snap)
with gzip.open(OUT, "wt") as f: json.dump(D, f, separators=(",", ":"))
from collections import Counter
print(day, "snapshots", len(D["snaps"]), Counter(v[0] for v in snap["sleeper"].values()).most_common(8))
