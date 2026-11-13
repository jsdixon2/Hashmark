"""Data test 1 probe: what does the MySportsFeeds key (secret MSF_KEY) return? Prints status codes and the shape of
each feed (keys, counts, position labels in game lineups, update times). Never prints the key. Manual workflow."""
import base64, json, os, urllib.request, collections, sys
K = os.environ.get("MSF_KEY", "")
if not K: sys.exit("no MSF_KEY")
AUTH = "Basic " + base64.b64encode(f"{K}:MYSPORTSFEEDS".encode()).decode()
B = "https://api.mysportsfeeds.com/v2.1/pull/nfl"
def get(path):
    try:
        r = urllib.request.urlopen(urllib.request.Request(B + path, headers={"Authorization": AUTH, "Accept-Encoding": "identity"}), timeout=30)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, (e.read()[:300].decode("utf-8", "replace"))
    except Exception as e: return None, str(e)[:200]
def shape(x, d=0):
    if isinstance(x, dict): return {k: shape(v, d + 1) if d < 2 else type(v).__name__ for k, v in list(x.items())[:12]}
    if isinstance(x, list): return [len(x), shape(x[0], d + 1) if x and d < 2 else None]
    return type(x).__name__
for path in ("/2025-regular/date/20251109/games.json", "/2026-regular/date/20261108/games.json", "/injuries.json", "/2026-regular/week/10/games.json"):
    s, j = get(path); print("\n==", path, s); print(json.dumps(shape(j))[:900] if isinstance(j, dict) else j)
    if isinstance(j, dict) and j.get("lastUpdatedOn"): print("lastUpdatedOn", j["lastUpdatedOn"])
for season, date in (("2025-regular", "20251109"), ("2026-regular", "20261108")):
    s, j = get(f"/{season}/date/{date}/games.json")
    gs = (j.get("games") if isinstance(j, dict) else None) or []
    for g in gs[:2]:
        sch = g.get("schedule", {}); gid = sch.get("id")
        s2, L = get(f"/{season}/games/{gid}/lineup.json"); print("\n== lineup", season, gid, sch.get("startTime"), s2)
        if not isinstance(L, dict): print(L); continue
        print("lastUpdatedOn", L.get("lastUpdatedOn"), json.dumps(shape(L))[:700])
        for tl in L.get("teamLineups") or []:
            for kind in ("expected", "actual"):
                lp = (tl.get(kind) or {}).get("lineupPositions") or []
                c = collections.Counter(p.get("position", "?").split("-")[0] for p in lp)
                print(" ", (tl.get("team") or {}).get("abbreviation"), kind, len(lp), dict(c.most_common(12)))
s, j = get("/injuries.json")
if isinstance(j, dict):
    pl = j.get("players") or []; c = collections.Counter(((p.get("currentInjury") or {}).get("playingProbability")) for p in pl)
    print("\ninjuries players", len(pl), dict(c)); print(json.dumps((pl or [{}])[0])[:600])
