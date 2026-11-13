"""Build D: injury-type multipliers on Hashmark's projection (proj_panel `hm`, which already has x.97 for questionable).
Cells: (Q, type) = listed Questionable this week and played; (R1, type) = first game back after missing 1+ games that began
with an Out/Doubtful listing of that type; (R23, type) = 2nd-3rd game back. Types grouped as in x6. Multiplier per cell
chosen on a grid to minimise MAE on 2021-23, shrunk to 1 by n/(n+60); tested on 2024-25 (MAE on the cell rows + overall)."""
import csv, collections, statistics as st, sys, json
sys.path.insert(0, "scripts"); import proj_panel as PP
rows = PP.build(range(2021, 2026)); idx = {(r["s"], r["w"], r["pid"]): r for r in rows}
g2s = {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s not in ("", "NA") and r.get("gsis_id") not in ("", "NA", None): g2s[r["gsis_id"]] = s
TYPE = lambda t: "concussion" if "oncuss" in t else "hamstring" if "amstring" in t else "knee" if "Knee" in t else "ankle" if "Ankle" in t else "foot" if t in ("Foot", "Toe") else "soft" if t in ("Groin", "Hip", "Quadricep", "Calf") else "upper" if t in ("Shoulder", "Wrist", "Hand", "Elbow", "Finger", "Thumb") else "torso" if t in ("Back", "Neck", "Rib", "Ribs", "Chest", "Oblique", "Abdomen") else "illness" if t == "Illness" else None
inj = {}
for y in range(2021, 2026):
    for r in csv.DictReader(open(f"backtest/dl/inj_{y}.csv", encoding="utf-8")):
        s = g2s.get(r["gsis_id"]); t = TYPE(r["report_primary_injury"] or "")
        if s and t and r["game_type"] == "REG": inj[(y, int(r["week"]), s)] = (t, r["report_status"])
played = {(r["s"], r["w"], r["pid"]) for r in rows}   # rows only include players who played
from proj_panel import json as _j
import gzip
ST = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]
def gp(y, w, s): x = ST.get(f"{y}-{w}", {}).get(s); return bool(x and x.get("gp"))
cell = {}
for r in rows:
    y, w, s = r["s"], r["w"], r["pid"]; c = inj.get((y, w, s))
    if c and c[1] == "Questionable": cell[(y, w, s)] = ("Q", c[0]); continue
    # games back: find the latest absence start before w
    k = w - 1; back = 0
    while k >= 1 and gp(y, k, s) and back < 3: back += 1; k -= 1
    if k >= 1 and not gp(y, k, s) and back < 3:
        j = k
        while j >= 1 and not gp(y, j, s): j -= 1
        c0 = inj.get((y, j + 1, s))
        if c0 and c0[1] in ("Out", "Doubtful"): cell[(y, w, s)] = ("R1" if back == 0 else "R23", c0[0])
tr = [r for r in rows if r["s"] <= 2023]; te = [r for r in rows if r["s"] >= 2024]
G = collections.defaultdict(list)
for r in tr:
    c = cell.get((r["s"], r["w"], r["pid"]))
    if c: G[c].append(r)
M = {}
for c, rs in G.items():
    best = min((st.mean(abs(r["a"] - r["hm"] * m) for r in rs), m) for m in [x / 100 for x in range(60, 121, 2)])[1]
    M[c] = round(1 + (best - 1) * len(rs) / (len(rs) + 60), 3)
def mae(rs, use): return st.mean(abs(r["a"] - r["hm"] * (M.get(cell.get((r["s"], r["w"], r["pid"])), 1) if use else 1)) for r in rs)
for c in sorted(M): print("|".join(c), "n", len(G[c]), "x%.3f" % M[c])
aff = [r for r in te if cell.get((r["s"], r["w"], r["pid"])) in M]
print("held-out 2024-25 affected n", len(aff), "MAE %.3f -> %.3f" % (mae(aff, False), mae(aff, True)), "| all n", len(te), "%.4f -> %.4f" % (mae(te, False), mae(te, True)))
for kind in ("Q", "R1", "R23"):
    a = [r for r in aff if cell[(r["s"], r["w"], r["pid"])][0] == kind]
    if a: print("  ", kind, "n", len(a), "MAE %.3f -> %.3f" % (mae(a, False), mae(a, True)))
for y in (2024, 2025):
    a = [r for r in aff if r["s"] == y]; print("  ", y, "n", len(a), "MAE %.3f -> %.3f" % (mae(a, False), mae(a, True)))
json.dump({"|".join(c): v for c, v in M.items()}, open("backtest/x6_fit.json", "w"))
print("pooled:")
P = {}
for kind in ("Q", "R1", "R23"):
    rs = [r for r in tr if (cell.get((r["s"], r["w"], r["pid"])) or ("",))[0] == kind]
    P[kind] = min((st.mean(abs(r["a"] - r["hm"] * m) for r in rs), m) for m in [x / 100 for x in range(80, 116)])[1]
    a = [r for r in te if (cell.get((r["s"], r["w"], r["pid"])) or ("",))[0] == kind]
    print("  ", kind, "fit x%.2f (n %d)" % (P[kind], len(rs)), "held-out n", len(a), "MAE %.3f -> %.3f" % (st.mean(abs(r["a"] - r["hm"]) for r in a), st.mean(abs(r["a"] - r["hm"] * P[kind]) for r in a)))
for typ in ("hamstring", "concussion", "soft", "ankle", "knee"):
    for kind in ("Q", "R1"):
        a = [r for r in te if cell.get((r["s"], r["w"], r["pid"])) == (kind, typ)]
        if a: print("   held-out", kind, typ, "n", len(a), "median real/Hashmark %.2f" % st.median(r["a"] / r["hm"] for r in a if r["hm"] > 2))
