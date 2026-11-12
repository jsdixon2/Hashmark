"""Engine 4 retest (B6): trade-grade calibration on real Sleeper trades with today's value scale, and the IDP retest.
Data: every 2-team trade in dynasty (type 2) and keeper (type 1) leagues in bt/leagues.json.gz, 2021-2026.
Grade replayed the way the app grades a past trade on the day it was made (`hvDay1`/`dayOne` value core):
  player value = FantasyPros ECR on that date (bt/hv.json.gz) through the app's curve VANS/VAN1, blended like the app
    (dynasty: SF .75 dynasty + .25 redraft, 1QB .7/.3; keeper: .5*(.7d+.3r) + .5r); unranked -> rank 400.
  pick value = PKB by round x .93^(years past next season) (x.6 in keeper leagues).
  side value = effV (TC: d .75, g 1.3); gap = (in - out) / max(in, out); P(side ahead) = pvTable(gap) (PVT, shipped).
  (The dynasty grade also adds a contender lineup term; it needs full weekly rosters (2022-25 only) and is left out.)
Outcome: points above replacement (PAR) received minus sent, from the trade week (week 1 for offseason deals) to the end
  of that regular season (wk 17) plus next season weeks 1-9 ("H9", the window 2025 trades can be followed through 2026
  wk 9); also "HF" = through all of next season (2021-24 trades only) and "HL" = through two more full seasons (2021-23). Weekly replacement = k-th best score at the
  position that week (QB 14 / 26 SF, RB 30, WR 42, TE 14; IDP DL 30, LB 30, DB 40) under the league's scoring key.
  Picks: average PAR of rookies taken in that round in real rookie drafts in the archive over a window of the same
  length (rookie season + next season wks 1-9), i.e. what that round has produced; no timing noise.
"Started" outcomes (s9 / sL, coordinator check): PAR counted only in weeks the player was in the starting lineup of the
  team holding him from the trade (received players on the receiver, sent players on their new team), following the
  league into later seasons by its prev link (same roster id); picks = round's average started PAR for the drafting team.
IDP: positions from bt/idp/players.json.gz, weekly points from bt/idp/weekly.json.gz with each league's idp_* scoring.
  No IDP rank history exists (bt/idp/ecr.json is today's only), so IDP trades are also graded with a production proxy
  (PAR per game at the time: season-to-date if 4+ games, else prior season, blended), the same proxy for offense, to
  compare like with like.
Writes backtest/e25_trades.pkl (one row per trade)."""
import json, gzip, os, collections, bisect, datetime as dt, numpy as np, pandas as pd
B = os.path.dirname(os.path.abspath(__file__)); H = os.path.join(B, "..", "bt")
ST = json.load(gzip.open(f"{H}/sleeper_stats.json.gz", "rt"))["w"]
PJ = json.load(gzip.open(f"{H}/sleeper_proj.json.gz", "rt"))["w"]
HV = json.load(gzip.open(f"{H}/hv.json.gz", "rt")); HD = [dt.date.fromisoformat(d) for d in HV["d"]]
LG = json.load(gzip.open(f"{H}/leagues.json.gz", "rt"))["leagues"]
IW = json.load(gzip.open(f"{H}/idp/weekly.json.gz", "rt")); IP = json.load(gzip.open(f"{H}/idp/players.json.gz", "rt"))
ids = pd.read_csv(B + "/dl/ids.csv", low_memory=False).dropna(subset=["sleeper_id"])
BD = {str(int(s)): b for s, b in zip(ids.sleeper_id, ids.birthdate) if isinstance(b, str)}
POSD = {str(int(s)): p for s, p in zip(ids.sleeper_id, ids.position)}
for w in PJ.values():
    for pid, s in w.items():
        if s.get("pos"): POSD[pid] = s["pos"]
IDPMAP = {"DE": "DL", "DT": "DL", "DL": "DL", "NT": "DL", "LB": "LB", "ILB": "LB", "OLB": "LB", "MLB": "LB", "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB", "DB": "DB"}
for pid in list(POSD):
    if POSD[pid] in IDPMAP: POSD[pid] = IDPMAP[POSD[pid]]
for pid, (ps, bd, ex) in IP.items():
    POSD[pid] = ps
    if bd and pid not in BD: BD[pid] = bd
