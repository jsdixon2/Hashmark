#!/usr/bin/env python3
"""Build data/values.json: market trade values from every free source we can reach, keyed by Sleeper id.

Sources (each optional; a failed source is skipped and reported):
  Dynasty Dealer   https://www.dynastydealer.com  (values from 672k+ real Sleeper trades; attribution required)
  FantasyCalc      https://www.fantasycalc.com    (values from real fantasy trades; dynasty + redraft, 1QB + SF)
  RosterAudit      https://rosteraudit.com        (dynasty values; attribution required; ROSTERAUDIT_KEY optional)
  DynastyProcess   https://github.com/dynastyprocess/data (consensus values, CC-BY)
  FantasyPros ECR  via DynastyProcess (weekly / rest-of-season consensus ranks and expert spread)
  Fantasy Football Calculator ADP (attribution required). FFC only lists players with enough recent mock drafts:
    in-season the PPR feed returns a handful of players and the dynasty/rookie feeds return none. A feed below its
    minimum (FFC_MIN) keeps the last good values from the previous file (same season, up to FFC_MAX_DAYS old), marked
    with that run's `asof` in `sources`; with no good earlier run the keys are not written.
  nflverse injury reports (career injury history)
"""
import calendar, csv, io, json, os, re, sys, time, urllib.parse, urllib.request
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


OUT = os.environ.get("HM_OUT_VALUES", "").strip() or "data/values.json"       # where to write
PREV = os.environ.get("HM_PREV_VALUES", "").strip() or "data/values.json"     # last published file (read only)
FFC_MIN = {"adp_ppr": 100, "adp_dyn": 100, "adp_rook": 24}   # a real 12-team board lists 180 (rookie: 36+)
FFC_MAX_DAYS = 150
FFC_POS = {"PK": "K"}


def load_prev():
    try:
        with open(PREV) as fh:
            return json.load(fh)
    except Exception:
        return None


def age_days(asof):
    try:
        return (time.time() - calendar.timegm(time.strptime(asof, "%Y-%m-%dT%H:%MZ"))) / 86400
    except Exception:
        return None


def season_now():
    t = time.gmtime()
    return t.tm_year if t.tm_mon >= 8 else t.tm_year - 1


def main():
    cur = season_now()
    prev = load_prev()
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

    def note(name, n, **extra):
        STATUS.append({"name": name, "ok": n > 0, "n": n, **extra}); print(f"  {name}: {n}", extra or "")

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
    # Fantasy Football Calculator ADP (thin in-season: keep the last good board, see FFC_MIN)
    pv = (prev or {}).get("v") or {}
    pst = {x.get("name"): x for x in (prev or {}).get("sources") or [] if isinstance(x, dict)}
    now = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())
    for key, path in (("adp_ppr", f"ppr?teams=12&year={cur}"), ("adp_dyn", f"dynasty?teams=12&year={cur}"), ("adp_rook", f"rookie?teams=12&year={cur}")):
        j = jget("https://fantasyfootballcalculator.com/api/v1/adp/" + path)
        pl = j.get("players") if isinstance(j, dict) and isinstance(j.get("players"), list) else []
        meta = j.get("meta") if isinstance(j, dict) and isinstance(j.get("meta"), dict) else {}
        got = {}
        for d in pl:
            nm, adp = d.get("name"), f(d.get("adp"))
            ps = FFC_POS.get(d.get("position"), d.get("position"))
            sid = n2s.get((norm(nm), ps)) if nm and adp else None
            if sid:
                got[sid] = adp
        live = dict(fetched=len(pl), matched=len(got), drafts=meta.get("total_drafts"),
                    window=f"{meta.get('start_date')}..{meta.get('end_date')}" if meta else None)
        print(f"  FFC {key}: {len(pl)} listed, {len(got)} matched, meta {json.dumps(meta)[:160]}" if j is not None else f"  FFC {key}: no response")
        if len(got) >= FFC_MIN[key]:
            for sid, adp in got.items():
                put(sid, key, adp)
            note("FFC " + key, len(got), asof=now, **live)
            continue
        old = pst.get("FFC " + key) or {}
        oasof = old.get("asof") or (prev or {}).get("asof")
        oage = age_days(oasof) if oasof else None
        keep = {k: v[key] for k, v in pv.items() if isinstance(v, dict) and key in v}
        if old.get("ok") and (prev or {}).get("season") == cur and oage is not None and oage <= FFC_MAX_DAYS and len(keep) >= FFC_MIN[key]:
            for sid, adp in keep.items():
                put(sid, key, adp)
            note("FFC " + key, len(keep), asof=oasof, carried=True, **live)
        else:
            note("FFC " + key, 0, dropped="feed below minimum and no recent good board", **live)
    # injury history: weeks listed Out/IR on official reports, last 3 seasons
    inj = defaultdict(lambda: [0, 0, 0])
    for i, y in enumerate((cur - 2, cur - 1, cur)):
        for r in rows(NV + f"injuries/injuries_{y}.csv"):
            if (r.get("report_status") or "") in ("Out", "Doubtful") and r.get("gsis_id") in g2s:
                inj[g2s[r["gsis_id"]]][i] += 1
    for sid, a in inj.items():
        put(sid, "injh", a)
    note("injury history", len(inj))
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    out = {"asof": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), "season": cur, "sources": STATUS, "v": V}
    with open(OUT, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print(f"{len(V)} players with values; file {OUT} {os.path.getsize(OUT)//1024} KB")


if __name__ == "__main__":
    main()
