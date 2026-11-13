"""Edge test 4: do role changes lead points beyond the projections? 2022-25 player-weeks (proj_panel: Hashmark's full
projection `hm` and Sleeper's `base`). Role change before week w = last game's offensive snap share (nflverse snaps) or
target share (targets / team targets, nflverse weekly) minus his previous-3-game average. Outcome: real points minus
Hashmark's projection this week and the next 2 (per game). Bins of the change; edge if the residual moves with it."""
import csv, collections, statistics as st, sys
sys.path.insert(0, "scripts"); import proj_panel as PP
rows = PP.build(range(2022, 2026))
p2s = {}; g2s = {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s in ("", "NA"): continue
    if r.get("pfr_id") not in ("", "NA", None): p2s[r["pfr_id"]] = s
    if r.get("gsis_id") not in ("", "NA", None): g2s[r["gsis_id"]] = s
SN = {}; TG = {}; tt = collections.Counter(); tgt = {}
for y in range(2022, 2026):
    for r in csv.DictReader(open(f"backtest/dl/snap_{y}.csv", encoding="utf-8")):
        s = p2s.get(r["pfr_player_id"])
        if s and r["game_type"] == "REG": SN[(y, int(r["week"]), s)] = float(r["offense_pct"] or 0)
    for r in csv.DictReader(open(f"backtest/dl/pw_{y}.csv", encoding="utf-8")):
        if r["season_type"] != "REG": continue
        w = int(r["week"]); t = float(r.get("targets") or 0); tt[(y, w, r["team"])] += t; s = g2s.get(r["player_id"])
        if s: tgt[(y, w, s)] = (t, r["team"])
for (y, w, s), (t, tm) in tgt.items():
    if tt[(y, w, tm)]: TG[(y, w, s)] = t / tt[(y, w, tm)]
def delta(D, y, w, s):
    last = D.get((y, w - 1, s)); prev = [D.get((y, w - k, s)) for k in (2, 3, 4)]; prev = [x for x in prev if x is not None]
    return None if last is None or len(prev) < 2 else last - st.mean(prev)
idx = {(r["s"], r["w"], r["pid"]): r for r in rows}
def fut(y, w, s):
    xs = [idx.get((y, k, s)) for k in (w, w + 1, w + 2)]; xs = [x for x in xs if x]
    return (st.mean(x["a"] - x["hm"] for x in xs), st.mean(x["a"] - x["base"] for x in xs)) if xs else None
for name, D, bins in (("snap share", SN, [-1, -.15, -.05, .05, .15, 1]), ("target share", TG, [-1, -.08, -.03, .03, .08, 1])):
    B = collections.defaultdict(list)
    for r in rows:
        if r["pos"] == "QB" or r["hm"] < 3 or r["w"] < 5: continue
        d = delta(D, r["s"], r["w"], r["pid"]); f = fut(r["s"], r["w"], r["pid"])
        if d is None or f is None: continue
        b = next(i for i in range(len(bins) - 1) if bins[i] <= d < bins[i + 1]); B[(b, r["s"] >= 2024)].append(f)
    print(name)
    for b in range(len(bins) - 1):
        for te in (False, True):
            xs = B[(b, te)]
            if xs: print("  change %+.2f..%+.2f %s n %5d  real minus Hashmark %+.2f  minus Sleeper %+.2f" % (bins[b], bins[b + 1], "2024-25" if te else "2022-23", len(xs), st.mean(x[0] for x in xs), st.mean(x[1] for x in xs)))
