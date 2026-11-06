#!/usr/bin/env python3
"""Build data/adv.json: free advanced metrics keyed by Sleeper player id.

Sources (all free; nflverse data is CC-BY 4.0, FTN charting is CC-BY-SA 4.0):
  nflverse player stats   target share, air-yards share, WOPR, RACR, EPA, CPOE
  ffopportunity (ffverse) expected fantasy points from each player's opportunities
  nflverse play-by-play   red-zone and goal-line usage, team pass rate over expected, pace
  FTN charting            catchable / contested targets, drops, first-read targets, created receptions
  Next Gen Stats          separation, cushion, YAC over expected, rush yards over expected, time to throw
  PFR advanced stats      broken tackles, yards after contact, drops, bad throws, pressure
  PFR snap counts         offensive snap share
  ESPN QBR                QB rating per game
  official injury reports game status and practice participation
  ESPN depth charts       current depth-chart rank
IDs are joined through DynastyProcess's player id table.
"""
import csv, gzip, io, json, os, sys, time, statistics, urllib.request
from collections import defaultdict

NV = "https://github.com/nflverse/nflverse-data/releases/download/"
FF = "https://github.com/ffverse/ffopportunity/releases/download/latest-data/"
DP = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
OFF = {"QB", "RB", "WR", "TE", "FB"}


def get(url, tries=3):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "hashmark-build"}), timeout=180) as r:
                b = r.read()
            return gzip.decompress(b).decode("utf-8", "replace") if url.endswith(".gz") else b.decode("utf-8", "replace")
        except Exception as e:
            if k == tries - 1:
                print("  skip", url, e)
                return None
            time.sleep(3)


def rows(url):
    t = get(url)
    return list(csv.DictReader(io.StringIO(t))) if t else []


def f(x):
    try:
        v = float(x)
        return v if v == v else None
    except Exception:
        return None


def mean(a):
    a = [x for x in a if x is not None]
    return sum(a) / len(a) if a else None


def r2(x, n=2):
    return None if x is None else round(x, n)


def season_now():
    t = time.gmtime()
    return t.tm_year if t.tm_mon >= 8 else t.tm_year - 1


