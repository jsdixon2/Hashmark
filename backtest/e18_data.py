"""e18 (task B8): panel for testing risk score and breakout odds.

One row per (season Y, cut week W, player) for QB/RB/WR/TE with the inputs the app has at runtime
(p.age, p.adv: g/fp/xfp/fp3/xfp3/snap/snap3/ts/ts3/wopr/prev/draft, VAL injh missed weeks, p.inj, p.log)
and the outcomes:
  brk_next  : not yet a top finisher (this season so far or last season) and top-12 QB/TE / top-24 RB/WR in PPR
              points per game NEXT season (min 8 games)
  brk_ros   : same, rest of THIS season (weeks after W, min 4 games)
  bust_ros  : share of his team's remaining games (after W) he missed or scored under 50% of his season-to-date ppg
  drop_next : next season ppg < 70% of this season's (or under 8 games) - season-to-season drop
Data: nflverse weekly stats (backtest/dl/pw_YYYY.csv 2021+, .build/agents/b8/dl/pw_YYYY.csv 2016-20), ffopportunity
expected points (ep_YYYY.csv), bt/nfl/snaps, bt/nfl/injuries, bt/nfl/schedules, backtest/dl/ids.csv, bt/sleeper_proj.
Output: .build/agents/b8/e18_panel.pkl
"""
import csv, gzip, json, math, os, pickle, datetime, collections

R = "/home/user/Hashmark"
DL2 = R + "/.build/agents/b8/dl"
OUT = R + "/.build/agents/b8/e18_panel.pkl"
POS = ("QB", "RB", "WR", "TE")
TOPN = {"QB": 12, "TE": 12, "RB": 24, "WR": 24}
SEASONS = range(2016, 2027)


