"""Opening and closing NFL lines for test 1 (backtest/x14_open.py): for every regular-season game 2019-2025 in nflverse's
schedule (bt/nfl/schedules.csv.gz has the ESPN event id), read ESPN's public odds endpoint and keep each provider's
open / close / current spread, total and moneylines. Writes bt/nfl/lines_espn.jsonl.gz (one JSON object per game, numbers
only). Run by .github/workflows/open-lines.yml (manual). ESPN's public API, no key; ~0.15 s between calls."""
import csv, gzip, json, os, time, urllib.request
OUT = "bt/nfl/lines_espn.jsonl.gz"; U = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/{e}/competitions/{e}/odds"
def get(u):
    for k in range(3):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "hashmark-build"}), timeout=20).read())
        except Exception: time.sleep(1 + k)
    return None
def pick(x, *ks):
    for k in ks:
        if not isinstance(x, dict): return None
        x = x.get(k)
    return x
def side(o):
    if not isinstance(o, dict): return None
    out = {}
    for when in ("open", "close", "current"):
        w = o.get(when) or {}
        out[when] = {"sp": pick(w, "pointSpread", "american") or pick(w, "pointSpread", "alternateDisplayValue"),
                     "ml": pick(w, "moneyLine", "american") or pick(w, "moneyLine", "alternateDisplayValue")}
    out["ml_now"] = o.get("moneyLine"); return out
done = set(); rows = []
if os.path.exists(OUT):
    for l in gzip.open(OUT, "rt"):
        r = json.loads(l); done.add(r["gid"]); rows.append(r)
games = [g for g in csv.DictReader(gzip.open("bt/nfl/schedules.csv.gz", "rt")) if g["game_type"] == "REG" and 2019 <= int(g["season"]) <= 2025 and g["espn"] not in ("", "NA")]
if len(games) < 500:   # schedules archive may be short: fall back to the full nflverse games file
    games = [g for g in csv.DictReader(urllib.request.urlopen("https://github.com/nflverse/nfldata/raw/master/data/games.csv").read().decode().splitlines()) if g["game_type"] == "REG" and 2019 <= int(g["season"]) <= 2025 and g["espn"] not in ("", "NA")]
print("games", len(games), "already", len(done))
for i, g in enumerate(games):
    if g["game_id"] in done: continue
    e = str(int(float(g["espn"]))); d = get(U.format(e=e)); items = (d or {}).get("items") or []
    prov = []
    for it in items:
        prov.append({"p": pick(it, "provider", "name"), "spread": it.get("spread"), "ou": it.get("overUnder"),
                     "open_ou": pick(it, "open", "total", "american") or pick(it, "open", "total", "alternateDisplayValue"),
                     "close_ou": pick(it, "close", "total", "american") or pick(it, "close", "total", "alternateDisplayValue"),
                     "home": side(it.get("homeTeamOdds")), "away": side(it.get("awayTeamOdds"))})
    def clean(x):
        if isinstance(x, dict): return {k: clean(v) for k, v in x.items() if not k.startswith("$") and k not in ("links", "provider") or k == "provider"}
        if isinstance(x, list): return [clean(v) for v in x]
        return x
    rows.append({"gid": g["game_id"], "espn": e, "prov": prov, "raw0": clean(items[0]) if items else None}); time.sleep(.15)
    if i % 200 == 0: print(i, g["game_id"], len(prov))
with gzip.open(OUT, "wt") as f:
    for r in rows: f.write(json.dumps(r, separators=(",", ":")) + "\n")
print("wrote", len(rows), "games;", sum(1 for r in rows if r["prov"]), "with odds")
