#!/usr/bin/env python3
"""e23: pull high-school recruiting ratings for the 2011-2020 recruiting classes (the 2016-2023 draft classes) from
CollegeFootballData. Needs CFBD_API_KEY (repo secret) -> run in GitHub Actions only. 10 calls (one per class).

Writes $E23_REC (default /tmp/e23_recruit.json): {athleteId or "n:<name>|<school>": {"stars","rating","rank","cls"}}.
Numbers only plus public player ids; nothing is committed by this script.
Workflow step (after checkout, python 3.11):
  - run: python3 backtest/e23_cfbd_pull.py && bash backtest/e23_run.sh
    env: { CFBD_API_KEY: ${{ secrets.CFBD_API_KEY }} }
"""
import json, os, re, sys, time, urllib.request

KEY = os.environ.get("CFBD_API_KEY", "").strip()
OUT = os.environ.get("E23_REC", "/tmp/e23_recruit.json")
SK = {"QB", "RB", "WR", "TE", "ATH", "APB", "DUAL", "PRO"}


def norm(n):
    n = (n or "").lower().replace(".", "").replace("'", "").replace("’", "")
    n = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", n.strip())
    return re.sub(r"[^a-z ]", "", n).strip()


def main():
    if not KEY:
        sys.exit("CFBD_API_KEY not set (run this in GitHub Actions with the repo secret)")
    H = {"Authorization": "Bearer " + KEY, "Accept": "application/json", "User-Agent": "hashmark-build"}
    rec = {}
    for y in range(2011, 2021):
        url = f"https://api.collegefootballdata.com/recruiting/players?year={y}&classification=HighSchool"
        for k in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=120) as r:
                    xs = json.loads(r.read().decode())
                break
            except Exception as e:
                if k == 2:
                    sys.exit(f"failed {y}: {e}")
                time.sleep(5)
        n = 0
        for x in xs:
            if (x.get("position") or "") not in SK:
                continue
            v = {"stars": x.get("stars"), "rating": x.get("rating"), "rank": x.get("ranking"), "cls": y}
            if x.get("athleteId"):
                rec[str(x["athleteId"])] = v
            rec[f'n:{norm(x.get("name"))}|{(x.get("committedTo") or "").lower()}'] = v
            n += 1
        print(y, n, "skill-position recruits")
    json.dump(rec, open(OUT, "w"))
    print("wrote", OUT, len(rec))


if __name__ == "__main__":
    main()
