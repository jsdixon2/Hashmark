"""Future rookie picks: (1) what managers really pay for a pick 0/1/2/3 drafts out (implied discount per year), by the
buyer's team status; (2) where a pick traded 1 or 2 years ahead actually landed, by the original owner's status when it
was traded. bt/leagues.json.gz (keeper/dynasty leagues 2019-26, real trades with picks, season-to-season links, drafts),
player values = FantasyPros dynasty consensus at the trade date (bt/hv.json.gz) on the app's 1QB/SF curve.
Pick entries are [season, round, original roster, previous owner, new owner].
Implied pick price: trades where only one side sends picks, all of the same round and years out:
  price per pick = (value of the players it bought - value of players sent with it) / number of picks; medians.
Status at the trade (in-season, week >= 4): points-for rank thirds (contender = top third, rebuilder = bottom third)."""
import gzip, json, datetime as dt, collections, statistics as st, math, re, csv
H = json.load(gzip.open("bt/hv.json.gz", "rt")); D = [dt.date.fromisoformat(x) for x in H["d"]]; IDS = H["ids"]
src = open("index.html", encoding="utf-8").read(); VAN = {k: json.loads(re.search(r"const %s=(\[\[.*?\]\]);" % k, src).group(1)) for k in ("VAN1", "VANS")}
def curve(r, A):
    if r <= 1: return A[0][1]
    for (r1, v1), (r2, v2) in zip(A, A[1:]):
        if r <= r2: t = (math.log(r) - math.log(r1)) / (math.log(r2) - math.log(r1)); return math.exp(math.log(v1) + t * (math.log(v2) - math.log(v1)))
    return 5
RK = {f: [({IDS[j]: n + 1 for n, j in enumerate(T)} if T else None) for T in H["t"][k]] for f, k in (("1qb", "do"), ("sf", "dsf"))}
def near(d):
    i = min(range(len(D)), key=lambda i: abs((D[i] - d).days)); return i if abs((D[i] - d).days) <= 21 else None
L = json.load(gzip.open("bt/leagues.json.gz", "rt"))["leagues"]
nxt = {l["prev"]: l for l in L.values() if l.get("prev")}
def status_at(l, w):
    pf = collections.Counter(); g = collections.Counter()
    for wk, ms in l.get("weeks", {}).items():
        if int(wk) < w:
            for t in ms: pf[t[0]] += t[2]; g[t[0]] += 1
    if not pf or min(g.values()) < 3: return {}
    order = sorted(pf, key=lambda r: -pf[r]); n = len(order)
    return {r: ("contender" if i < n / 3 else "rebuilder" if i >= n * 2 / 3 else "middle") for i, r in enumerate(order)}
PR = collections.defaultdict(list); land = collections.defaultdict(list); ntr = 0
for l in L.values():
    if l["type"] not in (1, 2) or l["status"] != "complete" and l["season"] >= 2026 and False: pass
    if l["type"] not in (1, 2): continue
    f = "sf" if "SUPER_FLEX" in l["pos"] or l["pos"].count("QB") > 1 else "1qb"; A = VAN["VANS" if f == "sf" else "VAN1"]; Y = l["season"]
    for t in l.get("tx", []):
        if t[0] != "trade" or not t[5] or len(t[2]) != 2: continue
        ntr += 1; d0 = dt.datetime.fromtimestamp(t[8] / 1000, dt.timezone.utc).date(); up = Y + 1 if d0 >= dt.date(Y, 9, 1) else Y
        stt = status_at(l, t[1]) if d0 >= dt.date(Y, 9, 1) else {}
        # (2) landing slot of each pick traded 1-2 drafts ahead
        for pk in t[5]:
            ps, rnd, orig = int(pk[0]), pk[1], pk[2]; yo = ps - up
            if yo not in (1, 2) or rnd > 2 or orig not in stt: continue
            lg = l
            for _ in range(ps - Y):
                lg = nxt.get(lg["id"])
                if not lg: break
            if not lg or lg["season"] != ps: continue
            # original owner's slot: final standing of the season before the draft (worst -> pick 1)
            prev = L.get(lg.get("prev"))
            if not prev or not prev.get("rost"): continue
            rost = prev["rost"]; n = len(rost)
            fin = sorted(rost, key=lambda r: (r[1] - r[2], r[4]))   # worst first by record then points
            sl = next((i + 1 for i, r in enumerate(fin) if r[0] == orig), None)
            if sl: land[(yo, stt[orig])].append(sl / n)
        # (1) implied price
        rec = collections.defaultdict(lambda: {"p": [], "k": []})
        for pid, r in t[3].items(): rec[r]["p"].append(pid)
        for pk in t[5]: rec[pk[4]]["k"].append((int(pk[0]) - up, pk[1]))
        sides = [r for r in t[2]]
        kside = [r for r in sides if rec[r]["k"]]
        if len(kside) != 1: continue
        buyer = kside[0]; seller = [r for r in sides if r != buyer][0]; ks = rec[buyer]["k"]
        if len(set(ks)) != 1: continue
        yo, rnd = ks[0]
        if yo < 0 or yo > 3 or rnd > 3: continue
        i = near(d0)
        if i is None or not RK[f][i]: continue
        V = lambda ps: sum(curve(RK[f][i].get(p, 450), A) for p in ps)
        price = (V(rec[seller]["p"]) - V(rec[buyer]["p"])) / len(ks)   # buyer of picks paid players to the seller
        if not rec[seller]["p"] or price <= 0: continue
        PR[(f, rnd, yo, "all")].append(price)
        if stt: PR[(f, rnd, yo, stt.get(buyer, "?"))].append(price)
