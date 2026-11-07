#!/usr/bin/env python3
"""Weekly nflverse pull for Hashmark's engines and backtests -> bt/nfl/<dataset>/<season>.csv.gz (+ single tables).
Past seasons are written once; the current season is rebuilt every run. Everything is reduced to what the models use
(QB/RB/WR/TE/K focus, gsis ids), so the repo stays small.

datasets: injuries, snaps, depth, ngs, pfr, pbp_team, pbp_player, ftn_team, combine, draft_picks, players, schedules"""
import io, os, sys, time, traceback, urllib.request
from datetime import datetime, timezone
import pandas as pd

NV = "https://github.com/nflverse/nflverse-data/releases/download"
OUT = "bt/nfl"
FIRST = int(os.environ.get("NFL_FIRST", "2016"))
NOW = datetime.now(timezone.utc)
CUR = NOW.year if NOW.month >= 8 else NOW.year - 1
SKILL = ["QB", "RB", "WR", "TE", "FB", "K"]
LOG = []


def fetch(path, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{NV}/{path}", headers={"User-Agent": "hashmark-build"}), timeout=300) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(3 + 5 * k)
        except Exception:
            time.sleep(3 + 5 * k)
    return None


def read(path, **kw):
    b = fetch(path)
    if b is None: return None
    if path.endswith(".parquet"): return pd.read_parquet(io.BytesIO(b), **kw)
    return pd.read_csv(io.BytesIO(b), low_memory=False, compression="gzip" if path.endswith(".gz") else None, **kw)


def save(df, name, season=None):
    d = f"{OUT}/{name}"
    if season is not None: os.makedirs(d, exist_ok=True)
    p = f"{d}/{season}.csv.gz" if season is not None else f"{OUT}/{name}.csv.gz"
    df.to_csv(p, index=False, compression={"method": "gzip", "mtime": 0}, float_format="%.4g")
    LOG.append(f"{name}{'/' + str(season) if season is not None else ''}: {len(df)} rows")


def need(name, season):
    return season >= CUR or not os.path.exists(f"{OUT}/{name}/{season}.csv.gz")


def keep(df, cols):
    return df[[c for c in cols if c in df.columns]]


def players():
    p = read("players/players.csv")
    if p is None: return None
    p = keep(p, ["gsis_id", "pfr_id", "display_name", "position", "birth_date", "height", "weight", "college_name", "draft_year", "draft_round", "draft_pick", "rookie_season", "status", "latest_team"])
    save(p, "players"); return p


def run(fn, *a):
    try:
        fn(*a)
    except Exception as e:
        LOG.append(f"FAILED {fn.__name__}{a}: {e}"); traceback.print_exc()


def injuries(y):
    if not need("injuries", y): return
    d = read(f"injuries/injuries_{y}.csv")
    if d is None: return
    d = d[d.position.isin(SKILL)] if "position" in d else d
    save(keep(d, ["season", "game_type", "week", "team", "gsis_id", "position", "full_name", "report_primary_injury", "report_status", "practice_primary_injury", "practice_status", "date_modified"]), "injuries", y)


def snaps(y, pmap):
    if not need("snaps", y): return
    d = read(f"snap_counts/snap_counts_{y}.csv")
    if d is None: return
    d = d[d.position.isin(SKILL)]
    d["gsis_id"] = d.pfr_player_id.map(pmap)
    save(keep(d, ["season", "game_type", "week", "team", "opponent", "gsis_id", "pfr_player_id", "player", "position", "offense_snaps", "offense_pct", "st_snaps", "st_pct"]), "snaps", y)


def depth(y):
    if not need("depth", y): return
    d = read(f"depth_charts/depth_charts_{y}.csv")
    if d is None: return
    if "depth_team" in d.columns:  # through 2024: one row per player per week
        d = d[d.formation.eq("Offense") & d.depth_position.isin(SKILL)] if "formation" in d else d
        d = keep(d, ["season", "game_type", "week", "club_code", "gsis_id", "full_name", "position", "depth_position", "depth_team"]).rename(columns={"club_code": "team", "depth_team": "depth"})
    else:  # 2025 on: dated snapshots
        pos = "pos_abb" if "pos_abb" in d.columns else "position"
        d = d[d[pos].isin(SKILL)]
        d = keep(d, ["dt", "team", "gsis_id", "player_name", pos, "pos_rank", "pos_grp"]).rename(columns={"pos_rank": "depth", pos: "position"})
        # one snapshot per team per calendar week (the latest), instead of every daily update
        t = pd.to_datetime(d.dt, errors="coerce", utc=True); d = d.assign(_t=t, wk=t.dt.strftime("%G-%V"))
        last = d.groupby(["team", "wk"])._t.transform("max"); d = d[d._t == last].drop(columns=["_t"])
        d["season"] = y
    save(d, "depth", y)


def ngs():
    fr = []
    for t in ("passing", "rushing", "receiving"):
        d = read(f"nextgen_stats/ngs_{t}.parquet")
        if d is None: continue
        d = d[(d.season >= FIRST) & (d.week > 0)].copy(); d["stat_type"] = t
        fr.append(d)
    if not fr: return
    d = pd.concat(fr, ignore_index=True)
    d = d.rename(columns={"player_gsis_id": "gsis_id"})
    for y, q in d.groupby("season"):
        if need("ngs", int(y)): save(q.dropna(axis=1, how="all"), "ngs", int(y))


def pfr(y, pmap):
    if y < 2018 or not need("pfr", y): return
    fr = []
    for t in ("pass", "rush", "rec"):
        d = read(f"pfr_advstats/advstats_week_{t}_{y}.csv")
        if d is None: continue
        d = d.copy(); d["stat_type"] = t; fr.append(d)
    if not fr: return
    d = pd.concat(fr, ignore_index=True)
    d["gsis_id"] = d.pfr_player_id.map(pmap)
    save(d.dropna(axis=1, how="all"), "pfr", y)


PBP_COLS = ["game_id", "play_id", "season", "season_type", "week", "posteam", "defteam", "play_type", "pass_attempt", "rush_attempt", "sack", "epa", "success",
            "xpass", "pass_oe", "air_yards", "yards_after_catch", "yardline_100", "complete_pass", "touchdown", "pass_touchdown", "rush_touchdown",
            "receiver_player_id", "rusher_player_id", "passer_player_id", "qb_scramble", "cpoe", "wp", "half_seconds_remaining", "score_differential", "down", "ydstogo"]


def pbp(y):
    if not (need("pbp_team", y) or need("pbp_player", y) or need("ftn_team", y)): return
    d = read(f"pbp/play_by_play_{y}.parquet", columns=PBP_COLS)
    if d is None: return
    d = d[d.play_type.isin(["pass", "run"]) & d.posteam.notna()].copy()
    d["neutral"] = d.wp.between(.2, .8) & (d.half_seconds_remaining > 120)
    d["rz"] = d.yardline_100 <= 20; d["gl"] = d.yardline_100 <= 5
    g = ["season", "season_type", "week"]
    off = d.groupby(g + ["posteam"]).agg(plays=("epa", "size"), off_epa=("epa", "mean"), off_sr=("success", "mean"), pass_rate=("pass_attempt", "mean"),
                                         proe=("pass_oe", "mean"), rz_plays=("rz", "sum")).reset_index().rename(columns={"posteam": "team"})
    neu = d[d.neutral].groupby(g + ["posteam"]).agg(neutral_pass_rate=("pass_attempt", "mean"), neutral_plays=("epa", "size")).reset_index().rename(columns={"posteam": "team"})
    de = d.groupby(g + ["defteam"]).agg(def_epa=("epa", "mean"), def_sr=("success", "mean"), def_pass_epa=("epa", lambda s: s[d.loc[s.index, "pass_attempt"] == 1].mean()),
                                        def_rush_epa=("epa", lambda s: s[d.loc[s.index, "rush_attempt"] == 1].mean())).reset_index().rename(columns={"defteam": "team"})
    save(off.merge(neu, on=g + ["team"], how="left").merge(de, on=g + ["team"], how="left"), "pbp_team", y)
    # player-week opportunity detail
    p = d[d.pass_attempt == 1]
    rec = p.groupby(g + ["posteam", "receiver_player_id"]).agg(targets=("epa", "size"), air_yards=("air_yards", "sum"), adot=("air_yards", "mean"),
                                                               rz_targets=("rz", "sum"), ez_targets=("yardline_100", lambda s: ((p.loc[s.index, "air_yards"] >= s)).sum()),
                                                               deep_targets=("air_yards", lambda s: (s >= 20).sum()), rec_epa=("epa", "sum")).reset_index().rename(columns={"receiver_player_id": "gsis_id", "posteam": "team"})
    r = d[d.rush_attempt == 1]
    ru = r.groupby(g + ["posteam", "rusher_player_id"]).agg(carries=("epa", "size"), rz_carries=("rz", "sum"), gl_carries=("gl", "sum"), rush_epa=("epa", "sum"),
                                                            scrambles=("qb_scramble", "sum")).reset_index().rename(columns={"rusher_player_id": "gsis_id", "posteam": "team"})
    pa = p.groupby(g + ["posteam", "passer_player_id"]).agg(dropbacks=("epa", "size"), pass_epa=("epa", "sum"), cpoe=("cpoe", "mean"), pass_air=("air_yards", "sum")).reset_index().rename(columns={"passer_player_id": "gsis_id", "posteam": "team"})
    pl = rec.merge(ru, on=g + ["team", "gsis_id"], how="outer").merge(pa, on=g + ["team", "gsis_id"], how="outer")
    tt = p.groupby(g + ["posteam"]).epa.size().rename("team_targets").reset_index().rename(columns={"posteam": "team"})
    pl = pl.merge(tt, on=g + ["team"], how="left"); pl["target_share"] = pl.targets / pl.team_targets
    save(pl.dropna(subset=["gsis_id"]), "pbp_player", y)
    # FTN charting (2022 on): team-week tendencies
    if y >= 2022:
        f = read(f"ftn_charting/ftn_charting_{y}.csv")
        if f is not None:
            f = f.rename(columns={"nflverse_game_id": "game_id", "nflverse_play_id": "play_id"})
            f = f.drop(columns=[c for c in ("season", "week", "season_type", "posteam", "week_number") if c in f.columns])
            m = d[["game_id", "play_id", "season", "season_type", "week", "posteam"]].merge(f, on=["game_id", "play_id"], how="inner")
            flags = [c for c in m.columns if c.startswith("is_") or c in ("n_offense_backfield", "n_defense_box", "n_pass_rushers", "n_blitzers")]
            for c in flags: m[c] = pd.to_numeric(m[c].replace({True: 1, False: 0, "TRUE": 1, "FALSE": 0}), errors="coerce")
            save(m.groupby(g + ["posteam"])[flags].mean().reset_index().rename(columns={"posteam": "team"}), "ftn_team", y)


def singles():
    c = read("combine/combine.csv")
    if c is not None: save(c, "combine")
    dp = read("draft_picks/draft_picks.csv")
    if dp is not None: save(dp, "draft_picks")
    s = read("schedules/games.csv")
    if s is not None: save(s[s.season >= FIRST], "schedules")


def main():
    os.makedirs(OUT, exist_ok=True)
    pl = players()
    pmap = dict(zip(pl.pfr_id, pl.gsis_id)) if pl is not None else {}
    run(singles); run(ngs)
    for y in range(FIRST, CUR + 1):
        for fn, args in ((injuries, (y,)), (snaps, (y, pmap)), (depth, (y,)), (pfr, (y, pmap)), (pbp, (y,))):
            run(fn, *args)
    with open(f"{OUT}/README.md", "w") as f:
        f.write("# nflverse pull for Hashmark\n\nBuilt " + NOW.strftime("%Y-%m-%d %H:%M UTC") + f" for seasons {FIRST}-{CUR}. Source: nflverse (CC-BY 4.0; FTN charting data via nflverse, attribution required).\n\n" + "\n".join("- " + x for x in LOG) + "\n")
    print("\n".join(LOG))
    if any(x.startswith("FAILED") for x in LOG): sys.exit(0)


if __name__ == "__main__":
    main()
