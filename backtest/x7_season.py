"""Edge test 7: predictable seasonal swings in dynasty value? bt/hv.json.gz: FantasyPros dynasty 1QB consensus ranks
2019-2026 (DynastyProcess history). Value = the app's 1QB curve (VAN1) of the rank. Players ranked <= 200 in mid-November
of season Y; value change to mid-May Y+1 (after the NFL draft) and to early September Y+1, by position x age group.
Ranks are relative, so changes are vs the market as a whole. Predictable = same sign in (almost) every year."""
import gzip, json, csv, datetime as dt, collections, statistics as st, math
H = json.load(gzip.open("bt/hv.json.gz", "rt")); D = [dt.date.fromisoformat(x) for x in H["d"]]; T = H["t"]["do"]; IDS = H["ids"]
VAN = [[1,10000],[2,9713],[3,9455],[6,8778],[12,7677],[18,6782],[24,6028],[36,4819],[50,3762],[75,2476],[100,1664],[150,782],[200,381],[300,98],[450,14],[600,5]]
def val(r):
    if r <= 1: return 10000
    for (r1, v1), (r2, v2) in zip(VAN, VAN[1:]):
        if r <= r2: t = (math.log(r) - math.log(r1)) / (math.log(r2) - math.log(r1)); return math.exp(math.log(v1) + t * (math.log(v2) - math.log(v1)))
    return 5
info = {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    s = str(r.get("sleeper_id") or "").split(".")[0]
    if s not in ("", "NA"): info[s] = (r.get("position"), r.get("birthdate"), r.get("draft_year"))
def near(d):
    i = min(range(len(D)), key=lambda i: abs((D[i] - d).days)); return i if abs((D[i] - d).days) <= 20 else None
def ranks(i): return {IDS[k]: j + 1 for j, k in enumerate(T[i])}
G = collections.defaultdict(lambda: collections.defaultdict(list))
for Y in range(2019, 2026):
    a, b, c = near(dt.date(Y, 11, 12)), near(dt.date(Y + 1, 5, 15)), near(dt.date(Y + 1, 9, 5))
    if a is None or b is None: continue
    A, B = ranks(a), ranks(b); C = ranks(c) if c is not None else None
    for pid, r in A.items():
        if r > 200 or pid not in info: continue
        pos, bd, dy = info[pid]
        if pos not in ("QB", "RB", "WR", "TE") or not bd or bd == "NA": continue
        age = (dt.date(Y, 11, 12) - dt.date.fromisoformat(bd[:10])).days / 365.25
        grp = pos + (" rookie" if dy == str(Y) else " <=23" if age < 24 else " 24-26" if age < 27 else " 27-29" if age < 30 else " 30+")
        v0 = val(r); G[grp][Y].append((val(B.get(pid, 600)) / v0 - 1, (val(C.get(pid, 600)) / v0 - 1) if C else None))
print("%-12s %5s  %-9s %-9s  per year Nov->May" % ("group", "n", "Nov->May", "Nov->Sep"))
for g in sorted(G):
    ys = G[g]; allx = [x for v in ys.values() for x in v]
    if len(allx) < 40: continue
    yr = [st.median(x[0] for x in v) for y, v in sorted(ys.items()) if len(v) >= 5]
    sep = [x[1] for x in allx if x[1] is not None]
    print("%-12s %5d  %+7.0f%%  %+7.0f%%   %s" % (g, len(allx), 100 * st.median(x[0] for x in allx), 100 * st.median(sep) if sep else 0, " ".join("%+.0f" % (100 * v) for v in yr)))
