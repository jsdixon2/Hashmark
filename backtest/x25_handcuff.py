"""x25 (owner: does value account for handcuffs, e.g. Kaelon Black behind an ageing, injury-prone McCaffrey?). Three parts.
Lead back (RB1) and backup (RB2) per team = most / second-most RB offensive snaps before a checkpoint week W (4 or 10).
"Clear" backup = RB2 had 1.5x+ the snaps of RB3. Availability from nflverse snap counts 2016-25 (a game with no offensive
snap, or played for another team, = missed); fantasy points (PPR) from nflverse weekly 2021-25.
 1. Step-in: when RB1 misses a game, what does RB2 score (vs games RB1 plays)?
 2. Miss risk: does age / past missed games / workload / games already missed predict RB1 missing 3+ of the remaining
    games? Logistic fit 2017-21, tested 2022-25 (AUC vs age alone and vs no model).
 3. Market: FantasyPros dynasty ranks (bt/hv.json.gz) in early November 2021-24, RBs ranked 25-250. Do backups behind a
    lead back the model calls fragile (top third of predicted miss risk) beat rank-matched peers on (a) PPR points from
    week 10 through the next season and (b) dynasty value one year later? Residuals from log(outcome) ~ log(value now)
    fitted on all RBs in the band; groups compared with bootstrap 95% CIs."""
import csv, gzip, json, math, re, random, statistics as st, datetime as dt
from collections import defaultdict
import numpy as np
random.seed(7)
# ---------- ids
G2S, BIRTH, POSS = {}, {}, {}
for r in csv.DictReader(open("backtest/dl/ids.csv", encoding="utf-8")):
    g = r.get("gsis_id"); s = str(r.get("sleeper_id") or "").split(".")[0]
    if g and g != "NA":
        if s not in ("", "NA"): G2S[g] = s
        try: BIRTH[g] = dt.date.fromisoformat(r["birthdate"])
        except Exception: pass
    if s not in ("", "NA"): POSS[s] = r.get("position")
S2G = {s: g for g, s in G2S.items()}
# ---------- snaps
TG = defaultdict(lambda: defaultdict(set))          # season -> team -> weeks played
PLAY = defaultdict(dict)                            # (season, gsis) -> week -> (team, snaps)
RBS = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))  # season -> team -> gsis -> {week: snaps} via key
RBW = defaultdict(list)                             # (season, team, gsis) -> [(week, snaps)]
NAME = {}
for y in range(2016, 2026):
    for r in csv.DictReader(gzip.open(f"bt/nfl/snaps/{y}.csv.gz", "rt")):
        if r["game_type"] != "REG": continue
        w = int(r["week"]); t = r["team"]; g = r["gsis_id"]
        TG[y][t].add(w)
        if not g or g == "NA": continue
        sn = float(r["offense_snaps"] or 0); PLAY[(y, g)][w] = (t, sn); NAME[g] = r["player"]
        if r["position"] == "RB": RBW[(y, t, g)].append((w, sn))
# ---------- points
PTS = {}
for y in range(2021, 2026):
    for r in csv.DictReader(open(f"backtest/dl/pw_{y}.csv", encoding="utf-8")):
        if r["season_type"] != "REG": continue
        PTS[(y, r["player_id"], int(r["week"]))] = float(r["fantasy_points_ppr"] or 0)
def played(y, g, w, t):
    x = PLAY.get((y, g), {}).get(w); return bool(x and x[0] == t and x[1] > 0)
def season_avail(y, g):
    wk = PLAY.get((y, g))
    if not wk: return None
    n = sum(1 for (t, s) in wk.values() if s > 0); tm = max(len(TG[y][t]) for (t, s) in wk.values())
    return n / max(1, tm)
# ---------- units
U = []
for y in range(2017, 2026):
    for t in TG[y]:
        weeks = sorted(TG[y][t])
        for W in (4, 10):
            pre = [w for w in weeks if w < W]; post = [w for w in weeks if w >= W]
            if len(pre) < 2 or len(post) < 4: continue
            tot = defaultdict(float)
            for (yy, tt, g), xs in RBW.items():
                if yy == y and tt == t:
                    for w, s in xs:
                        if w < W: tot[g] += s
            rk = sorted(tot.items(), key=lambda kv: -kv[1])
            if len(rk) < 2: continue
            allrb = sum(tot.values())
            (g1, s1), (g2, s2) = rk[0], rk[1]; s3 = rk[2][1] if len(rk) > 2 else 0
            if s1 / allrb < .4: continue
            last = max(PLAY[(y, g1)]);
            miss_post = sum(1 for w in post if not played(y, g1, w, t)); miss_pre = sum(1 for w in pre if not played(y, g1, w, t))
            av = [season_avail(y - k, g1) for k in (1, 2)]; avv = [a for a in av if a is not None]
            age = (dt.date(y, 9, 1) - BIRTH[g1]).days / 365.25 if g1 in BIRTH else None
            U.append(dict(y=y, t=t, W=W, g1=g1, g2=g2, share=s1 / allrb, clear=s2 >= 1.5 * s3, post=post, pre=pre, miss=miss_post,
                          frac=miss_post / len(post), mpre=miss_pre / len(pre), prior=(1 - st.mean(avv)) if avv else None,
                          noprior=not avv, age=age))
