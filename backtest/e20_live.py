#!/usr/bin/env python3
"""e20 step 2: live win odds replayed on real league matchups (bt/leagues.json.gz, 2023-25, regular season).
Each week's NFL games are grouped into kickoff windows (Thu night, Sun early, Sun late, SNF, MNF, ...). States: every window
at 0/25/50/75/100% of its games' clock, earlier windows final, later ones not started. Starter points by game time come from
play-by-play (e20_pbp.py, league scoring adjusted for receptions / pass TD / INT values); K, DEF, IDP and scoring the
rebuild misses (team score minus rebuilt skill points) accrue evenly over their games. Pregame projections: Hashmark replay
(PPR leagues) or the report's simple projection, like scripts/build_report.py.
shipped: live = so_far + pre x clock share left; variance (proj x .16 + 5)^2 x lineup share left; logistic 1.7 x 1.01.
new: remaining x (1 + g[pos] x team margin / 10) for QB/RB/WR/TE, variance exponent / scale fitted on 2023-24."""
import gzip, json, csv, collections, math, sys, os, re, datetime
sys.path.insert(0, "backtest")
OUT = ".build/agents/b10/"
WP = {"k": .16, "c": 5, "b": 1.01}
G_POS = {"QB": -.14, "RB": -.06, "WR": -.2, "TE": -.2}          # e20_model.py lin+g (fit 2023-24)
FR = (0, .25, .5, .75, 1.0)

def load_pjc():
    return json.loads(re.search(r"const PJC=(\{.*?\});", open("index.html", encoding="utf-8").read()).group(1))

def pts(st, sc):
    rec = sc.get("rec", 1)
    b = st.get("pts_ppr") if rec >= .75 else st.get("pts_half_ppr") if rec >= .25 else st.get("pts_std")
    return b if b is not None else (st.get("pts_ppr") or 0)

def hmS(v, c, w):
    return max(0.0, c[0] + sum(c[1:6]) * v + (0 if w <= 2 else c[8] + c[9])) if c else v

def windows(season):
    G = collections.defaultdict(list)
    for r in csv.DictReader(open("backtest/dl/games.csv")):
        if int(r["season"]) != season or r["game_type"] != "REG": continue
        t = r["gametime"] or "13:00"; h = int(t[:2])
        slot = 0 if h < 12 else 1 if h < 15 else 2 if h < 19 else 3
        G[int(r["week"])].append((r["gameday"], slot, r["game_id"], r["home_team"], r["away_team"]))
    out = {}
    for w, gs in G.items():
        keys = sorted({(d, s) for d, s, *_ in gs})
        out[w] = {"win": {k: i for i, k in enumerate(keys)}, "team": {}, "lab": [datetime.date.fromisoformat(d).strftime("%a") + "-" + ("am","early","late","night")[s] for d, s in keys]}
        for d, s, gid, h, a in gs:
            for t in (h, a): out[w]["team"][t] = (gid, out[w]["win"][(d, s)])
    return out

