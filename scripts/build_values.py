#!/usr/bin/env python3
"""Build data/values.json: market trade values from every free source we can reach, keyed by Sleeper id.

Sources (each optional; a failed source is skipped and reported):
  Dynasty Dealer   https://www.dynastydealer.com  (values from 672k+ real Sleeper trades; attribution required)
  FantasyCalc      https://www.fantasycalc.com    (values from real fantasy trades; dynasty + redraft, 1QB + SF)
  RosterAudit      https://rosteraudit.com        (dynasty values; attribution required; ROSTERAUDIT_KEY optional)
  DynastyProcess   https://github.com/dynastyprocess/data (consensus values, CC-BY)
  FantasyPros ECR  via DynastyProcess (weekly / rest-of-season consensus ranks and expert spread)
  Fantasy Football Calculator ADP (attribution required)
  nflverse injury reports (career injury history)
  The Odds API     player props, only if ODDS_API_KEY is set (kept under the free monthly credit budget)
"""
import csv, io, json, os, re, sys, time, urllib.parse, urllib.request
from collections import defaultdict

UA = "Hashmark/1.0 (fantasy football hub; github.com/jsdixon2/Hashmark)"
DP_IDS = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
DP_VAL = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/values-players.csv"
DP_ECR = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_fpecr_latest.csv"
NV = "https://github.com/nflverse/nflverse-data/releases/download/"
STATUS = []


def get(url, headers=None, tries=2, raw=False):
    for k in range(tries):
        try:
            h = {"User-Agent": UA, "Accept": "application/json, text/csv, */*"}
            h.update(headers or {})
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
                b = r.read()
            return b if raw else b.decode("utf-8", "replace")
        except Exception as e:
            if k == tries - 1:
                print("  skip", url[:110], e)
                return None
            time.sleep(2)


def jget(url, headers=None):
    t = get(url, headers)
    try:
        return json.loads(t) if t else None
    except Exception:
        return None


def rows(url):
    t = get(url)
    return list(csv.DictReader(io.StringIO(t))) if t else []


def f(x):
    try:
        v = float(x)
        return v if v == v else None
    except Exception:
        return None


def norm(n):
    n = (n or "").lower().replace(".", "").replace("'", "").replace("’", "")
    n = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", n.strip())
    return re.sub(r"[^a-z ]", "", n).strip()


def walk(o):
    """Yield every dict inside a JSON document."""
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def find(d, *keys):
    for k in keys:
        cur = d
        ok = True
        for part in k.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok and cur not in (None, ""):
            return cur
    return None


def season_now():
    t = time.gmtime()
    return t.tm_year if t.tm_mon >= 8 else t.tm_year - 1


