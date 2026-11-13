"""Test 2 (owner: "we need to beat betting lines"): start from the closing line and test small adjustments the market might
underprice. nflverse games (backtest/dl/games.csv), regular season, closing spread + moneylines.
Baseline: de-vigged closing moneyline (spread-based logistic where no moneyline), recalibrated on the train years.
Adjustments (each a feature in a logistic regression on top of logit(line probability)):
  backup QB (team's starter this game is not the QB who started 60%+ of its earlier games this season, 3+ games),
  rest (short week <= 5 days, off a bye >= 13 days, rest difference), wind >= 15 mph outdoors x line strength,
  west-coast team at an Eastern 1 pm kickoff, division game x line strength, home field (intercept).
Fit 2006-2022, test 2023-2025 (held out). Score: Brier and log loss vs the line alone; bootstrap 95% CI of the gain."""
import csv, math, random, collections, statistics as st
import numpy as np
from sklearn.linear_model import LogisticRegression
random.seed(1)
R = [r for r in csv.DictReader(open("backtest/dl/games.csv")) if r["game_type"] == "REG" and r["result"] not in ("", "NA") and r["spread_line"] not in ("", "NA")]
TZ = {"SEA": -3, "SF": -3, "LA": -3, "LAR": -3, "LAC": -3, "SD": -3, "OAK": -3, "LV": -3, "ARI": -2, "DEN": -2,
      "KC": -1, "DAL": -1, "HOU": -1, "MIN": -1, "CHI": -1, "GB": -1, "NO": -1, "TEN": -1, "STL": -1}
def tz(t): return TZ.get(t, 0)
def ml_prob(h, a):
    try: h, a = float(h), float(a)
    except ValueError: return None
    f = lambda m: 100 / (m + 100) if m > 0 else -m / (-m + 100)
    ph, pa = f(h), f(a); return ph / (ph + pa)
# regular starter per team-season from earlier games
R.sort(key=lambda r: (int(r["season"]), int(r["week"])))
seen = collections.defaultdict(list); rows = []
for r in R:
    y = int(r["season"]); res = float(r["result"])
    if res == 0: continue
    feats = {}
    for side in ("home", "away"):
        t = r[side + "_team"]; prev = seen[(y, t)]; qb = r[side + "_qb_id"]
        bk = 0
        if len(prev) >= 3 and qb:
            c = collections.Counter(prev).most_common(1)[0]
            if c[1] / len(prev) >= .6 and c[0] != qb: bk = 1
        feats[side + "_bk"] = bk
    for side in ("home", "away"):
        if r[side + "_qb_id"]: seen[(y, r[side + "_team"])].append(r[side + "_qb_id"])
    sp = float(r["spread_line"]); p_ml = ml_prob(r["home_moneyline"], r["away_moneyline"])
    hr, ar = (int(float(r["home_rest"] or 7)), int(float(r["away_rest"] or 7)))
    wind = float(r["wind"]) if r["wind"] not in ("", "NA") else 0
    outd = r["roof"] in ("outdoors", "open")
    rows.append(dict(y=y, win=1 if res > 0 else 0, sp=sp, pml=p_ml, f=dict(
        bk=feats["home_bk"] - feats["away_bk"], short=(hr <= 5) - (ar <= 5), bye=(hr >= 13) - (ar >= 13), restd=max(-7, min(7, hr - ar)) / 7,
        wind=(1 if outd and wind >= 15 else 0), westEarly=(1 if tz(r["away_team"]) == -3 and tz(r["home_team"]) == 0 and (r["gametime"] or "").startswith("13") else 0) - (1 if tz(r["home_team"]) == -3 and tz(r["away_team"]) == 0 and (r["gametime"] or "").startswith("13") else 0),
        div=int(r["div_game"] or 0))))
# line probability: moneyline where present, else logistic on spread fitted on games with both
both = [x for x in rows if x["pml"]]; A = np.array([[x["sp"]] for x in both]); yv = np.array([math.log(x["pml"] / (1 - x["pml"])) for x in both])
k = float(np.linalg.lstsq(np.c_[A, np.ones(len(A))], yv, rcond=None)[0][0])
for x in rows:
    p = x["pml"] if x["pml"] else 1 / (1 + math.exp(-k * x["sp"])); p = min(.98, max(.02, p)); x["L"] = math.log(p / (1 - p))
FN = ["bk", "short", "bye", "restd", "westEarly"]
def X(x, use):
    v = [x["L"]]
    if use:
        v += [x["f"][n] for n in FN] + [x["f"]["wind"] * x["L"], x["f"]["div"] * x["L"]]
    return v
tr = [x for x in rows if 2006 <= x["y"] <= 2022]; te = [x for x in rows if 2023 <= x["y"] <= 2025]
def fit(use):
    m = LogisticRegression(C=1.0, max_iter=2000).fit(np.array([X(x, use) for x in tr]), np.array([x["win"] for x in tr])); return m
m0, m1 = fit(False), fit(True)
def pr(m, xs, use): return m.predict_proba(np.array([X(x, use) for x in xs]))[:, 1]
y = np.array([x["win"] for x in te]); raw = np.array([1 / (1 + math.exp(-x["L"])) for x in te])
p0, p1 = pr(m0, te, False), pr(m1, te, True)
br = lambda p: float(np.mean((p - y) ** 2)); ll = lambda p: float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
acc = lambda p: float(np.mean((p > .5) == (y == 1)))
print("train games", len(tr), " test games 2023-25", len(te))
print("closing line as is     : Brier %.4f  logloss %.4f  right %.1f%%" % (br(raw), ll(raw), 100 * acc(raw)))
print("line, recalibrated     : Brier %.4f  logloss %.4f  right %.1f%%" % (br(p0), ll(p0), 100 * acc(p0)))
print("line + adjustments     : Brier %.4f  logloss %.4f  right %.1f%%" % (br(p1), ll(p1), 100 * acc(p1)))
d = (p0 - y) ** 2 - (p1 - y) ** 2; bs = []
for _ in range(2000):
    ix = np.random.randint(0, len(y), len(y)); bs.append(d[ix].mean())
bs.sort(); print("Brier gain (line - adjusted): %+.4f, 95%% CI %+.4f .. %+.4f" % (d.mean(), bs[50], bs[1949]))
names = ["line logit"] + FN + ["wind x line", "division x line"]
print("coefficients:", ", ".join("%s %+.3f" % (n, c) for n, c in zip(names, m1.coef_[0])), " intercept %+.3f" % m1.intercept_[0])
print("feature counts in test:", {n: int(sum(1 for x in te if x["f"][n])) for n in FN + ["wind", "div"]})
# one at a time, held out
for n in FN + ["wind", "div"]:
    def X1(x): v = [x["L"]]; v.append(x["f"][n] * (x["L"] if n in ("wind", "div") else 1)); return v
    mm = LogisticRegression(C=1.0, max_iter=2000).fit(np.array([X1(x) for x in tr]), np.array([x["win"] for x in tr]))
    pp = mm.predict_proba(np.array([X1(x) for x in te]))[:, 1]
    print("  only %-9s Brier %.4f (%+.4f vs recalibrated line)  coef %+.3f" % (n, br(pp), br(p0) - br(pp), mm.coef_[0][1]))
