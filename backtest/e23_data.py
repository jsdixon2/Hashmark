#!/usr/bin/env python3
"""e23 step 1: rebuild the shipped devy score for draft classes 2016-2023 and attach NFL fantasy outcomes.

Inputs (free, no key): cfbfastR-data player_stats_{2014..2022}.csv + cfb_rosters_{2010..2023}.csv (GitHub, the same files
scripts/build_cfb.py reads), nflverse stats_player_reg_{2016..2026}.csv, bt/nfl/draft_picks|combine|players.csv.gz.
Downloads are expected in $E23_DL (default /tmp/b11/dl) and $E23_NFL (default /tmp/b11/nfl); see FETCH below.
For class D the college pool is built exactly as build_cfb.main() does with cur = D-1 (seasons cur-4..cur, >= 2014),
and the shipped score is recomputed with the same weights. Roster class-year ('year') is unreliable before ~2019
(mostly '4' or the season), so cls = seasons since first roster appearance in the window (as the app can do from p.teams).
Output: $E23_OUT (default /tmp/b11/e23_rows.json), one row per class member (drafted in D, or left college after cur).
"""
import csv, gzip, json, os, pickle, sys, importlib.util
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("bcfb", os.path.join(HERE, "..", "scripts", "build_cfb.py"))
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
DL = os.environ.get("E23_DL", "/tmp/b11/dl"); NFL = os.environ.get("E23_NFL", "/tmp/b11/nfl")
OUT = os.environ.get("E23_OUT", "/tmp/b11/e23_rows.json"); CACHE = os.path.join(DL, "seasons.pkl")
FETCH = ("curl -o $E23_DL/ps_Y.csv .../cfbfastR-data/main/player_stats/csv/player_stats_Y.csv; "
         "ro_Y.csv <- rosters/csv/cfb_rosters_Y.csv; $E23_NFL/reg_Y.csv <- nflverse stats_player/stats_player_reg_Y.csv")
FBS, P5, POS, f, norm, pct_rank = B.FBS, B.P5, B.POS, B.f, B.norm, B.pct_rank


def local_get(url, tries=1, headers=None):
    y = url.rsplit("_", 1)[-1].split(".")[0]
    p = os.path.join(DL, ("ps_" if "player_stats" in url else "ro_") + y + ".csv")
    return open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else None


B.get = local_get


def seasons():
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE, "rb"))
    S = {}
    for y in range(2014, 2023):
        P, G, TM, T, conf = B.parse_season(y)
        S[y] = ({k: dict(v) for k, v in P.items()}, {k: len(v) for k, v in G.items()}, {k: dict(v) for k, v in TM.items()},
                {k: {kk: vv for kk, vv in v.items() if not kk.startswith("g_")} for k, v in T.items()}, conf)
        print("  parsed", y, len(P), file=sys.stderr)
    pickle.dump(S, open(CACHE, "wb"))
    return S


def season_line(pid, y, S):
    P, G, TM, T, conf = S
    p = P.get(pid)
    if not p or not TM.get(pid):
        return None
    team = Counter(TM[pid]).most_common(1)[0][0]; t = T[team]; g = G.get(pid, 0)
    sh = lambda a, b: (a / b) if b else None
    gv = lambda k: p.get(k, 0)
    ln = {"y": y, "team": team, "conf": conf.get(team), "g": g, "tgt": gv("tgt"), "rec": gv("rec"), "ryd": gv("ryd"), "rtd": gv("rtd"),
          "car": gv("car"), "ruyd": gv("ruyd"), "rutd": gv("rutd"), "att": gv("att"), "cmp": gv("cmp"), "pyd": gv("pyd"), "ptd": gv("ptd"), "int": gv("int"),
          "ts": sh(gv("tgt"), t.get("tgt", 0)), "ys": sh(gv("ryd"), t.get("ryd", 0)), "tds": sh(gv("rtd"), t.get("rtd", 0)),
          "yptpa": sh(gv("ryd"), t.get("pa", 0)), "rs": sh(gv("car"), t.get("car", 0)),
          "scrim": sh(gv("ryd") + gv("ruyd"), t.get("ryd", 0) + t.get("ruyd", 0)), "x20": gv("r20"), "x15": gv("r15")}
    ln["dom"] = ((ln["ys"] or 0) + (ln["tds"] or 0)) / 2 if ln["tgt"] else None
    return {k: v for k, v in ln.items() if v not in (None, 0) or k in ("y", "team", "g")}


