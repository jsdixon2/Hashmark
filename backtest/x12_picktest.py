"""Do better pick values grade real trades better? Dynasty leagues (bt/leagues.json.gz), trades between two teams with
at least one pick for a rookie draft that later happened in the archive. Outcome at T = that draft (latest pick in the
trade) + 180 days: each side's real value = its players' consensus value at T + the value at T of the rookies actually
drafted with its picks (found in the next seasons' rookie drafts; the pick's owner made the pick). Prediction at the
trade: players' consensus value then + picks valued by a rule. Score: share of trades where the rule names the side
that ended ahead (sides within 5% at T skipped) and mean |log(predicted ratio / real ratio)|. Rules:
  app    PKB round value x .93 per year beyond the next draft; next-draft 1sts early/mid/late by the original owner's
         status at the trade (top third -> late, bottom third -> early); rebuild/contend multipliers left out (they are
         value-to-team, not value)
  new(d,s) round value x d per year beyond the next draft; slot lean for the next draft as app, for the draft after at
         strength s (0 = mid, 1 = same as next draft)
Fit d/s on trades made 2019-22, test on 2023+."""
import gzip, json, datetime as dt, collections, statistics as st, math, re
H = json.load(gzip.open("bt/hv.json.gz", "rt")); D = [dt.date.fromisoformat(x) for x in H["d"]]; IDS = H["ids"]
src = open("index.html", encoding="utf-8").read(); VAN = {k: json.loads(re.search(r"const %s=(\[\[.*?\]\]);" % k, src).group(1)) for k in ("VAN1", "VANS")}
PKB = {"1qb": {1: 3772, 2: 2025, 3: 1427, 4: 630, 5: 300}, "sf": {1: 3722, 2: 1990, 3: 1397, 4: 615, 5: 300}}
PKSLOT = {"1qb": [4401, 3772, 3274], "sf": [5060, 3722, 3271]}
def curve(r, A):
    if r <= 1: return A[0][1]
    for (r1, v1), (r2, v2) in zip(A, A[1:]):
        if r <= r2: t = (math.log(r) - math.log(r1)) / (math.log(r2) - math.log(r1)); return math.exp(math.log(v1) + t * (math.log(v2) - math.log(v1)))
    return 5
RK = {f: [({IDS[j]: n + 1 for n, j in enumerate(T)} if T else None) for T in H["t"][k]] for f, k in (("1qb", "do"), ("sf", "dsf"))}
def near(d):
    i = min(range(len(D)), key=lambda i: abs((D[i] - d).days)); return i if abs((D[i] - d).days) <= 21 else None
L = json.load(gzip.open("bt/leagues.json.gz", "rt"))["leagues"]; nxt = {l["prev"]: l for l in L.values() if l.get("prev")}
def status_at(l, w):
    pf = collections.Counter(); g = collections.Counter()
    for wk, ms in l.get("weeks", {}).items():
        if int(wk) < w:
            for t in ms: pf[t[0]] += t[2]; g[t[0]] += 1
    if not pf or min(g.values()) < 3: return {}
    o = sorted(pf, key=lambda r: -pf[r]); n = len(o); return {r: (0 if i < n / 3 else 2 if i >= n * 2 / 3 else 1) for i, r in enumerate(o)}  # 0 contender
items = []
for l in L.values():
    if l["type"] != 2: continue
    f = "sf" if "SUPER_FLEX" in l["pos"] or l["pos"].count("QB") > 1 else "1qb"; A = VAN["VANS" if f == "sf" else "VAN1"]; Y = l["season"]
    for t in l.get("tx", []):
        if t[0] != "trade" or not t[5] or len(t[2]) != 2: continue
        d0 = dt.datetime.fromtimestamp(t[8] / 1000, dt.timezone.utc).date(); up = Y + 1 if d0 >= dt.date(Y, 9, 1) else Y
        i = near(d0)
        if i is None or not RK[f][i]: continue
        stt = status_at(l, t[1]) if d0 >= dt.date(Y, 9, 1) else {}
        a, b = t[2]; picks = []; ok = True; last = 0
        for pk in t[5]:
            ps, rnd, orig, new = int(pk[0]), pk[1], pk[2], pk[4]; yo = ps - up
            if yo < 0 or rnd > 4: ok = False; break
            lg = l
            for _ in range(ps - Y):
                lg = nxt.get(lg["id"]);
                if not lg: break
            dr = lg and lg.get("draft") or {}
            if not lg or lg["season"] != ps or not dr.get("picks") or dr.get("rounds", 9) > 6: ok = False; break
            mine = [p for p in dr["picks"] if p[0] == rnd and p[3] == new]
            if not mine: ok = False; break
            n = len(lg.get("rost") or []) or 12; slot = (mine[0][1] - 1) % n + 1
            picks.append(dict(to=new, rnd=rnd, yo=yo, st=stt.get(orig, 1) if yo <= 1 else 1, pid=mine[0][2], ps=ps)); last = max(last, ps)
        if not ok or not picks: continue
        T = near(dt.date(last, 5, 15) + dt.timedelta(days=180))
        if T is None or not RK[f][T]: continue
        pv = lambda r, j: sum(curve(RK[f][j].get(p, 450), A) for p, rr in t[3].items() if rr == r)
        real = {r: pv(r, T) + sum(curve(RK[f][T].get(k["pid"], 450), A) for k in picks if k["to"] == r) for r in (a, b)}
        items.append(dict(f=f, y=Y, a=a, b=b, now={r: pv(r, i) for r in (a, b)}, picks=picks, real=real))
