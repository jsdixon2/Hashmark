"""Time Machine Draft data (v177): every QB/RB/WR/TE who scored PPR points in a regular season 1999-<last>, split by the
team he scored them for (a traded player counts for each team), with the season line, college, draft year and Sleeper
id (for the "on your roster" bonus). Source: nflverse player stats (weekly files, CC-BY 4.0) + nflverse players +
DynastyProcess id map. Writes data/tm.json (compact arrays; the app loads it only when the game is opened).
Run: python3 scripts/build_tm.py [first_season] [last_season]   (default 1999 .. last completed season)"""
import csv, io, json, sys, gzip, urllib.request, datetime as dt
from concurrent.futures import ThreadPoolExecutor
UA = {"User-Agent": "hashmark-build"}
WEEK = "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{}.csv"
PLAYERS = "https://github.com/nflverse/nflverse-data/releases/download/players/players.csv"
IDS = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
def get(u, tries=3):
    for k in range(tries):
        try: return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read().decode("utf-8", "replace")
        except Exception as e:
            if k == tries - 1: raise
now = dt.date.today()
last_done = now.year - 1 if now.month < 3 else now.year - 1  # a season is complete by February of the next year
first = int(sys.argv[1]) if len(sys.argv) > 1 else 1999
last = int(sys.argv[2]) if len(sys.argv) > 2 else last_done
F = lambda r, k: float(r.get(k) or 0) if (r.get(k) or "") not in ("", "NA") else 0.0
def season(y):
    try: txt = get(WEEK.format(y))
    except Exception as e: print("skip", y, e); return y, {}
    agg = {}
    for r in csv.DictReader(io.StringIO(txt)):
        if r.get("season_type") != "REG": continue
        pos = r.get("position") or ""; pos = "RB" if pos == "FB" else pos
        if pos not in ("QB", "RB", "WR", "TE"): continue
        tm = r.get("team") or r.get("recent_team") or ""; pid = r.get("player_id") or ""
        if not tm or not pid: continue
        k = (pid, tm); a = agg.get(k)
        if not a: a = agg[k] = {"pid": pid, "name": r.get("player_display_name") or r.get("player_name") or "", "pos": pos, "tm": tm, "wk": set(), "s": [0.0] * 11}
        a["wk"].add(r.get("week")); s = a["s"]
        for i, key in enumerate(("fantasy_points_ppr", "attempts", "completions", "passing_yards", "passing_tds", "passing_interceptions", "carries", "rushing_yards", "rushing_tds", "receptions", "receiving_yards")):
            s[i] += F(r, key)
        a.setdefault("wtd", 0.0); a["wtd"] += F(r, "receiving_tds"); a.setdefault("tgt", 0.0); a["tgt"] += F(r, "targets")
    return y, agg
with ThreadPoolExecutor(6) as ex: res = dict(ex.map(season, range(first, last + 1)))
# players: college, draft year; sleeper ids
meta = {}
try:
    for r in csv.DictReader(io.StringIO(get(PLAYERS))):
        g = r.get("gsis_id") or ""
        if g: meta[g] = (r.get("college_name") or r.get("college") or "", r.get("draft_year") or "")
except Exception as e:
    print("players.csv from nflverse failed, using bt/nfl/players.csv.gz:", e)
    for r in csv.DictReader(gzip.open("bt/nfl/players.csv.gz", "rt")):
        if r.get("gsis_id"): meta[r["gsis_id"]] = (r.get("college_name") or "", r.get("draft_year") or "")
slp = {}
try:
    for r in csv.DictReader(io.StringIO(get(IDS))):
        if r.get("gsis_id") not in ("", "NA", None) and r.get("sleeper_id") not in ("", "NA", None): slp[r["gsis_id"]] = str(r["sleeper_id"]).split(".")[0]
except Exception as e: print("id map failed:", e)
clean = lambda c: "" if c in ("", "NA", "None", "none") else c
P, PI, T = [], {}, {}
n_ps = 0
for y in sorted(res):
    for a in res[y].values():
        s = a["s"]
        if s[0] <= 0: continue
        pid = a["pid"]
        if pid not in PI:
            col, dy = meta.get(pid, ("", ""))
            try: dy = int(float(dy)) if dy not in ("", "NA") else 0
            except ValueError: dy = 0
            PI[pid] = len(P); P.append([a["name"], a["pos"], clean(col), dy, slp.get(pid, "")])
        g = len(a["wk"]); r1 = lambda v: int(round(v))
        T.setdefault(f"{a['tm']}|{y}", []).append([PI[pid], g, r1(s[0] * 10), r1(s[2]), r1(s[1]), r1(s[3]), r1(s[4]), r1(s[5]), r1(s[6]), r1(s[7]), r1(s[8]), r1(s[9]), r1(s[10]), r1(a.get("wtd", 0)), r1(a.get("tgt", 0))])
        n_ps += 1
for k in T: T[k].sort(key=lambda x: -x[2])
out = {"v": 1, "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "first": first, "last": max(res) if res else last,
       "cols": ["p", "g", "pts10", "cmp", "att", "pyd", "ptd", "int", "car", "ryd", "rtd", "rec", "wyd", "wtd", "tgt"],
       "P": P, "T": T, "src": "nflverse player stats (CC-BY 4.0), DynastyProcess ids"}
json.dump(out, open("data/tm.json", "w"), separators=(",", ":"))
print(f"seasons {out['first']}-{out['last']}: {len(T)} team-seasons, {n_ps} player-seasons, {len(P)} players")
