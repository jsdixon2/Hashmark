"""F1 / e33 item 4: how often Questionable players play. Final NFL injury report (bt/nfl/injuries, report_status
Questionable, final practice_status) for QB/RB/WR/TE, regular season 2021-26, team played that week. Played = any
offensive or special-teams snap (bt/nfl/snaps). Level = PPR points per game in his earlier games this season
(nflverse weekly, >= 2 games): <8 / 8-14 / 14+ / none. Tables fitted on 2021-24, checked on 2025-26 (Brier):
overall rate vs by practice vs practice x position vs practice x level."""
import csv, gzip, json, os, collections
import numpy as np
B = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(B)
PR = {"Did Not Participate In Practice": "DNP", "Limited Participation in Practice": "LP", "Full Participation in Practice": "FP"}
rows = []
for y in range(2021, 2027):
    snap = collections.defaultdict(set); teams = collections.defaultdict(set)
    for r in csv.DictReader(gzip.open(f"{R}/bt/nfl/snaps/{y}.csv.gz", "rt")):
        if r["game_type"] != "REG": continue
        w = int(r["week"]); teams[w].add(r["team"])
        if (float(r["offense_snaps"] or 0) > 0 or float(r["st_snaps"] or 0) > 0) and r.get("gsis_id"): snap[w].add(r["gsis_id"])
    pts = collections.defaultdict(dict)
    for r in csv.DictReader(open(f"{B}/dl/pw_{y}.csv")):
        if r["season_type"] == "REG": pts[r["player_id"]][int(r["week"])] = float(r["fantasy_points_ppr"] or 0)
    for r in csv.DictReader(gzip.open(f"{R}/bt/nfl/injuries/{y}.csv.gz", "rt")):
        if r["game_type"] != "REG" or r["report_status"] != "Questionable" or r["position"] not in ("QB", "RB", "WR", "TE"): continue
        w = int(r["week"])
        if r["team"] not in teams[w]: continue
        g = r["gsis_id"]; prev = [v for k, v in pts.get(g, {}).items() if k < w]
        ppg = sum(prev) / len(prev) if len(prev) >= 2 else None
        lvl = "none" if ppg is None else "<8" if ppg < 8 else "8-14" if ppg < 14 else "14+"
        rows.append(dict(y=y, w=w, pos=r["position"], ps=PR.get(r["practice_status"], "-"), lvl=lvl, ppg=ppg, played=g in snap[w]))
print("Questionable QB/RB/WR/TE player-weeks:", len(rows), {y: sum(1 for r in rows if r["y"] == y) for y in range(2021, 2027)})
TR = [r for r in rows if r["y"] <= 2024]; TE = [r for r in rows if r["y"] >= 2025]
def table(R, key, k=20):
    base = np.mean([r["played"] for r in R]); c = collections.defaultdict(list)
    for r in R: c[key(r)].append(r["played"])
    return {g: (sum(v) + k * base) / (len(v) + k) for g, v in c.items()}, base
def brier(R, T, key, base):
    return float(np.mean([(T.get(key(r), base) - r["played"]) ** 2 for r in R]))
KEYS = {"overall": lambda r: 0, "practice": lambda r: r["ps"], "practice x pos": lambda r: (r["ps"], r["pos"]),
        "practice x level": lambda r: (r["ps"], r["lvl"]), "practice x pos x level": lambda r: (r["ps"], r["pos"], r["lvl"])}
out = {"n": len(rows), "brier": {}, "tables": {}}
for name, f in KEYS.items():
    T, b = table(TR, f)
    out["brier"][name] = {s: round(brier([r for r in TE if r["y"] == s], T, f, b), 4) for s in (2025, 2026)}
    print(f"{name:24s} held-out Brier 2025 {out['brier'][name][2025]}  2026 {out['brier'][name][2026]}")
