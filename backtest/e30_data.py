"""e30 step 1: player-week panel for the range model (A3) -> .build/agents/a3/work/e30_panel.json.gz
Rows: season, week, pid, pos, Hashmark projection (scripts/proj_panel.py build(), current index.html), actual PPR points,
questionable flag, this season's prior games (count, mean, sd of PPR points), NFL team and opponent."""
import csv, gzip, json, os, sys, statistics as st, collections, importlib.util
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
spec = importlib.util.spec_from_file_location("pp", "scripts/proj_panel.py"); PP = importlib.util.module_from_spec(spec); spec.loader.exec_module(PP)
panel = PP.build(range(2021, 2027))
ST = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]
hist = collections.defaultdict(list)
for key in sorted(ST, key=lambda k: tuple(map(int, k.split("-")))):
    y, w = map(int, key.split("-"))
    for pid, s in ST[key].items():
        if s.get("gp"): hist[(y, pid)].append((w, s.get("pts_ppr") or 0))
g2s = {}
for r in csv.DictReader(open(PP._get("ids.csv", PP.IDS), encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s not in ("", "NA") and r.get("gsis_id") not in ("", "NA", None): g2s[r["gsis_id"]] = s
tm = {}
for y in range(2021, 2027):
    f = f"backtest/dl/pw_{y}.csv"
    if not os.path.exists(f): continue
    for r in csv.DictReader(open(f, encoding="utf-8")):
        s = g2s.get(r["player_id"])
        if s and r.get("season_type") == "REG": tm[(y, int(r["week"]), s)] = (r["team"], r["opponent_team"])
out = []
for r in panel:
    past = [p for w, p in hist[(r["s"], r["pid"])] if w < r["w"]]
    t = tm.get((r["s"], r["w"], r["pid"]), (None, None))
    out.append([r["s"], r["w"], r["pid"], r["pos"], round(r["hm"], 3), round(r["base"], 2), round(r["a"], 2), int(r["q"]), len(past),
                round(st.mean(past), 3) if past else None, round(st.pstdev(past), 3) if len(past) >= 2 else None, t[0], t[1]])
json.dump({"cols": ["s", "w", "pid", "pos", "hm", "base", "a", "q", "n", "mu", "sd", "team", "opp"], "rows": out},
          gzip.open(".build/agents/a3/work/e30_panel.json.gz", "wt"))
print(len(out), collections.Counter(r[0] for r in out))
