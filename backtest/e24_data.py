"""Task B2 (QB projections), step 1: QB player-week panel = backtest/e14_panel.pkl (the app's inputs) + QB-specific inputs
that exist at runtime in the app, all computed from games BEFORE the week:
  rpg   rush attempts per game (season to date)          app: p.adv.cs x team carries (or log)
  cs    share of team carries (season to date)            app: p.adv.cs
  rsh   share of his fantasy points from rushing           (from weekly stats; app would need build_adv)
  epad  passing EPA per attempt (season to date)          app: p.adv.epad
  cpoe  mean CPOE (season to date)                         app: p.adv.cpoe
  sackr sacks / dropbacks (season to date)
  dq    opponent QB points allowed per game to date minus league average, shrunk n/(n+4)  app: adv.teams[opp].dvp.QB
  sp    own team spread (positive = favoured), tot game total, home, dome (dome/closed), wind, temp (outdoor only)
Output backtest/e24_panel.pkl (QBs with Sleeper projection >= 3 who played)."""
import csv, gzip, os, collections, statistics as st
import pandas as pd
B = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(B)
g2s = {}
for r in csv.DictReader(open(f"{B}/dl/ids.csv")):
    s = str(r["sleeper_id"]).split(".")[0]
    if s not in ("", "NA") and r["gsis_id"] not in ("", "NA"): g2s[r["gsis_id"]] = s
F = lambda x: float(x) if x not in ("", "NA", None) else 0.0
pl = collections.defaultdict(dict)     # (y,pid) -> {w: stats}
tcar = collections.defaultdict(float); qba = collections.defaultdict(float); dg = collections.defaultdict(set)
for y in range(2021, 2027):
    for r in csv.DictReader(open(f"{B}/dl/pw_{y}.csv")):
        if r["season_type"] != "REG": continue
        w = int(r["week"]); tcar[(y, r["team"], w)] += F(r["carries"])
        if r["position"] == "QB":
            qba[(y, r["opponent_team"], w)] += F(r["fantasy_points_ppr"]); dg[(y, r["opponent_team"])].add(w)
            s = g2s.get(r["player_id"])
            if s:
                rp = F(r["rushing_yards"]) * .1 + F(r["rushing_tds"]) * 6
                pl[(y, s)][w] = dict(team=r["team"], car=F(r["carries"]), att=F(r["attempts"]), sk=F(r["sacks_suffered"]), epa=F(r["passing_epa"]),
                                     cpoe=(float(r["passing_cpoe"]) if r["passing_cpoe"] not in ("", "NA") else None), rp=rp, fp=F(r["fantasy_points_ppr"]))
def dq(y, w, opp):
    vals = {}
    for (yy, t), ws in dg.items():
        if yy != y: continue
        ws2 = [x for x in ws if x < w]
        if ws2: vals[t] = (sum(qba[(y, t, x)] for x in ws2) / len(ws2), len(ws2))
    if opp not in vals or len(vals) < 20: return None
    lg = st.mean(v[0] for v in vals.values()); a, n = vals[opp]
    return (a - lg) * n / (n + 4)
G = {}
for r in csv.DictReader(gzip.open(f"{R}/bt/nfl/schedules.csv.gz", "rt")):
    if r["game_type"] != "REG": continue
    y, w = int(r["season"]), int(r["week"])
    try: sp, tot = float(r["spread_line"]), float(r["total_line"])
    except ValueError: sp = tot = None
    dome = int(r["roof"] in ("dome", "closed"))
    wind = float(r["wind"]) if r["wind"] not in ("", "NA") and not dome else (0.0 if dome else None)
    temp = float(r["temp"]) if r["temp"] not in ("", "NA") and not dome else None
    G[(y, w, r["home_team"])] = dict(opp=r["away_team"], sp=sp, tot=tot, home=1, dome=dome, wind=wind, temp=temp)
    G[(y, w, r["away_team"])] = dict(opp=r["home_team"], sp=-sp if sp is not None else None, tot=tot, home=0, dome=dome, wind=wind, temp=temp)
df = pd.read_pickle(f"{B}/e14_panel.pkl"); df = df[(df.pos == "QB") & (df.base >= 3)].copy()
ex = []; DQ = {}
for y, w, pid in zip(df.season, df.week, df.pid):
    P = pl.get((y, pid), {}); prev = [P[x] for x in sorted(P) if x < w]
    cur = P.get(w); team = cur["team"] if cur else (prev[-1]["team"] if prev else None)
    o = {}
    if len(prev) >= 2:
        car = sum(x["car"] for x in prev); att = sum(x["att"] for x in prev); sk = sum(x["sk"] for x in prev); fp = sum(x["fp"] for x in prev)
        tc = sum(tcar[(y, x["team"], ww)] for ww, x in sorted(P.items()) if ww < w)
        o = dict(rpg=car / len(prev), cs=car / tc if tc else None, rsh=(sum(x["rp"] for x in prev) / fp) if fp > 0 else None,
                 epad=sum(x["epa"] for x in prev) / (att + sk) if att + sk else None, sackr=sk / (att + sk) if att + sk else None,
                 cpoe=st.mean([x["cpoe"] for x in prev if x["cpoe"] is not None]) if any(x["cpoe"] is not None for x in prev) else None)
    g = G.get((y, w, team)) if team else None
    if g:
        k = (y, w, g["opp"])
        if k not in DQ: DQ[k] = dq(y, w, g["opp"])
        o.update(dq=DQ[k], sp=g["sp"], tot=g["tot"], home=g["home"], dome=g["dome"], wind=g["wind"], temp=g["temp"])
    ex.append(o)
df = pd.concat([df.reset_index(drop=True), pd.DataFrame(ex)], axis=1)
df.to_pickle(f"{B}/e24_panel.pkl"); print(len(df), df.groupby("season").size().to_dict()); print(df.notna().mean().round(2).to_dict())