print(f"units {len(U)} (team-season-checkpoints 2017-25)")
# ---------- 1. step-in
print("\n1. When the lead back misses a game (2021-25, PPR):")
for lab, f in (("clear backup", lambda u: u["clear"]), ("crowded backfield", lambda u: not u["clear"])):
    out_, in_ = [], []
    for u in U:
        if u["y"] < 2021 or u["W"] != 4 or not f(u): continue
        for w in u["post"]:
            if not played(u["y"], u["g2"], w, u["t"]): continue
            p = PTS.get((u["y"], u["g2"], w), 0.0)
            (in_ if played(u["y"], u["g1"], w, u["t"]) else out_).append(p)
    if out_:
        print(f"   {lab:18s} backup scores {st.mean(out_):5.1f} pts with the starter OUT (n {len(out_)}), {st.mean(in_):4.1f} with him in (n {len(in_)});"
              f" 12+ pts {100*sum(p>=12 for p in out_)/len(out_):.0f}% of out-games vs {100*sum(p>=12 for p in in_)/len(in_):.0f}%")
# ---------- 2. miss risk
def feats(u):
    a = u["age"] if u["age"] is not None else 26
    return [1, a - 26, max(0, a - 28), u["prior"] if u["prior"] is not None else .15, 1 if u["noprior"] else 0, u["mpre"], u["share"] - .6, 1 if u["W"] == 10 else 0]
def fit(X, y, l2=1.0):
    X = np.array(X, float); y = np.array(y, float); b = np.zeros(X.shape[1])
    for _ in range(50):
        p = 1 / (1 + np.exp(-X @ b)); Wd = p * (1 - p); H = X.T @ (X * Wd[:, None]) + l2 * np.eye(len(b)); H[0, 0] -= l2
        b = b + np.linalg.solve(H, X.T @ (y - p) - l2 * np.r_[0, b[1:]])
    return b
def auc(s, y):
    pos = [a for a, b in zip(s, y) if b]; neg = [a for a, b in zip(s, y) if not b]
    if not pos or not neg: return float("nan")
    return sum((p > n) + .5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))
tgt = lambda u: 1 if u["miss"] >= 3 else 0
tr = [u for u in U if u["y"] <= 2021]; te = [u for u in U if u["y"] >= 2022]
b = fit([feats(u) for u in tr], [tgt(u) for u in tr]); ba = fit([[1, (u["age"] or 26) - 26] for u in tr], [tgt(u) for u in tr])
pr = lambda u: 1 / (1 + math.exp(-float(np.dot(b, feats(u)))))
yt = [tgt(u) for u in te]; s_full = [pr(u) for u in te]; s_age = [float(np.dot(ba, [1, (u["age"] or 26) - 26])) for u in te]
print(f"\n2. Lead back misses 3+ of the remaining games: base rate train {100*st.mean(tgt(u) for u in tr):.0f}% / test {100*st.mean(yt):.0f}%")
print(f"   held out 2022-25 AUC: full model {auc(s_full, yt):.3f}, age only {auc(s_age, yt):.3f} (0.5 = no skill)")
print("   coefficients:", dict(zip(["const", "age-26", "age over 28", "prior miss rate", "no prior", "missed so far", "snap share-.6", "week-10 checkpoint"], np.round(b, 2))))
for lo, hi in ((0, 25), (25, 28), (28, 30), (30, 99)):
    g = [u for u in U if u["age"] is not None and lo <= u["age"] < hi]
    print(f"   lead back age {lo}-{hi if hi < 99 else '+'}: missed 3+ of the rest {100*st.mean(tgt(u) for u in g):.0f}%, avg share of remaining games missed {100*st.mean(u['frac'] for u in g):.0f}% (n {len(g)})")
for lab, f in (("missed 25%+ of games the last 2 seasons", lambda u: u["prior"] is not None and u["prior"] >= .25), ("missed under 10%", lambda u: u["prior"] is not None and u["prior"] < .1)):
    g = [u for u in U if f(u)]; print(f"   {lab}: missed 3+ {100*st.mean(tgt(u) for u in g):.0f}% (n {len(g)})")
