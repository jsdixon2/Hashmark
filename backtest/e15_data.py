"""B1 step 1: projection panels in PPR, half-PPR and standard (scripts/proj_panel.build(scoring=...)): Sleeper projection,
PPG, last-3 and actual points in that scoring; xFP scaled like the app (x ppg / PPR ppg). Output backtest/e15_panel.pkl."""
import os, sys
import pandas as pd
B = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(B); os.chdir(R); sys.path.insert(0, f"{R}/scripts")
import proj_panel
out = []
for f in ("ppr", "half", "std"):
    d = pd.DataFrame(proj_panel.build(scoring=f, feats=True)); d["fmt"] = f; out.append(d)
    print(f, len(d))
pd.concat(out, ignore_index=True).to_pickle(f"{B}/e15_panel.pkl")
