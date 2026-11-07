#!/usr/bin/env python3
"""One-off probe: how far back do OddsPapi's NFL player props go? Writes bt/oddspapi_probe.json (no key stored)."""
import json, os, time, urllib.parse, urllib.request
KEY = os.environ.get("ODDSPAPI_KEY", "").strip()
BASE = "https://api.oddspapi.io/v4"
LOG = []


def call(path, **q):
    q["apiKey"] = KEY
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(q)
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "hashmark-probe"}), timeout=60) as r:
                return r.status, json.loads(r.read().decode() or "null")
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:400]
            try:
                j = json.loads(body); wait = (j.get("error") or {}).get("retryMs")
            except Exception:
                j, wait = body, None
            if e.code == 429 and wait:
                time.sleep(wait / 1000 + .5); continue
            LOG.append({"path": path, "q": {k: v for k, v in q.items() if k != "apiKey"}, "status": e.code, "body": j if isinstance(j, (dict, list)) else str(j)[:300]})
            return e.code, None
        except Exception as e:
            LOG.append({"path": path, "err": str(e)[:200]}); time.sleep(3)
    return None, None


def main():
    out = {"ran": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), "seasons": {}}
    if not KEY:
        out["error"] = "ODDSPAPI_KEY not set"
    else:
        st, mk = call("markets", sportId=14)
        names = {}
        if isinstance(mk, list):
            for m in mk:
                names[str(m.get("marketId"))] = m.get("marketName")
        out["n_markets"] = len(names)
        out["prop_market_names"] = sorted({n for n in names.values() if n and "Player" in n})[:80]
        windows = {"2025-wk14": ("2025-12-07", "2025-12-09"), "2025-wk18": ("2026-01-04", "2026-01-06"), "2026-wk1": ("2026-09-10", "2026-09-15"),
                   "2026-wk2": ("2026-09-17", "2026-09-22"), "2026-wk3": ("2026-09-24", "2026-09-29"), "2026-wk9": ("2026-11-01", "2026-11-03")}
        for season, (a, b) in windows.items():
            time.sleep(1.5)
            st, fx = call("fixtures", sportId=14, tournamentId=31, **{"from": a, "to": b})
            info = {"fixtures_status": st, "n_fixtures": len(fx) if isinstance(fx, list) else None}
            if isinstance(fx, list) and fx:
                f = fx[0]; info["sample_fixture"] = {k: f.get(k) for k in ("fixtureId", "participant1Name", "participant2Name", "startTime", "statusName")}
                time.sleep(5.5)
                st2, h = call("historical-odds", fixtureId=f["fixtureId"], bookmakers="draftkings,fanduel,caesars")
                info["hist_status"] = st2
                if isinstance(h, dict):
                    books = {}
                    for slug, bk in (h.get("bookmakers") or {}).items():
                        props, players, snaps, mkts, first = 0, set(), 0, {}, None
                        for mid, m in (bk.get("markets") or {}).items():
                            for oc in (m.get("outcomes") or {}).values():
                                for pid, rows in (oc.get("players") or {}).items():
                                    if pid == "0":
                                        continue
                                    props += 1; players.add(pid); rows = rows if isinstance(rows, list) else [rows]; snaps += len(rows)
                                    nm = names.get(str(mid), str(mid)); mkts[nm] = mkts.get(nm, 0) + 1
                                    for r in rows:
                                        c = r.get("createdAt")
                                        if c and (first is None or c < first): first = c
                        books[slug] = {"prop_outcomes": props, "players": len(players), "snapshots": snaps, "first_snapshot": first,
                                       "markets": dict(sorted(mkts.items(), key=lambda x: -x[1])[:12])}
                    info["books"] = books
            out["seasons"][season] = info
    out["errors"] = LOG[:20]
    os.makedirs("bt", exist_ok=True)
    json.dump(out, open("bt/oddspapi_probe.json", "w"), indent=1)
    print(json.dumps(out, indent=1)[:3000])


if __name__ == "__main__":
    main()
