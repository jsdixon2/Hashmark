#!/usr/bin/env python3
"""Archive closing NFL player props from OddsPapi (free tier) for model backtests: bt/props_hist.json.gz.
For every finished game: the last pregame price at DraftKings, FanDuel and Caesars, turned into a fair median line per stat
(the ladder rung where over/under is 50/50, vig removed) and a fair anytime-TD chance; then the median across books.
Free tier = one historical call every ~5 s, so a full backfill (~140 games) takes ~15 minutes; weekly runs only add new games."""
import gzip, json, os, statistics, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

KEY = os.environ.get("ODDSPAPI_KEY", "").strip()
BASES = ["https://api.oddspapi.io/v4", "https://v5.oddspapi.io/en"]
OUT = "bt/props_hist.json.gz"
BOOKS = "draftkings,fanduel,caesars"
FAM = {"Over Under Player Receiving Yards (incl. overtime)": "recyd", "Over Under Player Rush Yards (incl. overtime)": "rushyd",
       "Over Under Player Pass Yards (incl. overtime)": "passyd", "Over Under Player Receptions (incl. overtime)": "rec",
       "Over Under Player TD Passes (incl. overtime)": "passtd", "Over Under Player Rush Attempts (incl. overtime)": "rushatt",
       "Over Under Player Pass Attempts (incl. overtime)": "passatt"}
TD = "Player To Score TD (incl. overtime)"
SEASON_START = os.environ.get("PROPS_FROM", "2026-09-08")


def call(path, base=0, **q):
    q["apiKey"] = KEY
    url = f"{BASES[base]}/{path}?" + urllib.parse.urlencode(q)
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "hashmark-props"}), timeout=120) as r:
                return json.loads(r.read().decode() or "null")
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            try:
                w = (json.loads(body).get("error") or {}).get("retryMs")
            except Exception:
                w = None
            if e.code == 429:
                time.sleep((w or 6000) / 1000 + .5); continue
            print("  http", e.code, path, body[:120]); return None
        except Exception as e:
            print("  err", path, str(e)[:120]); time.sleep(4)
    return None


def fair2(po, pu):
    a, b = 1 / po, 1 / pu
    return a / (a + b)


def closing(rows, start):
    rows = [r for r in rows if isinstance(r, dict) and r.get("createdAt") and r["createdAt"] <= start and r.get("price")]
    if not rows: return None
    act = [r for r in rows if r.get("active")]
    return sorted(act or rows, key=lambda r: r["createdAt"])[-1]["price"]


def median_line(rungs):
    """rungs: [(handicap, p_over)] -> handicap where p_over crosses 0.5"""
    rs = sorted(rungs)
    if not rs: return None
    for (h1, p1), (h2, p2) in zip(rs, rs[1:]):
        if p1 >= .5 >= p2 and p1 != p2:
            return round(h1 + (p1 - .5) / (p1 - p2) * (h2 - h1), 2)
    h, p = min(rs, key=lambda x: abs(x[1] - .5))
    return h if .3 <= p <= .7 else None


