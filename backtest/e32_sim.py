"""e32 simulation: numpy replay of the app's simTitle (index.html v57/v47): per draw each team's strength
s = str*(1+u*z), str shrunk toward the league mean by sh; every remaining game each side scores s + N(0,1)*(s*k + c);
seeds by wins then points for; bracket as bracketWin (byes to top seeds, top vs bottom, prt 2-week rounds).
Extras for the fit (all off = app): a = weight on season-to-date pts/game in the strength; med = simulate the median win."""
import numpy as np
WPK, WPC = .16, 5.0

def sim(r, u=.04, sh=.5, a=0.0, med=False, N=2000, seed=1, k=WPK, c=WPC, kmul=1.0):
    n = r["n"]; rng = np.random.default_rng(seed)
    st = r["st"].astype(float)
    if a:
        ppg = np.where(r["g"] > 0, r["pf"] / np.maximum(1, r["g"]), st)
        st = (1 - a) * st + a * ppg
    st = st * (1 - sh) + st.mean() * sh
    s = st[None, :] * (1 + u * rng.standard_normal((N, n)))
    sd = (s * k + c) * kmul
    W = np.tile(r["w"].astype(float), (N, 1)); PF = np.tile(r["pf"].astype(float), (N, 1))
    for wk in r["fut"]:
        sc = s + rng.standard_normal((N, n)) * sd
        for x, y in wk:
            PF[:, x] += sc[:, x]; PF[:, y] += sc[:, y]
            xw = sc[:, x] > sc[:, y]; W[:, x] += xw; W[:, y] += ~xw
        if med and r["med"]:
            m = np.median(sc, axis=1, keepdims=True); W += sc > m
    key = W * 1e5 + PF
    ord_ = np.argsort(-key, axis=1, kind="stable")
    P = min(n, r["pt"]); seeds = ord_[:, :P]
    po = np.zeros(n); np.add.at(po, seeds.ravel(), 1)
    # bracket
    size = 1
    while size < P: size *= 2
    R = int(np.log2(size)); byes = size - P
    rows = np.arange(N)
    def game(x, y, nw):
        sx = np.zeros(N); sy = np.zeros(N)
        for _ in range(nw):
            sx += s[rows, x] + rng.standard_normal(N) * sd[rows, x]; sy += s[rows, y] + rng.standard_normal(N) * sd[rows, y]
        return np.where(sx > sy, x, y)
    rd = [seeds[:, i] for i in range(byes, P)]; adv = [seeds[:, i] for i in range(byes)]; ri = 0; prt = r["prt"]
    while True:
        nw = 2 if prt == 2 else (2 if prt == 1 and ri == R - 1 else 1)
        nx = [game(rd[i], rd[len(rd) - 1 - i], nw) for i in range(len(rd) // 2)]; ri += 1
        pool = adv + nx; adv = []
        if len(pool) == 1: champ = pool[0]; break
        rd = pool
    ch = np.bincount(champ, minlength=n).astype(float)
    return po / N, ch / N