def main():
    cur = season_now()
    ids = rows(DP_IDS)
    fp2s = {r["fantasypros_id"]: r["sleeper_id"] for r in ids if r.get("fantasypros_id") not in ("", "NA") and r.get("sleeper_id") not in ("", "NA")}
    g2s = {r["gsis_id"]: r["sleeper_id"] for r in ids if r.get("gsis_id") not in ("", "NA") and r.get("sleeper_id") not in ("", "NA")}
    n2s = {}
    for r in ids:
        if r.get("sleeper_id") in ("", "NA"):
            continue
        n2s.setdefault((norm(r.get("merge_name") or r.get("name")), r.get("position")), r["sleeper_id"])
    V = defaultdict(dict)

    def put(sid, key, val):
        if sid and val is not None:
            V[str(sid)][key] = round(val, 1) if isinstance(val, float) else val

    def note(name, n):
        STATUS.append({"name": name, "ok": n > 0, "n": n}); print(f"  {name}: {n}")

    # Dynasty Dealer (dynasty, and redraft PPR in 1QB/SF)
    for key, url in (("dd", "https://www.dynastydealer.com/api/player-values"),
                     ("dd_1q", "https://www.dynastydealer.com/api/player-values?sf=false"),
                     ("dd_rd_sf", "https://www.dynastydealer.com/api/player-values?format=redraft&scoring=ppr&sf=true"),
                     ("dd_rd_1q", "https://www.dynastydealer.com/api/player-values?format=redraft&scoring=ppr")):
        j = jget(url); n = 0
        for d in walk(j):
            sid = find(d, "sleeper_id", "sleeperId"); val = f(find(d, "current_value", "value", "base_value"))
            if sid and val:
                put(sid, key, val); n += 1
        note("Dynasty Dealer " + key, n)
    # FantasyCalc
    for key, q in (("fc_sf", "isDynasty=true&numQbs=2&numTeams=12&ppr=1"), ("fc_1q", "isDynasty=true&numQbs=1&numTeams=12&ppr=1"),
                   ("fc_rd_sf", "isDynasty=false&numQbs=2&numTeams=12&ppr=1"), ("fc_rd_1q", "isDynasty=false&numQbs=1&numTeams=12&ppr=1")):
        j = jget("https://api.fantasycalc.com/values/current?" + q); n = 0
        for d in walk(j):
            sid = find(d, "player.sleeperId", "sleeperId"); val = f(find(d, "value"))
            if sid and val and "player" in d:
                put(sid, key, val); n += 1
                tr = f(find(d, "trend30Day"))
                if tr is not None and key == "fc_sf":
                    put(sid, "fc_tr", tr)
        note("FantasyCalc " + key, n)
    # RosterAudit (no key needed for rankings; key optional)
    rk = os.environ.get("ROSTERAUDIT_KEY", "").strip()
    hdr = {"X-RA-Key": rk} if rk else {}
    for key, q in (("ra_sf", "format=sf"), ("ra_1q", "format=1qb")):
        j = jget("https://rosteraudit.com/wp-json/ra/v1/rankings/values?" + q, hdr); n = 0
        if isinstance(j, dict):
            for k2, v2 in (j.get("values") or j.get("data") or j).items() if isinstance(j.get("values") or j.get("data") or j, dict) else []:
                val = f(v2 if not isinstance(v2, dict) else find(v2, "sf" if key == "ra_sf" else "1qb", "value", "dynasty_value"))
                if val and str(k2).isdigit():
                    put(k2, key, val); n += 1
        if not n:
            for d in walk(j):
                sid = find(d, "sleeper_id", "sleeperId", "player_id"); val = f(find(d, "value", "dynasty_value", "sf_value"))
                if sid and val:
                    put(sid, key, val); n += 1
        if not n:
            print("  RosterAudit response sample:", json.dumps(j)[:400] if j is not None else None)
        note("RosterAudit " + key, n)
    # DynastyProcess values
    n = 0
    for r in rows(DP_VAL):
        sid = fp2s.get(r.get("fp_id")) or n2s.get((norm(r.get("player")), r.get("pos")))
        if sid:
            put(sid, "dp_1q", f(r.get("value_1qb"))); put(sid, "dp_sf", f(r.get("value_2qb"))); n += 1
    note("DynastyProcess", n)
    # FantasyPros ECR (redraft weekly/ROS), with expert spread
    n = 0
    for r in rows(DP_ECR):
        sid = fp2s.get(r.get("id"))
        if not sid:
            continue
        pg, et = r.get("fp_page") or "", r.get("ecr_type") or ""
        if re.search(r"idp|/dl|/lb|/db|dst|/k\.php|-k\.php", pg):
            continue
        key = {"dsf": "ecr_dsf", "do": "ecr_d", "ro": "ecr_ros", "wsf": "ecr_wk", "dp": "ecr_dpos", "rp": "ecr_rpos", "wp": "ecr_wpos", "drk": "ecr_rook"}.get(et)
        if not key:
            continue
        put(sid, key, f(r.get("ecr"))); put(sid, key + "_sd", f(r.get("sd")))
        n += 1
    note("FantasyPros ECR", n)
    # Fantasy Football Calculator ADP
    for key, path in (("adp_ppr", f"ppr?teams=12&year={cur}"), ("adp_dyn", f"dynasty?teams=12&year={cur}"), ("adp_rook", f"rookie?teams=12&year={cur}")):
        j = jget("https://fantasyfootballcalculator.com/api/v1/adp/" + path); n = 0
        for d in walk(j):
            nm, ps, adp = d.get("name"), d.get("position"), f(d.get("adp"))
            if nm and adp:
                sid = n2s.get((norm(nm), ps))
                if sid:
                    put(sid, key, adp); n += 1
        if n < 20:
            print("  FFC response sample:", json.dumps(j)[:400] if j is not None else None)
        note("FFC " + key, n)
    # injury history: weeks listed Out/IR on official reports, last 3 seasons
    inj = defaultdict(lambda: [0, 0, 0])
    for i, y in enumerate((cur - 2, cur - 1, cur)):
        for r in rows(NV + f"injuries/injuries_{y}.csv"):
            if (r.get("report_status") or "") in ("Out", "Doubtful") and r.get("gsis_id") in g2s:
                inj[g2s[r["gsis_id"]]][i] += 1
    for sid, a in inj.items():
        put(sid, "injh", a)
    note("injury history", len(inj))
    # The Odds API player props (optional key; one pull on Wednesdays keeps us under the free credit budget)
    ok = os.environ.get("ODDS_API_KEY", "").strip()
    props = {}
    if ok and time.gmtime().tm_wday in (2,) or (ok and os.environ.get("FORCE_PROPS")):
        ev = jget(f"https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events?apiKey={ok}") or []
        for e in ev[:16]:
            j = jget(f"https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events/{e['id']}/odds?apiKey={ok}&regions=us&markets=player_anytime_td,player_reception_yds&oddsFormat=american&bookmakers=draftkings")
            for d in walk(j):
                if d.get("key") not in ("player_anytime_td", "player_reception_yds"):
                    continue
                for o in d.get("outcomes", []):
                    nm = o.get("description") or o.get("name")
                    sid = next((n2s.get((norm(nm), ps)) for ps in ("WR", "RB", "TE", "QB") if n2s.get((norm(nm), ps))), None)
                    if not sid:
                        continue
                    pr = f(o.get("price"))
                    p = (100 / (pr + 100)) if pr and pr > 0 else (-pr / (-pr + 100)) if pr else None
                    if d["key"] == "player_anytime_td" and (o.get("name") in ("Yes", None) or o.get("name") == nm):
                        props.setdefault(sid, {})["atd"] = round(p, 3) if p else None
                    elif d["key"] == "player_reception_yds" and o.get("name") == "Over":
                        props.setdefault(sid, {})["recyd"] = f(o.get("point"))
        note("Odds API props", len(props))
    os.makedirs("data", exist_ok=True)
    out = {"asof": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), "season": cur, "sources": STATUS, "v": V}
    if props:
        out["props"] = props; out["props_asof"] = out["asof"]
    elif os.path.exists("data/values.json"):
        try:
            old = json.load(open("data/values.json"))
            if old.get("props"):
                out["props"] = old["props"]; out["props_asof"] = old.get("props_asof")
        except Exception:
            pass
    with open("data/values.json", "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print(f"{len(V)} players with values; file {os.path.getsize('data/values.json')//1024} KB")


if __name__ == "__main__":
    main()
