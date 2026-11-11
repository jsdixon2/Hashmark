#!/usr/bin/env python3
"""e20 step 0: rebuild each skill player's PPR points by game time from nflverse play-by-play (2023-2025).
Output .build/agents/b10/pbp_cum.json.gz: {season: {week: {gsis: {"g": game_id, "t": team, "c": [cum pts at elapsed 0,.05..1],
"m": [team score margin at same grid], "f": pbp final incl. OT}}}} plus game info.  Approximate PPR (validated vs pw_*.csv)."""
import gzip, json, os, sys, collections
import pandas as pd, numpy as np
PBP = os.environ.get("HM_PBP", "/tmp/hm_pbp")
OUT = ".build/agents/b10/pbp_cum.json.gz"
GRID = [i / 20 for i in range(21)]
COLS = ["game_id", "season_type", "week", "posteam", "home_team", "away_team", "game_seconds_remaining", "qtr", "play_type",
        "passer_player_id", "receiver_player_id", "rusher_player_id", "passing_yards", "receiving_yards", "rushing_yards",
        "complete_pass", "interception", "pass_touchdown", "td_player_id", "two_point_attempt", "two_point_conv_result",
        "fumble_lost", "fumbled_1_player_id", "fumbled_1_team", "fumbled_2_player_id", "total_home_score", "total_away_score", "play_deleted"]

def nz(x):
    return 0.0 if x is None or (isinstance(x, float) and np.isnan(x)) else float(x)

def build(season):
    df = pd.read_csv(f"{PBP}/play_by_play_{season}.csv.gz", usecols=COLS, low_memory=False)
    df = df[df.season_type == "REG"]
    out = collections.defaultdict(dict)   # week -> gsis -> data
    for gid, g in df.groupby("game_id", sort=True):
        wk = int(g.week.iloc[0]); home, away = g.home_team.iloc[0], g.away_team.iloc[0]
        ev = collections.defaultdict(list)   # pid -> [(elapsed, pts)]
        xv = collections.defaultdict(list)   # pid -> [(elapsed, receptions, pass TDs, interceptions)]
        team = {}
        marg = []  # (elapsed, home-away)
        for r in g.itertuples(index=False):
            if nz(r.play_deleted): continue
            gsr = r.game_seconds_remaining
            q = nz(r.qtr)
            e = 1.0 if q >= 5 or gsr != gsr else max(0.0, min(1.0, (3600 - float(gsr)) / 3600))
            hs, as_ = nz(r.total_home_score), nz(r.total_away_score); marg.append((e, hs - as_))
            pts = collections.defaultdict(float)
            pa, rc, ru = r.passer_player_id, r.receiver_player_id, r.rusher_player_id
            pa = pa if isinstance(pa, str) else None; rc = rc if isinstance(rc, str) else None; ru = ru if isinstance(ru, str) else None
            pos = r.posteam if isinstance(r.posteam, str) else None
            if nz(r.two_point_attempt):
                if r.two_point_conv_result == "success":
                    for p in (pa, rc, ru):
                        if p: pts[p] += 2
            else:
                if pa: pts[pa] += .04 * nz(r.passing_yards) + 4 * nz(r.pass_touchdown) - 2 * nz(r.interception)
                if pa and (nz(r.pass_touchdown) or nz(r.interception)): xv[pa].append((e, 0, nz(r.pass_touchdown), nz(r.interception)))
                if rc and nz(r.complete_pass): xv[rc].append((e, 1, 0, 0))
                if rc: pts[rc] += .1 * nz(r.receiving_yards) + nz(r.complete_pass)
                if ru: pts[ru] += .1 * nz(r.rushing_yards)
                td = r.td_player_id if isinstance(r.td_player_id, str) else None
                if td: pts[td] += 6
            if nz(r.fumble_lost):
                fp = r.fumbled_1_player_id if isinstance(r.fumbled_1_player_id, str) else None
                if fp: pts[fp] -= 2
            for p in (pa, rc, ru):
                if p and pos: team.setdefault(p, pos)
            for p, v in pts.items():
                if v: ev[p].append((e, v))
                else: ev[p]
        marg.sort(key=lambda x: x[0])
        def mat(t):
            out_ = []
            j = 0; cur = 0.0
            for x in GRID:
                while j < len(marg) and marg[j][0] <= x + 1e-9: cur = marg[j][1]; j += 1
                out_.append(cur)
            return out_
        mh = mat(None)
        out["G"][gid] = {"h": home, "a": away, "m": mh, "w": wk}
        for p, es in ev.items():
            t = team.get(p)
            if t not in (home, away): continue
            es.sort(key=lambda x: x[0])
            c = [round(sum(v for e, v in es if e <= x + 1e-9 and (x < 1 or True)), 2) for x in GRID]
            c[-1] = round(sum(v for _, v in es), 2)   # final includes OT
            # cumulative at x<1 excludes OT plays (e=1.0 only at the very end)
            c = [round(sum(v for e, v in es if e <= x + 1e-9), 2) if x < 1 else c[-1] for x in GRID]
            sgn = 1 if t == home else -1
            xs = xv.get(p, [])
            cx = [[sum(x[j] for x in xs if (x[0] <= g + 1e-9 or g >= 1)) for g in GRID] for j in (1, 2, 3)]
            out[wk][p] = {"g": gid, "t": t, "c": c, "m": [sgn * v for v in mh], "r": cx[0], "p": cx[1], "i": cx[2]}
    return out

def main():
    res = {}
    for s in (2023, 2024, 2025):
        res[str(s)] = {str(k): v for k, v in build(s).items()}; print(s, sum(len(v) for v in res[str(s)].values()), file=sys.stderr)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, gzip.open(OUT, "wt"))

if __name__ == "__main__":
    main()
