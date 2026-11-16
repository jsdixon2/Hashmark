"""x26 step 1: team scheme profiles per season (full regular season and weeks 1-4), 2016-2025.
Defense (nflverse participation, pass plays): man-coverage rate, single-high shell rate (Cover 0/1/3), pressure rate,
mean pass rushers, mean box (all plays); plus bt/nfl/pbp_team def_epa / def_pass_epa / def_rush_epa and ftn blitzers.
Offense (bt/nfl/pbp_team): pass rate over expected (proe), neutral pass rate, plays per game; (pbp_player) top RB carry
share, top target share. Output backtest/x26_profiles.json {"YYYY|TM": {"full": {...}, "w14": {...}}}."""
import csv, gzip, io, json, os, collections, urllib.request
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); DL = "/tmp/hm_dl"; os.makedirs(DL, exist_ok=True)
PURL = "https://github.com/nflverse/nflverse-data/releases/download/pbp_participation/pbp_participation_{}.csv"
FIX = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA"}
fx = lambda t: FIX.get(t, t)
def dl(y):
    f = f"{DL}/part_{y}.csv"
    if not os.path.exists(f):
        try: open(f, "wb").write(urllib.request.urlopen(urllib.request.Request(PURL.format(y), headers={"User-Agent": "hashmark-backtest"}), timeout=300).read())
        except Exception as e: print("no participation", y, e); return None
    return f
weeks = {}
for r in csv.DictReader(gzip.open(f"{R}/bt/nfl/schedules.csv.gz", "rt")):
    weeks[r["game_id"]] = (int(r["season"]), int(r["week"]), r["game_type"])
P = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0]))
def add(k, m, v):
    if v is None: return
    a = P[k][m]; a[0] += v; a[1] += 1
for y in range(2016, 2026):
    f = dl(y)
    if not f: continue
    n = 0
    for r in csv.DictReader(open(f, encoding="utf-8", errors="replace")):
        gid = r.get("nflverse_game_id") or ""
        w = weeks.get(gid)
        if not w or w[2] != "REG": continue
        parts = gid.split("_")
        if len(parts) < 4: continue
        a, h = fx(parts[2]), fx(parts[3]); off = fx(r.get("possession_team") or "")
        if off not in (a, h): continue
        d = h if off == a else a
        keys = [f"{y}|{d}|full"] + ([f"{y}|{d}|w14"] if w[1] <= 4 else [])
        mz = (r.get("defense_man_zone_type") or "").upper(); cv = (r.get("defense_coverage_type") or "").upper()
        box = r.get("defenders_in_box"); pr = r.get("number_of_pass_rushers"); wp = (r.get("was_pressure") or "").upper()
        for k in keys:
            if box not in ("", "NA", None): add(k, "box", float(box))
            if mz in ("MAN_COVERAGE", "ZONE_COVERAGE"):
                add(k, "man", 1.0 if mz == "MAN_COVERAGE" else 0.0)
                if cv and cv not in ("PREVENT", "NA"): add(k, "single_high", 1.0 if cv in ("COVER_0", "COVER_1", "COVER_3") else 0.0)
                if pr not in ("", "NA", None): add(k, "rushers", float(pr))
                if wp in ("TRUE", "FALSE", "1", "0"): add(k, "pressure", 1.0 if wp in ("TRUE", "1") else 0.0)
        n += 1
    print(y, "participation plays", n)
# pbp_team (weekly team rows) and ftn_team
def team_rows(path):
    if not os.path.exists(path): return []
    return list(csv.DictReader(gzip.open(path, "rt")))
for y in range(2016, 2026):
    for r in team_rows(f"{R}/bt/nfl/pbp_team/{y}.csv.gz"):
        if r["season_type"] != "REG": continue
        t = fx(r["team"]); wk = int(r["week"]); ks = [f"{y}|{t}|full"] + ([f"{y}|{t}|w14"] if wk <= 4 else [])
        for k in ks:
            for m in ("proe", "neutral_pass_rate", "plays", "def_epa", "def_pass_epa", "def_rush_epa", "off_epa"):
                v = r.get(m)
                if v not in ("", "NA", None): add(k, m, float(v))
    for r in team_rows(f"{R}/bt/nfl/ftn_team/{y}.csv.gz"):
        if r["season_type"] != "REG": continue
        t = fx(r["team"]); wk = int(r["week"]); ks = [f"{y}|{t}|full"] + ([f"{y}|{t}|w14"] if wk <= 4 else [])
        for k in ks:
            for m, c in (("off_motion", "is_motion"), ("off_pa", "is_play_action")):
                v = r.get(c)
                if v not in ("", "NA", None): add(k, m, float(v))
    # player shares: top RB carry share and top target share per team-season (offense usage concentration)
    car = collections.defaultdict(lambda: collections.defaultdict(float)); tg = collections.defaultdict(lambda: collections.defaultdict(float))
    for r in team_rows(f"{R}/bt/nfl/pbp_player/{y}.csv.gz"):
        if r["season_type"] != "REG": continue
        t = fx(r["team"]); wk = int(r["week"])
        for sc in ["full"] + (["w14"] if wk <= 4 else []):
            if r.get("carries") not in ("", "NA", None) and not r.get("dropbacks"): car[(t, sc)][r["gsis_id"]] += float(r["carries"])
            if r.get("targets") not in ("", "NA", None): tg[(t, sc)][r["gsis_id"]] += float(r["targets"])
    for (t, sc), d in car.items():
        tot = sum(d.values())
        if tot > 20: P[f"{y}|{t}|{sc}"]["rb1_share"] = [max(d.values()) / tot, 1]
    for (t, sc), d in tg.items():
        tot = sum(d.values())
        if tot > 30: P[f"{y}|{t}|{sc}"]["tgt1_share"] = [max(d.values()) / tot, 1]
out = {}
for k, ms in P.items():
    y, t, sc = k.split("|"); out.setdefault(f"{y}|{t}", {})[sc] = {m: round(s / n, 4) for m, (s, n) in ms.items() if n}
json.dump(out, open(f"{R}/backtest/x26_profiles.json", "w"))
print(len(out), "team-seasons;", "example", sorted(out)[0], out[sorted(out)[0]].get("full"))
