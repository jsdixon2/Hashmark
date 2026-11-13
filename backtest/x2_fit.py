"""Build C check: league-only habit measures (what the app can compute from one league's transactions) and whether
they persist from weeks 1-8 to weeks 9-17. bt/rosters.json.gz FAAB leagues 2022-25.
- bid style: log(winning bid / median winning bid in that league that week), averaged per manager (3+ bids per half)
- player-matched check: same as x2 (cross-league median for the same player-week) vs the league-only measure
- does first-half bid style predict who wins contested-looking claims? (share of the league's 20%+-of-budget wins)"""
import gzip, json, collections, math, statistics as st
R = json.load(gzip.open("bt/rosters.json.gz", "rt"))["leagues"]
def corr(xs):
    a = [x for x, _ in xs]; b = [y for _, y in xs]; ma, mb = st.mean(a), st.mean(b)
    return sum((x - ma) * (y - mb) for x, y in xs) / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
H = collections.defaultdict(lambda: ([], [])); big = collections.defaultdict(lambda: [0, 0]); tot = collections.Counter(); spent = collections.defaultdict(lambda: [0, 0])
for l in R.values():
    if l["waiver_type"] != 2 or not l.get("waiver_budget"): continue
    B = l["waiver_budget"]; wk = collections.defaultdict(list)
    for t in l["tx"]:
        if t[0] == "waiver" and t[7] is not None and len(t[2]) == 1: wk[t[1]].append((t[2][0], max(.5, t[7])))
    for w, xs in wk.items():
        if len(xs) < 3: continue
        m = st.median(b for _, b in xs)
        for r, b in xs:
            H[(l["id"], r)][0 if w <= 8 else 1].append(math.log(b / m))
            if w > 8 and b >= .2 * B: big[(l["id"], r)][0] += 1; tot[l["id"]] += 1
            spent[(l["id"], r)][0 if w <= 8 else 1] += b
ps = [(st.mean(a), st.mean(b)) for a, b in H.values() if len(a) >= 3 and len(b) >= 3]
print("league-only bid style persistence r = %.2f (managers %d)" % (corr(ps), len(ps)))
ps.sort(); n = len(ps) // 3
print("  top third early -> later bids %.2fx league-week median; bottom third %.2fx" % (math.exp(st.mean(b for _, b in ps[-n:])), math.exp(st.mean(b for _, b in ps[:n]))))
sp = [(a, b) for a, b in spent.values()]; print("budget spent weeks 1-8 vs 9-17 r = %.2f" % corr(sp))
# who wins the big (20%+ of budget) claims later: top-third early bidders' share vs fair share
share = []; 
for (lid, r), (a, b) in H.items():
    if len(a) >= 3 and tot[lid]: share.append((st.mean(a), big[(lid, r)][0] / tot[lid]))
share.sort(); n = len(share) // 3
print("share of the league's big claims after week 8: top third early style %.1f%%, bottom third %.1f%%" % (100 * st.mean(s for _, s in share[-n:]), 100 * st.mean(s for _, s in share[:n])))
T = collections.defaultdict(lambda: [0, 0]); pairs = []
for l in R.values():
    rids = {t[0] for ws in l["weeks"].values() for t in ws}
    for t in l["tx"]:
        if t[0] == "trade":
            for r in t[2]: T[(l["id"], r)][0 if t[1] <= 8 else 1] += 1
    for r in rids: T[(l["id"], r)]
G = collections.defaultdict(list)
for (lid, r), (a, b) in T.items(): G["0" if a == 0 else "1" if a == 1 else "2+"].append(b)
for k in ("0", "1", "2+"): v = G[k]; print("trades weeks 1-8 = %s: managers %d, made a trade in weeks 9-17 %.0f%%, avg %.2f" % (k, len(v), 100 * sum(x > 0 for x in v) / len(v), st.mean(v)))
