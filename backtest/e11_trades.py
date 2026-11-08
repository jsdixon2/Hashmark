"""Engine 4 (v68 trade finder rule) on real trades: do trades that fit BOTH teams' plans turn out better for both?
Data: exact weekly rosters + trades (bt/rosters.json.gz), Sleeper weekly stats and projections, dynasty market history
(bt/hv.json.gz, FantasyPros ECR via DynastyProcess), birthdates (backtest/dl/ids.csv).
For every 2-team, in-season (weeks 2-13) trade in dynasty and keeper leagues, 2022-25:
  plan of each side at the time, from its record and points-for rank (the app adds playoff odds; this approximates it):
    rebuilding if win% <= .30 (4+ games) or (win% < .45 and bottom third in points for);
    contender  if win% >= .65 (4+ games) or (win% >= .45 and top third in points for); else middle.
  the v68 fit rule: contender's projected starting lineup +0.3 pts/wk or more; rebuilder takes on no player at his
    position's age cliff - 1 or older and gets 1.5+ years younger on average or adds a pick; market within 20%.
Outcomes per side:
  now: rest-of-regular-season starting-lineup points, post-trade roster vs pre-trade roster (best lineup each week,
       actual points), per week.
  future: dynasty market value one year later of what it received minus what it sent (picks at their value at the time).
  "benefited by its plan": contender -> now > 0; rebuilder -> future > 0; middle -> future > 0 or now > 0.5."""
import json, gzip, os, collections, bisect, datetime as dt, numpy as np, pandas as pd, sys
B = os.path.dirname(os.path.abspath(__file__)); H = os.path.join(B, "..", "bt")
ST = json.load(gzip.open(f"{H}/sleeper_stats.json.gz", "rt"))["w"]
PJ = json.load(gzip.open(f"{H}/sleeper_proj.json.gz", "rt"))["w"]
HV = json.load(gzip.open(f"{H}/hv.json.gz", "rt")); HD = [dt.date.fromisoformat(d) for d in HV["d"]]
LG = json.load(gzip.open(f"{H}/rosters.json.gz", "rt"))["leagues"]
ids = pd.read_csv(B + "/dl/ids.csv", low_memory=False).dropna(subset=["sleeper_id"])
BD = {str(int(s)): b for s, b in zip(ids.sleeper_id, ids.birthdate) if isinstance(b, str)}
POSD = {str(int(s)): p for s, p in zip(ids.sleeper_id, ids.position)}
for w in PJ.values():
    for pid, s in w.items():
        if s.get("pos"): POSD[pid] = s["pos"]
OFF = ("QB", "RB", "WR", "TE"); CLIFF = {"QB": 35, "RB": 27, "WR": 29, "TE": 30}
ELIG = {"QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"}, "FLEX": {"RB", "WR", "TE"}, "WRRB_FLEX": {"RB", "WR"}, "REC_FLEX": {"WR", "TE"}, "SUPER_FLEX": set(OFF)}
A1 = np.array([[1, 10000], [2, 9713], [3, 9455], [6, 8778], [12, 7677], [18, 6782], [24, 6028], [36, 4819], [50, 3762], [75, 2476], [100, 1664], [150, 782], [200, 381], [300, 98], [450, 14], [600, 5]], float)
AS = np.array([[1, 10000], [2, 9766], [3, 9548], [6, 8960], [12, 7959], [18, 7114], [24, 6382], [36, 5178], [50, 4093], [75, 2732], [100, 1849], [150, 870], [200, 421], [300, 103], [450, 14], [600, 5]], float)
PKB = {1: 3772, 2: 2025, 3: 1427, 4: 630, 5: 300}
cv = lambda A, r: float(np.exp(np.interp(np.log(max(1, r)), np.log(A[:, 0]), np.log(A[:, 1]))))
RK = {}
def rank(t, di, pid):
    m = RK.get((t, di))
    if m is None: m = RK[(t, di)] = {HV["ids"][ix]: i + 1 for i, ix in enumerate(HV["t"][t][di])}
    return m.get(pid)
def di_at(d):
    i = bisect.bisect_right(HD, d) - 1; return max(0, i)
def mval(pid, d, sf):
    r = rank("dsf" if sf else "do", di_at(d), pid); return cv(AS if sf else A1, r or 450)
def pkval(y, r, season):
    return PKB.get(r, 200) * (.93 ** max(0, int(y) - (season + 1)))
def age(pid, d):
    b = BD.get(pid)
    if not b: return None
    try: return (d - dt.date.fromisoformat(b[:10])).days / 365.25
    except Exception: return None
def opt(players, val, slots):
    pool = sorted([p for p in players if POSD.get(p) in OFF], key=lambda p: -val(p)); used = set(); tot = 0.0
    for sl in sorted(slots, key=lambda x: len(ELIG[x])):
        for p in pool:
            if p not in used and POSD.get(p) in ELIG[sl]: used.add(p); tot += max(0.0, val(p)); break
    return tot
