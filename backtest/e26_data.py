"""B4 / e26: rest-of-season (ROS) panel. One row per (season, checkpoint week w, player) with what was known before
week w's games, and what he then scored: next 4 weeks (w..w+3) and rest of the fantasy regular season (w..17).
Outcomes kept two ways: per team game (bye weeks excluded, missed games count 0) and per game played.
Seasons 2021-2026 (2026 only through the last archived week). Sleeper PPR points."""
import json, gzip, os, collections, numpy as np, pandas as pd
B = os.path.dirname(os.path.abspath(__file__)); H = os.path.join(B, "..", "bt"); DL = B + "/dl"
ST = json.load(gzip.open(f"{H}/sleeper_stats.json.gz", "rt"))["w"]
PJ = json.load(gzip.open(f"{H}/sleeper_proj.json.gz", "rt"))["w"]
ids = pd.read_csv(DL + "/ids.csv", low_memory=False).dropna(subset=["sleeper_id"])
ids["sid"] = ids.sleeper_id.astype(int).astype(str)
s2g = dict(zip(ids.sid, ids.gsis_id)); s2pfr = dict(zip(ids.sid, ids.pfr_id)); s2b = dict(zip(ids.sid, ids.birthdate))
POS = {}
for w in PJ.values():
    for pid, s in w.items():
        if s.get("pos"): POS[pid] = s["pos"]
for s, p in zip(ids.sid, ids.position):
    if s not in POS and p in ("QB", "RB", "WR", "TE"): POS[s] = p
