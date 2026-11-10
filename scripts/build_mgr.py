#!/usr/bin/env python3
"""Sleeper-wide manager reference: data/mgr_ref.json.

Turns the anonymous league archive (bt/leagues.json.gz, plus exact rosters from bt/rosters.json.gz and weekly
player stats from bt/sleeper_stats.json.gz) into the tables the app uses to place a manager's whole career
against every team-season we have studied ("Top 12% of Sleeper managers").

Per team-season metrics (same definitions as the app, v88):
  ap    all-play win % in the regular season (share of the other teams you outscored each week)
  sc    points relative to the league's weekly average (0.10 = 10% above average)
  cons  consistency: minus the coefficient of variation of weekly scores
  lu    lineup efficiency: points started / best possible lineup (rosters archive only)
  out   hardware: finish value (title 1, runner-up .45, 3rd .25, 4th .2, other playoff team .1) + .1 per playoff
        game won + .3 for the league's points title, minus the league's average, so a title in a 14-team league is worth more than in an 8-team one
  luck  (wins - all-play wins) per game; shown, never part of the score

Data hygiene (outliers kill rankings):
  - leagues left out: guillotine, under 8 teams, under 10 scored regular-season weeks, no head-to-head pairs,
    average team score outside 40-260 (custom scoring that breaks comparisons), 25%+ abandoned teams
  - team-seasons left out: abandoned (2+ zero-point weeks, or 3+ weeks with a quarter of the lineup empty),
    under 8 games
  - lineup efficiency only from weeks where our rebuilt starter points match Sleeper's score (within 8%)
  - every metric winsorized at the 2.5th/97.5th percentile of its format bucket; z-scores clipped to +-3
  - buckets (league type x size) with fewer than MIN_N team-seasons fall back to the league type, then to all
Career skill (tau2): measured from managers seen in 2+ seasons once the archive carries hashed owner ids
(scripts/fetch_leagues.py stores them from v88 on); until then a conservative assumed value is used."""
import gzip, json, math, os, statistics as stt, collections, time

H = "bt"
OUT = "data/mgr_ref.json"
MIN_N = 150
VAL = {1: 1.0, 2: .45, 3: .25, 4: .2}
PO_VAL = .1
PT = .3   # points title: most regular-season points in the league
PW = .1   # each playoff game won (winners bracket)
W = {"ap": .40, "lu": .15, "out": .45}
TAU2_DEFAULT = {"S": .25, "ap": .25, "lu": .35, "sc": .25, "cons": .12, "out": .10}
STARTERS = {"QB", "RB", "WR", "TE", "K", "DEF", "FLEX", "WRRB_FLEX", "REC_FLEX", "SUPER_FLEX"}
ELIG = {"QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"}, "K": {"K"}, "DEF": {"DEF"}, "FLEX": {"RB", "WR", "TE"},
        "WRRB_FLEX": {"RB", "WR"}, "REC_FLEX": {"WR", "TE"}, "SUPER_FLEX": {"QB", "RB", "WR", "TE"}}


def load(p, k="leagues"):
    return json.load(gzip.open(p, "rt"))[k] if os.path.exists(p) else {}


def size_b(n):
    return "10" if n <= 10 else "12" if n <= 12 else "14"


def sdv(a):
    if len(a) < 2: return 0.0
    m = sum(a) / len(a); return math.sqrt(sum((x - m) ** 2 for x in a) / (len(a) - 1))


def finish_vals(lg):
    """roster id -> finish value from the winners bracket (complete leagues only)."""
    br = lg.get("bracket") or []
    if lg.get("status") != "complete" or not br: return None
    fin, po = {}, set()
    for r, m, t1, t2, w, l, p in br:
        for t in (t1, t2):
            if isinstance(t, int): po.add(t)
        if p and w is not None:
            fin[w] = p
            if l is not None: fin[l] = p + 1
    if not any(v == 1 for v in fin.values()): return None
    pw = collections.Counter(w for r, m, t1, t2, w, l, p in br if isinstance(w, int) and isinstance(t1, int) and isinstance(t2, int))
    return {rid: VAL.get(fin.get(rid), PO_VAL if rid in po else 0.0) + PW * pw.get(rid, 0) for rid in [x[0] for x in lg["rost"]]}