qs = sorted(s_full); cut = [qs[len(qs) // 3], qs[2 * len(qs) // 3]]
for i, (lo, hi) in enumerate(((0, cut[0]), (cut[0], cut[1]), (cut[1], 1.01))):
    g = [(u, s) for u, s in zip(te, s_full) if lo <= s < hi]
    print(f"   predicted {('low', 'mid', 'high')[i]:4s}: said {100*st.mean(s for _, s in g):.0f}%, happened {100*st.mean(tgt(u) for u, _ in g):.0f}% (n {len(g)}); avg games missed {st.mean(u['miss'] for u, _ in g):.1f} of {st.mean(len(u['post']) for u, _ in g):.1f}")
# ---------- 3. market
H = json.load(gzip.open("bt/hv.json.gz", "rt")); DD = [dt.date.fromisoformat(x) for x in H["d"]]; IDS = H["ids"]
src = open("index.html", encoding="utf-8").read(); VAN = {k: json.loads(re.search(r"const %s=(\[\[.*?\]\]);" % k, src).group(1)) for k in ("VAN1", "VANS")}
def curve(r, A):
    if r <= 1: return A[0][1]
    for (r1, v1), (r2, v2) in zip(A, A[1:]):
        if r <= r2: t = (math.log(r) - math.log(r1)) / (math.log(r2) - math.log(r1)); return math.exp(math.log(v1) + t * (math.log(v2) - math.log(v1)))
    return 5
def near(d):
    i = min(range(len(DD)), key=lambda i: abs((DD[i] - d).days)); return i if abs((DD[i] - d).days) <= 21 else None
U10 = {}
for u in U:
    if u["W"] == 10: U10[(u["y"], u["g2"])] = u; U10.setdefault(("rb1", u["y"], u["g1"]), u)
# model trained only on seasons before each test year
BY = {}
for Y in range(2021, 2026):
    trY = [u for u in U if u["y"] < Y]; BY[Y] = fit([feats(u) for u in trY], [tgt(u) for u in trY])
def risk(u): return 1 / (1 + math.exp(-float(np.dot(BY[u["y"]], feats(u)))))
for fmt, key, A in (("Superflex", "dsf", VAN["VANS"]), ("1QB", "do", VAN["VAN1"])):
    rows = []
    for Y in range(2021, 2025):
        i = near(dt.date(Y, 11, 6)); j = near(dt.date(Y + 1, 11, 6))
        if i is None or not H["t"][key][i]: continue
        rk = {IDS[k]: n + 1 for n, k in enumerate(H["t"][key][i])}; rk2 = {IDS[k]: n + 1 for n, k in enumerate(H["t"][key][j])} if j is not None and H["t"][key][j] else None
        risks = [risk(u) for (k, u) in U10.items() if k[0] != "rb1" and u["y"] == Y]; hi = sorted(risks)[2 * len(risks) // 3] if risks else 1
        for s, r in rk.items():
            if POSS.get(s) != "RB" or not (25 <= r <= 250): continue
            g = S2G.get(s)
            if not g: continue
            u = U10.get((Y, g)); lead = ("rb1", Y, g) in U10
            grp = "lead back" if lead else ("handcuff, fragile starter" if u and risk(u) >= hi else "handcuff, sturdy starter" if u else "other back")
            old = bool(u and u["age"] is not None and u["age"] >= 28)
            pts = sum(v for (yy, gg, w), v in PTS.items() if gg == g and ((yy == Y and w >= 10) or yy == Y + 1)) if Y + 1 <= 2025 else None
            nv = curve(rk2.get(s, 400), A) if rk2 is not None else None
            rows.append(dict(Y=Y, grp=grp, v=curve(r, A), pts=pts, nv=nv, clear=bool(u and u["clear"]), old=old))
    print(f"\n3. {fmt}: {len(rows)} RB-dates ranked 25-250 (Nov 2021-24); groups:", {g: sum(1 for x in rows if x['grp'] == g) for g in sorted(set(x['grp'] for x in rows))})
    for oname, ok in (("PPR points wk10 -> end of next season", "pts"), ("dynasty value 1 year later", "nv")):
        R = [x for x in rows if x[ok] is not None]
        X = np.array([[1, math.log(x["v"])] for x in R]); yv = np.array([math.log(x[ok] + 20) for x in R]); co = np.linalg.lstsq(X, yv, rcond=None)[0]
        for x, e in zip(R, yv - X @ co): x["res"] = e
        print(f"   {oname}: residual vs rank-matched expectation (log scale; +0.10 ~ 10% better than expected)")
        for gname in ("handcuff, fragile starter", "handcuff, sturdy starter", "other back", "lead back"):
            z = [x["res"] for x in R if x["grp"] == gname]
            if len(z) < 8: continue
            bs = sorted(st.mean(random.choices(z, k=len(z))) for _ in range(2000))
            print(f"     {gname:26s} n {len(z):3d}  {st.mean(z):+.3f}  (95% CI {bs[50]:+.3f}..{bs[1949]:+.3f})")
        for lab, f in (("backup, starter 28+", lambda x: x["grp"].startswith("handcuff") and x["old"]), ("backup, starter under 28", lambda x: x["grp"].startswith("handcuff") and not x["old"]), ("all backups (RB2)", lambda x: x["grp"].startswith("handcuff"))):
            z = [x["res"] for x in R if f(x)]
            if len(z) >= 8:
                bs = sorted(st.mean(random.choices(z, k=len(z))) for _ in range(2000)); print(f"     {lab:26s} n {len(z):3d}  {st.mean(z):+.3f}  (95% CI {bs[50]:+.3f}..{bs[1949]:+.3f})")
        z = [x["res"] for x in R if x["grp"] == "handcuff, fragile starter" and x["clear"]]
        if len(z) >= 8: print(f"     {'  of which clear backups':26s} n {len(z):3d}  {st.mean(z):+.3f}")