def build(season, ids, light=False):
    """Return {sleeper_id: summary} for one regular season."""
    g2s, p2s, e2s = ids
    P = defaultdict(lambda: {"wk": {}})

    # --- player stats (shares, EPA) ---
    for r in rows(NV + f"stats_player/stats_player_week_{season}.csv"):
        if r.get("season_type") != "REG" or r["player_id"] not in g2s:
            continue
        s = g2s[r["player_id"]]; w = int(r["week"]); o = P[s]["wk"].setdefault(w, {})
        o.update(fp=f(r.get("fantasy_points_ppr")), ts=f(r.get("target_share")), as_=f(r.get("air_yards_share")), wopr=f(r.get("wopr")),
                 racr=f(r.get("racr")), tgt=f(r.get("targets")), car=f(r.get("carries")), ay=f(r.get("receiving_air_yards")),
                 repa=f(r.get("receiving_epa")), ruepa=f(r.get("rushing_epa")), pepa=f(r.get("passing_epa")), cpoe=f(r.get("passing_cpoe")),
                 att=f(r.get("attempts")), team=r.get("team"), pos=r.get("position"))
    # --- expected fantasy points ---
    for r in rows(FF + f"ep_weekly_{season}.csv"):
        if r.get("player_id") not in g2s:
            continue
        s = g2s[r["player_id"]]; w = int(float(r["week"])); o = P[s]["wk"].setdefault(w, {})
        o.update(xfp=f(r.get("total_fantasy_points_exp")), afp=f(r.get("total_fantasy_points")), td=f(r.get("total_touchdown")), xtd=f(r.get("total_touchdown_exp")),
                 xrec=f(r.get("receptions_exp")), xryd=f(r.get("rec_yards_gained_exp")), xruyd=f(r.get("rush_yards_gained_exp")))
    if light:
        return P, {}
    # --- snap counts ---
    for r in rows(NV + f"snap_counts/snap_counts_{season}.csv"):
        if r.get("game_type") != "REG" or r.get("pfr_player_id") not in p2s:
            continue
        s = p2s[r["pfr_player_id"]]; w = int(r["week"]); P[s]["wk"].setdefault(w, {})["snap"] = r2((f(r.get("offense_pct")) or 0) * 100, 1)
    # --- PFR advanced ---
    for kind in ("rec", "rush", "pass"):
        for r in rows(NV + f"pfr_advstats/advstats_week_{kind}_{season}.csv"):
            if r.get("game_type") != "REG" or r.get("pfr_player_id") not in p2s:
                continue
            o = P[p2s[r["pfr_player_id"]]]["wk"].setdefault(int(r["week"]), {})
            if kind == "rec":
                o.update(rbt=f(r.get("receiving_broken_tackles")), drop=f(r.get("receiving_drop")))
            elif kind == "rush":
                o.update(ybc=f(r.get("rushing_yards_before_contact")), yac2=f(r.get("rushing_yards_after_contact")), bt=f(r.get("rushing_broken_tackles")))
            else:
                o.update(bad=f(r.get("passing_bad_throw_pct")), prs=f(r.get("times_pressured_pct")))
    # --- Next Gen Stats (week 0 = season to date; keep weekly rows) ---
    for kind in ("receiving", "rushing", "passing"):
        for r in rows(NV + f"nextgen_stats/ngs_{kind}.csv.gz"):
            if r.get("season") != str(season) or r.get("season_type") != "REG" or r.get("player_gsis_id") not in g2s:
                continue
            w = int(r["week"]); s = g2s[r["player_gsis_id"]]
            tgt = P[s].setdefault("ngs", {}) if w == 0 else P[s]["wk"].setdefault(w, {})
            if kind == "receiving":
                tgt.update(sep=f(r.get("avg_separation")), cush=f(r.get("avg_cushion")), yacoe=f(r.get("avg_yac_above_expectation")), iay=f(r.get("percent_share_of_intended_air_yards")))
            elif kind == "rushing":
                tgt.update(ryoe=f(r.get("rush_yards_over_expected_per_att")), box8=f(r.get("percent_attempts_gte_eight_defenders")), eff=f(r.get("efficiency")))
            else:
                tgt.update(ttt=f(r.get("avg_time_to_throw")), aggr=f(r.get("aggressiveness")), cpoe_ngs=f(r.get("completion_percentage_above_expectation")), iad=f(r.get("avg_intended_air_yards")))
    # --- ESPN QBR ---
    for r in rows(NV + "espn_data/qbr_week_level.csv"):
        if r.get("season") != str(season) or r.get("season_type") != "Regular" or r.get("player_id") not in e2s:
            continue
        try:
            w = int(float(r.get("week_num") or r.get("game_week")))
        except Exception:
            continue
        P[e2s[r["player_id"]]]["wk"].setdefault(w, {})["qbr"] = f(r.get("qbr_total"))
    # --- play-by-play (+ FTN charting): red zone, goal line, first reads, catchable/contested ---
    team = defaultdict(lambda: {"plays": 0, "games": set(), "pass_oe": [], "rz": 0, "gl": 0})
    pbp = get(NV + f"pbp/play_by_play_{season}.csv.gz")
    ftn = {}
    for r in rows(NV + f"ftn_charting/ftn_charting_{season}.csv"):
        ftn[(r.get("nflverse_game_id"), r.get("nflverse_play_id"))] = r
    if pbp:
        for r in csv.DictReader(io.StringIO(pbp)):
            if r.get("season_type") != "REG" or r.get("play_type") not in ("pass", "run"):
                continue
            tm = r.get("posteam"); T = team[tm]; T["plays"] += 1; T["games"].add(r.get("game_id"))
            yl = f(r.get("yardline_100")) or 99; wp = f(r.get("wp")); dn = r.get("down")
            if wp is not None and .2 <= wp <= .8 and dn in ("1", "2") and f(r.get("pass_oe")) is not None:
                T["pass_oe"].append(f(r["pass_oe"]))
            if yl <= 20: T["rz"] += 1
            if yl <= 5: T["gl"] += 1
            who = r.get("receiver_player_id") if r.get("play_type") == "pass" else r.get("rusher_player_id")
            if not who or who not in g2s:
                continue
            s = g2s[who]; w = int(r["week"]); o = P[s]["wk"].setdefault(w, {})
            if yl <= 20: o["rz"] = o.get("rz", 0) + 1
            if yl <= 5: o["gl"] = o.get("gl", 0) + 1
            o.setdefault("team", tm)
            fx = ftn.get((r.get("game_id"), r.get("play_id")))
            if fx and r.get("play_type") == "pass":
                o["ft"] = o.get("ft", 0) + 1
                if fx.get("is_catchable_ball") == "TRUE" or fx.get("is_catchable_ball") == "1": o["catchable"] = o.get("catchable", 0) + 1
                if fx.get("is_contested_ball") in ("TRUE", "1"): o["contested"] = o.get("contested", 0) + 1
                if fx.get("is_created_reception") in ("TRUE", "1"): o["created"] = o.get("created", 0) + 1
                if fx.get("is_drop") in ("TRUE", "1"): o["fdrop"] = o.get("fdrop", 0) + 1
                if fx.get("read_thrown") == "1": o["read1"] = o.get("read1", 0) + 1
    tm_out = {}
    for tm, T in team.items():
        g = max(1, len(T["games"]))
        tm_out[tm] = {"ppg": r2(T["plays"] / g, 1), "proe": r2(mean(T["pass_oe"]), 2), "rzpg": r2(T["rz"] / g, 2), "glpg": r2(T["gl"] / g, 2)}
    # team red-zone share
    for s, v in P.items():
        for w, o in v["wk"].items():
            tm = o.get("team")
            if tm and tm in team and "rz" in o:
                o["rzs"] = None  # filled in summary from totals
    # --- injuries (latest report per player) ---
    for r in rows(NV + f"injuries/injuries_{season}.csv"):
        if r.get("gsis_id") not in g2s:
            continue
        s = g2s[r["gsis_id"]]; w = int(r["week"])
        if w >= P[s].get("injw", 0):
            P[s]["injw"] = w; P[s]["inj"] = [r.get("report_status") or "", r.get("practice_status") or "", r.get("report_primary_injury") or ""]
    # --- depth chart (latest snapshot only) ---
    dc = get(NV + f"depth_charts/depth_charts_{season}.csv")
    if dc:
        last = None; best = {}
        for r in csv.DictReader(io.StringIO(dc)):
            d = r.get("dt", "")
            if last is None or d > last:
                last = d; best = {}
            if d != last or r.get("pos_abb") not in ("QB", "RB", "WR", "TE"):
                continue
            g = r.get("gsis_id")
            if g in g2s:
                rk = int(float(r.get("pos_rank") or 9))
                if rk < best.get(g, 99):
                    best[g] = rk
        for g, rk in best.items():
            P[g2s[g]]["dc"] = rk
    return P, tm_out