def positions(L):
    """player id -> position, learned from fixed lineup slots (starters line up with roster_positions)."""
    c = collections.defaultdict(collections.Counter)
    for lg in L.values():
        slots = [s for s in (lg.get("pos") or []) if s in STARTERS]
        for rows in (lg.get("weeks") or {}).values():
            for row in rows:
                st = row[3] or []
                if len(st) != len(slots): continue
                for s, pid in zip(slots, st):
                    if s in ("QB", "RB", "WR", "TE", "K", "DEF"): c[pid][s] += 1
    return {pid: cc.most_common(1)[0][0] for pid, cc in c.items()}


def lineup_eff(lg, rl, ST, POS):
    """rid -> (points started, best lineup) summed over regular-season weeks that rebuild cleanly."""
    slots = [s for s in (lg.get("pos") or []) if s in ELIG]
    if not slots: return {}
    sc = rl.get("sc") or lg.get("sc") or {}
    order = sorted(slots, key=lambda s: len(ELIG[s]))
    out = collections.defaultdict(lambda: [0.0, 0.0, 0])
    # taxi leagues: like the app (v62), a player this team never started all season counts as a stash, not a bench option
    started = collections.defaultdict(set)
    if rl.get("taxi"):
        for rows in (rl.get("weeks") or {}).values():
            for row in rows: started[row[0]].update(row[3] or [])
    for wk, rows in (rl.get("weeks") or {}).items():
        w = int(wk)
        if w >= (lg.get("pws") or 15): continue
        stw = ST.get(f"{lg['season']}-{w}", {})
        def pts(p):  # league scoring on the archived stat lines; K and D/ST use Sleeper's standard points
            st = stw.get(p) or {}
            if not p.isdigit() or POS.get(p) in ("K", "DEF"): return float(st.get("pts_std", 0.0) or 0.0)
            return sum(float(st.get(k, 0.0) or 0.0) * v for k, v in sc.items())
        for row in rows:
            rid, _, real, st, pl = row[0], row[1], row[2], row[3] or [], row[4] if len(row) > 4 else None
            if not pl or real is None or real <= 0: continue
            act = sum(pts(p) for p in st)
            if abs(act - real) > max(2.0, .08 * real): continue  # custom scoring we can't rebuild: skip the week
            if rl.get("taxi"): pl = [p for p in pl if p in started[rid]]
            pool = sorted(pl, key=lambda p: -pts(p)); used = set(); best = 0.0
            for s in order:
                for p in pool:
                    if p not in used and POS.get(p) in ELIG[s]: used.add(p); best += max(0.0, pts(p)); break
            o = out[rid]; o[0] += act; o[1] += max(best, act); o[2] += 1
    return {rid: v[0] / v[1] for rid, v in out.items() if v[2] >= 6 and v[1] > 0}


