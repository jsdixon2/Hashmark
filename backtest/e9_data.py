"""Engine 5 data: one row per (season, week w, player) with what was known before week w's games,
and what he then scored in weeks w..w+3 (Sleeper PPR, 0 when he didn't play). Also league ownership from rebuilt rosters."""
import json, gzip, os, collections, numpy as np, pandas as pd
B = os.path.dirname(os.path.abspath(__file__)); H = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bt"); DL = B + "/dl"
ST = json.load(gzip.open(f"{H}/sleeper_stats.json.gz", "rt"))["w"]
PJ = json.load(gzip.open(f"{H}/sleeper_proj.json.gz", "rt"))["w"]
ids = pd.read_csv(DL + "/ids.csv", low_memory=False)
ids = ids.dropna(subset=["sleeper_id"]); ids["sid"] = ids.sleeper_id.astype(int).astype(str)
s2g = dict(zip(ids.sid, ids.gsis_id)); g2s = {g: s for s, g in s2g.items() if isinstance(g, str)}
s2pfr = dict(zip(ids.sid, ids.pfr_id))
POS = {}
for w in PJ.values():
    for pid, s in w.items():
        if s.get("pos"): POS[pid] = s["pos"]
for s, p in zip(ids.sid, ids.position):
    if s not in POS and p in ("QB", "RB", "WR", "TE"): POS[s] = p
SEAS = [2021, 2022, 2023, 2024, 2025]
G = pd.read_csv(DL + "/games.csv", low_memory=False); G = G[G.game_type == "REG"]
teams_w = collections.defaultdict(set)
for r in G.itertuples(): teams_w[(r.season, r.week)] |= {r.home_team, r.away_team}
def norm_t(t): return {"LA": "LA", "LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LA"}.get(t, t)
rows = []
for y in SEAS:
    ep = pd.read_csv(f"{DL}/ep_{y}.csv", low_memory=False, usecols=["week", "player_id", "posteam", "total_fantasy_points_exp", "rush_attempt", "rush_attempt_team", "rec_attempt", "rec_attempt_team"])
    ep["cs"] = ep.rush_attempt / ep.rush_attempt_team.replace(0, np.nan); ep["ts"] = ep.rec_attempt / ep.rec_attempt_team.replace(0, np.nan)
    EPd = {(r.player_id, r.week): (r.total_fantasy_points_exp, r.cs, r.ts, r.posteam) for r in ep.itertuples()}
    sn = pd.read_csv(f"{DL}/snap_{y}.csv", low_memory=False); sn = sn[sn.game_type == "REG"]
    SN = {(r.pfr_player_id, r.week): r.offense_pct for r in sn.itertuples()}
    inj = pd.read_csv(f"{DL}/inj_{y}.csv", low_memory=False); inj = inj[inj.game_type == "REG"]
    INJ = {(r.gsis_id, r.week): r.report_status for r in inj.itertuples() if isinstance(r.report_status, str)}
    dp = pd.read_csv(f"{H}/nfl/depth/{y}.csv.gz", low_memory=False) if os.path.exists(f"{H}/nfl/depth/{y}.csv.gz") else None
    DC = {}
    if dp is not None:
        if "wk" in dp.columns:
            dp = dp[dp.wk.str.startswith(str(y))].copy(); dp["week"] = dp.wk.str.split("-").str[1].astype(int) - 35; dp["depth_position"] = dp.position
        dp = dp[dp.game_type == "REG"] if "game_type" in dp.columns else dp
        for r in dp.itertuples():
            try: d_ = int(r.depth)
            except Exception: continue
            if r.depth_position in ("QB", "RB", "WR", "TE"): DC[(r.gsis_id, r.week)] = min(DC.get((r.gsis_id, r.week), 9), d_)
    prev = collections.defaultdict(list)
    for w in range(1, 19):
        for pid, s in ST.get(f"{y-1}-{w}", {}).items():
            if s.get("gp") and "pts_ppr" in s or s.get("gp"): prev[pid].append(s.get("pts_ppr", 0.0))
    hist = collections.defaultdict(list)  # pid -> [(week, pts)]
    for w in range(1, 18):
        for pid, s in ST.get(f"{y}-{w}", {}).items():
            if s.get("gp"): hist[pid].append((w, s.get("pts_ppr", 0.0)))
    for w in range(2, 15):
        pj = PJ.get(f"{y}-{w}", {}); pj1 = PJ.get(f"{y}-{w+1}", {})
        for pid, pr in pj.items():
            pos = POS.get(pid)
            if pos not in ("QB", "RB", "WR", "TE"): continue
            p0 = pr.get("pts_ppr") or 0.0
            if p0 < 0.3: continue
            past = [p for k, p in hist[pid] if k < w]
            gsis = s2g.get(pid); pfr = s2pfr.get(pid)
            xs = [EPd[(gsis, k)] for k in range(1, w) if (gsis, k) in EPd]
            sn_ = [SN[(pfr, k)] for k in range(1, w) if (pfr, k) in SN] if isinstance(pfr, str) else []
            team = xs[-1][3] if xs else None
            y4 = sum((ST.get(f"{y}-{k}", {}).get(pid) or {}).get("pts_ppr", 0.0) for k in range(w, w + 4))
            gw = sum(1 for k in range(w, w + 4) if team is None or norm_t(team) in teams_w[(y, k)]) if team else 4
            rows.append(dict(s=y, w=w, pid=pid, pos=pos, team=norm_t(team) if team else None, play=[int(team is None or norm_t(team) in teams_w[(y, k)]) for k in range(w, w + 4)], proj=p0, proj1=(pj1.get(pid) or {}).get("pts_ppr"), gp=len(past),
                             ppg=np.mean(past) if past else np.nan, l3=np.mean(past[-3:]) if past else np.nan, lw=past[-1] if past else np.nan,
                             prev=np.mean(prev[pid]) if len(prev[pid]) >= 4 else np.nan, xfp=np.mean([x[0] for x in xs]) if xs else np.nan,
                             x3=np.mean([x[0] for x in xs[-3:]]) if xs else np.nan, cs=np.nanmean([x[1] for x in xs]) if xs else np.nan,
                             cs3=np.nanmean([x[1] for x in xs[-3:]]) if xs else np.nan, ts=np.nanmean([x[2] for x in xs]) if xs else np.nan,
                             ts3=np.nanmean([x[2] for x in xs[-3:]]) if xs else np.nan, snap=np.mean(sn_) if sn_ else np.nan, snap3=np.mean(sn_[-3:]) if sn_ else np.nan,
                             inj=INJ.get((gsis, w)), dc=DC.get((gsis, w)), games=gw, y4=y4,
                             y2=sum((ST.get(f"{y}-{k}", {}).get(pid) or {}).get("pts_ppr", 0.0) for k in range(w, w + 2)),
                             y1=(ST.get(f"{y}-{w}", {}).get(pid) or {}).get("pts_ppr", 0.0)))
    print(y, len(rows))
