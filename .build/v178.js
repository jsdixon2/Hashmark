/* ===== v178 (owner: "projection bars on the league matchups" + "make them clickable so you can view rosters and
   scoring"): League › Matchups cards use the same numbers as the Matchup page (this week's projection, live points,
   live win chance via myMatchup) instead of rest-of-season strength, draw a bar per team (solid = points scored,
   faded = projected rest of the game), and open a read-only game view for any pair (route matchup-vs-<li>-<team>):
   both lineups with live/final cells, K/DST, edge by position, both benches. Your own game opens the full Matchup page.
   MX178 points myMatchup at another team (patched into the base definition, so every wrapper still applies). ===== */
var MX178=null;
function mx178(L,a){const o=MX178;MX178={L,a};try{return myMatchup(L);}catch(e){console.error(e);return null;}finally{MX178=o;}}
function mx178State(M){const lv=W=>W.live!=null&&W.live>0;const fin=M.left&&M.left[0]<.001&&M.left[1]<.001&&(lv(M.A)||lv(M.B));
  return fin?"final":(lv(M.A)||lv(M.B))?"live":"pre";}
function lm178Pairs(L){let P=(L.matchups&&L.matchups.length)?L.matchups.filter(([a,b])=>a&&b&&a.i>=0&&b.i>=0).map(([a,b])=>[a.i,b.i]):[[0,1],[2,3],[4,5]].filter(([a,b])=>L.teams[a]&&L.teams[b]);
  const me=mineIdx(L);P=P.map(p=>p[1]===me?[p[1],p[0]]:p);return P.sort((x,y)=>(y[0]===me)-(x[0]===me));}
function lm178Side(W,wp,mx,st,mine,fav){const pts=W.live!=null&&W.live>0?W.live:0,pr=Math.max(W.proj||0,pts),big=st==="pre"?W.proj:pts;
  const sw=Math.min(100,pts/mx*100),fw=Math.max(0,Math.min(100-sw,(pr-pts)/mx*100));
  const lab=st==="final"?`${wp>=.5?"Won":"Lost"}`:st==="live"?`proj ${f1(pr)} · ${pc(wp)} win`:`proj · ${pc(wp)} win`;
  return `<div class="lm178s${fav?" fav":""}"><div class="lm178h"><span class="lm178n"><b>${esc(W.t.name)}</b>${mine?' <span class="tag good">you</span>':""}</span><span class="lm178v num">${f1(big)}</span></div>
    <div class="lm178b" aria-hidden="true"><i style="width:${sw.toFixed(1)}%"></i><i class="r" style="width:${fw.toFixed(1)}%"></i></div>
    <div class="lm178l sub num"><span>${esc(W.t.owner||"")}</span><span>${lab}</span></div></div>`;}
function lm178Cards(L){const li=S.leagues.indexOf(L),me=mineIdx(L);const Ms=lm178Pairs(L).map(([a,b])=>({a,b,M:mx178(L,a)})).filter(x=>x.M);
  const mx=Math.max(1,...Ms.map(x=>Math.max(x.M.A.proj||0,x.M.B.proj||0,x.M.A.live||0,x.M.B.live||0)))*1.04;
  const anyLive=Ms.some(x=>mx178State(x.M)==="live");
  const cards=Ms.map(({a,M})=>{const st=mx178State(M),wp=M.wpA,mine=M.A.ti===me||M.B.ti===me;
    const left=M.left&&st==="live"?Math.round((M.left[0]+M.left[1])/2*100):null;
    const tag=st==="final"?'<span class="lm178t">Final</span>':st==="live"?`<span class="lm178t live"><i></i>Live${left!=null?` · ${left}% to play`:""}</span>`:`<span class="lm178t">Week ${S.week} projection</span>`;
    return `<button class="pan mt lm178${mine?" mine":""}" data-go="${M.A.ti===me?"matchup-"+li:`matchup-vs-${li}-${a}`}" aria-label="Open ${esc(M.A.t.name)} vs ${esc(M.B.t.name)}">
      <div class="lm178top">${tag}<span class="lm178go">Lineups ${CHEV}</span></div>
      ${lm178Side(M.A,wp,mx,st,M.A.ti===me,st==="final"?M.A.live>=M.B.live:wp>=.5)}${lm178Side(M.B,1-wp,mx,st,M.B.ti===me,st==="final"?M.B.live>M.A.live:wp<.5)}</button>`;}).join("");
  const note=L.matchups&&L.matchups.length?"":`<p class="sub">Demo pairings. Your real Sleeper matchups and live points appear here after linking.</p>`;
  return note+cards+`<p class="sub mt">Bars: solid = points scored, faded = projected for the time left${anyLive?"":""}. Tap a game for both lineups.</p>`+(L.matchups&&L.matchups.length?`<div class="row mt"><button class="btn ghost" data-refresh="1">Refresh live scores</button></div>`:"");}
