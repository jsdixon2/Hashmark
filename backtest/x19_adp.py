"""Data test 2: ADP from the Sleeper drafts in our league archive (bt/leagues.json.gz) vs FantasyPros consensus.
Redraft (type 0, snake, 1QB, 10-14 teams): mean pick per player, players picked in >= 40% of that season's drafts
(undrafted = last pick + 1); vs FantasyPros redraft ECR ("ro") nearest Aug 20. Target: real PPR points that season
(weeks 1-17), and points per game (6+ games). Score: rank correlation over the top 150 by either list.
Rookies (type 2 leagues, drafts where every pick has draft_year == season): mean pick vs FantasyPros dynasty rank on the
nearest Jul 15 (dsf/do by format). Targets: PPR points over the first two NFL seasons; dynasty market rank 1 year later.
Blend weight fitted on 2022-23, tested on 2024-25 (rookies: 2021-22 fit, 2023-24 test, points need 2 seasons)."""
import gzip, json, csv, statistics as st, collections, datetime as dt
import numpy as np
L = json.load(gzip.open("bt/leagues.json.gz", "rt"))["leagues"]; H = json.load(gzip.open("bt/hv.json.gz", "rt")); IDS = H["ids"]
def near(md, y, k):
    t = dt.date(y, *md); best = min((abs((dt.date.fromisoformat(d) - t).days), i) for i, d in enumerate(H["d"]) if H["t"][k][i])
    return {IDS[j]: n + 1 for n, j in enumerate(H["t"][k][best[1]])} if best[0] <= 25 else {}
info = {}; g2s = {}
for r in csv.DictReader(open("backtest/dl/ids.csv")):
    s = r["sleeper_id"]
    if s not in ("", "NA"): info[s] = (r["position"], r["draft_year"]); g2s[r["gsis_id"]] = s
P = collections.defaultdict(float); G = collections.Counter()
for y in range(2021, 2027):
    for r in csv.DictReader(open(f"backtest/dl/pw_{y}.csv")):
        if r["season_type"] == "REG" and int(r["week"]) <= 17 and r["player_id"] in g2s:
            s = g2s[r["player_id"]]; P[(y, s)] += float(r["fantasy_points_ppr"] or 0); G[(y, s)] += 1
def spear(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b)); return float(np.corrcoef(ra, rb)[0, 1])
def adp(drafts):
    pk = collections.defaultdict(list); mx = 0
    for d in drafts:
        n = len(d["picks"]); mx = max(mx, n)
        for p in d["picks"]: pk[str(p[2])].append(p[0] * 1000 + p[1])
    out = {}
    for s, v in pk.items():
        if len(v) >= .4 * len(drafts):
            nums = []
            for d in drafts:
                m = {str(p[2]): i + 1 for i, p in enumerate(sorted(d["picks"], key=lambda p: (p[0], p[1])))}
                nums.append(m.get(s, len(d["picks"]) + 1))
            out[s] = st.mean(nums)
    return out
def ranks(d): return {s: i + 1 for i, s in enumerate(sorted(d, key=d.get))}
print("=== REDRAFT")
rows = []
for y in range(2022, 2027):
    ds = [l["draft"] for l in L.values() if int(l["season"]) == y and str(l["type"]) == "0" and l.get("draft") and l["draft"]["type"] == "snake"
          and "SUPER_FLEX" not in l["pos"] and l["pos"].count("QB") == 1 and 10 <= int(l["n"]) <= 14]
    A = ranks(adp(ds)); E = near((8, 20), y, "ro")
    U = [s for s in set(A) | set(E) if (A.get(s, 999) <= 150 or E.get(s, 999) <= 150) and info.get(s, ("",))[0] in ("QB", "RB", "WR", "TE")]
    for s in U: rows.append(dict(y=y, a=A.get(s, 400), e=E.get(s, 400), pts=P[(y, s)], ppg=P[(y, s)] / G[(y, s)] if G[(y, s)] >= 6 else None))
    print(y, "drafts", len(ds), "players", len(U))
def evr(xs, f, k):
    xs = [x for x in xs if x[k] is not None]; return spear([-f(x) for x in xs], [x[k] for x in xs])
for name, xs in (("2022-23", [x for x in rows if x["y"] <= 2023]), ("2024-25 held out", [x for x in rows if 2024 <= x["y"] <= 2025]), ("2026 (9 weeks)", [x for x in rows if x["y"] == 2026])):
    wb = max([i / 10 for i in range(11)], key=lambda w: evr([x for x in rows if x["y"] <= 2023], lambda x: w * np.log(x["a"]) + (1 - w) * np.log(x["e"]), "pts"))
    print("  %-17s n %4d | season points rank corr: Sleeper ADP %.3f  FantasyPros %.3f  blend(w ADP %.1f, fit 22-23) %.3f | per game: ADP %.3f FP %.3f" % (
        name, len(xs), evr(xs, lambda x: x["a"], "pts"), evr(xs, lambda x: x["e"], "pts"), wb, evr(xs, lambda x: wb * np.log(x["a"]) + (1 - wb) * np.log(x["e"]), "pts"),
        evr(xs, lambda x: x["a"], "ppg"), evr(xs, lambda x: x["e"], "ppg")))
print("=== ROOKIES (dynasty rookie drafts)")
for sf in (True, False):
    rows = []
    for y in range(2021, 2026):
        ds = []
        for l in L.values():
            d = l.get("draft")
            if int(l["season"]) != y or str(l["type"]) != "2" or not d or len(d["picks"]) < 12: continue
            if ("SUPER_FLEX" in l["pos"] or l["pos"].count("QB") > 1) != sf: continue
            if all(info.get(str(p[2]), ("", ""))[1] == str(y) for p in d["picks"]): ds.append(d)
        A = ranks(adp(ds)); k = "dsf" if sf else "do"; E0 = near((7, 15), y, k); E1 = near((7, 15), y + 1, k)
        rk = {s: i + 1 for i, s in enumerate(sorted([s for s in E0 if info.get(s, ("", ""))[1] == str(y)], key=E0.get))}
        U = [s for s in set(A) | set(rk) if (A.get(s, 99) <= 36 or rk.get(s, 99) <= 36) and info.get(s, ("",))[0] in ("QB", "RB", "WR", "TE")]
        for s in U: rows.append(dict(y=y, a=A.get(s, 60), e=rk.get(s, 60), pts=(P[(y, s)] + P[(y + 1, s)]) if y <= 2024 else None, nx=-E1.get(s, 600) if E1 else None))
        print(" ", "SF" if sf else "1QB", y, "rookie drafts", len(ds), "players", len(U))
    for name, xs in (("2021-22", [x for x in rows if x["y"] <= 2022]), ("2023-24 held out", [x for x in rows if x["y"] >= 2023])):
        print("  %-4s %-17s n %3d | 2-season points: ADP %.3f FP %.3f | market 1 yr later: ADP %.3f FP %.3f" % ("SF" if sf else "1QB", name, len(xs),
              evr(xs, lambda x: x["a"], "pts"), evr(xs, lambda x: x["e"], "pts"), evr(xs, lambda x: x["a"], "nx"), evr(xs, lambda x: x["e"], "nx")))
