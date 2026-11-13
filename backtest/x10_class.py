"""Do strong/weak draft classes matter, and can Hashmark see them coming? Classes 2016-2023 (e23 rows: every class
member, pre-draft college features, NFL pick, hit3 = top-24 RB/WR or top-12 QB/TE PPR season in first 3 NFL seasons).
Rookie-draft proxy: a class's top 12 / top 24 skill players by NFL draft pick (what 1QB rookie drafts mostly follow).
Class strength actual = hits among them. Predictions, leave-one-class-out (fit on the other 7 classes):
  pre  = Hashmark's pre-draft college model ("pre" in e23_fit) -> expected hits of the class's top 24 by that model
  cap  = after the NFL draft (adds draft position) -> expected hits of the top 12 / 24 by pick
Also: how much classes really differ (hits per class), and whether it's more than chance (binomial spread)."""
import json, math, os, sys, statistics as st
sys.argv = [sys.argv[0]]
import io, contextlib
ns = {"__name__": "e23"}
with contextlib.redirect_stdout(io.StringIO()): exec(open("backtest/e23_fit.py").read(), ns)
R = json.load(open(os.environ.get("E23_OUT", "/tmp/b11/e23_rows.json")))
D = sorted({r["D"] for r in R}); print("classes", D, "rows", len(R))
def corr(a, b):
    ma, mb = st.mean(a), st.mean(b); n = sum((x - ma) * (y - mb) for x, y in zip(a, b)); d = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)); return n / d if d else 0
out = []
for c in D:
    tr = [r for r in R if r["D"] != c]; te = [r for r in R if r["D"] == c]
    Mp = ns["fit"](tr, "pre"); pp = ns["pred"](Mp, te, "pre")
    dr = [r for r in tr if r.get("pick")]; Mc = ns["fit"](dr, "cap"); ted = [r for r in te if r.get("pick")]; pc = ns["pred"](Mc, ted, "cap") if ted else []
    for r, p in zip(te, pp): r["_pre"] = float(p)
    for r, p in zip(ted, pc): r["_cap"] = float(p)
    byp = sorted(ted, key=lambda r: r["pick"])
    row = {"D": c, "n": len(te), "hits_all": sum(r["o3"]["hit"] for r in te)}
    for k in (12, 24):
        top = byp[:k]; row[f"hits{k}"] = sum(r["o3"]["hit"] for r in top); row[f"cap{k}"] = sum(r["_cap"] for r in top)
        row[f"pre{k}"] = sum(sorted((r["_pre"] for r in te), reverse=True)[:k])
    out.append(row)
print("%-6s %5s %8s | %7s %7s %7s | %7s %7s %7s" % ("class", "n", "hits all", "hits12", "pre12", "cap12", "hits24", "pre24", "cap24"))
for o in out: print("%-6d %5d %8d | %7d %7.1f %7.1f | %7d %7.1f %7.1f" % (o["D"], o["n"], o["hits_all"], o["hits12"], o["pre12"], o["cap12"], o["hits24"], o["pre24"], o["cap24"]))
for k in (12, 24):
    h = [o[f"hits{k}"] for o in out]; m = st.mean(h); p = m / k
    print(f"top {k}: hits per class mean {m:.1f}, range {min(h)}-{max(h)}, sd {st.pstdev(h):.2f} vs {math.sqrt(k*p*(1-p)):.2f} expected from luck alone;",
          "corr with pre-draft model %.2f, with draft-capital model %.2f" % (corr(h, [o[f'pre{k}'] for o in out]), corr(h, [o[f'cap{k}'] for o in out])))
json.dump(out, open("backtest/x10_class.json", "w"), indent=1)
