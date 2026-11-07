#!/usr/bin/env python3
"""One-off probe: dump the raw shape of OddsPapi NFL player-prop history for one finished game (bt/oddspapi_sample.json)."""
import json, os, time, urllib.parse, urllib.request
KEY = os.environ.get("ODDSPAPI_KEY", "").strip()
BASE = "https://api.oddspapi.io/v4"


def call(path, **q):
    q["apiKey"] = KEY
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(q)
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "hashmark-probe"}), timeout=90) as r:
                return json.loads(r.read().decode() or "null")
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:400]
            try:
                w = (json.loads(body).get("error") or {}).get("retryMs")
            except Exception:
                w = None
            if e.code == 429 and w:
                time.sleep(w / 1000 + .5); continue
            return {"_error": e.code, "_body": body}
    return None


def main():
    cat = call("markets", sportId=14) or []
    fx = call("fixtures", sportId=14, tournamentId=31, **{"from": "2026-11-01", "to": "2026-11-03"}) or []
    f = fx[0] if isinstance(fx, list) and fx else {}
    time.sleep(5.5)
    h = call("historical-odds", fixtureId=f.get("fixtureId"), bookmakers="draftkings") or {}
    bk = (h.get("bookmakers") or {}).get("draftkings") or {}
    used = list((bk.get("markets") or {}).keys())
    want = []
    for mid in used:
        m = next((c for c in cat if str(c.get("marketId")) == str(mid)), None)
        if m and any(s in (m.get("marketName") or "") for s in ("Receiving Yards", "To Score TD", "Pass Yards", "Rush Yards", "Receptions")):
            want.append(mid)
    sample = {}
    for mid in want[:8]:
        mk = json.loads(json.dumps(bk["markets"][mid]))
        for oc in (mk.get("outcomes") or {}).values():
            pl = oc.get("players") or {}
            keep = dict(list(pl.items())[:2])
            for k2, rows in keep.items():
                if isinstance(rows, list):
                    keep[k2] = rows[:2] + (["..."] if len(rows) > 2 else []) + rows[-1:]
            oc["players"] = keep
        sample[mid] = mk
    out = {"fixture": f, "fixture_keys": list(f.keys()), "top_keys": list(h.keys()), "book_keys": list(bk.keys()),
           "catalog_examples": [c for c in cat if str(c.get("marketId")) in want[:8]],
           "catalog_item_keys": list(cat[0].keys()) if isinstance(cat, list) and cat else None, "markets_sample": sample, "n_markets_in_game": len(used)}
    os.makedirs("bt", exist_ok=True)
    json.dump(out, open("bt/oddspapi_sample.json", "w"), indent=1)


if __name__ == "__main__":
    main()