def main():
    if not KEY:
        print("ODDSPAPI_KEY not set"); return
    old = json.load(gzip.open(OUT, "rt")) if os.path.exists(OUT) else {"games": {}, "names": {}}
    cat = call("markets", sportId=14) or []
    M = {str(c["marketId"]): c for c in cat if isinstance(c, dict)}
    now = datetime.now(timezone.utc)
    d0 = datetime.fromisoformat(SEASON_START).replace(tzinfo=timezone.utc)
    fixtures = []
    while d0 < now:
        d1 = min(d0 + timedelta(days=9), now)
        fx = call("fixtures", sportId=14, tournamentId=31, **{"from": d0.strftime("%Y-%m-%d"), "to": d1.strftime("%Y-%m-%d")}) or []
        fixtures += [f for f in fx if isinstance(f, dict)]
        d0 = d1 + timedelta(days=1); time.sleep(1.2)
    seen = set()
    todo = []
    for f in fixtures:
        if f["fixtureId"] in seen: continue
        seen.add(f["fixtureId"])
        st = datetime.fromisoformat(f["startTime"].replace("Z", "+00:00"))
        if st > now - timedelta(hours=5) or f["fixtureId"] in old["games"]: continue
        todo.append(f)
    print(f"{len(fixtures)} fixtures, {len(todo)} to archive")
    for f in todo:
        time.sleep(5.3)
        h = call("historical-odds", fixtureId=f["fixtureId"], bookmakers=BOOKS)
        if not isinstance(h, dict): continue
        start = f["startTime"]
        per = {}  # pid -> stat -> [book values]
        for slug, bk in (h.get("bookmakers") or {}).items():
            fam_rungs, td = {}, {}
            for mid, mk in (bk.get("markets") or {}).items():
                c = M.get(str(mid))
                if not c: continue
                name = c.get("marketName"); oc_names = {str(o["outcomeId"]): o["outcomeName"] for o in c.get("outcomes", [])}
                if name not in FAM and name != TD: continue
                prices = {}
                for oid, oc in (mk.get("outcomes") or {}).items():
                    for pid, rows in (oc.get("players") or {}).items():
                        if pid == "0": continue
                        pr = closing(rows if isinstance(rows, list) else [rows], start)
                        if pr: prices.setdefault(pid, {})[oc_names.get(str(oid), oid)] = pr
                for pid, side in prices.items():
                    if name == TD:
                        if "Yes" in side:
                            td[pid] = fair2(side["Yes"], side["No"]) if "No" in side else min(.99, .94 / side["Yes"])
                    elif "Over" in side and "Under" in side:
                        fam_rungs.setdefault(pid, {}).setdefault(FAM[name], []).append((float(c.get("handicap") or 0), fair2(side["Over"], side["Under"])))
            for pid, fams in fam_rungs.items():
                for k, rungs in fams.items():
                    v = median_line(rungs)
                    if v is not None: per.setdefault(pid, {}).setdefault(k, []).append(v)
            for pid, p in td.items():
                per.setdefault(pid, {}).setdefault("td", []).append(p)
        players = {pid: {k: round(statistics.median(v), 3) for k, v in st.items()} for pid, st in per.items()}
        old["games"][f["fixtureId"]] = {"start": start, "home": f.get("participant1Abbr"), "away": f.get("participant2Abbr"),
                                        "homeName": f.get("participant1Name"), "awayName": f.get("participant2Name"), "hid": f.get("participant1Id"), "aid": f.get("participant2Id"), "p": players}
        print(f["startTime"][:10], f.get("participant2Abbr"), "@", f.get("participant1Abbr"), len(players), "players")
    # player names: by id list, then by team (participant) as a fallback
    teams = {}
    for f in fixtures:
        for k in ("participant1Id", "participant2Id"):
            if f.get(k): teams[f[k]] = 1
    def absorb(r):
        n = 0
        if isinstance(r, dict): r = r.get("players") or r.get("data") or []
        if isinstance(r, list):
            for x in r:
                if isinstance(x, dict) and x.get("playerName") and x.get("playerId") is not None:
                    old["names"][str(x["playerId"])] = x["playerName"]; n += 1
        return n
    need = sorted({pid for g in old["games"].values() for pid in g["p"] if pid not in old["names"]})
    for i in range(0, len(need), 50):
        chunk = need[i:i + 50]; got = 0
        for b in (0, 1):
            got = absorb(call("players", base=b, playerIds=",".join(chunk)))
            if got: break
        time.sleep(1.2)
        if not got and i == 0: print("  name lookup by id returned nothing; trying by team"); break
    # names ride along on live odds (/odds lists playerName); harvest them from upcoming games
    up = [f for f in fixtures if datetime.fromisoformat(f["startTime"].replace("Z", "+00:00")) > now]
    nx = call("fixtures", sportId=14, tournamentId=31, **{"from": now.strftime("%Y-%m-%d"), "to": (now + timedelta(days=9)).strftime("%Y-%m-%d")}) or []
    up += [f for f in nx if isinstance(f, dict)]
    for f in {f["fixtureId"]: f for f in up}.values():
        o = call("odds", fixtureId=f["fixtureId"])
        if isinstance(o, dict):
            for bk in (o.get("bookmakerOdds") or {}).values():
                for mk in (bk.get("markets") or {}).values():
                    for oc in (mk.get("outcomes") or {}).values():
                        for pid, pr in (oc.get("players") or {}).items():
                            if pid != "0" and isinstance(pr, dict) and pr.get("playerName"): old["names"][str(pid)] = pr["playerName"]
        time.sleep(1.5)
    print("named after odds harvest:", len(old["names"]))
    r = call("players", base=0, playerIds=",".join(need[:3])); print("players probe:", str(r)[:300])
    if len([pid for g in old["games"].values() for pid in g["p"] if pid not in old["names"]]) > 50:
        for tid in teams:
            for b in (0, 1):
                if absorb(call("players", base=b, participantId=tid)): break
            time.sleep(1.2)
    old["built"] = now.strftime("%Y-%m-%dT%H:%MZ")
    os.makedirs("bt", exist_ok=True)
    with gzip.open(OUT, "wt") as fh:
        json.dump(old, fh, separators=(",", ":"))
    print(f"archived {len(old['games'])} games, {len(old['names'])} named players")


if __name__ == "__main__":
    main()
