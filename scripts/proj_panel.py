"""Shared by build_report.py (Engine 8) and the Engine 1 backtests: every player-week since 2021 with the inputs the app's
projection uses (hmProj in index.html) and the projection rebuilt from them, standard library only.

Inputs per player-week: Sleeper projection (PPR), season PPG and last-3 PPG before the week, season / last-3 expected
fantasy points (ffopportunity), opponent defense-vs-position rank to date (1 = gives up the most), team implied points
from the closing line (bt/nfl/schedules), questionable flag (bt/nfl/injuries), betting props when archived
(bt/props_hist, current season). Projection = PJC formula (read from index.html) x .88 if questionable, then blended with
the props estimate (PJ_PROPS_POS). Wind/rain and practice tweaks are not replayed (no archive)."""
import csv, gzip, io, json, os, re, statistics as st, collections, urllib.request
NV = "https://github.com/nflverse/nflverse-data/releases/download/"
FF = "https://github.com/ffverse/ffopportunity/releases/download/latest-data/"
IDS = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
LOCAL = "backtest/dl"; CACHE = os.environ.get("HM_DL", "/tmp/hm_dl")

def _get(name, url):
    for d in (LOCAL, CACHE):
        f = os.path.join(d, name)
        if os.path.exists(f) and os.path.getsize(f) > 1000: return f
    os.makedirs(CACHE, exist_ok=True); f = os.path.join(CACHE, name)
    data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "hashmark-build"}), timeout=120).read()
    open(f, "wb").write(data); return f

def load_app():
    s = open("index.html", encoding="utf-8").read()
    C = json.loads(re.search(r"const PJC=(\{.*?\});", s).group(1))
    m = re.search(r"PJ_PROPS_POS=(\{[^}]*\})", s)
    pw = json.loads(re.sub(r":\.", ":0.", re.sub(r"(\w+):", r'"\1":', m.group(1)))) if m else {}
    return C, pw

def proj(c, base, ppg, l3, xs, x3, rk, imp):
    v = lambda x: base if x is None else x
    m = (c[0] + c[1] * base + c[2] * v(ppg) + c[3] * v(l3) + c[4] * v(xs) + c[5] * v(x3)
         + (c[6] * base * (16.5 - rk) / 16 if rk is not None else 0) + (c[7] * base * (imp - 22.5) / 22.5 if imp is not None else 0)
         + c[8] * (ppg is not None) + c[9] * (xs is not None))
    return max(0.0, m)

def props_pts(pr, rec=1):   # the app's formula (index.html hmProj): yards, receptions ~ rec yards / 11.5 x league rec, QB 1.6 TD, anytime TD
    mk = k = 0
    if pr.get("recyd") is not None: mk += pr["recyd"] * .1 + pr["recyd"] / 11.5 * rec; k += 1
    if pr.get("rushyd") is not None: mk += pr["rushyd"] * .1; k += 1
    if pr.get("passyd") is not None: mk += pr["passyd"] * .04 + 1.6 * 4; k += 1
    if pr.get("td") is not None: mk += pr["td"] * 6
    return mk if k else None

FMT = {"ppr": ("pts_ppr", 1), "half": ("pts_half_ppr", .5), "std": ("pts_std", 0)}

