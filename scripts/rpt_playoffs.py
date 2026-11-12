"""Report card: playoff and title odds (key playoff_odds). Backtest numbers from backtest/e32_fix.json (backtest/e32_*.py):
the app's season simulation replayed for 617 archived Sleeper leagues 2022-25 (bt/rosters.json.gz exact weekly rosters)
at the weeks after weeks 4, 8 and 11 and in the last regular-season week, with what the app knew then (record so far,
real remaining schedule, each team's best lineup by the app's rest-of-season pts/game). PO.u/PO.sh refit on 2022-23
kept the shipped .04/.5; v116 (this week's game, median wins, last regular week) graded on 2024-25, never fitted on.
This season's leagues are not finished, so only the held-out seasons are graded."""
import json, os

def _g(x):
    return {"brier": x["brier"], "log_loss": x["ll"], "n": x["n"]}

def section(ctx=None):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backtest", "e32_fix.json")
    try:
        R = json.load(open(p))
    except Exception:
        return {}
    T = R["test"]; old, new = T["shipped"], T["fixed"]
    by = {c: {"before": _g(old["po"][c]), "after": _g(new["po"][c])} for c in ("4", "8", "11")}
    cal = [{"said": r[2], "made": r[3], "n": r[1], "bin": r[0]} for r in new["cal_po"]["all"]]
    calc = [{"said": r[2], "won": r[3], "n": r[1], "bin": r[0]} for r in new["cal_ch"]["all"]]
    LW = R["last_week"]["test"]
    out = {
        "seasons_tested": "2024-25", "seasons_fit": "2022-23", "leagues_tested": None,
        "playoffs": {"before": _g(old["po"]["all"]), "after": _g(new["po"]["all"]), "by_week": by,
                     "standings_rank": _g(R["baselines_test"]["standings_rank"]["po"]["all"]),
                     "pf_rank": _g(R["baselines_test"]["pf_rank"]["po"]["all"]), "calibration": cal},
        "title": {"before": _g(old["ch"]["all"]), "after": _g(new["ch"]["all"]),
                  "standings_rank": _g(R["baselines_test"]["standings_rank"]["ch"]["all"]), "calibration": calc},
        "last_week": {"before": _g(LW["page_shipped_6random"]["po"]["all"]), "after": _g(LW["fixed"]["po"]["all"])},
        "median_leagues": {"n_leagues": R["median_test"]["n_leagues"], "before": _g(R["median_test"]["shipped"]["po"]["all"]),
                           "after": _g(R["median_test"]["fixed"]["po"]["all"])},
        "constants": {"u": R["refit"]["u"], "sh": R["refit"]["sh"]},
    }
    out["leagues_tested"] = (R.get("n_leagues") or {}).get("test")
    return {"playoff_odds": out}

if __name__ == "__main__":
    print(json.dumps(section({}), indent=1)[:3000])
