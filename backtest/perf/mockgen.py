# Fake Sleeper API for a 5-league live launch (startup measurement). Real 2026 weekly stats/projections from bt/,
# players from ids.csv padded to Sleeper's field set, leagues dealt by value. Writes scratchpad/mock/*.json
import gzip, json, csv, random, os, sys
random.seed(3); OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
J = lambda n, o: json.dump(o, open(os.path.join(OUT, n), "w"), separators=(",", ":"))
P = {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s in ("", "NA"): continue
    fn = (r["name"] or "x y").split(" ", 1)
    P[s] = {"player_id": s, "full_name": r["name"], "first_name": fn[0], "last_name": fn[-1], "position": r["position"], "fantasy_positions": [r["position"]],
            "team": r["team"] if r["team"] not in ("", "NA", "FA") else None, "age": int(float(r["age"])) if r["age"] not in ("", "NA") else None,
            "years_exp": max(0, 2026 - int(float(r["draft_year"]))) if r["draft_year"] not in ("", "NA") else None, "college": r["college"],
            "height": r["height"], "weight": r["weight"], "number": random.randint(1, 99), "depth_chart_order": random.choice([1, 1, 2, 3, None]),
            "depth_chart_position": r["position"], "injury_status": random.choice([None] * 12 + ["Questionable", "Out", "IR"]), "injury_body_part": None,
            "status": "Active", "sport": "nfl", "active": True, "search_rank": random.randint(1, 9999999), "birth_date": r["birthdate"],
            "espn_id": r["espn_id"], "yahoo_id": r["yahoo_id"], "rotowire_id": r["rotowire_id"], "sportradar_id": r["sportradar_id"],
            "fantasy_data_id": r["fantasy_data_id"], "stats_id": r["stats_id"], "gsis_id": r["gsis_id"], "practice_participation": None,
            "news_updated": None, "hashtag": "#" + r["merge_name"].replace(" ", ""), "search_full_name": r["merge_name"].replace(" ", ""),
            "metadata": {"channel_id": str(random.randint(10**17, 10**18))}, "competitions": [], "injury_notes": None, "high_school": None, "birth_country": None}
for t in ["ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE","DAL","DEN","DET","GB","HOU","IND","JAX","KC","LV","LAC","LAR","MIA","MIN","NE","NO","NYG","NYJ","PHI","PIT","SF","SEA","TB","TEN","WAS"]:
    P[t] = {"player_id": t, "first_name": t, "last_name": "Defense", "position": "DEF", "fantasy_positions": ["DEF"], "team": t, "active": True}
J("players.json", P); print("players", len(P), os.path.getsize(os.path.join(OUT, "players.json")) // 1024, "KB")
PJ = json.load(gzip.open("bt/sleeper_proj.json.gz", "rt"))["w"]; ST = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]
tmpl = ["rush_att", "rush_yd", "rush_td", "rec", "rec_tgt", "rec_yd", "rec_td", "pass_att", "pass_cmp", "pass_yd", "pass_td", "pass_int", "fum_lost",
        "off_snp", "tm_off_snp", "tm_def_snp", "tm_st_snp", "rush_fd", "rec_fd", "pass_fd", "rec_0_4", "rec_5_9", "rec_10_19", "rec_20_29", "rec_air_yd",
        "rec_yar", "rush_ypa", "rec_ypr", "rec_ypt", "rush_lng", "rec_lng", "bonus_rec_wr", "pos_rank_ppr", "pos_rank_half_ppr", "pos_rank_std"]
def pad(d):
    out = {}
    for sid, s in d.items():
        e = dict(s); e.setdefault("gp", 1.0)
        for k in tmpl: e.setdefault(k, round(random.random() * 20, 2))
        out[sid] = e
    return out
for w in range(1, 11):
    J(f"stats_2026_{w}.json", pad(ST.get(f"2026-{w}", {}))); J(f"proj_2026_{w}.json", pad(PJ.get(f"2026-{w}", {})))
for y in range(2020, 2026):
    tot = {}
    for w in range(1, 19):
        for sid, s in ST.get(f"{y}-{w}", {}).items():
            e = tot.setdefault(sid, {"gp": 0, "pts_ppr": 0, "pts_half_ppr": 0, "pts_std": 0})
            e["gp"] += 1; e["pts_ppr"] += s.get("pts_ppr", 0); e["pts_half_ppr"] += s.get("pts_half_ppr", 0); e["pts_std"] += s.get("pts_std", 0)
    J(f"stats_{y}.json", pad(tot))
V = json.load(open("data/values.json"))["v"]
ranked = [s for s in sorted(V, key=lambda s: -(V[s].get("dd") or V[s].get("fc_sf") or 0)) if s in P and P[s]["position"] in ("QB", "RB", "WR", "TE")]
K = [s for s in P if P[s]["position"] in ("K", "PK")][:40] or ["K_dummy"]
P.setdefault("K_dummy", {"player_id": "K_dummy", "full_name": "Kicker Dummy", "position": "K", "team": "KC", "active": True})
SC = {"pass_yd": .04, "pass_td": 4, "pass_int": -2, "rush_yd": .1, "rush_td": 6, "rec_yd": .1, "rec_td": 6, "fum_lost": -2, "rec": 1}
cfg = [("dyn_sf_a", 2, 12, ["QB","RB","RB","WR","WR","TE","FLEX","FLEX","SUPER_FLEX"] + ["BN"] * 16 + ["TAXI"] * 3, 1),
       ("dyn_sf_b", 2, 12, ["QB","RB","RB","WR","WR","WR","TE","FLEX","SUPER_FLEX"] + ["BN"] * 15 + ["TAXI"] * 3, 1),
       ("dyn_1q", 2, 10, ["QB","RB","RB","WR","WR","TE","FLEX","FLEX","K","DEF"] + ["BN"] * 14, .5),
       ("keeper", 1, 10, ["QB","RB","RB","WR","WR","TE","FLEX","K","DEF"] + ["BN"] * 7 + ["IR"] * 3, .5),
       ("redraft", 0, 10, ["QB","RB","RB","WR","WR","TE","FLEX","K","DEF"] + ["BN"] * 7, 1)]
leagues = []
for lid, typ, n, rp, rec in cfg:
    size = len([x for x in rp if x not in ("IR",)])
    pool = ranked[:n * size]; random.shuffle(pool); teams = [pool[i::n][:size] for i in range(n)]
    for i, t in enumerate(teams): t += [K[(i + len(leagues) * 10) % len(K)], ["KC","BUF","PHI","SF","DAL","DET","BAL","MIA","CIN","GB","SEA","LAR"][i % 12]]
    sc = dict(SC, rec=rec)
    leagues.append({"league_id": lid, "name": lid.replace("_", " ").title(), "season": "2026", "status": "in_season", "total_rosters": n,
                    "roster_positions": rp, "scoring_settings": sc, "previous_league_id": None,
                    "settings": {"type": typ, "playoff_week_start": 15, "playoff_teams": 6, "draft_rounds": 4, "waiver_budget": 100, "taxi_slots": 3 if typ == 2 else 0, "reserve_slots": 3},
                    "metadata": {}})
    me = 0
    J(f"lg_{lid}_rosters.json", [{"roster_id": i + 1, "owner_id": "u_me" if i == me else f"u{i}", "players": t, "starters": t[:9], "reserve": [], "taxi": [],
                                   "co_owners": None, "settings": {"wins": random.randint(2, 7), "losses": random.randint(2, 7), "ties": 0, "fpts": random.randint(900, 1300),
                                   "fpts_decimal": 12, "waiver_position": i + 1, "waiver_budget_used": random.randint(0, 60), "division": 0}} for i, t in enumerate(teams)])
    J(f"lg_{lid}_users.json", [{"user_id": "u_me" if i == me else f"u{i}", "display_name": f"user{i}", "metadata": {"team_name": f"Team {lid} {i}"}} for i in range(n)])
    for w in range(1, 16):
        mu = []
        for i, t in enumerate(teams):
            pp = {p: round(random.random() * 25, 2) for p in t}
            mu.append({"roster_id": i + 1, "matchup_id": i // 2 + 1, "starters": t[:9], "players": t, "points": round(sum(list(pp.values())[:9]), 2) if w < 10 else 0,
                       "players_points": pp if w < 10 else {}, "starters_points": [pp[p] for p in t[:9]]})
        J(f"lg_{lid}_mu_{w}.json", mu)
        J(f"lg_{lid}_tx_{w}.json", [{"type": random.choice(["waiver", "free_agent", "trade"]), "status": "complete", "roster_ids": [random.randint(1, n)],
                                     "adds": {random.choice(ranked[300:600]): random.randint(1, n)}, "drops": None, "leg": w, "created": 1790000000000 + w * 6e8,
                                     "transaction_id": f"{lid}{w}{k}", "settings": {"waiver_bid": random.randint(0, 30)}, "draft_picks": [], "waiver_budget": []} for k in range(random.randint(2, 8))])
J("leagues.json", leagues)
print("leagues", len(leagues))
