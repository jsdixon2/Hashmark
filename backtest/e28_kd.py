"""e28: grade K and D/ST projections. What the app shows = Sleeper's weekly projection scored with league scoring
(kdPts: score(LIVE.proj[id], L.scoring)); here pts_std (Sleeper default). Candidate corrections fitted 2021-24
(OLS on runtime inputs), tested on 2025 and 2026: MAE and weeks where the corrected MAE beats Sleeper's."""
import csv, gzip, json, os, sys, collections
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backtest"))
import e19_data
FIX = {"LA": "LAR", "OAK": "LV", "SD": "LAC", "STL": "LAR"}; fx = lambda t: FIX.get(t, t)

def panel():
    rows, G, done = e19_data.build()
    W = {}
    for r in csv.DictReader(gzip.open(os.path.join(ROOT, "bt/nfl/schedules.csv.gz"), "rt")):
        if r["game_type"] != "REG" or int(r["season"]) < 2021: continue
        y, w = int(r["season"]), int(r["week"])
        dome = r["roof"] in ("dome", "closed")
        wind = float(r["wind"]) if r["wind"] not in ("", "NA") else None
        for t, h in ((fx(r["home_team"]), 1), (fx(r["away_team"]), 0)):
            W[(y, w, t)] = {"home": h, "dome": dome, "wind": 0.0 if dome else wind}
    rows.sort(key=lambda r: (r["y"], r["w"], r["pos"], r["id"]))
    hist = collections.defaultdict(list)
    for r in rows:
        r.update(W.get((r["y"], r["w"], r["team"]), {"home": 0, "dome": False, "wind": None}))
        h = hist[(r["y"], r["id"])]
        r["avg"] = sum(h) / len(h) if len(h) >= 2 else None; r["ng"] = len(h)
        if r["pos"] == "DEF" or r.get("played"): h.append(r["pts"])
    return rows

def X(r, spec):
    p = r["proj"]; o = r["oimp"] - 22; i = r["imp"] - 22; a = (r["avg"] - p) if r["avg"] is not None else 0.0
    ha = 1.0 if r["avg"] is not None else 0.0
    wind = r["wind"] if r["wind"] is not None else 0.0
    f = {"proj": [1, p], "imp": [1, p, o, i], "imp+avg": [1, p, o, i, a, ha], "all": [1, p, o, i, a, ha, r["home"]],
         "all+wx": [1, p, o, i, a, ha, r["home"], 1.0 * r["dome"], max(0.0, wind - 10)]}
    return f[spec]

def mae(a, b): return float(np.mean(np.abs(np.array(a) - np.array(b))))

def main():
    rows = panel()
    out = {}
    for pos in ("K", "DEF"):
        R = [r for r in rows if r["pos"] == pos and r["proj"] is not None and r["proj"] > 0 and (pos == "DEF" or r["played"])]
        miss = [r for r in rows if r["pos"] == pos and (r["proj"] is None or r["proj"] <= 0) and (pos == "DEF" or r["played"])]
        print(f"\n== {pos}: rows with projection {len(R)}; played without projection {len(miss)} (app shows 0 for those)")
        tr = [r for r in R if r["y"] <= 2024]
        res = {}
        for spec in ("proj", "imp", "imp+avg", "all", "all+wx"):
            if spec == "all+wx" and pos == "DEF": continue
            Xt = np.array([X(r, spec) for r in tr]); yt = np.array([r["pts"] for r in tr])
            b = np.linalg.lstsq(Xt, yt, rcond=None)[0]
            line = f"  {spec:8s} b={np.round(b,3).tolist()}"
            res[spec] = {"b": [round(float(v), 4) for v in b]}
            for y in (2021, 2022, 2023, 2024, 2025, 2026):
                te = [r for r in R if r["y"] == y]
                if not te: continue
                pr = np.array([X(r, spec) for r in te]) @ b
                sl = [r["proj"] for r in te]; ac = [r["pts"] for r in te]
                wk = collections.defaultdict(lambda: [0, 0, 0])
                for r, p in zip(te, pr):
                    k = wk[r["w"]]; k[0] += abs(r["pts"] - p); k[1] += abs(r["pts"] - r["proj"]); k[2] += 1
                beat = sum(1 for v in wk.values() if v[0] < v[1]); tie = sum(1 for v in wk.values() if v[0] == v[1])
                res[spec][y] = {"n": len(te), "fit": round(mae(pr, ac), 3), "sleeper": round(mae(sl, ac), 3), "weeks": f"{beat}/{len(wk)}"}
                if y >= 2025 or spec == "proj": line += f" | {y} n={len(te)} fit {mae(pr, ac):.3f} vs Sleeper {mae(sl, ac):.3f} ({beat}/{len(wk)} wks)"
            print(line)
        # bias of raw Sleeper by season
        for y in range(2021, 2027):
            te = [r for r in R if r["y"] == y]
            if te: print(f"  {y}: n={len(te)} mean proj {np.mean([r['proj'] for r in te]):.2f} mean pts {np.mean([r['pts'] for r in te]):.2f} Sleeper MAE {mae([r['proj'] for r in te],[r['pts'] for r in te]):.3f}")
        out[pos] = res
    json.dump(out, open(os.path.join(ROOT, ".build/agents/b3/e28_kd.json"), "w"), indent=1)

if __name__ == "__main__" and "lad" not in sys.argv: main()

def lad(Xt, yt, it=60):
    b = np.linalg.lstsq(Xt, yt, rcond=None)[0]
    for _ in range(it):
        w = 1 / np.maximum(np.abs(yt - Xt @ b), .5)
        b = np.linalg.lstsq(Xt * w[:, None] ** .5, yt * w ** .5, rcond=None)[0]
    return b

def main_lad():
    rows = panel()
    for pos in ("K", "DEF"):
        R = [r for r in rows if r["pos"] == pos and r["proj"] is not None and r["proj"] > 0 and (pos == "DEF" or r["played"])]
        tr = [r for r in R if r["y"] <= 2024]
        for spec in ("proj", "imp", "imp+avg", "all+wx"):
            if spec == "all+wx" and pos == "DEF": continue
            b = lad(np.array([X(r, spec) for r in tr]), np.array([r["pts"] for r in tr]))
            line = f"{pos} LAD {spec:8s} b={np.round(b,3).tolist()}"
            for y in (2025, 2026):
                te = [r for r in R if r["y"] == y]; pr = np.array([X(r, spec) for r in te]) @ b
                wk = collections.defaultdict(lambda: [0, 0])
                for r, p in zip(te, pr): wk[r["w"]][0] += abs(r["pts"] - p); wk[r["w"]][1] += abs(r["pts"] - r["proj"])
                line += f" | {y} {mae(pr,[r['pts'] for r in te]):.3f} vs {mae([r['proj'] for r in te],[r['pts'] for r in te]):.3f} ({sum(a<b for a,b in wk.values())}/{len(wk)})"
            print(line)

if __name__ == "__main__" and "lad" in sys.argv: main_lad()
