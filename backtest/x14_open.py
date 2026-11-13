"""Test 1 (owner: "we need to beat betting lines"): can Hashmark beat the OPENING line? ESPN open/close lines
(bt/nfl/lines_espn.jsonl.gz from scripts/fetch_open_lines.py) for 2019-25 regular-season games + Hashmark's team rating
(Engine 6 shipped constants, rebuilt game by game from backtest/dl/games.csv, using only earlier games).
1) Outcomes: Brier of the opening line vs a blend of opening line + rating (blend weight fit 2023, tested 2024-25; ESPN opening lines exist from 2023 only; closing = nflverse spread_line),
   with the closing line as the ceiling.
2) Line movement: does (rating - opening line) predict which way the line moves by kickoff?
3) Against the opening spread: when the rating disagrees with the opener by 2+/3+/4+ points, how often does the
   rating's side cover the OPENING spread (52.4% breaks even at -110)?"""
import gzip, json, math, csv, collections, statistics as st, sys
import numpy as np
def num(x):
    try: return float(str(x).replace("+", "")) if x not in (None, "", "EVEN", "even") else (0.0 if str(x).lower() == "even" else None)
    except ValueError: return None
def ml2p(h, a):
    if h is None or a is None: return None
    f = lambda m: 100 / (m + 100) if m > 0 else -m / (-m + 100)
    ph, pa = f(h), f(a); return ph / (ph + pa)
CLOSE = {g["game_id"]: float(g["spread_line"]) for g in csv.DictReader(open("backtest/dl/games.csv")) if g["spread_line"] not in ("", "NA")}
PRI = ["ESPN BET", "Caesars Sportsbook (New Jersey)", "DraftKings", "Draft Kings", "MGM", "SugarHouse", "Unibet", "PointsBet", "Titanbets", "consensus"]
L = {}
for l in gzip.open("bt/nfl/lines_espn.jsonl.gz", "rt"):
    r = json.loads(l)
    if r["gid"] not in CLOSE: continue
    cands = [p for p in r["prov"] if "Live" not in (p.get("p") or "") and num(((p.get("home") or {}).get("open") or {}).get("sp")) is not None]
    cands.sort(key=lambda p: PRI.index(p["p"]) if p["p"] in PRI else 99)
    if not cands: continue
    p = cands[0]; osp = num(p["home"]["open"]["sp"])
    L[r["gid"]] = dict(osp=osp, csp=-CLOSE[r["gid"]], prov=p["p"])   # ESPN home spread: -3 = home favoured; nflverse spread_line +3 = home favoured
print("games with open+close home spread:", len(L))
# Hashmark rating (Engine 6 shipped: K .08, home 2.0, prior x.7, cap 28, sigma 12.5)
G = [g for g in csv.DictReader(open("backtest/dl/games.csv")) if g["home_score"] not in ("", "NA") and g["away_score"] not in ("", "NA")]
G.sort(key=lambda g: (int(g["season"]), int(g["week"]), g["gameday"]))
K, HFA, REG, CAP, SIG = .08, 2.0, .7, 28, 12.5
phi = lambda x: .5 * (1 + math.erf(x / math.sqrt(2)))
r = {}; season = None; rows = []
for g in G:
    s = int(g["season"])
    if s != season: r = {t: REG * v for t, v in r.items()}; season = s
    h, a = r.get(g["home_team"], 0.0), r.get(g["away_team"], 0.0); hfa = 0.0 if g["location"] == "Neutral" else HFA
    pred = h - a + hfa; m = float(g["home_score"]) - float(g["away_score"])
    if g["game_type"] == "REG" and g["game_id"] in L and m != 0:
        x = L[g["game_id"]]; rows.append(dict(s=s, gid=g["game_id"], pred=pred, osp=-x["osp"], csp=-x["csp"], m=m, y=1.0 if m > 0 else 0.0))   # spreads as expected home margin
    err = max(-CAP, min(CAP, m)) - pred; r[g["home_team"]] = h + K * err; r[g["away_team"]] = a - K * err
print("rated games with lines:", len(rows), collections.Counter(x["s"] for x in rows))
if not rows: sys.exit()
tr = [x for x in rows if x["s"] <= 2023]; te = [x for x in rows if x["s"] >= 2024]
brier = lambda xs, f: st.mean((phi(f(x) / SIG) - x["y"]) ** 2 for x in xs)
best_w = min((brier(tr, lambda x, w=w: (1 - w) * x["osp"] + w * x["pred"]), w) for w in [i / 20 for i in range(21)])[1]
print("\n1) OUTCOMES (Brier, lower is better)  fit 2023 -> blend weight on the rating %.2f" % best_w)
for name, xs in (("2023 (fit)", tr), ("2024-25 held out", te)):
    print("  %-17s opening line %.4f | Hashmark rating %.4f | blend %.4f | closing line %.4f  (n %d)" % (name, brier(xs, lambda x: x["osp"]), brier(xs, lambda x: x["pred"]), brier(xs, lambda x: (1 - best_w) * x["osp"] + best_w * x["pred"]), brier(xs, lambda x: x["csp"]), len(xs)))
print("\n2) LINE MOVEMENT: does the rating say where the line goes?")
for name, xs in (("2023", tr), ("2024-25", te)):
    d = [(x["pred"] - x["osp"], x["csp"] - x["osp"]) for x in xs]; a = [p for p, q in d]; b = [q for p, q in d]
    ma, mb = st.mean(a), st.mean(b); c = sum((p - ma) * (q - mb) for p, q in d) / math.sqrt(sum((p - ma) ** 2 for p in a) * sum((q - mb) ** 2 for q in b))
    mv = [(p, q) for p, q in d if abs(q) >= .5 and abs(p) >= 2]; agree = sum(1 for p, q in mv if p * q > 0)
    print("  %s corr(rating - open, close - open) %.3f; when the rating differs by 2+ pts and the line moved: moved toward the rating %d of %d (%.0f%%)" % (name, c, agree, len(mv), 100 * agree / max(1, len(mv))))
print("\n3) AGAINST THE OPENING SPREAD (rating's side covers?)  break-even 52.4%")
for name, xs in (("2023", tr), ("2024-25", te)):
    for th in (2, 3, 4, 5):
        pk = [x for x in xs if abs(x["pred"] - x["osp"]) >= th and x["m"] != x["osp"]]
        win = sum(1 for x in pk if (x["m"] > x["osp"]) == (x["pred"] > x["osp"]))
        print("  %s |rating - open| >= %d: %d of %d covered (%.1f%%)" % (name, th, win, len(pk), 100 * win / max(1, len(pk))))
    pk = [x for x in xs if abs(x["pred"] - x["osp"]) >= 3 and x["m"] != x["csp"]]; win = sum(1 for x in pk if (x["m"] > x["csp"]) == (x["pred"] > x["osp"]))
    print("  %s same picks vs the CLOSING spread: %d of %d (%.1f%%)" % (name, win, len(pk), 100 * win / max(1, len(pk))))