def summarize(P, tm, season):
    out = {}
    for s, v in P.items():
        wk = v["wk"]; ws = sorted(w for w, o in wk.items() if o.get("fp") is not None or o.get("xfp") is not None)
        if not ws:
            continue
        L = [wk[w] for w in ws]; l3 = L[-3:]
        g = len(L)
        def col(k, src=L): return [o.get(k) for o in src]
        def tot(k, src=L): return sum(o.get(k) or 0 for o in src)
        fp = mean(col("fp")); xfp = mean(col("xfp")); td = tot("td"); xtd = tot("xtd")
        tg = tot("tgt"); ft = tot("ft")
        team = next((o.get("team") for o in reversed(L) if o.get("team")), None)
        T = tm.get(team or "", {})
        rz = tot("rz"); gl = tot("gl")
        S = {"g": g, "team": team, "pos": next((o.get("pos") for o in reversed(L) if o.get("pos")), None), "fp": r2(fp), "xfp": r2(xfp), "fpoe": r2(None if fp is None or xfp is None else fp - xfp),
             "td": r2(td, 1), "xtd": r2(xtd, 1), "snap": r2(mean(col("snap")), 1), "snap3": r2(mean(col("snap", l3)), 1),
             "ts": r2(mean(col("ts")), 3), "ts3": r2(mean(col("ts", l3)), 3), "as": r2(mean(col("as_")), 3), "wopr": r2(mean(col("wopr")), 3),
             "racr": r2(mean(col("racr"))), "adot": r2(tot("ay") / tg, 1) if tg else None,
             "epat": r2(tot("repa") / tg, 2) if tg else None, "epac": r2(tot("ruepa") / tot("car"), 2) if tot("car") else None,
             "epad": r2(tot("pepa") / tot("att"), 2) if tot("att") else None, "cpoe": r2(mean(col("cpoe")), 1), "qbr": r2(mean(col("qbr")), 1),
             "rz": rz, "gl": gl, "rzpg": r2(rz / g, 2), "rzshare": r2(rz / (T.get("rzpg", 0) * g), 3) if T.get("rzpg") else None,
             "catch": r2(tot("catchable") / ft, 3) if ft >= 8 else None, "cont": r2(tot("contested") / ft, 3) if ft >= 8 else None,
             "read1": r2(tot("read1") / ft, 3) if ft >= 8 else None, "created": tot("created") or None, "drops": tot("drop") or tot("fdrop") or None,
             "ybc": r2(tot("ybc") / tot("car"), 2) if tot("car") >= 10 else None, "yaco": r2(tot("yac2") / tot("car"), 2) if tot("car") >= 10 else None,
             "bt": (tot("bt") + tot("rbt")) or None, "bad": r2(mean(col("bad")), 1), "prs": r2(mean(col("prs")), 1),
             "xfp3": r2(mean(col("xfp", l3))), "fp3": r2(mean(col("fp", l3))),
             "w": [[w, r2(wk[w].get("fp"), 1), r2(wk[w].get("xfp"), 1), wk[w].get("snap"), r2((wk[w].get("ts") or 0) * 100, 1) if wk[w].get("ts") is not None else None] for w in ws]}
        n = v.get("ngs") or {}
        if not n:
            n = {k: mean([o.get(k) for o in L]) for k in ("sep", "cush", "yacoe", "iay", "ryoe", "box8", "eff", "ttt", "aggr", "cpoe_ngs", "iad")}
        for k, val in n.items():
            if val is not None:
                S[k] = r2(val, 2)
        if v.get("inj"):
            S["inj"] = v["inj"]; S["injw"] = v["injw"]
        if v.get("dc"):
            S["dc"] = v["dc"]
        out[s] = {k: val for k, val in S.items() if val is not None}
    return out