OFF = ("QB", "RB", "WR", "TE"); IDP = ("DL", "LB", "DB")
LAST = (2026, 9)                       # last week with both offense and IDP stats
def wkey(s, w): return f"{s}-{w}"
VAN1 = np.array([[1, 10000], [2, 9713], [3, 9455], [6, 8778], [12, 7677], [18, 6782], [24, 6028], [36, 4819], [50, 3762], [75, 2476], [100, 1664], [150, 782], [200, 381], [300, 98], [450, 14], [600, 5]], float)
VANS = np.array([[1, 10000], [2, 9766], [3, 9548], [6, 8960], [12, 7959], [18, 7114], [24, 6382], [36, 5178], [50, 4093], [75, 2732], [100, 1849], [150, 870], [200, 421], [300, 103], [450, 14], [600, 5]], float)
PKB = {"1q": {1: 3772, 2: 2025, 3: 1427, 4: 630, 5: 300}, "sf": {1: 3722, 2: 1990, 3: 1397, 4: 615, 5: 300}}
def curve(A, r):
    if r <= 1: return A[0, 1]
    if r >= A[-1, 0]: return 5.0
    return float(np.exp(np.interp(np.log(r), np.log(A[:, 0]), np.log(A[:, 1]))))
RK = {}
def hrank(t, di, pid):
    m = RK.get((t, di))
    if m is None: m = RK[(t, di)] = {HV["ids"][ix]: i + 1 for i, ix in enumerate(HV["t"][t][di])}
    return m.get(pid)
def di_at(d): return max(0, bisect.bisect_right(HD, d) - 1)
def ecr_val(pid, d, sf, ty):
    di = di_at(d); A = VANS if sf else VAN1
    vr = curve(A, hrank("rsf" if sf else "ro", di, pid) or 400); vd = curve(A, hrank("dsf" if sf else "do", di, pid) or 400)
    return .5 * (.7 * vd + .3 * vr) + .5 * vr if ty == 1 else (.75 * vd + .25 * vr if sf else .7 * vd + .3 * vr)
def ranked(pid, d, sf):
    di = di_at(d); return (hrank("dsf" if sf else "do", di, pid) or hrank("rsf" if sf else "ro", di, pid)) is not None
def pick_val(y, r, s, sf, ty):
    return PKB["sf" if sf else "1q"][min(5, max(1, int(r)))] * (.93 ** max(0, int(y) - (s + 1))) * (.6 if ty == 1 else 1)
def age(pid, d):
    b = BD.get(pid)
    if not b: return None
    try: return (d - dt.date.fromisoformat(str(b)[:10])).days / 365.25
    except Exception: return None
# ---- weekly points above replacement ----
RREP = {"QB": 14, "RB": 30, "WR": 42, "TE": 14, "DL": 30, "LB": 30, "DB": 40}
PAR = {}
def off_par(key, sf, s, w):
    k = (key, sf, s, w)
    if k in PAR: return PAR[k]
    wk = ST.get(wkey(s, w), {}); by = collections.defaultdict(list)
    for pid, st in wk.items():
        p = POSD.get(pid)
        if p in OFF and st.get(key) is not None: by[p].append((st.get(key) or 0.0, pid))
    out = {}
    for p, L in by.items():
        L.sort(reverse=True); n = (26 if sf else 14) if p == "QB" else RREP[p]
        rep = L[n - 1][0] if len(L) >= n else 0.0
        for v, pid in L: out[pid] = max(0.0, v - rep)
    PAR[k] = out; return out
DEF_IDP = {"idp_tkl_solo": 1, "idp_tkl_ast": .5, "idp_sack": 4, "idp_int": 3, "idp_ff": 3, "idp_fum_rec": 3, "idp_pass_def": 1, "idp_def_td": 6, "idp_safe": 2, "idp_tkl_loss": 1, "idp_qb_hit": 1, "idp_blk_kick": 3}
def idp_par(sck, s, w):
    k = ("idp", sck, s, w)
    if k in PAR: return PAR[k]
    sc = dict(sck) or DEF_IDP; wk = IW.get(wkey(s, w), {}); by = collections.defaultdict(list)
    for pid, st in wk.items():
        p = POSD.get(pid)
        if p in IDP and st.get("gp"): by[p].append((sum(st.get(x, 0.0) * v for x, v in sc.items()), pid))
    out = {}
    for p, L in by.items():
        L.sort(reverse=True); n = RREP[p]; rep = L[n - 1][0] if len(L) >= n else 0.0
        for v, pid in L: out[pid] = max(0.0, v - rep)
    PAR[k] = out; return out
def weeks(s, w0, nxt):
    out = [(s, w) for w in range(max(1, w0), 18)] + [(s + 1, w) for w in range(1, nxt + 1)]
    return [x for x in out if x <= LAST]
def par_sum(pid, wl, key, sf, sck):
    if POSD.get(pid) in IDP: return sum(idp_par(sck, s, w).get(pid, 0.0) for s, w in wl)
    return sum(off_par(key, sf, s, w).get(pid, 0.0) for s, w in wl)
