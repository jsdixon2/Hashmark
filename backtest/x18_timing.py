"""Data test 1 (timing), run after the Sunday logger (scripts/log_inactives.py, inactives-log.yml): for each logged
Sunday, which QB/RB/WR/TE did NOT play though their team did (nflverse weekly stats), and when did Sleeper's
injury_status first show them as out (Out / IR / Inactive / NA / Sus) in the snapshots? Also: players shown out who played.
Usage: python3 backtest/x18_timing.py [stats_csv]  (default: nflverse stats_player_week_<season>.csv downloaded to
$X18_DL, default /tmp/x18). Snapshot files: bt/inactives/<date>.json.gz."""
import gzip, json, csv, glob, os, sys, datetime as dt, collections, urllib.request
OUT = {"Out", "IR", "Inactive", "NA", "Sus", "PUP", "DNR", "COV"}
g2s = {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s not in ("", "NA") and r.get("gsis_id") not in ("", "NA", None): g2s[r["gsis_id"]] = s
files = sorted(glob.glob(os.environ.get("X18_SNAPS", "bt/inactives") + "/*.json.gz"))
if not files: sys.exit("no snapshots in bt/inactives yet")
DL = os.environ.get("X18_DL", "/tmp/x18"); os.makedirs(DL, exist_ok=True)
for fpath in files:
    D = json.load(gzip.open(fpath, "rt")); day = dt.date.fromisoformat(D["day"]); season = day.year if day.month >= 3 else day.year - 1
    stats = sys.argv[1] if len(sys.argv) > 1 else f"{DL}/week_{season}.csv"
    if not os.path.exists(stats):
        urllib.request.urlretrieve(f"https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv", stats)
    rows = list(csv.DictReader(open(stats, encoding="utf-8")))
    # the NFL week whose Sunday is this day: the week with the most games on/around it is found from team appearances
    played = collections.defaultdict(set); teams = collections.defaultdict(set)
    for r in rows:
        if r.get("season_type") != "REG": continue
        w = int(r["week"]); teams[w].add(r.get("team") or r.get("recent_team")); s = g2s.get(r["player_id"])
        if s: played[w].add(s)
    snaps = D["snaps"]; last = snaps[-1]["sleeper"]
    # pick the week: the one in which the most players shown Out in the last snapshot did NOT play
    wk = max(played, key=lambda w: sum(1 for s, v in last.items() if (v[0] or "") in OUT and s not in played[w]) - sum(1 for s, v in last.items() if (v[0] or "") in OUT and s in played[w]))
    print(f"\n{D['day']} (season {season}, week {wk}): {len(snaps)} snapshots at " + ", ".join(s["t"][11:16] + " UTC" for s in snaps))
    # players on teams that played, who did not play, and who were not already out in the FIRST snapshot (= late news)
    first = snaps[0]["sleeper"]; dnp = []
    team_of = {sid: None for sid in last}
    for r in rows:
        if r.get("season_type") == "REG" and int(r["week"]) < wk:
            s = g2s.get(r["player_id"])
            if s in team_of: team_of[s] = r.get("team") or r.get("recent_team")
    regular = collections.Counter()
    for r in rows:
        if r.get("season_type") == "REG" and wk - 3 <= int(r["week"]) < wk:
            s = g2s.get(r["player_id"]); pts = float(r.get("fantasy_points_ppr") or 0)
            if s and pts >= 6: regular[s] += 1
    for sid in last:
        if regular[sid] >= 2 and team_of.get(sid) in teams[wk] and sid not in played[wk]: dnp.append(sid)
    first_seen = collections.Counter(); never = 0; already = 0
    for sid in dnp:
        if (first.get(sid, [None])[0] or "") in OUT: already += 1; continue
        hit = next((s["t"][11:16] for s in snaps if (s["sleeper"].get(sid, [None])[0] or "") in OUT), None)
        if hit: first_seen[hit] += 1
        else: never += 1
    print(f"  regulars (6+ PPR in 2 of last 3 weeks) who did not play though their team did: {len(dnp)}")
    print(f"  already out before inactives (first snapshot): {already}")
    for t, n in sorted(first_seen.items()): print(f"  first shown out at {t} UTC: {n}")
    print(f"  never shown out by Sleeper in any snapshot: {never}")
    wrong = [sid for sid, v in last.items() if (v[0] or "") in OUT and sid in played[wk]]
    print(f"  shown out in the last snapshot but played: {len(wrong)}")