def build(seasons=range(2021, 2027), scoring="ppr", C=None, feats=False):
    """scoring: "ppr" (default), "half" or "std": Sleeper projection, PPG, last-3 and actual points in that scoring; expected
    points (PPR) scaled by the player's PPG in this scoring / his PPR PPG, clamped .6-1.6, like the app (a.xfp x ppg/a.fp).
    C: weights {pos: [10 coefs]} instead of index.html's PJC. feats=True adds the inputs to each row."""
    seasons = list(seasons); PK, REC = FMT[scoring]
    norm = lambda s: re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s.lower()))
    ids = {}; g2s = {}; byname = collections.defaultdict(list)
    for r in csv.DictReader(open(_get("ids.csv", IDS), encoding="utf-8")):
        s = str(r.get("sleeper_id") or "").split(".")[0]
        if s in ("", "NA"): continue
        ids[s] = r
        if r.get("gsis_id") not in ("", "NA", None): g2s[r["gsis_id"]] = s
        if r.get("position") in ("QB", "RB", "WR", "TE"): byname[norm(r["name"])].append(s)
    SP = json.load(gzip.open("bt/sleeper_proj.json.gz", "rt"))["w"]; ST = json.load(gzip.open("bt/sleeper_stats.json.gz", "rt"))["w"]
    tm = {}; allowed = collections.defaultdict(float); dgames = collections.defaultdict(set); xfp = {}
    for y in seasons:
        try: f = _get(f"pw_{y}.csv", NV + f"stats_player/stats_player_week_{y}.csv")
        except Exception: continue
        for r in csv.DictReader(open(f, encoding="utf-8")):
            if r.get("season_type") != "REG": continue
            w = int(r["week"]); s = g2s.get(r["player_id"])
            if s: tm[(y, w, s)] = (r["team"], r["opponent_team"])
            if r.get("position") in ("QB", "RB", "WR", "TE"):
                allowed[(y, r["opponent_team"], r["position"], w)] += float(r.get("fantasy_points_ppr") or 0); dgames[(y, r["opponent_team"])].add(w)
        try: f = _get(f"ep_{y}.csv", FF + f"ep_weekly_{y}.csv")
        except Exception: continue
        for r in csv.DictReader(open(f, encoding="utf-8")):
            s = g2s.get(r.get("player_id"))
            if not s: continue
            try: xfp[(y, int(float(r["week"])), s)] = float(r["total_fantasy_points_exp"] or 0)
            except (ValueError, KeyError): pass
    DV = {}
    def dvp_rank(y, w, opp, pos):
        k = (y, w, opp, pos)
        if k in DV: return DV[k]
        per = {}
        for (yy, t), ws in dgames.items():
            if yy != y: continue
            ws2 = [x for x in ws if x < w]
            if len(ws2) < 2: DV[k] = None; return None
            per[t] = sum(allowed.get((y, t, pos, x), 0) for x in ws2) / len(ws2)
        DV[k] = (sorted(per, key=lambda t: -per[t]).index(opp) + 1) if opp in per else None; return DV[k]
    imp = {}; sched = {}
    for r in csv.DictReader(gzip.open("bt/nfl/schedules.csv.gz", "rt")):
        if r["game_type"] != "REG": continue
        y, w = int(r["season"]), int(r["week"]); sched[(y, r["home_team"], r["away_team"])] = w
        try: sp, tot = float(r["spread_line"]), float(r["total_line"])
        except ValueError: continue
        imp[(y, w, r["home_team"])] = tot / 2 + sp / 2; imp[(y, w, r["away_team"])] = tot / 2 - sp / 2
    q = set()
    for y in seasons:
        f = f"bt/nfl/injuries/{y}.csv.gz"
        if not os.path.exists(f): continue
        for r in csv.DictReader(gzip.open(f, "rt")):
            if r.get("report_status") == "Questionable" and r.get("game_type", "REG") == "REG" and r["gsis_id"] in g2s:
                q.add((int(r["season"]), int(r["week"]), g2s[r["gsis_id"]]))
    props = {}
    try:
        P = json.load(gzip.open("bt/props_hist.json.gz", "rt")); FIX = {"LA": "LAR", "WSH": "WAS"}
        for g in P["games"].values():
            y = int(g["start"][:4]) if int(g["start"][5:7]) >= 3 else int(g["start"][:4]) - 1
            h, a = FIX.get(g["home"], g["home"]), FIX.get(g["away"], g["away"]); w = sched.get((y, h, a))
            if not w: continue
            for oid, pr in g["p"].items():
                n = P["names"].get(oid)
                if not n: continue
                last, _, first = n.partition(", "); c = byname.get(norm(first + " " + last)) or []
                if len(c) == 1: props[(y, w, c[0])] = props_pts(pr, REC)
    except Exception: pass
    C0, PW = load_app(); C = C or C0
    rows = []; log = collections.defaultdict(list)
    for key in sorted(ST, key=lambda k: tuple(map(int, k.split("-")))):
        y, w = map(int, key.split("-"))
        if y not in seasons: continue
        P = SP.get(key) or {}; S = ST[key]
        for pid, pr in P.items():
            r = ids.get(pid); pos = r and r.get("position")
            if pos not in ("QB", "RB", "WR", "TE"): continue
            stt = S.get(pid)
            if not stt or not stt.get("gp"): continue
            base = pr.get(PK) or 0; L = log[(y, pid)]
            ppg = st.mean(x[1] for x in L) if len(L) >= 2 else None; l3 = st.mean(x[1] for x in L[-3:]) if len(L) >= 3 else None
            xs_ = [x[2] for x in L if x[2] is not None]; xs = st.mean(xs_) if len(xs_) >= 2 else None; x3 = st.mean(xs_[-3:]) if len(xs_) >= 3 else None
            if PK != "pts_ppr" and ppg is not None and xs is not None:
                fp = st.mean(x[3] for x in L); sc = max(.6, min(1.6, ppg / fp)) if fp else 1
                xs *= sc; x3 = x3 * sc if x3 is not None else None
            t = tm.get((y, w, pid)); rk = dvp_rank(y, w, t[1], pos) if t else None; ii = imp.get((y, w, t[0])) if t else None
            qq = (y, w, pid) in q
            hm = proj(C[pos], base, ppg, l3, xs, x3, rk, ii) * (.88 if qq else 1)
            mk = props.get((y, w, pid))
            if mk is not None: pwt = PW.get(pos, .2); hm = hm * (1 - pwt) + mk * pwt
            row = {"s": y, "w": w, "pid": pid, "pos": pos, "base": base, "hm": hm, "a": stt.get(PK) or 0, "q": qq, "props": mk is not None}
            if feats: row.update(ppg=ppg, l3=l3, xs=xs, x3=x3, rk=rk, imp=ii, mk=mk)
            rows.append(row)
        for pid, stt in S.items():
            if stt.get("gp"): log[(y, pid)].append((w, stt.get(PK) or 0, xfp.get((y, w, pid)), stt.get("pts_ppr") or 0))
    return rows

if __name__ == "__main__":
    import sys
    rows = build(scoring=sys.argv[1] if len(sys.argv) > 1 else "ppr"); print(len(rows))
    for y in sorted({r["s"] for r in rows}):
        R = [r for r in rows if r["s"] == y and r["base"] >= 3]
        print(y, len(R), "sleeper", round(sum(abs(r["a"] - r["base"]) for r in R) / len(R), 3), "hashmark", round(sum(abs(r["a"] - r["hm"]) for r in R) / len(R), 3))
