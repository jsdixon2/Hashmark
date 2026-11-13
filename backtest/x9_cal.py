"""x9 band calibration: widen the 10-90% band around the median by factor k (on the log scale); held-out coverage."""
import math
exec(open("backtest/x9_paths.py").read().split("# real trades")[0].replace('print("\\nPLAYERS','0 and print("'))
for k in (1.0, 1.1, 1.15, 1.2, 1.3):
    row = []
    for h in (180, 365, 730, 1095):
        n = ins = 0
        for ck, hh, d0, d1, pid, v0, v1, f, i in test:
            if hh != h: continue
            q = look(M, ck, h)
            if not q: continue
            lr = math.log(v1 / v0); m = q[5]; n += 1; ins += m - k * (m - q[1]) <= lr <= m + k * (q[9] - m)
        row.append("%dd %.1f%%" % (h, 100 * ins / n))
    print("k", k, " ".join(row))