W = {"WR": [("dom", .3), ("yptpa", .25), ("ts", .15), ("x20", .1), ("bo", .2)], "TE": [("dom", .3), ("yptpa", .25), ("ts", .15), ("x20", .1), ("bo", .2)],
     "RB": [("scrim", .3), ("ts", .15), ("ypc", .15), ("x15", .15), ("bo", .15), ("rtd", .1)], "QB": [("ypa", .3), ("tdint", .15), ("cmp", .15), ("rush", .15), ("att", .1), ("bo", .15)]}


def pool(cur, S, R):
    yrs = [y for y in range(cur - 4, cur + 1)]
    # position: build_cfb takes the roster position as is; older rosters often say '?' or 'NA' (Chubb, Michel), so
    # fall back to the player's position in any other roster year of the window (a fix build_cfb could adopt too)
    PS = {}
    for y in range(cur + 1, cur - 6, -1):
        for aid, r in R.get(y, {}).items():
            if r.get("position") in POS:
                PS.setdefault(aid, r["position"])
    UNK = {"?", "NA", "", "ATH", None}
    ids = {aid for y in (cur, cur - 1) for aid, r in R.get(y, {}).items() if aid in PS or r.get("position") in UNK}
    out = {}
    for aid in ids:
        ro = R.get(cur, {}).get(aid) or R.get(cur - 1, {}).get(aid)
        lines = [ln for y in yrs if y in S for ln in [season_line(aid, y, S[y])] if ln]
        if not lines:
            continue
        if lines[-1].get("conf") not in FBS and not any(l.get("conf") in FBS for l in lines):
            continue
        vol = sum(l.get("tgt", 0) + l.get("car", 0) + l.get("att", 0) for l in lines)
        if vol < 25:
            continue
        if aid not in PS:  # unknown roster position: infer from usage (QB if 50+ attempts, RB if carries > targets, TE if 235+ lb)
            A = {k: sum(l.get(k, 0) for l in lines) for k in ("att", "car", "tgt")}
            PS[aid] = "QB" if A["att"] >= 50 else "RB" if A["car"] > A["tgt"] else "TE" if (f(ro.get("weight")) or 0) >= 235 else "WR"
        first = min(y for y in yrs if aid in R.get(y, {}))
        out[aid] = {"id": aid, "n": f'{ro.get("first_name","")} {ro.get("last_name","")}'.strip(), "pos": ro.get("position") if ro.get("position") in POS else PS[aid], "school": (R.get(cur, {}).get(aid) or ro).get("team"),
                    "conf": lines[-1].get("conf"), "cls": min(5, cur - first + 1), "active": aid in R.get(cur, {}), "wt": f(ro.get("weight")), "ht": f(ro.get("height")),
                    "seasons": lines, "first": first}
    CF_ = lambda l: 1.0 if l.get("conf") in P5 else .88 if l.get("conf") in FBS else .65
    for p in out.values():  # identical to build_cfb.main()
        L = p["seasons"]; pos = p["pos"]; Lq = [l for l in L if l.get("g", 0) >= 4] or L
        def best(k):
            vals = [(l.get(k) or 0) * CF_(l) for l in Lq]
            return (.55 * max(vals) + .45 * vals[-1]) if vals else 0
        p["m"] = m = {}
        if pos in ("WR", "TE"):
            m.update(dom=best("dom"), yptpa=best("yptpa"), ts=best("ts"), ypr=max(((l.get("ryd", 0) / l["rec"]) if l.get("rec") else 0) for l in L),
                     x20=max((l.get("x20", 0) / max(1, l.get("g", 1))) for l in L))
            thr = .2 if pos == "WR" else .15
            bo = next((l for l in L if (l.get("dom") or 0) >= thr and l.get("g", 0) >= 6 and l.get("conf") in FBS), None)
        elif pos == "RB":
            m.update(scrim=best("scrim"), rs=best("rs"), ypc=max(((l.get("ruyd", 0) / l["car"]) if l.get("car", 0) >= 50 else 0) for l in L),
                     ts=best("ts"), x15=max((l.get("x15", 0) / max(1, l.get("g", 1))) for l in L), rtd=max(l.get("rutd", 0) for l in L))
            bo = next((l for l in L if (l.get("scrim") or 0) >= .25 and l.get("g", 0) >= 6 and l.get("conf") in FBS), None)
        else:
            def ypa(l): return (l.get("pyd", 0) / l["att"]) if l.get("att", 0) >= 100 else 0
            m.update(ypa=max(ypa(l) for l in L), cmp=max(((l.get("cmp", 0) / l["att"]) if l.get("att", 0) >= 100 else 0) for l in L),
                     tdint=max(((l.get("ptd", 0) + 1) / (l.get("int", 0) + 1)) if l.get("att", 0) >= 100 else 0 for l in L),
                     rush=max(l.get("ruyd", 0) / max(1, l.get("g", 1)) for l in L), att=sum(l.get("att", 0) for l in L))
            bo = next((l for l in L if l.get("att", 0) >= 200 and ypa(l) >= 8), None)
        p["bo"] = {"y": bo["y"], "cls": max(1, p["cls"] - (cur - bo["y"]))} if bo else None
    for pos, ws in W.items():
        group = [p for p in out.values() if p["pos"] == pos]
        dist = {k: sorted(p["m"].get(k, 0) for p in group) for k, _ in ws if k != "bo"}
        for p in group:
            sc = 0; p["pct"] = {}
            for k, w in ws:
                if k == "bo":
                    c = (p["bo"] or {}).get("cls")
                    v = 1.0 if c and c <= 1 else .8 if c == 2 else .55 if c == 3 else .3 if p["bo"] else 0
                else:
                    v = pct_rank(dist[k], p["m"].get(k, 0)) or 0
                p["pct"][k] = v; sc += v * w
            conf = p.get("conf"); sc *= 1.0 if conf in P5 else .9 if conf in FBS else .8
            if pos in ("WR", "RB", "TE") and p.get("wt"):
                ideal = {"WR": 200, "RB": 210, "TE": 245}[pos]
                sc *= 1 - min(.08, abs(p["wt"] - ideal) / 400)
            p["score"] = round(sc * 100)
    return out