rows = []
for lg in LG.values():
    s = lg["season"]; typ = lg.get("type")
    if typ not in (1, 2) or s not in (2022, 2023, 2024, 2025): continue
    slots = [x for x in (lg.get("pos") or []) if x in ELIG]
    if not slots: continue
    sf = "SUPER_FLEX" in slots or slots.count("QB") > 1
    rec = (lg.get("sc") or {}).get("rec", 1); key = "pts_ppr" if rec >= .75 else "pts_half_ppr" if rec >= .25 else "pts_std"
    WK = {int(k): v for k, v in (lg.get("weeks") or {}).items()}; last = min(17, (lg.get("pws") or 15) - 1); n = lg.get("n") or 12
    for t in lg.get("tx") or []:
        if t[0] != "trade" or len(t[2] or []) != 2: continue
        w = t[1]
        if not (2 <= w <= 13) or (w - 1) not in WK: continue
        a, b = t[2]; ts = dt.datetime.utcfromtimestamp((t[8] or 0) / 1000).date() if t[8] else dt.date(s, 9, 1) + dt.timedelta(weeks=w)
        pre = {r[0]: [str(x) for x in (r[4] or [])] for r in WK[w - 1]}
        if a not in pre or b not in pre: continue
        # assets each side receives
        inc = {a: [], b: []}
        for pid, rid in (t[3] or {}).items():
            if rid in inc: inc[rid].append(("p", str(pid)))
        for pk in t[5] or []:
            y, rnd, orig, prev, own = pk
            if own in inc: inc[own].append(("k", (int(y), int(rnd))))
        sent = {a: inc[b], b: inc[a]}
        if not inc[a] or not inc[b]: continue
        if any(x[0] == "p" and POSD.get(x[1]) not in OFF for x in inc[a] + inc[b]): continue  # offense only (IDP/K/DEF left out, like the app)
        # records and points-for through week w-1
        W = collections.Counter(); G = collections.Counter(); PF = collections.Counter()
        for k in range(1, w):
            if k not in WK: continue
            by = collections.defaultdict(list)
            for r in WK[k]:
                PF[r[0]] += r[2] or 0
                if r[1] is not None: by[r[1]].append(r)
            for m in by.values():
                if len(m) != 2: continue
                x, y = m
                if (x[2] or 0) == 0 and (y[2] or 0) == 0: continue
                G[x[0]] += 1; G[y[0]] += 1
                if x[2] > y[2]: W[x[0]] += 1
                elif y[2] > x[2]: W[y[0]] += 1
                else: W[x[0]] += .5; W[y[0]] += .5
        pfr = {rid: i + 1 for i, rid in enumerate(sorted(PF, key=lambda r: -PF[r]))}
        def plan(rid):
            g = G[rid]; wp = W[rid] / g if g else .5; pr = pfr.get(rid, n / 2)
            if g >= 4 and wp <= .3: return "rebuilding"
            if g >= 4 and wp >= .65: return "contender"
            if wp < .45 and pr > 2 * n / 3: return "rebuilding"
            if wp >= .45 and pr <= n / 3: return "contender"
            return "middle"
        pj = PJ.get(f"{s}-{w}", {})
        rate = lambda p: (pj.get(p) or {}).get("pts_ppr") or 0.0
        side = {}
        for rid in (a, b):
            o = rid == a and b or a
            gp = [x[1] for x in inc[rid] if x[0] == "p"]; sp = [x[1] for x in sent[rid] if x[0] == "p"]
            post = [p for p in pre[rid] if p not in sp] + gp
            lu = opt(post, rate, slots) - opt(pre[rid], rate, slots)
            ag_in = [age(p, ts) or 26 for p in gp] + [21.5] * sum(1 for x in inc[rid] if x[0] == "k")
            ag_out = [age(p, ts) or 26 for p in sp] + [21.5] * sum(1 for x in sent[rid] if x[0] == "k")
            vets = [p for p in gp if (age(p, ts) or 0) >= CLIFF[POSD[p]] - 1]
            npk = sum(1 for x in inc[rid] if x[0] == "k")
            v_in = sum(mval(x[1], ts, sf) if x[0] == "p" else pkval(*x[1], s) for x in inc[rid])
            v_out = sum(mval(x[1], ts, sf) if x[0] == "p" else pkval(*x[1], s) for x in sent[rid])
            later = ts + dt.timedelta(days=365)
            fut = None
            if later <= HD[-1]:
                f_in = sum(mval(x[1], later, sf) if x[0] == "p" else pkval(*x[1], s) for x in inc[rid])
                f_out = sum(mval(x[1], later, sf) if x[0] == "p" else pkval(*x[1], s) for x in sent[rid])
                fut = (f_in - f_out) / max(1.0, v_in, v_out)
            ks = range(w, last + 1)
            act = lambda k: (lambda p: ((ST.get(f"{s}-{k}", {}).get(p) or {}).get(key) or 0.0))
            now = sum(opt(post, act(k), slots) - opt(pre[rid], act(k), slots) for k in ks) / max(1, len(ks))
            def season_pts(ps, yr):  # PPR points over that whole regular season (0 if he didn't play)
                return sum(((ST.get(f"{yr}-{k}", {}).get(p) or {}).get("pts_ppr") or 0.0) for p in ps for k in range(1, 18))
            nxt = (season_pts(gp, s + 1) - season_pts(sp, s + 1)) if s <= 2024 else None
            nxt2 = (season_pts(gp, s + 2) - season_pts(sp, s + 2)) if s <= 2023 else None
            side[rid] = dict(nxt=nxt, nxt2=nxt2, npl_in=len(gp), npl_out=len(sp), plan=plan(rid), lu=lu, ag_in=np.mean(ag_in), ag_out=np.mean(ag_out), vets=len(vets), npk=npk, v_in=v_in, v_out=v_out, fut=fut, now=now)
        mg = (side[a]["v_out"] - side[a]["v_in"]) / max(1.0, side[a]["v_in"], side[a]["v_out"])
        rows.append(dict(s=s, w=w, typ=typ, lg=lg["id"], mg=mg, **{f"{k}_{i}": v for i, rid in enumerate((a, b)) for k, v in side[rid].items()}))
D = pd.DataFrame(rows); D.to_pickle(B + "/e11_trades.pkl")
print(len(D), "trades;", D.groupby(["typ", "s"]).size().to_dict())
