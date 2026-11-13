"""Edge test 6: injury type vs what happens next (QB/RB/WR/TE, nflverse injury reports 2021-25 + Sleeper stats/projections).
Per primary injury type: (a) listed Questionable: share who played, and real minus Sleeper projection when they played;
(b) first game back after missing 1+ games: real minus Sleeper projection, that game and the next 2.
Baseline: all player-weeks without an injury listing (real minus projection)."""
import csv, gzip, json, collections, statistics as st
SP = json.load(gzip.open("bt/sleeper_proj.json.gz", "rt"))["w"]; ST = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]
g2s = {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s not in ("", "NA") and r.get("gsis_id") not in ("", "NA", None): g2s[r["gsis_id"]] = s
TYPE = lambda t: "Concussion" if "oncuss" in t else "Hamstring" if "amstring" in t else "Knee" if "Knee" in t else "Ankle" if "Ankle" in t else "Foot/Toe" if t in ("Foot", "Toe") else "Groin/Hip/Quad/Calf" if t in ("Groin", "Hip", "Quadricep", "Calf") else "Shoulder/Arm/Hand" if t in ("Shoulder", "Wrist", "Hand", "Elbow", "Finger", "Thumb") else "Back/Neck/Rib" if t in ("Back", "Neck", "Rib", "Ribs", "Chest", "Oblique", "Abdomen") else "Illness" if t == "Illness" else None
inj = {}
for y in range(2021, 2026):
    for r in csv.DictReader(open(f"backtest/dl/inj_{y}.csv", encoding="utf-8")):
        if r["game_type"] != "REG" or r["position"] not in ("QB", "RB", "WR", "TE"): continue
        s = g2s.get(r["gsis_id"]); t = TYPE(r["report_primary_injury"] or "")
        if s and t: inj[(y, int(r["week"]), s)] = (t, r["report_status"] or "")
def gp(y, w, s): x = ST.get(f"{y}-{w}", {}).get(s); return bool(x and x.get("gp"))
def res(y, w, s):
    x = ST.get(f"{y}-{w}", {}).get(s); p = SP.get(f"{y}-{w}", {}).get(s)
    if not (x and x.get("gp") and p and (p.get("pts_ppr") or 0) >= 3): return None
    return (x.get("pts_ppr") or 0) - p["pts_ppr"]
base = [res(*map(int, k.split("-")), s) for k in SP for s in SP[k] if int(k.split("-")[0]) >= 2021 and (int(k.split("-")[0]), int(k.split("-")[1]), s) not in inj]
base = [x for x in base if x is not None]; print("baseline real minus projection %+.2f (n %d)" % (st.mean(base), len(base)))
Q = collections.defaultdict(lambda: [0, 0, []]); RET = collections.defaultdict(lambda: [[], []]); MISS = collections.defaultdict(list)
for (y, w, s), (t, stt) in inj.items():
    if stt == "Questionable":
        q = Q[t]; q[0] += 1; q[1] += gp(y, w, s); r = res(y, w, s)
        if r is not None: q[2].append(r)
    if stt in ("Out", "Doubtful") and gp(y, w - 1, s) and not gp(y, w, s):   # start of an absence
        k = w
        while k <= 18 and not gp(y, k, s): k += 1
        MISS[t].append(k - w)
        if k <= 18:
            r0 = res(y, k, s); rs = [res(y, j, s) for j in (k, k + 1, k + 2)]; rs = [x for x in rs if x is not None]
            if r0 is not None: RET[t][0].append(r0)
            if rs: RET[t][1].append(st.mean(rs))
print("%-20s %6s %6s %8s | %6s %7s %9s %9s" % ("type", "Q n", "played", "Q resid", "absent", "median", "back game", "back 3g"))
for t in sorted(Q, key=lambda t: -Q[t][0]):
    n, p, r = Q[t]; m = MISS[t]; a, b = RET[t]
    print("%-20s %6d %5.0f%% %+8.2f | %6d %5.0f wk %+9.2f %+9.2f   (n back %d)" % (t, n, 100 * p / n, st.mean(r) if r else 0, len(m), st.median(m) if m else 0, st.mean(a) if a else 0, st.mean(b) if b else 0, len(a)))