def rate(R): return (round(float(np.mean([r["played"] for r in R])), 3), len(R)) if R else (None, 0)
for dim in ("ps", "pos", "lvl"):
    for g in sorted({r[dim] for r in rows}):
        a = rate([r for r in TR if r[dim] == g]); b = rate([r for r in TE if r[dim] == g])
        out["tables"][f"{dim}={g}"] = {"2021-24": a, "2025-26": b}; print(f"{dim}={g:6s} 2021-24 {a}  2025-26 {b}")
for ps in ("FP", "LP", "DNP"):
    for lv in ("14+", "8-14", "<8", "none"):
        a = rate([r for r in TR if r["ps"] == ps and r["lvl"] == lv]); b = rate([r for r in TE if r["ps"] == ps and r["lvl"] == lv])
        out["tables"][f"{ps}|{lv}"] = {"2021-24": a, "2025-26": b}; print(f"{ps:4s} {lv:5s} 2021-24 {a}  2025-26 {b}")
    for pos in ("QB", "RB", "WR", "TE"):
        a = rate([r for r in TR if r["ps"] == ps and r["pos"] == pos]); b = rate([r for r in TE if r["ps"] == ps and r["pos"] == pos])
        out["tables"][f"{ps}|{pos}"] = {"2021-24": a, "2025-26": b}; print(f"{ps:4s} {pos:5s} 2021-24 {a}  2025-26 {b}")
A = [r for r in rows if r["ps"] in ("FP", "LP", "DNP")]
out["ship_all_2021_26"] = {ps: rate([r for r in rows if r["ps"] == ps]) for ps in ("FP", "LP", "DNP", "-")}
out["ship_all_2021_26"]["all"] = rate(rows)
print("all seasons:", out["ship_all_2021_26"])
json.dump(out, open(B + "/e33_q.json", "w"), indent=1)
# regulars only (>= 8 PPR pts/game in 2+ earlier games): the players start/sit decisions are about
print("\nregulars (ppg >= 8):")
REG = lambda r: r["ppg"] is not None and r["ppg"] >= 8
TRr = [r for r in TR if REG(r)]; TEr = [r for r in TE if REG(r)]
out["regulars"] = {"brier": {}, "rates": {}}
for name in ("overall", "practice", "practice x pos", "practice x level"):
    f = KEYS[name]; T, b = table(TRr, f)
    out["regulars"]["brier"][name] = {s: round(brier([r for r in TEr if r["y"] == s], T, f, b), 4) for s in (2025, 2026)}
    print(f"  {name:20s} held-out Brier 2025 {out['regulars']['brier'][name][2025]}  2026 {out['regulars']['brier'][name][2026]}")
for ps in ("FP", "LP", "DNP"):
    for pos in ("QB", "RB", "WR", "TE", "ALL"):
        sel = lambda R: [r for r in R if r["ps"] == ps and (pos == "ALL" or r["pos"] == pos)]
        a, b, c = rate(sel(TRr)), rate(sel(TEr)), rate(sel(TRr + TEr))
        out["regulars"]["rates"][f"{ps}|{pos}"] = {"2021-24": a, "2025-26": b, "2021-26": c}; print(f"  {ps:4s} {pos:4s} 2021-24 {a}  2025-26 {b}  all {c}")
json.dump(out, open(B + "/e33_q.json", "w"), indent=1)
# shipped table (v127 Q127): regulars 2021-26, practice x position, shrunk k=10 to the practice rate, nearest 5%
ALLr = TRr + TEr; ship = {}
for ps in ("FP", "LP", "DNP", "-"):
    P = [r for r in ALLr if r["ps"] == ps] or ALLr; pr = np.mean([r["played"] for r in P])
    ship[ps] = {"*": int(round(pr * 20) * 5)}
    for pos in ("QB", "RB", "WR", "TE"):
        v = [r["played"] for r in P if r["pos"] == pos]; ship[ps][pos] = int(round((sum(v) + 10 * pr) / (len(v) + 10) * 20) * 5)
ship["all"] = int(round(np.mean([r["played"] for r in ALLr]) * 20) * 5)
out["ship"] = ship; print("ship", ship, "n regulars", len(ALLr))
json.dump(out, open(B + "/e33_q.json", "w"), indent=1)
