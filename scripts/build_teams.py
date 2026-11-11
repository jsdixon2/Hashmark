#!/usr/bin/env python3
"""Engine 6: NFL team ratings, game odds, implied points and schedule strength -> data/teams.json.

Fitted in backtest/e12_*.py (2002-2025 nflverse games):
- Rating: points-margin Elo (K .08, home edge 2.0, last season's rating x .7 as the prior, margins capped at 28,
  sigma 12.5). Tested on 1,355 games 2021-25: Brier .2246 (old power rank .230). Closing spread: .2118.
- Game odds: the betting line when there is one (blend weight on the line fitted at 1.0), the rating otherwise.
  For 1-6 weeks ahead the rating beat market-implied ratings (Brier .220-.227 vs .226-.232).
- Implied team points: line + total when available; otherwise league average + shrunk offense/defense scoring
  (4-game prior from last season x .5) with the margin from the rating.
- Player effect of the environment, used only for weeks with no Sleeper projection yet (Sleeper's projection already
  prices this week's line: adding it again tested worse): factor = 1 + beta_pos x (implied / team average - 1),
  beta QB .577, RB .535, WR .245, TE .224 (e12_env.json). Defense-vs-position adds ~0.02 pts MAE (e12_dvp.json):
  shown for context only.
- Prediction log: every game's pregame home win chance is stored once and graded when final (Brier by source)."""
import csv, io, json, math, os, urllib.request, datetime, collections
URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
LOCAL = "backtest/dl/games.csv"
OUT = "data/teams.json"
K, HFA, PRIOR, CAP, SIG = .08, 2.0, .7, 28, 12.5
BETA = {"QB": .577, "RB": .535, "WR": .245, "TE": .224}
FPLAY = (15, 16, 17)
CODE = {"LA": "LAR", "STL": "LAR", "OAK": "LV", "SD": "LAC"}

def phi(x): return .5 * (1 + math.erf(x / math.sqrt(2)))
def num(x):
    try: return float(x)
    except Exception: return None

def load():
    try:
        raw = urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "hashmark"}), timeout=60).read().decode()
    except Exception:
        raw = open(LOCAL).read()
    rows = list(csv.DictReader(io.StringIO(raw)))
    for r in rows:  # nflverse codes -> Sleeper's
        for k in ("home_team", "away_team"): r[k] = CODE.get(r[k], r[k])
    return rows