G = pd.read_csv(DL + "/games.csv", low_memory=False); G = G[G.game_type == "REG"]
def nt(t): return {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LA"}.get(t, t)
TW = collections.defaultdict(set); KICK = {}
for r in G.itertuples():
    TW[(r.season, r.week)] |= {nt(r.home_team), nt(r.away_team)}
    KICK[(r.season, r.week)] = min(KICK.get((r.season, r.week), "9999"), str(r.gameday))
def lastwk(y):
    return max([int(k.split("-")[1]) for k in ST if k.startswith(f"{y}-")] or [0])
rows = []
for y in range(2021, 2027):
    LW = min(17, lastwk(y))
    pw = pd.read_csv(f"{DL}/pw_{y}.csv", low_memory=False, usecols=["player_id", "week", "team", "season_type"])
    pw = pw[pw.season_type == "REG"]
    TEAM = collections.defaultdict(dict)
    for r in pw.itertuples(): TEAM[r.player_id][int(r.week)] = nt(r.team)
    ep = pd.read_csv(f"{DL}/ep_{y}.csv", low_memory=False, usecols=["week", "player_id", "posteam", "total_fantasy_points", "total_fantasy_points_exp", "rush_attempt", "rush_attempt_team", "rec_attempt", "rec_attempt_team"])
    ep["cs"] = ep.rush_attempt / ep.rush_attempt_team.replace(0, np.nan); ep["ts"] = ep.rec_attempt / ep.rec_attempt_team.replace(0, np.nan)
    EP = collections.defaultdict(dict)
    for r in ep.itertuples(): EP[r.player_id][int(r.week)] = (r.total_fantasy_points, r.total_fantasy_points_exp, r.cs, r.ts)
    snf = f"{DL}/snap_{y}.csv" if os.path.exists(f"{DL}/snap_{y}.csv") else f"{H}/nfl/snaps/{y}.csv.gz"
    sn = pd.read_csv(snf, low_memory=False); sn = sn[sn.game_type == "REG"]
    SN = collections.defaultdict(dict)
    for r in sn.itertuples(): SN[r.pfr_player_id][int(r.week)] = r.offense_pct * (100 if r.offense_pct <= 1 else 1)
    injf = f"{DL}/inj_{y}.csv" if os.path.exists(f"{DL}/inj_{y}.csv") else f"{H}/nfl/injuries/{y}.csv.gz"
    inj = pd.read_csv(injf, low_memory=False); inj = inj[inj.game_type == "REG"]
    INJ = {(r.gsis_id, int(r.week)): r.report_status for r in inj.itertuples() if isinstance(r.report_status, str)}
    dp = pd.read_csv(f"{H}/nfl/depth/{y}.csv.gz", low_memory=False)
    DC = {}
    if "dt" in dp.columns:  # dated snapshots: per week, the last snapshot before that week's first game
        dp = dp[dp.position.isin(["QB", "RB", "WR", "TE"])]
        dts = sorted(dp.dt.unique())
        for w in range(1, 19):
            k = KICK.get((y, w))
            if not k: continue
            prior = [d for d in dts if d[:10] < k]
            if not prior: continue
            snap = dp[dp.dt == prior[-1]]
            for r in snap.itertuples():
                try: DC[(r.gsis_id, w)] = min(DC.get((r.gsis_id, w), 9), int(r.depth))
                except Exception: pass
    else:
        dp = dp[dp.game_type == "REG"]
        for r in dp.itertuples():
            if r.depth_position not in ("QB", "RB", "WR", "TE") or pd.isna(r.week): continue
            try: DC[(r.gsis_id, int(r.week))] = min(DC.get((r.gsis_id, int(r.week)), 9), int(r.depth))
            except Exception: pass
    prev = collections.defaultdict(list)
    for w in range(1, 19):
        for pid, s in ST.get(f"{y-1}-{w}", {}).items():
            if s.get("gp"): prev[pid].append(s.get("pts_ppr", 0.0))
    PTS = collections.defaultdict(dict)  # pid -> week -> pts when played
    for w in range(1, 18):
        for pid, s in ST.get(f"{y}-{w}", {}).items():
            if s.get("gp"): PTS[pid][w] = s.get("pts_ppr", 0.0)
    for w in range(3, 15):
        if w > LW: continue
        pj = PJ.get(f"{y}-{w}", {})
        cand = set(pid for pid, s in pj.items() if (s.get("pts_ppr") or 0) >= 0.3) | set(pid for pid in PTS if any(k < w for k in PTS[pid]))
        for pid in cand:
            pos = POS.get(pid)
            if pos not in ("QB", "RB", "WR", "TE"): continue
            gsis = s2g.get(pid); pfr = s2pfr.get(pid)
            past = [PTS[pid][k] for k in sorted(PTS[pid]) if k < w]
            pr = (pj.get(pid) or {}).get("pts_ppr")
            tm = TEAM.get(gsis, {})
            def team_at(k):
                b = [x for x in tm if x <= k]
                if b: return tm[max(b)]
                a = [x for x in tm if x > k]
                return tm[min(a)] if a else None
            if not tm and not past: continue
            e = EP.get(gsis, {}); ew = [k for k in sorted(e) if k < w]
            xs = [e[k] for k in ew]
            snw = SN.get(pfr, {}) if isinstance(pfr, str) else {}
            sns = [snw[k] for k in sorted(snw) if k < w]
            def outc(lo, hi):
                tg = [k for k in range(lo, hi + 1) if team_at(k) in TW[(y, k)]]
                pl = [k for k in tg if k in PTS[pid]]
                return len(tg), len(pl), sum(PTS[pid][k] for k in pl)
            n4 = outc(w, min(w + 3, 17)) if w + 3 <= LW else (None, None, None)
            nr = outc(w, 17) if LW >= 17 else (None, None, None)
            nP = outc(w, LW)  # partial rest-of-season (for 2026)
            rec = [w - k for k in (1, 2, 3, 4) if w - k >= 1]
            played_set = set(k for k in PTS[pid] if k < w) | set(ew)
            bd = s2b.get(pid); age = None
            if isinstance(bd, str) and KICK.get((y, w)):
                age = (pd.Timestamp(KICK[(y, w)]) - pd.Timestamp(bd)).days / 365.25
            fpv = [x[0] for x in xs if not pd.isna(x[0])]; xfv = [x[1] for x in xs if not pd.isna(x[1])]
            rows.append(dict(s=y, w=w, pid=pid, pos=pos, proj=pr, bye=int(team_at(w) not in TW[(y, w)]), gp=len(past),
                ppg=np.mean(past) if past else np.nan, l3=np.mean(past[-3:]) if past else np.nan, l4=np.mean(past[-4:]) if past else np.nan,
                lw=past[-1] if past else np.nan, prev=np.mean(prev[pid]) if len(prev[pid]) >= 4 else np.nan,
                ag=len(xs), fp=np.mean(fpv) if fpv else np.nan, xfp=np.mean(xfv) if xfv else np.nan,
                x3=np.mean(xfv[-3:]) if xfv else np.nan,
                cs=np.nanmean([x[2] for x in xs]) if xs else np.nan, cs3=np.nanmean([x[2] for x in xs[-3:]]) if xs else np.nan,
                ts=np.nanmean([x[3] for x in xs]) if xs else np.nan, ts3=np.nanmean([x[3] for x in xs[-3:]]) if xs else np.nan,
                snap=np.mean(sns) if sns else np.nan, snap3=np.mean(sns[-3:]) if sns else np.nan,
                inj=INJ.get((gsis, w)), dc=DC.get((gsis, w)), age=age,
                nrec=len(rec), prec=sum(1 for k in rec if k in played_set),
                g4=n4[0], p4=n4[1], y4=n4[2], gR=nr[0], pR=nr[1], yR=nr[2], gP=nP[0], pP=nP[1], yP=nP[2], LW=LW))
    print(y, len(rows), "last wk", LW, flush=True)
D = pd.DataFrame(rows)
D.to_pickle(B + "/e26_panel.pkl")
print(len(D))