def fnum(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def src(kind, y):
    p = f"{R}/backtest/dl/{kind}_{y}.csv"
    return p if os.path.exists(p) else f"{DL2}/{kind}_{y}.csv"


def mean(a):
    a = [x for x in a if x is not None]
    return sum(a) / len(a) if a else None


# ---------- ids ----------
IDS = {}
for r in csv.DictReader(open(R + "/backtest/dl/ids.csv")):
    g = r["gsis_id"]
    if g and g != "NA":
        IDS[g] = r

# ---------- schedules: team regular-season game weeks ----------
TGW = collections.defaultdict(set)  # (season, team) -> weeks played
LAST_WK = {}
for r in csv.DictReader(gzip.open(R + "/bt/nfl/schedules.csv.gz", "rt")):
    if r["game_type"] != "REG":
        continue
    y, w = int(r["season"]), int(r["week"])
    if r["home_score"] in ("", "NA"):
        continue
    for t in (r["home_team"], r["away_team"]):
        TGW[(y, t)].add(w)
    LAST_WK[y] = max(LAST_WK.get(y, 0), w)
TEAMFIX = {"LA": "LA", "LAR": "LA", "STL": "LA", "SD": "LAC", "OAK": "LV"}


def tfix(t):
    return TEAMFIX.get(t, t)


TGW2 = collections.defaultdict(set)
for (y, t), ws in TGW.items():
    TGW2[(y, tfix(t))] |= ws

# ---------- sleeper projections (2021+) ----------
SPJ = json.load(gzip.open(R + "/bt/sleeper_proj.json.gz"))["w"]


def load_season(y):
    """weekly rows per gsis id: {wk: dict}"""
    W = collections.defaultdict(dict)
    for r in csv.DictReader(open(src("pw", y))):
        if r.get("season_type") != "REG" or r.get("position") not in POS:
            continue
        w = int(r["week"])
        W[r["player_id"]][w] = {
            "pos": r["position"], "team": tfix(r["team"]), "fp": fnum(r["fantasy_points_ppr"]) or 0.0,
            "ts": fnum(r.get("target_share")), "wopr": fnum(r.get("wopr")),
            "td6": (fnum(r.get("rushing_tds")) or 0) + (fnum(r.get("receiving_tds")) or 0), "td4": fnum(r.get("passing_tds")) or 0,
        }
    if os.path.exists(src("ep", y)):
        for r in csv.DictReader(open(src("ep", y))):
            pid = r["player_id"]
            try:
                w = int(r["week"])
            except ValueError:
                continue
            if pid in W and w in W[pid]:
                W[pid][w]["xfp"] = fnum(r.get("total_fantasy_points_exp"))
    sp = R + f"/bt/nfl/snaps/{y}.csv.gz"
    if os.path.exists(sp):
        for r in csv.DictReader(gzip.open(sp, "rt")):
            if r["game_type"] != "REG":
                continue
            g = r.get("gsis_id")
            w = int(r["week"])
            if g in W and w in W[g]:
                v = fnum(r.get("offense_pct"))
                W[g][w]["snap"] = None if v is None else 100 * v
    INJ = collections.defaultdict(dict)  # gsis -> wk -> status
    ip = R + f"/bt/nfl/injuries/{y}.csv.gz"
    if os.path.exists(ip):
        for r in csv.DictReader(gzip.open(ip, "rt")):
            if r["game_type"] != "REG":
                continue
            st = r.get("report_status") or ""
            if st in ("Out", "Doubtful", "Questionable"):
                INJ[r["gsis_id"]][int(r["week"])] = st
    return W, INJ


def season_ppg(W, wmin=1, wmax=99, mg=8):
    """per pos: ranks of ppg among players with >= mg games in weeks [wmin, wmax]"""
    out = {}
    for pid, wk in W.items():
        L = [o for w, o in wk.items() if wmin <= w <= wmax]
        if len(L) >= mg:
            pos = collections.Counter(o["pos"] for o in L).most_common(1)[0][0]
            out[pid] = (pos, sum(o["fp"] for o in L) / len(L), len(L))
    rk = {}
    for pos in POS:
        xs = sorted(((v[1], pid) for pid, v in out.items() if v[0] == pos), key=lambda t: (-t[0], t[1]))
        for i, (_, pid) in enumerate(xs):
            rk[pid] = i + 1
    return out, rk


def age_at(g, y, w):
    r = IDS.get(g)
    if not r or not r.get("birthdate") or r["birthdate"] == "NA":
        return None
    b = datetime.date.fromisoformat(r["birthdate"])
    d = datetime.date(y, 9, 7) + datetime.timedelta(days=7 * (w - 1))
    return (d - b).days / 365.25


def main():
    data = {y: load_season(y) for y in SEASONS}
    full = {y: season_ppg(data[y][0]) for y in SEASONS}
    rows = []
    for y in SEASONS:
        W, INJ = data[y]
        lastw = LAST_WK.get(y, 0)
        if y == 2026:
            lastw = max(w for wk in W.values() for w in wk)
        cuts = [c for c in (4, 6, 8, 10, 12) if c < lastw] + ([lastw] if y < 2026 else [])
        prev_full = full.get(y - 1)
        nxt = full.get(y + 1) if y + 1 <= 2025 else None
        for cut in cuts:
            # this-season "already a top finisher": ppg rank among players with >= max(2, 40% of max games) games
            gmax = max(len([w for w in wk if w <= cut]) for wk in W.values())
            mg = max(2, round(0.4 * gmax))
            now, now_rk = season_ppg(W, 1, cut, mg)
            ros = season_ppg(W, cut + 1, 99, 4) if cut < lastw - 3 else None
            # population: >=1 game through cut, or >=1 game last season, or drafted this year
            pop = set(pid for pid, wk in W.items() if any(w <= cut for w in wk))
            if prev_full:
                pop |= set(pid for pid, wk in data[y - 1][0].items() if wk)
            for g, r in IDS.items():
                if r.get("draft_year") == str(y) and r.get("position") in POS:
                    pop.add(g)
            for pid in sorted(pop):
                wk = W.get(pid, {})
                L = [(w, wk[w]) for w in sorted(wk) if w <= cut]
                idr = IDS.get(pid, {})
                pos = (collections.Counter(o["pos"] for _, o in L).most_common(1)[0][0] if L else None) or idr.get("position")
                if pos not in POS:
                    continue
                if not L and y - 1 in data and pid in data[y - 1][0]:
                    pos = collections.Counter(o["pos"] for o in data[y - 1][0][pid].values()).most_common(1)[0][0]
                    if pos not in POS:
                        continue
                team = L[-1][1]["team"] if L else None
                tgw = sorted(TGW2.get((y, team), ())) if team else []
                tg = len([w for w in tgw if w <= cut])
                fps = [o["fp"] for _, o in L]
                g = len(L)
                l3 = [o for _, o in L[-3:]]
                pv = data[y - 1][0].get(pid, {}) if y - 1 in data else {}
                pvL = list(pv.values())
                dy = idr.get("draft_year")
                dr = idr.get("draft_round")
                inj_w = INJ.get(pid, {})
                row = {
                    "y": y, "cut": cut, "last": lastw, "pid": pid, "sid": idr.get("sleeper_id"), "name": idr.get("name"), "pos": pos, "team": team,
                    "age": age_at(pid, y, cut), "dy": int(dy) if dy and dy != "NA" else None, "dr": int(dr) if dr and dr != "NA" else None,
                    "g": g, "tg": tg, "fp": mean(fps), "fp3": mean([o["fp"] for o in l3]), "last1": fps[-1] if fps else None,
                    "xfp": mean([o.get("xfp") for _, o in L]), "xfp3": mean([o.get("xfp") for o in l3]),
                    "snap": mean([o.get("snap") for _, o in L]), "snap3": mean([o.get("snap") for o in l3]),
                    "ts": mean([o.get("ts") for _, o in L]), "ts3": mean([o.get("ts") for o in l3]), "wopr": mean([o.get("wopr") for _, o in L]),
                    "pts_w": fps, "snap_w": [o.get("snap") for _, o in L], "td_w": [o["td6"] * 6 + o["td4"] * 4 for _, o in L],
                    "pg": len(pvL), "pfp": mean([o["fp"] for o in pvL]), "pxfp": mean([o.get("xfp") for o in pvL]),
                    "miss": len([w for w, s in inj_w.items() if w <= cut and s in ("Out", "Doubtful")]),
                    "inj_next": inj_w.get(cut + 1),
                }
                # sleeper next-week projection (2021+)
                sk = f"{y}-{cut + 1}"
                if row["sid"] and sk in SPJ:
                    pj = SPJ[sk].get(row["sid"])
                    row["sproj"] = pj.get("pts_ppr") if pj else None
                # already a top finisher
                row["top_now"] = pid in now_rk and now_rk[pid] <= TOPN[pos] and now[pid][0] == pos
                row["top_prev"] = bool(prev_full and pid in prev_full[1] and prev_full[1][pid] <= TOPN[pos] and prev_full[0][pid][0] == pos)
                # outcomes
                if nxt is not None:
                    row["brk_next"] = int(pid in nxt[1] and nxt[1][pid] <= TOPN[pos] and nxt[0][pid][0] == pos)
                    nf = nxt[0].get(pid)
                    row["next_ppg"] = nf[1] if nf else None
                if ros is not None:
                    row["brk_ros"] = int(pid in ros[1] and ros[1][pid] <= TOPN[pos] and ros[0][pid][0] == pos)
                    rem = [w for w in tgw if w > cut]
                    if g >= 3 and len(rem) >= 4 and row["fp"]:
                        thr = 0.5 * row["fp"]
                        bad = sum(1 for w in rem if w not in wk or wk[w]["fp"] < thr)
                        row["bust_ros"] = bad / len(rem)
                        row["miss_ros"] = sum(1 for w in rem if w not in wk) / len(rem)
                        row["nrem"] = len(rem)
                rows.append(row)
        print(y, len(rows), flush=True)
    pickle.dump(rows, open(OUT, "wb"))
    print("rows", len(rows))


if __name__ == "__main__":
    main()