function vLMx178(li,a){const L=S.leagues[li];if(!L)return `<div class="empty">That league isn’t loaded.</div>`;if(S.L!==L)selectLeague(L.id);
  const M=mx178(L,a);if(!M)return `<div class="empty">No Week ${S.week} game found for that team.</div>`;const {A,B,wpA}=M,st=mx178State(M);
  const head=(W,right,wp)=>`<div style="${right?"text-align:right":""}"><div class="sub">${esc(W.t.owner||"")}</div><h2>${esc(W.t.name)}</h2><div class="big mt">${f1(st==="pre"?W.proj:W.live)}</div><div class="sub">${st==="final"?"Final":st==="live"?"Live points":"Projected points"}</div><div class="sub num">${st==="live"?"Proj "+f1(W.proj)+" · ":""}${st==="final"?(wp>=.5?"Won":"Lost"):pc(wp)+" win chance"}</div></div>`;
  const cell=(r,right,W)=>r&&r.p?mxCell(r.p,right,W):`<span class="bad" style="${right?"text-align:right":""}">Empty</span>`;
  const n=Math.max(A.rows.length,B.rows.length);let kd="";try{kd=kdMatchRows(L,A,B);}catch(e){}
  const bench=W=>W.bench.slice().sort((x,y)=>wkProj(y)-wkProj(x)).map(p=>mxBench(p,W)).join("")||`<div class="empty">No bench players.</div>`;
  return `<section class="pan"><div class="mhd">${head(A,0,wpA)}${head(B,1,1-wpA)}</div>
    <div class="wp mt" role="img" aria-label="Win chance ${pc(wpA)}"><i style="width:${(wpA*100).toFixed(1)}%"></i><i style="width:${((1-wpA)*100).toFixed(1)}%"></i></div>
    <p class="sub">${st==="final"?"Every starter’s game is over.":`Win chance from each lineup’s Week ${S.week} projection${st==="live"?", counting points so far plus the projection for the time left":""}.`}</p></section>
  <section class="pan mt"><h2>Lineups</h2>${[...Array(n).keys()].map(k=>`<div class="slotrow">${cell(A.rows[k],0,A)}<span class="chip" style="justify-self:center">${slotLabel((A.rows[k]||B.rows[k]).slot)}</span>${cell(B.rows[k],1,B)}</div>`).join("")}${kd}</section>
  <section class="pan mt"><h2>Edge by position</h2><p class="sub">${esc(A.t.name)} minus ${esc(B.t.name)}, ${st==="pre"?`Week ${S.week} projection`:"live projection"}.</p>${posEdges(A,B)}</section>
  <section class="grid2 mt"><div class="pan"><h2>Bench</h2><p class="sub">${esc(A.t.name)}</p>${bench(A)}</div><div class="pan"><h2>Bench</h2><p class="sub">${esc(B.t.name)}</p>${bench(B)}</div></section>
  <div class="row mt" style="flex-wrap:wrap"><button class="btn ghost" data-go="team-${A.ti}">${esc(A.t.name)} roster</button><button class="btn ghost" data-go="team-${B.ti}">${esc(B.t.name)} roster</button>${S.mode==="live"?`<button class="btn ghost" data-refresh="1">Refresh live scores</button>`:""}</div>`;}
const MX178R=/^matchup-vs-(\d+)-(\d+)$/;
vMatchup=(function(prev){return function(li){const m=MX178R.exec(route());if(m)return vLMx178(+m[1],+m[2]);return prev(li);};})(vMatchup);
pageTitle=(function(prev){return function(r){const m=MX178R.exec(r||"");if(m){const L=S.leagues[+m[1]],M=L&&mx178(L,+m[2]);return {eb:["League"],h:`Week ${S.week} matchup`};}return prev(r);};})(pageTitle);
tabOf=(function(prev){return function(r){return MX178R.test(r||"")?"league":prev(r);};})(tabOf);
document.head.insertAdjacentHTML("beforeend",`<style>
.lm178{display:block;width:100%;text-align:left;font:inherit;color:inherit;border:1px solid var(--line);cursor:pointer}
.lm178.mine{border-color:color-mix(in srgb,var(--acc) 45%,var(--line))}
.lm178top{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;font-size:12px;color:var(--muted)}
.lm178go{display:inline-flex;align-items:center;gap:2px}.lm178go svg{width:14px;height:14px}
.lm178t{font-weight:600;letter-spacing:.02em}.lm178t.live{color:var(--bad);display:inline-flex;align-items:center;gap:6px}
.lm178t.live i{width:7px;height:7px;border-radius:50%;background:var(--bad);animation:lm178p 1.4s infinite}
@keyframes lm178p{50%{opacity:.35}}
.lm178s+.lm178s{margin-top:12px}
.lm178h{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.lm178n{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lm178v{font-size:22px;font-weight:700;letter-spacing:-.01em}
.lm178s.fav .lm178v{color:var(--acc)}
.lm178b{display:flex;height:8px;border-radius:4px;background:var(--panel2);overflow:hidden;margin:6px 0 4px}
.lm178b i{display:block;height:100%;background:color-mix(in srgb,var(--ink) 55%,transparent)}
.lm178b i.r{background:color-mix(in srgb,var(--ink) 18%,transparent)}
.lm178s.fav .lm178b i{background:var(--acc)}.lm178s.fav .lm178b i.r{background:color-mix(in srgb,var(--acc) 30%,transparent)}
.lm178l{display:flex;justify-content:space-between;gap:10px;font-size:12px}
.lm178l span:first-child{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
:root[data-theme="light"] .lm178s.fav .lm178v{color:#BF4706}
@media (prefers-color-scheme:light){:root:not([data-theme="dark"]) .lm178s.fav .lm178v{color:#BF4706}}
</style>`);