def par_pg(pid, s, w, key, sf, sck):
    """production proxy at the time: PAR per game this season before week w (4+ games), else blended with last season"""
    def pg(yr, w1):
        tot, g = 0.0, 0
        for k in range(1, w1):
            if POSD.get(pid) in IDP:
                st = IW.get(wkey(yr, k), {}).get(pid)
                if st and st.get("gp"): g += 1; tot += idp_par(sck, yr, k).get(pid, 0.0)
            else:
                st = ST.get(wkey(yr, k), {}).get(pid)
                if st and st.get("gp"): g += 1; tot += off_par(key, sf, yr, k).get(pid, 0.0)
        return tot, g
    t1, g1 = pg(s, w); t0, g0 = pg(s - 1, 18) if s > 2021 or True else (0, 0)
    a = t1 / g1 if g1 else None; b = t0 / g0 if g0 else None
    if a is not None and g1 >= 4: return a
    if a is None and b is None: return 0.0
    if a is None: return b
    if b is None: return a
    wt = g1 / 4; return wt * a + (1 - wt) * b
# ---- starting lineups: "started PAR" counts a player's PAR only in weeks he started for the team that holds him ----
NXT = {l["prev"]: l["id"] for l in LG.values() if l.get("prev")}
SCACHE = {}
def starters(lid, w, rid):
    k = (lid, w)
    if k not in SCACHE:
        rows = ((LG.get(lid) or {}).get("weeks") or {}).get(str(w)) or []
        SCACHE[k] = {r[0]: set(str(x) for x in (r[3] or [])) for r in rows}
    return SCACHE[k].get(rid, set())
def chain(lid, s, yr):
    while s < yr and lid: lid = NXT.get(lid); s += 1
    return lid
def started_sum(pid, wl, key, sf, sck, lid, s, rid):
    """None if a season in the window has no next-season league to follow"""
    tot = 0.0; cl = {}
    for yr, w in wl:
        if yr not in cl: cl[yr] = chain(lid, s, yr)
        l2 = cl[yr]
        if l2 is None: return None
        if pid in starters(l2, w, rid):
            tot += (idp_par(sck, yr, w) if POSD.get(pid) in IDP else off_par(key, sf, yr, w)).get(pid, 0.0)
    return tot
# ---- rookie-draft round averages (what each round has produced) ----
RD = collections.defaultdict(list); RDS = collections.defaultdict(list)
for lg in LG.values():
    if lg.get("type") != 2 or not lg.get("prev") or any(p in IDP + ("IDP_FLEX",) for p in lg.get("pos") or []): continue
    d = lg.get("draft") or {}; s = lg["season"]
    if not d.get("picks") or (d.get("rounds") or 99) > 6 or s > 2025: continue
    sf = "SUPER_FLEX" in lg["pos"] or lg["pos"].count("QB") > 1
    rec = (lg.get("sc") or {}).get("rec", 1); key = "pts_ppr" if rec >= .75 else "pts_half_ppr" if rec >= .25 else "pts_std"
    wl = weeks(s, 1, 9)
    if (s + 1, 9) > LAST: continue
    for pk in d["picks"]:
        rnd, pid = pk[0], pk[2]
        if pid and POSD.get(str(pid)) in OFF:
            RD[min(5, rnd)].append(par_sum(str(pid), wl, key, sf, ()))
            st_ = started_sum(str(pid), wl, key, sf, (), lg["id"], s, pk[3])
            if st_ is not None: RDS[min(5, rnd)].append(st_)
RAVG = {r: float(np.mean(v)) for r, v in RD.items()}; RAVGS = {r: float(np.mean(v)) for r, v in RDS.items()}
print("rookie round STARTED PAR:", {r: (round(v), len(RDS[r])) for r, v in sorted(RAVGS.items())})
print("rookie round PAR (rookie yr + next yr wk1-9):", {r: (round(v), len(RD[r])) for r, v in sorted(RAVG.items())})
TC = dict(d=.75, g=1.3)
def effV(vs):
    v = sorted([x for x in vs if x > 0], reverse=True); s = sum(TC["d"] ** i * x ** TC["g"] for i, x in enumerate(v))
    return s ** (1 / TC["g"]) if s > 0 else 0.0
