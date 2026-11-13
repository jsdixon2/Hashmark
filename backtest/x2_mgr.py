"""Edge test 2: do league-mates' habits persist (so profiling them helps)? bt/rosters.json.gz, 900 leagues 2022-25.
Each metric per manager (league-season roster id): first half of the season (weeks 1-8) vs second half (9-17).
- FAAB overpay: log(winning bid / median winning bid for the same player in the same week across all archived FAAB leagues,
  bids as % of budget); persistence = correlation of a manager's halves (3+ bids each half).
- Activity: waiver/FA moves and trades per half.
- Tilt: moves in the week after a loss vs after a win (same manager).
- Partners: share of trades with a partner they already traded with this season vs chance."""
import gzip, json, collections, math, statistics as st, random
R = json.load(gzip.open("bt/rosters.json.gz", "rt"))["leagues"]
def corr(xs):
    if len(xs) < 20: return None
    a = [x for x, _ in xs]; b = [y for _, y in xs]; ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in xs); den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return round(num / den, 3) if den else None
ref = collections.defaultdict(list); bids = []
for l in R.values():
    if l["waiver_type"] != 2 or not l.get("waiver_budget"): continue
    B = l["waiver_budget"]
    for t in l["tx"]:
        if t[0] == "waiver" and t[7] is not None and t[3] and len(t[2]) == 1:
            pid = next(iter(t[3])); pct = max(.25, t[7]) / B * 100
            ref[(l["season"], t[1], pid)].append(pct); bids.append((l["id"], t[2][0], t[1], l["season"], pid, pct))
over = collections.defaultdict(lambda: ([], []))
for lid, rid, w, y, pid, pct in bids:
    r = ref[(y, w, pid)]
    if len(r) < 4: continue
    m = st.median(r); over[(lid, rid)][0 if w <= 8 else 1].append(math.log(pct / m))
pairs = [(st.mean(a), st.mean(b)) for a, b in over.values() if len(a) >= 3 and len(b) >= 3]
print("FAAB overpay persistence r =", corr(pairs), "managers", len(pairs))
# top-vs-bottom tercile of first-half overpay: second-half overpay (as multiple of the median bid)
pairs.sort(); n = len(pairs) // 3
print("  second-half bid vs median: top third %.2fx, bottom third %.2fx" % (math.exp(st.mean(b for _, b in pairs[-n:])), math.exp(st.mean(b for _, b in pairs[:n]))))
act = []; trd = []; tilt = collections.defaultdict(lambda: [0, 0, 0, 0]); rep = [0, 0, 0.0]
for l in R.values():
    mv = collections.Counter(); tr = collections.Counter(); wk = collections.Counter()
    for t in l["tx"]:
        if t[0] in ("waiver", "free_agent") and t[2]: mv[(t[2][0], t[1] <= 8)] += 1; wk[(t[2][0], t[1])] += 1
        if t[0] == "trade": [tr.__setitem__((r, t[1] <= 8), tr[(r, t[1] <= 8)] + 1) for r in t[2]]
    rids = {t[0] for ws in l["weeks"].values() for t in ws}
    for r in rids: act.append((mv[(r, True)], mv[(r, False)])); trd.append((tr[(r, True)], tr[(r, False)]))
    for wkk, ms in l["weeks"].items():
        w = int(wkk); bym = collections.defaultdict(list)
        for t in ms: bym[t[1]].append(t)
        for pr in bym.values():
            if len(pr) != 2: continue
            for i in (0, 1):
                me, op = pr[i], pr[1 - i]; m = me[2] - op[2]; k = "big loss" if m < -25 else "loss" if m < 0 else "win"
                tilt[k][0] += 1; tilt[k][1] += wk[(me[0], w + 1)]
    seen = collections.defaultdict(set); tl = [t for t in l["tx"] if t[0] == "trade" and len(t[2]) == 2]
    for t in sorted(tl, key=lambda t: t[8]):
        a, b = t[2]
        if seen[a]:
            rep[0] += 1; rep[1] += b in seen[a]; rep[2] += len(seen[a]) / max(1, len(rids) - 1)
        seen[a].add(b); seen[b].add(a)
print("waiver/FA activity persistence r =", corr(act), " trades r =", corr(trd))
for k in ("win", "loss", "big loss"): n, m = tilt[k][:2]; print("  moves the week after a %s: %.2f (n %d)" % (k, m / n, n))
print("repeat trade partner: %.1f%% of trades (chance %.1f%%)" % (100 * rep[1] / rep[0], 100 * rep[2] / rep[0]))
