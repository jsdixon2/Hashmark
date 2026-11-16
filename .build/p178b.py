# p178b (v178 hooks): myMatchup can be pointed at any team (MX178), and League › Matchups renders v178 cards.
p = "index.html"; s = open(p).read()
a = '''function myMatchup(L){const me=Math.max(0,L.teams.findIndex(t=>t.mine));'''
b = '''function myMatchup(L){const me=typeof MX178!=="undefined"&&MX178&&MX178.L===L?MX178.a:Math.max(0,L.teams.findIndex(t=>t.mine));'''
assert s.count(a) == 1; s = s.replace(a, b)
a = '''    if(L.matchups&&L.matchups.length)body=L.matchups.filter(([a,b])=>a.i>=0&&b.i>=0).map(([a,b])=>card(a.i,b.i,a.pts,b.pts,"vs")).join("")+'''
b = '''    if(typeof lm178Cards==="function")body=lm178Cards(L);else if(L.matchups&&L.matchups.length)body=L.matchups.filter(([a,b])=>a.i>=0&&b.i>=0).map(([a,b])=>card(a.i,b.i,a.pts,b.pts,"vs")).join("")+'''
assert s.count(a) == 1; s = s.replace(a, b)
open(p, "w").write(s); print("p178b ok")