print("dynasty trades with picks traced to the real draft:", len(items), " 2019-22:", sum(x["y"] <= 2022 for x in items), " 2023+:", sum(x["y"] >= 2023 for x in items))
def val(k, f, d, s, app=False):
    base = PKB[f][min(k["rnd"], 5)]
    if k["rnd"] == 1 and k["yo"] == 0: base = PKSLOT[f][2 - k["st"]] if k["st"] != 1 else PKSLOT[f][1]
    if k["rnd"] == 1 and k["yo"] == 1 and not app: base = PKSLOT[f][1] + s * ((PKSLOT[f][2 - k["st"]] if k["st"] != 1 else PKSLOT[f][1]) - PKSLOT[f][1])
    return base * (d ** k["yo"])
def score(xs, d, s, app=False):
    n = right = 0; err = []
    for x in xs:
        P = {r: x["now"][r] + sum(val(k, x["f"], d, s, app) for k in x["picks"] if k["to"] == r) for r in (x["a"], x["b"])}
        Ra, Rb = x["real"][x["a"]], x["real"][x["b"]]
        if min(P.values()) <= 0 or min(Ra, Rb) <= 0: continue
        err.append(abs(math.log(P[x["a"]] / P[x["b"]]) - math.log(Ra / Rb)))
        if abs(Ra - Rb) < .05 * max(Ra, Rb): continue
        n += 1; right += (P[x["a"]] > P[x["b"]]) == (Ra > Rb)
    return right / n if n else 0, st.mean(err) if err else 0, n
tr = [x for x in items if x["y"] <= 2022]; te = [x for x in items if x["y"] >= 2023]
best = max(((d, s) for d in (.93, .9, .85, .8, .75, .7, .65) for s in (0, .5, 1)), key=lambda p: -score(tr, *p)[1])
print("fit on 2019-22 (lowest log error): discount per year %.2f, second-year slot lean %.1f" % best)
for name, xs in (("2019-22 (fit)", tr), ("2023+ (held out)", te)):
    a = score(xs, .93, 0, True); b = score(xs, *best); c = score(xs, .8, .5)
    print("%-17s app: right %.1f%%, error %.3f (n %d) | fitted: right %.1f%%, error %.3f | 20%%/yr + half lean: right %.1f%%, error %.3f" % (name, 100 * a[0], a[1], a[2], 100 * b[0], b[1], 100 * c[0], c[1]))
for d in (.93, .85, .8, .75, .7):
    print("  discount %.2f held-out error %.3f right %.1f%%" % (d, score(te, d, .5)[1], 100 * score(te, d, .5)[0]))
print("\nextra: discount 1.00 / .97 and overall pick level (x m), held out 2023+")
for d in (1.0, .97, .93):
    print("  discount %.2f error %.3f right %.1f%%" % (d, score(te, d, 0)[1], 100 * score(te, d, 0)[0]))
_val = val
for m in (.8, .9, 1.0, 1.1, 1.2):
    val = lambda k, f, d, s, app=False, m=m: m * _val(k, f, d, s, app)
    print("  pick level x%.1f: fit-years error %.3f, held-out error %.3f right %.1f%%" % (m, score(tr, .93, 0, True)[1], score(te, .93, 0, True)[1], 100 * score(te, .93, 0, True)[0]))
val = _val
# how much do future picks really hold vs what managers pay? realized value at T of picks by years out (1sts)
print("\nreal value of 1sts at draft + 180 days, by years out when traded (median):")
for f in ("1qb", "sf"):
    by = collections.defaultdict(list)
    for x in items:
        if x["f"] != f: continue
        for k in x["picks"]:
            if k["rnd"] == 1: by[k["yo"]].append(x)
    print(" ", f, {yo: len(v) for yo, v in sorted(by.items())})