def season_rows(L, R, ST, POS, ex):
    rows = []
    for lid, lg in L.items():
        n = lg.get("n") or len(lg.get("rost") or [])
        if lg.get("guillotine"): ex["guillotine"] += 1; continue
        if n < 8: ex["under 8 teams"] += 1; continue
        if lg.get("status") != "complete": ex["season not finished"] += 1; continue
        pws = lg.get("pws") or 15
        WK = {int(k): v for k, v in (lg.get("weeks") or {}).items() if int(k) < pws}
        WK = {k: v for k, v in WK.items() if sum(1 for r in v if r[2] > 0) >= n / 2}
        if len(WK) < 10: ex["under 10 scored weeks"] += 1; continue
        allp = [r[2] for v in WK.values() for r in v if r[2] > 0]
        if not allp or not (40 <= sum(allp) / len(allp) <= 260): ex["unusual scoring"] += 1; continue
        if sum(1 for v in WK.values() for r in v if r[1] is not None) < len(allp) * .8: ex["no head-to-head"] += 1; continue
        slots = [s for s in (lg.get("pos") or []) if s in STARTERS]
        per = collections.defaultdict(lambda: {"pts": [], "rel": [], "ap": 0.0, "g": 0, "w": 0.0, "zero": 0, "empty": 0})
        for w, v in WK.items():
            sc = [r[2] for r in v if r[2] > 0]; lm = sum(sc) / len(sc)
            by = collections.defaultdict(list)
            for r in v:
                T = per[r[0]]
                if r[2] <= 0: T["zero"] += 1; continue
                if slots and len([p for p in (r[3] or []) if p and p != "0"]) < .75 * len(slots): T["empty"] += 1
                if r[1] is not None: by[r[1]].append(r)
            for pair in by.values():
                if len(pair) != 2: continue
                for me, op in (pair, pair[::-1]):
                    T = per[me[0]]
                    others = [x for x in sc]; others.remove(me[2])
                    T["ap"] += (sum(1 for x in others if x < me[2]) + .5 * sum(1 for x in others if x == me[2])) / max(1, len(others))
                    T["g"] += 1; T["w"] += 1 if me[2] > op[2] else .5 if me[2] == op[2] else 0
                    T["pts"].append(me[2]); T["rel"].append(me[2] / lm - 1)
        bad = {rid for rid, T in per.items() if T["zero"] >= 2 or T["empty"] >= 3}
        if len(bad) >= .25 * n: ex["dead league (25%+ abandoned)"] += 1; continue
        fv = finish_vals(lg)
        lu = lineup_eff(lg, R[lid], ST, POS) if lid in R else {}
        own = {x[0]: x[5] for x in lg.get("rost") or [] if len(x) > 5 and x[5]}
        if fv is not None:  # hardware = finish + playoff wins + points title
            pf = {rid: sum(T["pts"]) for rid, T in per.items()}
            if pf:
                top = max(pf, key=pf.get); fv = dict(fv); fv[top] = fv.get(top, 0.0) + PT
        fmean = sum(fv.values()) / len(fv) if fv else None
        for rid, T in per.items():
            if rid in bad: ex["abandoned team"] += 1; continue
            if T["g"] < 8: ex["under 8 games"] += 1; continue
            g = T["g"]; m = sum(T["pts"]) / g
            row = {"k": f"{lg.get('type') or 0}|{size_b(n)}", "t": lg.get("type") or 0, "s": lg["season"], "lg": lid, "o": own.get(rid),
                   "ap": T["ap"] / g, "sc": sum(T["rel"]) / g, "cons": -(sdv(T["pts"]) / m) if m else None,
                   "luck": (T["w"] - T["ap"]) / g}
            if fv is not None: row["out"] = fv.get(rid, 0.0) - fmean
            if rid in lu: row["lu"] = lu[rid]
            rows.append(row)
    return rows


def pct(xs, q):
    xs = sorted(xs); i = (len(xs) - 1) * q; lo = math.floor(i); hi = math.ceil(i)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def stats(vals):
    lo, hi = pct(vals, .025), pct(vals, .975)
    v = [min(hi, max(lo, x)) for x in vals]
    return [round(sum(v) / len(v), 5), round(sdv(v) or 1e-6, 5), round(lo, 5), round(hi, 5), len(v)]