def main():
    D = json.load(gzip.open(OUT + "pbp_cum.json.gz", "rt"))
    HMP = json.load(gzip.open(OUT + "hm_proj.json.gz", "rt"))
    SP = json.load(gzip.open("bt/sleeper_proj.json.gz", "rt"))["w"]
    C = load_pjc()
    s2g, POS = {}, {}
    for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
        sid = str(r["sleeper_id"]).split(".")[0]
        if sid in ("", "NA"): continue
        POS[sid] = r["position"]
        if r["gsis_id"] not in ("", "NA"): s2g[sid] = r["gsis_id"]
    L = json.load(gzip.open("bt/leagues.json.gz", "rt"))["leagues"]
    recs = []   # one per matchup state: (season, label, f, side data...)
    nm = 0
    for season in (2023, 2024, 2025):
        WIN = windows(season); Ds = D[str(season)]; GG = Ds["G"]
        # team per player-week from pw (incl. K), for players without play-by-play events
        tmw = collections.defaultdict(dict)
        for r in csv.DictReader(open(f"backtest/dl/pw_{season}.csv", encoding="utf-8")):
            if r["season_type"] == "REG": tmw[r["player_id"]][int(r["week"])] = r["team"]
        def team_of(g, w):
            d = tmw.get(g)
            if not d: return None
            return d[min(d, key=lambda x: (abs(x - w), x))]
        lgs = sorted(k for k, v in L.items() if v["season"] == season and not v.get("guillotine"))
        for lid in lgs:
            lg = L[lid]; sc = lg.get("sc") or {}; pws = lg.get("pws") or 15
            rec, ptd, pint = sc.get("rec", 1), sc.get("pass_td", 4), sc.get("pass_int", -1)
            for wk, rows in sorted(lg["weeks"].items(), key=lambda x: int(x[0])):
                w = int(wk); P = SP.get(f"{season}-{w}")
                if not P or w >= pws or w not in WIN: continue
                Wt = WIN[w]["team"]; nwin = len(WIN[w]["win"]); labs = WIN[w]["lab"]
                by = collections.defaultdict(list)
                for rid, mid, pt, st in rows:
                    if mid is not None: by[mid].append((pt, st))
                for pair in by.values():
                    if len(pair) != 2 or pair[0][0] == pair[1][0] or min(pair[0][0], pair[1][0]) <= 0: continue
                    sides = []; ok = True
                    for pt, st in pair:
                        st = [x for x in st if x and x != "0"]
                        hit = [x for x in st if x in P]
                        if not st or len(hit) / len(st) < .9: ok = False; break
                        pl = []; skill_final = 0.0; other = []
                        for x in st:
                            if x.isalpha():
                                t = {"LAR": "LA", "JAC": "JAX"}.get(x, x); pos = "DEF"; g = None
                            else:
                                pos = POS.get(x); g = s2g.get(x); t = None
                            pr = P.get(x)
                            if pr is None: pre = 0.0
                            elif rec >= .75 and HMP.get(f"{season}-{w}-{x}") is not None and pos in G_POS: pre = HMP[f"{season}-{w}-{x}"]
                            else: pre = hmS(pts(pr, sc), C.get(pos), w)
                            d = Ds.get(str(w), {}).get(g) if g else None
                            if d:
                                t = d["t"]
                                cum = [d["c"][i] + (rec - 1) * d["r"][i] + (ptd - 4) * d["p"][i] + (pint + 2) * d["i"][i] for i in range(21)]
                                mg = d["m"]; skill_final += cum[20]
                            else:
                                if t is None and g: t = team_of(g, w)
                                cum = None; mg = None
                            gi = Wt.get(t) if t else None
                            if gi is None:   # bye / unknown team: treat as finished before the week with no points
                                gi = (None, -1)
                            if mg is None and gi[0] in GG:
                                sg = 1 if GG[gi[0]]["h"] == t else -1; mg = [sg * v for v in GG[gi[0]]["m"]]
                            item = {"pre": max(0.0, pre), "win": gi[1], "cum": cum, "m": mg or [0.0] * 21, "pos": pos, "skill": pos in G_POS}
                            if cum is None and pos in G_POS and gi[1] >= 0: item["cum"] = [0.0] * 21   # active but no touches / inactive
                            if item["cum"] is None: other.append(item)
                            pl.append(item)
                        R = pt - skill_final
                        tgt = [o for o in other if o["win"] >= 0] or [o for o in pl if o["win"] >= 0]
                        for o in tgt:
                            if o["cum"] is None: o["cum"] = [R / len(tgt) * i / 20 for i in range(21)]
                            else: o["cum"] = [a + R / len(tgt) * i / 20 for i, a in enumerate(o["cum"])]
                        for o in pl:
                            if o["cum"] is None: o["cum"] = [0.0] * 21
                        sides.append((pt, pl))
                    if not ok: continue
                    nm += 1
                    y = 1 if pair[0][0] > pair[1][0] else 0
                    for j in range(nwin):
                        for f in FR:
                            if j > 0 and f == 0: continue   # same as previous window final
                            i = int(round(f * 20)); row = [season, j, f, nwin, y]
                            for pt, pl in sides:
                                sof = 0.0; rs = 0.0; rg = 0.0; a = 0.0; b = 0.0
                                for o in pl:
                                    if o["win"] < j: ii = 20
                                    elif o["win"] > j: ii = 0
                                    else: ii = i
                                    rem = 1.0 if ii == 0 else 0.0 if ii == 20 else max(.02, 1 - ii / 20)
                                    sof += o["cum"][ii] if ii else 0.0
                                    rs += o["pre"] * rem
                                    gm = 1.0
                                    if o["skill"] and 0 < ii < 20: gm = min(1.6, max(.4, 1 + G_POS[o["pos"]] * o["m"][ii] / 10))
                                    rg += o["pre"] * rem * gm
                                    a += o["pre"]; b += o["pre"] * rem
                                row += [pt, sof, rs, rg, b / a if a > 0 else 1.0, a]
                            row.append(labs[j]); recs.append(row)
        print(season, nm, len(recs), file=sys.stderr)
    json.dump(recs, gzip.open(OUT + "live_states.json.gz", "wt"))

if __name__ == "__main__":
    main()
