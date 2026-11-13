"""Edge test 8: what late news costs managers. bt/rosters.json.gz (900 real leagues 2022-25): starters (QB/RB/WR/TE) who did
not play (Sleeper gp 0) though their team played. Split by that week's final injury-report status (nflverse): Out/Doubtful
(known by Friday), Questionable (decided ~90 min before kickoff), none (surprise). Cost = points the best bench player at
an eligible slot actually scored (who did play). Per team-season."""
import gzip, json, csv, collections, statistics as st
R = json.load(gzip.open("bt/rosters.json.gz", "rt"))["leagues"]; ST = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]
pos = {}; g2s = {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s not in ("", "NA"): pos[s] = r.get("position"); g2s[r.get("gsis_id")] = s
inj = {}; teamplayed = set(); tm = {}
for y in range(2022, 2026):
    for r in csv.DictReader(open(f"backtest/dl/inj_{y}.csv", encoding="utf-8")):
        s = g2s.get(r["gsis_id"])
        if s and r["game_type"] == "REG": inj[(y, int(r["week"]), s)] = r["report_status"]; tm[(y, s)] = r["team"]
    for r in csv.DictReader(open(f"backtest/dl/pw_{y}.csv", encoding="utf-8")):
        if r["season_type"] == "REG": teamplayed.add((y, int(r["week"]), r["team"])); s = g2s.get(r["player_id"]); s and tm.setdefault((y, s), r["team"])
FLEXP = {"RB", "WR", "TE"}
cnt = collections.Counter(); cost = collections.defaultdict(list); seasons = 0
for l in R.values():
    y = l["season"]; key = "pts_ppr" if l["sc"].get("rec", 0) >= .75 else "pts_half_ppr" if l["sc"].get("rec", 0) >= .25 else "pts_std"
    seasons += len({t[0] for ws in l["weeks"].values() for t in ws})
    for wk, ms in l["weeks"].items():
        w = int(wk)
        if w >= l.get("pws", 15): continue
        S = ST.get(f"{y}-{w}", {})
        for t in ms:
            bench = [x for x in t[4] if x not in t[3] and pos.get(x) in ("QB", "RB", "WR", "TE") and S.get(x, {}).get("gp")]
            for x in t[3]:
                p = pos.get(x)
                if p not in ("QB", "RB", "WR", "TE") or S.get(x, {}).get("gp"): continue
                team = tm.get((y, x))
                if not team or (y, w, team) not in teamplayed: continue   # bye week / unknown: not news
                stt = inj.get((y, w, x), "")
                k = "Out/Doubtful" if stt in ("Out", "Doubtful") else "Questionable" if stt == "Questionable" else "no listing"
                el = [b for b in bench if pos[b] == p or (p in FLEXP and pos[b] in FLEXP)]
                c = max((S[b].get(key) or 0 for b in el), default=0); cnt[k] += 1; cost[k].append(c)
print("team-seasons", seasons)
for k in ("Out/Doubtful", "Questionable", "no listing"):
    xs = cost[k]; print("%-13s started but inactive: %5d (%.2f per team-season)  bench option would have scored %.1f pts (%.0f%% had one 5+)" % (k, cnt[k], cnt[k] / seasons, st.mean(xs), 100 * sum(x >= 5 for x in xs) / len(xs)))
