"""Data test 3: CFBD player usage (share of team plays: overall / pass / rush) and play value (PPA per play, total) for
college seasons 2014-2021 -> $X20_OUT (default /tmp/x20_cfbd.json) {"<athleteId>|<season>": {...}}. Needs CFBD_API_KEY
(repo secret): GitHub Actions only (.github/workflows/devy-usage-test.yml). 16 calls. Transfer portal is NOT pulled: CFBD has
it from 2021 only, after every training class (2016-20 drafts)."""
import json, os, sys, time, urllib.request
KEY = os.environ.get("CFBD_API_KEY", "").strip(); OUT = os.environ.get("X20_OUT", "/tmp/x20_cfbd.json")
if not KEY: sys.exit("CFBD_API_KEY not set")
H = {"Authorization": "Bearer " + KEY, "Accept": "application/json", "User-Agent": "hashmark-build"}
def get(path):
    for k in range(3):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request("https://api.collegefootballdata.com" + path, headers=H), timeout=180).read())
        except Exception as e:
            if k == 2: print("failed", path, e); return []
            time.sleep(5)
D = {}
for y in range(2014, 2022):
    us = get(f"/player/usage?year={y}&excludeGarbageTime=true"); pp = get(f"/ppa/players/season?year={y}&excludeGarbageTime=true")
    for x in us:
        u = x.get("usage") or {}; D.setdefault(f'{x.get("id")}|{y}', {}).update(uo=u.get("overall"), up=u.get("pass"), ur=u.get("rush"), u3=u.get("thirdDown"))
    for x in pp:
        a = x.get("averagePPA") or {}; t = x.get("totalPPA") or {}; D.setdefault(f'{x.get("id")}|{y}', {}).update(pa=a.get("all"), pt=t.get("all"))
    print(y, "usage", len(us), "ppa", len(pp))
json.dump(D, open(OUT, "w")); print("wrote", len(D))