print("trades with picks", ntr)
print("\nIMPLIED PRICE PER PICK (median value of players paid for it, app curve)")
for f in ("1qb", "sf"):
    for rnd in (1, 2):
        row = []
        for yo in (0, 1, 2, 3):
            xs = PR.get((f, rnd, yo, "all"), [])
            row.append("%d out: %s (n %d)" % (yo, "%5.0f" % st.median(xs) if len(xs) >= 15 else "  -  ", len(xs)))
        print(f, "round", rnd, " | ".join(row))
print("\nBY THE PICK BUYER'S STATUS (in-season trades), round 1, all years out pooled -> median price")
for f in ("1qb", "sf"):
    for s in ("contender", "middle", "rebuilder"):
        xs = [x for yo in (0, 1, 2, 3) for x in PR.get((f, 1, yo, s), [])]
        if xs: print(" ", f, s, "%5.0f (n %d)" % (st.median(xs), len(xs)))
print("\nWHERE PICKS LANDED (slot / teams: 0 = first pick, 1 = last) by ORIGINAL OWNER's status when traded")
for yo in (1, 2):
    for s in ("contender", "middle", "rebuilder"):
        xs = land.get((yo, s), [])
        if xs: print("  %d draft(s) out, owner %-9s n %4d  avg slot %.2f  early third %.0f%%  late third %.0f%%" % (yo, s, len(xs), st.mean(xs), 100 * sum(x <= 1 / 3 for x in xs) / len(xs), 100 * sum(x > 2 / 3 for x in xs) / len(xs)))

# ---- (1b) regression on every trade: sum of picks received - sent = players sent - received (fair on average)
import numpy as np
def fit_prices(rows, keys):
    ix = {k: j for j, k in enumerate(keys)}; X = []; y = []
    for cnt, diff in rows:
        x = [0.0] * len(keys)
        for k, c in cnt.items():
            if k in ix: x[ix[k]] += c
            else: break
        else:
            if any(x): X.append(x); y.append(diff)
    X = np.array(X); y = np.array(y); w = np.ones(len(y))
    for _ in range(30):   # Huber IRLS, scale from MAD
        Wq = np.sqrt(w); b = np.linalg.lstsq(X * Wq[:, None], y * Wq, rcond=None)[0]; r = y - X @ b
        s = 1.4826 * np.median(np.abs(r)) or 1; c = 1.345 * s; w = np.where(np.abs(r) <= c, 1, c / np.abs(r))
    return dict(zip(keys, b)), len(y)
TR = collections.defaultdict(list)
for l in L.values():
    if l["type"] not in (1, 2): continue
    f = "sf" if "SUPER_FLEX" in l["pos"] or l["pos"].count("QB") > 1 else "1qb"; A = VAN["VANS" if f == "sf" else "VAN1"]; Y = l["season"]
    for t in l.get("tx", []):
        if t[0] != "trade" or not t[5] or len(t[2]) != 2: continue
        d0 = dt.datetime.fromtimestamp(t[8] / 1000, dt.timezone.utc).date(); up = Y + 1 if d0 >= dt.date(Y, 9, 1) else Y
        i = near(d0)
        if i is None or not RK[f][i]: continue
        a, b = t[2]; stt = status_at(l, t[1]) if d0 >= dt.date(Y, 9, 1) else {}
        V = lambda r: sum(curve(RK[f][i].get(p, 450), A) for p, rr in t[3].items() if rr == r)
        cnt = collections.Counter()
        for pk in t[5]:
            yo = int(pk[0]) - up; rnd = min(pk[1], 4)
            if yo < 0: continue
            key = (rnd, min(yo, 3)); cnt[key] += 1 if pk[4] == a else -1
        if not cnt or not any(cnt.values()): continue
        TR[f].append((cnt, V(b) - V(a), stt.get(a), stt.get(b)))
print("\nREGRESSION ON ALL TRADES WITH PICKS (value of one pick, app curve; 0 out = the next rookie draft)")
keys = [(r, y) for r in (1, 2, 3, 4) for y in (0, 1, 2, 3)]
for f in ("1qb", "sf"):
    P, n = fit_prices([(c, d) for c, d, *_ in TR[f]], keys)
    print(f, "trades", n)
    for r in (1, 2, 3):
        vals = [P[(r, y)] for y in (0, 1, 2, 3)]
        print("   round %d: %s   per-year change %s" % (r, "  ".join("%d out %5.0f" % (y, v) for y, v in enumerate(vals)), " ".join("%+.0f%%" % (100 * (vals[k + 1] / vals[k] - 1)) if vals[k] > 0 else "?" for k in range(3))))
print("\nPICK PRICE BY WHO RECEIVES THE PICKS (in-season trades): round-1/2 value pooled over years out")
for f in ("1qb", "sf"):
    for s in ("contender", "middle", "rebuilder"):
        rows = []
        for cnt, d, sa, sb in TR[f]:
            # keep trades where the net pick receiver has status s (a receives if counts positive)
            net = sum(cnt.values())
            recv = sa if net > 0 else sb if net < 0 else None
            if recv == s: rows.append((collections.Counter({(k[0] if k[0] <= 2 else 3, 0): v for k, v in cnt.items()}), d))
        if len(rows) < 40: continue
        P, n = fit_prices(rows, [(1, 0), (2, 0), (3, 0)])
        print("  %s receiver %-9s trades %4d  1st %5.0f  2nd %5.0f" % (f, s, n, P[(1, 0)], P[(2, 0)]))