def nfl_outcomes():
    """per gsis id: season -> (ppr, games, rank within position, vor)."""
    REPL = {"QB": 12, "RB": 24, "WR": 36, "TE": 12}; HIT = {"QB": 12, "RB": 24, "WR": 24, "TE": 12}
    o = defaultdict(dict)
    for y in range(2016, 2027):
        rs = [r for r in csv.DictReader(open(os.path.join(NFL, f"reg_{y}.csv"))) if r.get("position") in POS]
        for pos in POS:
            g = sorted((r for r in rs if r["position"] == pos), key=lambda r: (-(f(r["fantasy_points_ppr"]) or 0), r["player_id"]))
            rp = g[REPL[pos] - 1]; rppg = (f(rp["fantasy_points_ppr"]) or 0) / max(1, f(rp["games"]) or 1)
            for i, r in enumerate(g):
                pts = f(r["fantasy_points_ppr"]) or 0; gm = f(r["games"]) or 0
                o[r["player_id"]][y] = {"pts": pts, "g": gm, "rk": i + 1, "hit": i + 1 <= HIT[pos], "vor": max(0.0, pts - rppg * gm), "pos": pos}
    return o


def main():
    S = seasons()
    R = {}
    for y in range(2010, 2024):
        R[y] = {r["athlete_id"]: r for r in csv.DictReader(open(os.path.join(DL, f"ro_{y}.csv"), encoding="utf-8", errors="replace"))}
    picks = [r for r in csv.DictReader(gzip.open(os.path.join(HERE, "..", "bt/nfl/draft_picks.csv.gz"), "rt")) if 2016 <= int(r["season"]) <= 2023]
    comb = {}
    for r in csv.DictReader(gzip.open(os.path.join(HERE, "..", "bt/nfl/combine.csv.gz"), "rt")):
        comb[(norm(r["player_name"]), r["draft_year"] or r["season"])] = r
    pl = defaultdict(list)
    for r in csv.DictReader(gzip.open(os.path.join(HERE, "..", "bt/nfl/players.csv.gz"), "rt")):
        if r.get("position") in POS and r.get("rookie_season"):
            pl[(norm(r["display_name"]), r["position"])].append(r)
    O = nfl_outcomes()
    drafted_ids = {r["gsis_id"] for r in csv.DictReader(gzip.open(os.path.join(HERE, "..", "bt/nfl/draft_picks.csv.gz"), "rt")) if r["gsis_id"]}
    rows = []
    for D in range(2016, 2024):
        cur = D - 1; P = pool(cur, S, R)
        dp = defaultdict(list)
        for r in picks:
            if int(r["season"]) == D and r["position"] in POS | {"FB"}:
                dp[norm(r["pfr_player_name"])].append(r)
        used = set(); names = Counter(norm(p["n"]) for p in P.values() if p["pos"] in POS)
        cw = lambda c: (c or "").lower().replace("st.", "state").split(" ")[0][:5]
        for aid, p in sorted(P.items()):
            if p["pos"] not in POS:
                continue
            ms = dp.get(norm(p["n"]), [])
            if len(ms) > 1:
                ms = [r for r in ms if (r["position"] == p["pos"])] or ms
            ms = [r for r in ms if id(r) not in used and (cw(r["college"]) == cw(p["school"]) or names[norm(p["n"])] == 1)]
            d = ms[0] if len(ms) == 1 else None
            left = p["active"] and aid not in R.get(cur + 1, {}) and p["seasons"][-1]["y"] == cur
            if not d and not left:
                continue
            gsis = None
            if d:
                used.add(id(d)); gsis = d["gsis_id"] if d["gsis_id"] not in ("", "NA") else None
            if not gsis:  # undrafted (or missing id): unique name + position with rookie season D or D+1
                c = [r for r in pl.get((norm(p["n"]), p["pos"]), []) if r["rookie_season"] in (str(D), str(D + 1)) and r["gsis_id"] not in drafted_ids]
                if len(c) == 1:
                    gsis = c[0]["gsis_id"]
            cb = comb.get((norm(p["n"]), str(D)), {})
            oc = O.get(gsis, {}) if gsis else {}
            def win(n):
                ss = [oc.get(y) for y in range(D, D + n) if oc.get(y)]
                tops = sorted((s["pts"] for s in ss), reverse=True)
                return {"hit": any(s["hit"] for s in ss), "vor": sum(s["vor"] for s in ss) / n, "best2": sum(tops[:2]) / 2,
                        "ppg": max([s["pts"] / s["g"] for s in ss if s["g"] >= 6] or [0])}
            rows.append({"D": D, "id": aid, "n": p["n"], "pos": p["pos"], "score": p["score"], "pct": p["pct"], "m": p["m"], "bo": p["bo"], "cls": p["cls"],
                         "conf": p["conf"], "p5": p["conf"] in P5, "fbs": p["conf"] in FBS, "wt": p["wt"], "ht": p["ht"], "nseas": len(p["seasons"]),
                         "drafted": bool(d), "rd": int(d["round"]) if d else None, "pick": int(d["pick"]) if d else None, "age": f(d["age"]) if d else None,
                         "forty": f(cb.get("forty")), "cwt": f(cb.get("wt")), "nfl": bool(gsis), "o3": win(3), "o4": win(4) if D <= 2022 else None,
                         "pool_rank": None})
        # class-internal rank by the shipped score x positional value: the app's projected pick rule
        PV = {"QB": 1.0, "WR": .96, "RB": .86, "TE": .82}
        cls_rows = sorted((r for r in rows if r["D"] == D), key=lambda r: (-r["score"] * PV[r["pos"]], r["id"]))
        for i, r in enumerate(cls_rows):
            r["pool_rank"] = i + 1; r["proj_pick"] = int((i + 1) / .33)
        print(D, len(P), "class rows", len(cls_rows), "drafted", sum(r["drafted"] for r in cls_rows), "of",
              sum(1 for r in picks if int(r["season"]) == D and r["position"] in POS), "hits3", sum(r["o3"]["hit"] for r in cls_rows), file=sys.stderr)
    json.dump(rows, open(OUT, "w"))
    # devy snapshots: the same pool one and two seasons before the player's final college season (underclassmen in the app)
    byid = {}
    for r in rows:
        byid.setdefault(r["id"], r)
    snaps = []
    for cur in range(2014, 2022):
        P = pool(cur, S, R)
        for aid, p in sorted(P.items()):
            c = byid.get(aid)
            if not c or c["D"] - 1 <= cur or c["D"] - 1 - cur > 2 or c["pos"] != p["pos"]:
                continue
            snaps.append({"D": c["D"], "cur": cur, "ahead": c["D"] - 1 - cur, "id": aid, "pos": p["pos"], "score": p["score"], "pct": p["pct"], "bo": p["bo"],
                          "cls": c["cls"], "cls_now": p["cls"], "conf": p["conf"], "p5": p["conf"] in P5, "fbs": p["conf"] in FBS, "wt": p["wt"],
                          "drafted": c["drafted"], "pick": c["pick"], "o3": c["o3"]})
    json.dump(snaps, open(OUT.replace(".json", "_snap.json"), "w"))
    print("snapshots", len(snaps), file=sys.stderr)


if __name__ == "__main__":
    main()