def main():
    cur = int(sys.argv[1]) if len(sys.argv) > 1 else season_now()
    idr = rows(DP)
    g2s = {r["gsis_id"]: r["sleeper_id"] for r in idr if r["gsis_id"] not in ("", "NA") and r["sleeper_id"] not in ("", "NA")}
    p2s = {r["pfr_id"]: r["sleeper_id"] for r in idr if r["pfr_id"] not in ("", "NA") and r["sleeper_id"] not in ("", "NA")}
    e2s = {r["espn_id"]: r["sleeper_id"] for r in idr if r["espn_id"] not in ("", "NA") and r["sleeper_id"] not in ("", "NA")}
    ids = (g2s, p2s, e2s)
    P, tm = build(cur, ids)
    cur_s = summarize(P, tm, cur)
    if not cur_s:  # early in a season the new files may not exist yet
        cur -= 1; P, tm = build(cur, ids); cur_s = summarize(P, tm, cur)
    P2, _ = build(cur - 1, ids, light=True)
    prev = summarize(P2, {}, cur - 1)
    for s, v in prev.items():
        keep = {k: v[k] for k in ("g", "fp", "xfp", "fpoe", "ts", "wopr", "snap") if k in v}
        cur_s.setdefault(s, {})["prev"] = keep
    os.makedirs("data", exist_ok=True)
    with open("data/adv.json", "w") as fh:
        json.dump({"asof": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), "season": cur, "teams": tm, "p": cur_s}, fh, separators=(",", ":"))
    print(f"{len(cur_s)} players, {len(tm)} teams, season {cur}; file {os.path.getsize('data/adv.json')//1024} KB")


if __name__ == "__main__":
    main()