rows = []
for lg in LG.values():
    s = lg["season"]; ty = lg.get("type")
    if ty not in (1, 2) or s < 2021: continue
    pos = lg.get("pos") or []
    sf = "SUPER_FLEX" in pos or pos.count("QB") > 1; idl = any(p in IDP + ("IDP_FLEX",) for p in pos)
    rec = (lg.get("sc") or {}).get("rec", 1); key = "pts_ppr" if rec >= .75 else "pts_half_ppr" if rec >= .25 else "pts_std"
    sck = tuple(sorted((k, v) for k, v in (lg.get("sc") or {}).items() if k.startswith("idp_") and k in DEF_IDP | {"idp_tkl": 0}))
    for t in lg.get("tx") or []:
        if t[0] != "trade" or len(t[2] or []) != 2: continue
        a, b = t[2]; w = t[1] or 1
        ts = dt.datetime.fromtimestamp((t[8] or 0) / 1000, dt.timezone.utc).date() if t[8] else dt.date(s, 9, 5) + dt.timedelta(weeks=w - 1)
        if ts < HD[0]: continue
        w0 = 1 if (w <= 1 and ts < dt.date(s, 9, 12)) else w
        inc = {a: [], b: []}
        for pid, rid in (t[3] or {}).items():
            if rid in inc: inc[rid].append(("p", str(pid)))
        for pk in t[5] or []:
            y, rnd, orig, prev, own = pk
            if own in inc: inc[own].append(("k", (int(y), int(rnd))))
        if not inc[a] or not inc[b]: continue
        allp = [x[1] for x in inc[a] + inc[b] if x[0] == "p"]
        if any(POSD.get(p) not in OFF + IDP for p in allp): continue   # K / DEF / unknown left out
        nidp = sum(1 for p in allp if POSD.get(p) in IDP)
        if nidp and not idl: continue
        wl9 = weeks(s, w0, 9); wlF = weeks(s, w0, 17) if s <= 2024 else None
        wlL = wlF + [(s + 2, k) for k in range(1, 18)] if s <= 2023 else None
        if not wl9: continue
        def side(rid):
            got = inc[rid]
            v = [ecr_val(x[1], ts, sf, ty) if x[0] == "p" else pick_val(*x[1], s, sf, ty) for x in got]
            o9 = sum(par_sum(x[1], wl9, key, sf, sck) if x[0] == "p" else RAVG.get(min(5, x[1][1]), 0) for x in got)
            oF = None if wlF is None else sum(par_sum(x[1], wlF, key, sf, sck) if x[0] == "p" else RAVG.get(min(5, x[1][1]), 0) * len(wlF) / len(wl9) for x in got)
            oL = None if wlL is None else sum(par_sum(x[1], wlL, key, sf, sck) if x[0] == "p" else RAVG.get(min(5, x[1][1]), 0) * len(wlL) / len(wl9) for x in got)
            def st_o(wl):
                if wl is None: return None
                t_ = 0.0
                for x in got:
                    if x[0] == "p":
                        v_ = started_sum(x[1], wl, key, sf, sck, lg["id"], s, rid)
                        if v_ is None: return None
                        t_ += v_
                    else: t_ += RAVGS.get(min(5, x[1][1]), 0) * len(wl) / len(wl9)
                return t_
            s9, sL = st_o(wl9), st_o(wlL)
            pp = [par_pg(x[1], s, w0, key, sf, sck) for x in got if x[0] == "p"]
            ags = [age(x[1], ts) for x in got if x[0] == "p"]
            idpv = sum(vv for x, vv in zip(got, v) if x[0] == "p" and POSD.get(x[1]) in IDP)
            return dict(v=v, o9=o9, oF=oF, oL=oL, s9=s9, sL=sL, pp=pp, ages=ags, npl=sum(1 for x in got if x[0] == "p"), npk=sum(1 for x in got if x[0] == "k"),
                        nunr=sum(1 for x in got if x[0] == "p" and POSD.get(x[1]) in OFF and not ranked(x[1], ts, sf)),
                        idp=sum(1 for x in got if x[0] == "p" and POSD.get(x[1]) in IDP))
        A_, B_ = side(a), side(b)
        rows.append(dict(lg=lg["id"], s=s, w=w, w0=w0, ty=ty, sf=sf, idl=idl, ts=str(ts),
                         vA=A_["v"], vB=B_["v"], agA=A_["ages"], agB=B_["ages"], ppA=A_["pp"], ppB=B_["pp"],
                         o9=A_["o9"] - B_["o9"], oF=None if A_["oF"] is None else A_["oF"] - B_["oF"], oL=None if A_["oL"] is None else A_["oL"] - B_["oL"],
                         s9=None if A_["s9"] is None or B_["s9"] is None else A_["s9"] - B_["s9"], sL=None if A_["sL"] is None or B_["sL"] is None else A_["sL"] - B_["sL"],
                         nplA=A_["npl"], nplB=B_["npl"], npkA=A_["npk"], npkB=B_["npk"], idpA=A_["idp"], idpB=B_["idp"],
                         nunr=A_["nunr"] + B_["nunr"]))
D = pd.DataFrame(rows); D.to_pickle(B + "/e25_trades.pkl")
print(len(D), "trades;", D.groupby(["ty", "s"]).size().to_dict(), "IDP trades:", int(((D.idpA + D.idpB) > 0).sum()))