def main():
    L = load(f"{H}/leagues.json.gz"); R = load(f"{H}/rosters.json.gz")
    ST = json.load(gzip.open(f"{H}/sleeper_stats.json.gz", "rt"))["w"] if os.path.exists(f"{H}/sleeper_stats.json.gz") else {}
    POS = positions(L); POS.update({p: "DEF" for p in list(POS) if not p.isdigit()})
    ex = collections.Counter()
    rows = season_rows(L, R, ST, POS, ex)
    MET = ["ap", "sc", "cons", "lu", "out", "luck"]
    B = {}
    keys = sorted({r["k"] for r in rows})
    groups = {k: [r for r in rows if r["k"] == k] for k in keys}
    for t in (0, 1, 2): groups[f"{t}|*"] = [r for r in rows if r["t"] == t]
    groups["*|*"] = rows
    for k, rs in groups.items():
        b = {}
        for m in MET:
            v = [r[m] for r in rs if r.get(m) is not None]
            if len(v) >= MIN_N or (k == "*|*" and len(v) >= 30): b[m] = stats(v)
        if b: B[k] = b

    def ref(k, m):
        t = k.split("|")[0]
        for kk in (k, f"{t}|*", "*|*"):
            if kk in B and m in B[kk]: return B[kk][m]
        return None

    def z(r, m):
        b = ref(r["k"], m)
        if b is None or r.get(m) is None: return None
        x = min(b[3], max(b[2], r[m]))
        return max(-3.0, min(3.0, (x - b[0]) / b[1]))

    # composite season score, standardized per set of available parts
    SETS = {"full": ("ap", "lu", "out"), "nolu": ("ap", "out"), "perf": ("ap", "lu"), "ap": ("ap",)}
    def comp(r, parts):
        zs = [(W[p], z(r, p)) for p in parts]
        if any(v is None for _, v in zs): return None
        return sum(w * v for w, v in zs) / sum(w for w, _ in zs)
    S_SD = {}
    for nm, parts in SETS.items():
        v = [c for c in (comp(r, parts) for r in rows) if c is not None]
        S_SD[nm] = round(sdv(v), 5) if len(v) >= 30 else None
    for r in rows:
        nm = "full" if r.get("lu") is not None and r.get("out") is not None else "nolu" if r.get("out") is not None else None
        r["S"] = comp(r, SETS[nm]) / S_SD[nm] if nm and S_SD.get(nm) else None
        for m in ("ap", "sc", "cons", "lu", "out"): r["z_" + m] = z(r, m)

    # career persistence (tau2) from managers seen in 2+ seasons, when owner ids exist
    tau2, src = dict(TAU2_DEFAULT), "assumed"
    by_o = collections.defaultdict(list)
    for r in rows:
        if r.get("o"): by_o[r["o"]].append(r)
    multi = {o: rs for o, rs in by_o.items() if len({x["s"] for x in rs}) >= 2}
    if len(multi) >= 300:
        src = "measured"
        for m, key in (("S", "S"), ("ap", "z_ap"), ("lu", "z_lu"), ("sc", "z_sc"), ("cons", "z_cons"), ("out", "z_out")):
            cp, n = 0.0, 0
            for rs in multi.values():
                v = [(x["s"], x[key]) for x in rs if x.get(key) is not None]
                for i in range(len(v)):
                    for j in range(i + 1, len(v)):
                        if v[i][0] != v[j][0]: cp += v[i][1] * v[j][1]; n += 1
            if n >= 300:
                tot = [x[key] for rs in multi.values() for x in rs if x.get(key) is not None]
                var = sdv(tot) ** 2 or 1
                tau2[m] = round(min(.8, max(.03, cp / n / var)), 4)
    out = {"built": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), "v": 2,
           "n": {"team_seasons": len(rows), "leagues": len({r["lg"] for r in rows}), "with_lineups": sum(1 for r in rows if r.get("lu") is not None),
                 "managers_multi_season": len(multi), "seasons": sorted({r["s"] for r in rows})},
           "excluded": dict(ex), "W": W, "VAL": VAL, "PO_VAL": PO_VAL, "PT": PT, "PW": PW, "MIN_N": MIN_N, "S_SD": S_SD,
           "tau2": tau2, "tau2_src": src, "B": B}
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, separators=(",", ":"))
    print(json.dumps({k: out[k] for k in ("n", "excluded", "S_SD", "tau2", "tau2_src")}, indent=1))
    print("buckets:", {k: v["ap"][4] for k, v in B.items() if "ap" in v})


if __name__ == "__main__":
    main()
