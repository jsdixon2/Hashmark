"""Engine 1 refit, step 1: player-week panel 2021-2026 with exactly the inputs the app's projection uses (hmProj):
Sleeper projection (PPR), season PPG and last-3 PPG (games before this week), season / last-3 expected fantasy points
(ffopportunity), opponent defense-vs-position rank to date (1 = gives up the most), team implied points from the
closing line, questionable flag. Target: actual PPR points (Sleeper stats). Output backtest/e14_panel.pkl."""
import csv, gzip, json, os, collections, statistics as st
import pandas as pd
B = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(B)
ids = {}; g2s = {}
for r in csv.DictReader(open(f"{B}/dl/ids.csv")):
    s = str(r["sleeper_id"]).split(".")[0]
    if s in ("", "NA"): continue
    ids[s] = r
    if r["gsis_id"] not in ("", "NA"): g2s[r["gsis_id"]] = s
SP = json.load(gzip.open(f"{R}/bt/sleeper_proj.json.gz", "rt"))["w"]; ST = json.load(gzip.open(f"{R}/bt/sleeper_stats.json.gz", "rt"))["w"]
# nflverse weekly: team/opponent per player-week, points by defense vs position
tm = {}; allowed = collections.defaultdict(float); dgames = collections.defaultdict(set)
xfp = {}
for y in range(2021, 2027):
    for r in csv.DictReader(open(f"{B}/dl/pw_{y}.csv")):
        if r["season_type"] != "REG": continue
        w = int(r["week"]); pos = r["position"]
        s = g2s.get(r["player_id"])
        if s: tm[(y, w, s)] = (r["team"], r["opponent_team"])
        if pos in ("QB", "RB", "WR", "TE"):
            allowed[(y, r["opponent_team"], pos, w)] += float(r["fantasy_points_ppr"] or 0); dgames[(y, r["opponent_team"])].add(w)
    f = f"{B}/dl/ep_{y}.csv"
    for r in csv.DictReader(open(f)):
        s = g2s.get(r["player_id"])
        if not s: continue
        try: xfp[(y, int(float(r["week"])), s)] = float(r["total_fantasy_points_exp"] or 0)
        except ValueError: pass
def dvp_rank(y, w, opp, pos):
    teams = {t for (yy, t) in dgames if yy == y}; per = {}
    for t in teams:
        ws = [x for x in dgames[(y, t)] if x < w]
        if len(ws) < 2: return None
        per[t] = sum(allowed.get((y, t, pos, x), 0) for x in ws) / len(ws)
    if opp not in per: return None
    order = sorted(per, key=lambda t: -per[t]); return order.index(opp) + 1
DV = {}
imp = {}
for r in csv.DictReader(gzip.open(f"{R}/bt/nfl/schedules.csv.gz", "rt")):
    if r["game_type"] != "REG": continue
    try: sp, tot = float(r["spread_line"]), float(r["total_line"])
    except ValueError: continue
    y, w = int(r["season"]), int(r["week"])
    imp[(y, w, r["home_team"])] = tot / 2 + sp / 2; imp[(y, w, r["away_team"])] = tot / 2 - sp / 2
q = set()
for y in range(2021, 2027):
    for r in csv.DictReader(gzip.open(f"{R}/bt/nfl/injuries/{y}.csv.gz", "rt")):
        if r.get("report_status") == "Questionable" and r.get("game_type", "REG") == "REG" and r["gsis_id"] in g2s:
            q.add((int(r["season"]), int(r["week"]), g2s[r["gsis_id"]]))
rows = []
log = collections.defaultdict(list)   # (season,pid) -> [(w, pts, xfp)]
for key in sorted(ST, key=lambda k: tuple(map(int, k.split("-")))):
    y, w = map(int, key.split("-"))
    if y < 2021: continue
    P = SP.get(key) or {}; S = ST[key]
    for pid, pr in P.items():
        r = ids.get(pid)
        if not r or r["position"] not in ("QB", "RB", "WR", "TE"): continue
        stt = S.get(pid)
        if not stt or not stt.get("gp"): continue
        base = pr.get("pts_ppr") or 0
        L = log[(y, pid)]
        ppg = st.mean(x[1] for x in L) if len(L) >= 2 else None
        l3 = st.mean(x[1] for x in L[-3:]) if len(L) >= 3 else None
        xs_ = [x[2] for x in L if x[2] is not None]
        xs = st.mean(xs_) if len(xs_) >= 2 else None; x3 = st.mean(xs_[-3:]) if len(xs_) >= 3 else None
        t = tm.get((y, w, pid)); rk = None; ii = None
        if t:
            k = (y, w, t[1], r["position"])
            if k not in DV: DV[k] = dvp_rank(y, w, t[1], r["position"])
            rk = DV[k]; ii = imp.get((y, w, t[0]))
        rows.append(dict(season=y, week=w, pid=pid, pos=r["position"], base=base, actual=stt.get("pts_ppr") or 0, ppg=ppg, l3=l3, xs=xs, x3=x3,
                         rk=rk, imp=ii, q=int((y, w, pid) in q), n=len(L)))
    for pid, stt in S.items():
        if stt.get("gp"): log[(y, pid)].append((w, stt.get("pts_ppr") or 0, xfp.get((y, w, pid))))
df = pd.DataFrame(rows); df.to_pickle(f"{B}/e14_panel.pkl")
print(len(df), df.groupby("season").size().to_dict()); print(df.notna().mean().round(2).to_dict())
