"""3-way trades (owner: "trade recommendations if tested and proven"). bt/leagues.json.gz dynasty trades 2019-25, players
only (no picks), every player in FantasyPros dynasty consensus at the trade and ~1 year later (bt/hv.json.gz, app curve).
Per team: net value received at the trade (in - out) and one year later. Questions:
 1) Does the value read at the trade name which team ends ahead (net 1-yr change > 0) as well in 3-team as in 2-team trades?
 2) Do teams in 3-team trades end ahead more often / by more than in 2-team trades (is there a 3-way premium to recommend)?"""
import gzip, json, math, re, datetime as dt, collections, statistics as st
H = json.load(gzip.open("bt/hv.json.gz", "rt")); DD = [dt.date.fromisoformat(x) for x in H["d"]]; IDS = H["ids"]
src = open("index.html", encoding="utf-8").read(); VAN = {k: json.loads(re.search(r"const %s=(\[\[.*?\]\]);" % k, src).group(1)) for k in ("VAN1", "VANS")}
def curve(r, A):
    if r <= 1: return A[0][1]
    for (r1, v1), (r2, v2) in zip(A, A[1:]):
        if r <= r2: t = (math.log(r) - math.log(r1)) / (math.log(r2) - math.log(r1)); return math.exp(math.log(v1) + t * (math.log(v2) - math.log(v1)))
    return 5
RK = {f: [({IDS[j]: n + 1 for n, j in enumerate(T)} if T else None) for T in H["t"][k]] for f, k in (("1qb", "do"), ("sf", "dsf"))}
def near(d):
    i = min(range(len(DD)), key=lambda i: abs((DD[i] - d).days)); return i if abs((DD[i] - d).days) <= 21 and RK["sf"][i] else None
L = json.load(gzip.open("bt/leagues.json.gz", "rt"))["leagues"]; out = collections.defaultdict(list)
for l in L.values():
    if str(l["type"]) != "2": continue
    sf = "SUPER_FLEX" in l["pos"] or l["pos"].count("QB") > 1; f = "sf" if sf else "1qb"; A = VAN["VANS" if sf else "VAN1"]
    for t in l.get("tx") or []:
        if t[0] != "trade" or t[5] or len(t[2]) not in (2, 3): continue
        d0 = dt.datetime.fromtimestamp(t[8] / 1000, dt.timezone.utc).date(); i = near(d0); j = near(d0 + dt.timedelta(days=365))
        if i is None or j is None or not RK[f][i] or not RK[f][j]: continue
        got = collections.defaultdict(list); frm = {}
        for pid, rid in (t[3] or {}).items(): got[rid].append(str(pid))
        for pid, rid in (t[4] or {}).items(): frm[str(pid)] = rid
        pl = [p for ps in got.values() for p in ps]
        if not pl or any(p not in RK[f][i] for p in pl) or any(p not in frm for p in pl): continue
        v0 = lambda p: curve(RK[f][i][p], A); v1 = lambda p: curve(RK[f][j].get(p, 600), A)
        rows = []
        for r in t[2]:
            inn = got.get(r, []); og = [p for p in pl if frm[p] == r]
            if not inn and not og: continue
            n0 = sum(map(v0, inn)) - sum(map(v0, og)); n1 = sum(map(v1, inn)) - sum(map(v1, og))
            rows.append((n0, n1, sum(map(v0, og)) + sum(map(v0, inn))))
        if len(rows) == len(t[2]): out[len(t[2])].append(rows)
for k in (2, 3):
    T = out[k]; teams = [r for rows in T for r in rows]
    # 1) ahead at trade (net0 > 3% of what moved) vs ahead a year later
    sel = [(a, b) for a, b, m in teams if abs(a) >= .03 * m / 2 and b != 0]; right = sum((a > 0) == (b > 0) for a, b in sel)
    # 2) share of teams ending ahead and mean net change relative to value moved
    ahead = sum(b > 0 for a, b, m in teams) / len(teams); rel = st.median(b / max(1, m / 2) for a, b, m in teams)
    best = sum(1 for rows in T if max(rows, key=lambda r: r[0]) is max(rows, key=lambda r: r[1])) / len(T)
    print(f"{k}-team trades {len(T):5d} (teams {len(teams)}): value at trade names the team ahead 1 yr later {100*right/max(1,len(sel)):.1f}% (n {len(sel)}); "
          f"top team at trade = top team 1 yr later {100*best:.1f}% (chance {100/k:.0f}%); teams ahead after 1 yr {100*ahead:.1f}%; median net change {100*rel:+.1f}% of value moved")
