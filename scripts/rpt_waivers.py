"""Report card: waiver calls (key tested.waivers, replaces build_report.py's hard-coded e9 numbers).

From backtest/e31_exact.py + e31_an.py (written to backtest/e31.json): 516 real Sleeper leagues with exact weekly rosters,
2024-25 (the archive has no 2026 leagues yet), 62,616 team-weeks. Each week the app's waiver code path picks one add/drop
per team (wvRate/WVC, WV_DROPW .25, WV_FAH 1.5, bar 4 / 6 dynasty, and v115: WR adds whose best game is 45%+ of their
season points don't count as a move). Unit: real lineup points the move added over the next 3 weeks (weeks w+1..w+3),
lineups set before each week by Hashmark's current weekly projection and scored on actual points, against keeping the
roster. helped > +1 pt, hurt < -1, neutral in between. Managers' own single-add waiver claims measured the same way.
(The old 73% "helped" came from hindsight-best lineups, which never matched the +8.8 shown beside it.)
Standard library only; numbers are fixed backtest results, not recomputed in Actions."""

FMT = {
    "redraft": {"pts": 8.38, "helped": .625, "neutral": .149, "hurt": .226, "n": 9292,
                "managers_pts": 3.79, "managers_helped": .411, "managers_hurt": .209, "managers_n": 8316},
    "keeper": {"pts": 7.18, "helped": .586, "neutral": .182, "hurt": .232, "n": 2643,
               "managers_pts": 3.08, "managers_helped": .371, "managers_hurt": .189, "managers_n": 2222},
    "dynasty": {"pts": 6.08, "helped": .500, "neutral": .287, "hurt": .213, "n": 5057,
                "managers_pts": 1.16, "managers_helped": .203, "managers_hurt": .134, "managers_n": 10958},
}

def section(ctx=None):
    w = dict(FMT["redraft"])
    w.update(src="redraft 2024-25, 516 leagues", backtest="e31", weeks=3,
             unit="real lineup pts over the next 3 weeks, lineups set by Hashmark's projection",
             by_fmt=FMT)
    return {"tested": {"waivers": w}}

if __name__ == "__main__":
    import json; print(json.dumps(section(), indent=1))