D = pd.DataFrame(rows)
# ownership: rebuild redraft rosters (draft + every add/drop/trade in time order) and count, per week, how many leagues roster each player
L = json.load(gzip.open(f"{H}/leagues.json.gz", "rt"))["leagues"]
own = collections.Counter(); nlg = collections.Counter(); ADDS = []
for lg in L.values():
    s = lg["season"]
    if s not in SEAS or lg.get("type") not in (0, None) or not lg.get("draft") or not lg["draft"].get("picks"): continue
    ro = {}
    for p in lg["draft"]["picks"]:
        if p[2]: ro[str(p[2])] = p[3]
    tx = sorted([t for t in (lg.get("tx") or [])], key=lambda t: (t[1], t[8] or 0))
    i = 0
    for w in range(1, 16):
        # moves processed before week w's games = transactions logged in week < w (Sleeper logs waivers by the leg they clear for)
        while i < len(tx) and tx[i][1] < w:
            t = tx[i]
            for pid in (t[4] or {}): ro.pop(str(pid), None)
            for pid, rid in (t[3] or {}).items(): ro[str(pid)] = rid
            i += 1
        if w >= 2:
            nlg[(s, w)] += 1
            for pid in ro: own[(s, w, pid)] += 1
        # adds that clear for week w (log week w): who was added, by whom, bid
        for t in tx:
            if t[1] == w and t[0] in ("waiver", "free_agent"):
                for pid, rid in (t[3] or {}).items(): ADDS.append((s, w, str(pid), lg["id"], rid, t[0], t[7], lg["n"]))
D["own"] = [own.get((s, w, p), 0) / max(1, nlg[(s, w)]) for s, w, p in zip(D.s, D.w, D.pid)]
D.to_pickle(B + "/e9_D.pkl"); pd.DataFrame(ADDS, columns=["s", "w", "pid", "lg", "rid", "typ", "bid", "n"]).to_pickle(B + "/e9_adds.pkl")
print(len(D), "rows;", D.groupby("s").size().to_dict(), "own mean", D.own.mean().round(3), "leagues/wk", np.mean(list(nlg.values())))
