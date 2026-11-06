#!/usr/bin/env python3
"""Build data/odds.json from The Odds API (free tier: 500 credits a month).

Budget, enforced here because this runs every 30 minutes:
  game lines  spreads + totals, US books      2 credits, at most every 12 hours  (~120 a month)
  player props anytime TD, receiving, rushing,
               passing yards for the next 7 days 4 credits per game, once per NFL week (~260 a month)
The /events listing is free. Every response reports credits left; we stop well short of zero.
Output: {lines_asof, games:{"AWAY@HOME":{sp,tot,n,t}}, props_asof, props_wk, props:{sleeper_id:{atd,rec,rush,pass}}, left}
sp follows nflverse: positive means the home team is favored.
"""
import csv, io, json, os, re, statistics, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

KEY = os.environ.get("ODDS_API_KEY", "").strip()
BASE = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl"
OUT = "data/odds.json"
ABBR = {"Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF", "Carolina Panthers": "CAR",
        "Chicago Bears": "CHI", "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL", "Denver Broncos": "DEN",
        "Detroit Lions": "DET", "Green Bay Packers": "GB", "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
        "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC", "Los Angeles Rams": "LAR", "Miami Dolphins": "MIA",
        "Minnesota Vikings": "MIN", "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG", "New York Jets": "NYJ",
        "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT", "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA",
        "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN", "Washington Commanders": "WAS"}
MARKETS = {"player_anytime_td": "atd", "player_reception_yds": "rec", "player_rush_yds": "rush", "player_pass_yds": "pass"}
LEFT = [None]


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "hashmark-build"}), timeout=60) as r:
            left = r.headers.get("x-requests-remaining")
            if left is not None:
                LEFT[0] = int(float(left))
            return json.loads(r.read().decode())
    except Exception as e:
        print("  skip", re.sub(r"apiKey=[^&]+", "apiKey=***", url)[:140], e)
        return None


def norm(n):
    n = (n or "").lower().replace(".", "").replace("'", "").replace("’", "")
    n = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", n.strip())
    return re.sub(r"[^a-z ]", "", n).strip()


def implied(price):
    if price is None:
        return None
    return 100 / (price + 100) if price > 0 else -price / (-price + 100)


def iso(t):
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


def main():
    if not KEY:
        print("ODDS_API_KEY not set; skipping odds"); return
    old = {}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT))
        except Exception:
            old = {}
    now = datetime.now(timezone.utc)
    force = os.environ.get("FORCE_ODDS") == "1"
    out = dict(old)
    changed = False
    # ---- game lines ----
    la = old.get("lines_asof")
    if force or not la or now - iso(la) > timedelta(hours=12):
        j = get(f"{BASE}/odds?apiKey={KEY}&regions=us&markets=spreads,totals&oddsFormat=american")
        if isinstance(j, list):
            games = {}
            for e in j:
                h, a = ABBR.get(e.get("home_team")), ABBR.get(e.get("away_team"))
                if not h or not a:
                    continue
                sps, tots = [], []
                for bk in e.get("bookmakers", []):
                    for m in bk.get("markets", []):
                        for o in m.get("outcomes", []):
                            if m["key"] == "spreads" and o.get("name") == e["home_team"] and o.get("point") is not None:
                                sps.append(-float(o["point"]))
                            elif m["key"] == "totals" and o.get("name") == "Over" and o.get("point") is not None:
                                tots.append(float(o["point"]))
                if sps or tots:
                    games[f"{a}@{h}"] = {"sp": round(statistics.median(sps) * 2) / 2 if sps else None,
                                         "tot": round(statistics.median(tots) * 2) / 2 if tots else None,
                                         "n": max(len(sps), len(tots)), "t": e.get("commence_time")}
            out["games"] = games; out["lines_asof"] = now.strftime("%Y-%m-%dT%H:%M:%SZ"); changed = True
            print(f"  lines: {len(games)} games")
    # ---- player props, once per NFL week (week key = most recent Tuesday) ----
    tue = (now - timedelta(days=(now.weekday() - 1) % 7)).strftime("%Y-%m-%d")
    due = old.get("props_wk") != tue and (now.weekday() in (2, 3, 4, 5, 6) or not old.get("props"))
    if (force or due) and (LEFT[0] is None or LEFT[0] >= 90):
        ev = get(f"{BASE}/events?apiKey={KEY}") or []
        ev = [e for e in ev if now <= iso(e["commence_time"]) <= now + timedelta(days=7)][:16]
        names = {}
        try:
            txt = urllib.request.urlopen(urllib.request.Request("https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv",
                                                                headers={"User-Agent": "hashmark-build"}), timeout=60).read().decode()
            for r in csv.DictReader(io.StringIO(txt)):
                if r.get("sleeper_id") not in ("", "NA") and r.get("position") in ("QB", "RB", "WR", "TE"):
                    names.setdefault(norm(r.get("merge_name") or r.get("name")), r["sleeper_id"])
        except Exception as e:
            print("  player ids unavailable", e)
        acc = {}
        for e in ev:
            if LEFT[0] is not None and LEFT[0] < 60:
                print("  stopping props early to protect the monthly budget"); break
            j = get(f"{BASE}/events/{e['id']}/odds?apiKey={KEY}&regions=us&markets={','.join(MARKETS)}&oddsFormat=american")
            for bk in (j or {}).get("bookmakers", []):
                for m in bk.get("markets", []):
                    k = MARKETS.get(m.get("key"))
                    if not k:
                        continue
                    for o in m.get("outcomes", []):
                        sid = names.get(norm(o.get("description") or ""))
                        if not sid:
                            continue
                        d = acc.setdefault(sid, {})
                        if k == "atd" and o.get("name") in ("Yes", "Over"):
                            p = implied(o.get("price"))
                            if p:
                                d.setdefault("atd", []).append(p)
                        elif k != "atd" and o.get("name") == "Over" and o.get("point") is not None:
                            d.setdefault(k, []).append(float(o["point"]))
        if acc:
            props = {}
            for sid, d in acc.items():
                v = {}
                for k, xs in d.items():
                    m = statistics.median(xs)
                    v[k] = round(m * .94, 3) if k == "atd" else round(m * 2) / 2  # trim the bookmaker margin from TD odds
                props[sid] = v
            out["props"] = props; out["props_asof"] = now.strftime("%Y-%m-%dT%H:%M:%SZ"); out["props_wk"] = tue; changed = True
            print(f"  props: {len(props)} players from {len(ev)} games")
    out["left"] = LEFT[0] if LEFT[0] is not None else old.get("left")
    if changed:
        os.makedirs("data", exist_ok=True)
        json.dump(out, open(OUT, "w"), separators=(",", ":"))
    print(f"odds: credits left {out.get('left')}; {'updated' if changed else 'nothing due'}")


if __name__ == "__main__":
    main()
