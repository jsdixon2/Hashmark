"""Data test 1 (MySportsFeeds inactives): how many real matchups would knowing game-day inactives have flipped?
Same population as x8_news.py (bt/rosters.json.gz, real leagues 2022-25, regular season): a QB/RB/WR/TE starter who did
not play though his team did. Swap in the best eligible bench player who played; count losses that become wins
(the swap gain > losing margin, after any other swap in that matchup). Split by the final injury-report status:
Out/Doubtful (known Friday; the app knows if its 24 h player cache is fresh), Questionable and no listing (decided
~90 min before kickoff = what an inactives feed adds)."""
import gzip, json, csv, collections
exec(open("backtest/x8_news.py").read().split("FLEXP =")[0])
FLEXP = {"RB", "WR", "TE"}
flip = collections.Counter(); games = collections.Counter(); seasons = 0; lost_with = collections.Counter()
for l in R.values():
    y = l["season"]; key = "pts_ppr" if l["sc"].get("rec", 0) >= .75 else "pts_half_ppr" if l["sc"].get("rec", 0) >= .25 else "pts_std"
    seasons += len({t[0] for ws in l["weeks"].values() for t in ws})
    for wk, ms in l["weeks"].items():
        w = int(wk)
        if w >= l.get("pws", 15): continue
        S = ST.get(f"{y}-{w}", {}); bym = collections.defaultdict(list)
        for t in ms: bym[t[1]].append(t)
        for t in ms:
            opp = [o for o in bym[t[1]] if o is not t]
            if len(opp) != 1 or t[1] is None: continue
            gain = collections.Counter(); used = set()
            bench = [x for x in t[4] if x not in t[3] and pos.get(x) in ("QB", "RB", "WR", "TE") and S.get(x, {}).get("gp")]
            for x in t[3]:
                p = pos.get(x)
                if p not in ("QB", "RB", "WR", "TE") or S.get(x, {}).get("gp"): continue
                team = tm.get((y, x))
                if not team or (y, w, team) not in teamplayed: continue
                stt = inj.get((y, w, x), ""); k = "Out/Doubtful" if stt in ("Out", "Doubtful") else "late (Q or no listing)"
                el = sorted([b for b in bench if b not in used and (pos[b] == p or (p in FLEXP and pos[b] in FLEXP))], key=lambda b: -(S[b].get(key) or 0))
                if el: used.add(el[0]); gain[k] += (S[el[0]].get(key) or 0) - (S.get(x, {}).get(key) or 0)
            if not gain: continue
            m = t[2] - opp[0][2]
            for k in gain: games[k] += 1
            if m < 0:
                for k in gain: lost_with[k] += 1
                if gain["Out/Doubtful"] > -m: flip["Out/Doubtful only"] += 1
                if gain["Out/Doubtful"] <= -m < gain["Out/Doubtful"] + gain["late (Q or no listing)"]: flip["needs the late news"] += 1
print("team-seasons", seasons)
for k in ("Out/Doubtful", "late (Q or no listing)"): print("%-24s matchups with an inactive starter %6d, lost %6d" % (k, games[k], lost_with[k]))
for k, v in flip.items(): print("losses that become wins - %-20s %5d  (%.3f per team-season, 1 every %.0f team-seasons)" % (k, v, v / seasons, seasons / max(1, v)))