def main():
    rows = [r for r in load() if int(r["season"]) >= 2002]
    rows.sort(key=lambda r: (int(r["season"]), int(r["week"]), r.get("gameday") or ""))
    season = max(int(r["season"]) for r in rows)
    sched = {}
    try:
        sj = json.load(open("data/sched.json"))
        for g in sj.get("games", []): sched[(g["wk"], g["a"], g["h"])] = g
    except Exception: pass
    r, last_season = {}, None
    for g in rows:
        s = int(g["season"])
        if s != last_season: r = {t: PRIOR * v for t, v in r.items()}; last_season = s
        hs, as_ = num(g["home_score"]), num(g["away_score"])
        if hs is None or as_ is None: continue
        h, a = r.get(g["home_team"], 0.0), r.get(g["away_team"], 0.0); hfa = 0 if g.get("location") == "Neutral" else HFA
        err = max(-CAP, min(CAP, hs - as_)) - (h - a + hfa)
        r[g["home_team"]] = h + K * err; r[g["away_team"]] = a - K * err
    cur = [g for g in rows if int(g["season"]) == season and g["game_type"] == "REG"]
    prev = [g for g in rows if int(g["season"]) == season - 1 and g["game_type"] == "REG" and num(g["home_score"]) is not None]
    done = [g for g in cur if num(g["home_score"]) is not None]
    teams = sorted({g["home_team"] for g in cur} | {g["away_team"] for g in cur})
    def scoring(games):
        pf, pa, n = collections.Counter(), collections.Counter(), collections.Counter()
        for g in games:
            hs, as_ = num(g["home_score"]), num(g["away_score"])
            pf[g["home_team"]] += hs; pa[g["home_team"]] += as_; n[g["home_team"]] += 1
            pf[g["away_team"]] += as_; pa[g["away_team"]] += hs; n[g["away_team"]] += 1
        return pf, pa, n
    pf, pa, n = scoring(done); ppf, ppa, pn = scoring(prev)
    lg = (sum(pf.values()) / max(1, sum(n.values()))) if done else 22.0
    plg = (sum(ppf.values()) / max(1, sum(pn.values()))) if prev else lg
    off, dfn = {}, {}
    for t in teams:
        po = .5 * ((ppf[t] / pn[t] - plg) if pn[t] else 0); pd = .5 * ((ppa[t] / pn[t] - plg) if pn[t] else 0)
        off[t] = ((pf[t] - lg * n[t]) + 4 * po) / (n[t] + 4); dfn[t] = ((pa[t] - lg * n[t]) + 4 * pd) / (n[t] + 4)
    wl = {t: [0, 0, 0] for t in teams}
    for g in done:
        hs, as_ = num(g["home_score"]), num(g["away_score"])
        if hs > as_: wl[g["home_team"]][0] += 1; wl[g["away_team"]][1] += 1
        elif as_ > hs: wl[g["away_team"]][0] += 1; wl[g["home_team"]][1] += 1
        else: wl[g["home_team"]][2] += 1; wl[g["away_team"]][2] += 1
    games, by_team = [], collections.defaultdict(list)
    for g in cur:
        wk, h, a = int(g["week"]), g["home_team"], g["away_team"]; neu = g.get("location") == "Neutral"
        final = num(g["home_score"]) is not None
        s = sched.get((wk, a, h), {})
        sp = s.get("sp") if s.get("sp") is not None else num(g.get("spread_line"))   # expected home margin
        tot = s.get("tot") if s.get("tot") is not None else num(g.get("total_line"))
        rm = r.get(h, 0) - r.get(a, 0) + (0 if neu else HFA)
        if sp is not None and not final: mu, src = sp, "line"
        else: mu, src = rm, "rating"
        if tot is None: tot = (lg + off[h] + dfn[a]) + (lg + off[a] + dfn[h])
        ih, ia = tot / 2 + mu / 2, tot / 2 - mu / 2
        row = {"wk": wk, "h": h, "a": a, "p": round(phi(mu / SIG), 4), "mu": round(mu, 2), "src": src, "ih": round(ih, 1), "ia": round(ia, 1), "final": final}
        if final: row.update(hs=num(g["home_score"]), as_=num(g["away_score"]))
        games.append(row)
        for t, imp, o, p in ((h, ih, a, row["p"]), (a, ia, h, 1 - row["p"])):
            by_team[t].append({"wk": wk, "o": o, "home": t == h, "imp": round(imp, 1), "p": round(p, 3), "final": final})
    out_t = {}
    rank = sorted(teams, key=lambda t: -r.get(t, 0))
    for t in teams:
        avg = (lg + off[t])
        fut = [x for x in by_team[t] if not x["final"]]
        env = {pos: [{"wk": x["wk"], "f": round(1 + b * (x["imp"] / max(10, avg) - 1), 3)} for x in fut] for pos, b in BETA.items()}
        fp = [x for x in fut if x["wk"] in FPLAY]
        out_t[t] = {"r": round(r.get(t, 0), 2), "rank": rank.index(t) + 1, "rec": wl[t], "off": round(off[t], 2), "def": round(dfn[t], 2), "avg": round(avg, 1),
                    "next": fut[:4], "fplay": fp, "env": env,
                    "sos_rest": round(sum(r.get(x["o"], 0) for x in fut) / max(1, len(fut)), 2), "sos_fplay": round(sum(r.get(x["o"], 0) for x in fp) / max(1, len(fp)), 2) if fp else None,
                    "dst_fplay": round(sum(next((g["ia"] if g["h"] == t else g["ih"]) for g in games if g["wk"] == x["wk"] and t in (g["h"], g["a"])) for x in fp) / max(1, len(fp)), 1) if fp else None}
    # prediction log: first pregame prediction per game is kept; graded when final
    log = {}
    try: log = json.load(open(OUT)).get("log", {})
    except Exception: pass
    for g in games:
        k = f"{season}-{g['wk']}-{g['a']}@{g['h']}"
        if not g["final"] and k not in log: log[k] = {"p": g["p"], "src": g["src"], "t": datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d")}
        if g["final"] and k in log and "y" not in log[k] and g.get("hs") != g.get("as_"): log[k]["y"] = 1 if g["hs"] > g["as_"] else 0
    graded = [v for v in log.values() if "y" in v]
    card = {"n": len(graded), "brier": round(sum((v["p"] - v["y"]) ** 2 for v in graded) / len(graded), 4) if graded else None,
            "acc": round(sum((v["p"] > .5) == (v["y"] == 1) for v in graded) / len(graded), 3) if graded else None}
    out = {"built": datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat() + "Z", "season": season, "lg": round(lg, 1), "sigma": SIG, "hfa": HFA, "beta": BETA,
           "fplay_weeks": list(FPLAY), "teams": out_t, "games": games, "log": log, "card": card,
           "method": {"test_brier_rating": .2246, "test_brier_line": .2118, "old_power_rank": .230}}
    try:  # no commit churn: keep the old file when nothing but the timestamp changed
        old = json.load(open(OUT)); old.pop("built", None)
        if old == {k: v for k, v in out.items() if k != "built"}: print("teams.json unchanged"); return
    except Exception: pass
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    print(f"{len(teams)} teams, {len(games)} games ({sum(1 for g in games if g['src']=='line' and not g['final'])} with lines), log graded {card}")

if __name__ == "__main__":
    main()
