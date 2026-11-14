/* ===== v171 (owner: "do the same thing for any other boring pages"). Audit of hub and list pages in the demo:
   - Trade Lab hub was six link tiles: now leads with "Best deals right now" (top 3 Trade finder ideas, one per team,
     graded by the calculator, with lineup and value change + Build trade). The Pre-breakout tile said "None right now"
     while its page listed targets (tile read sig().pre only; the page uses targetsAll): tile now uses targetsAll.
     Trade partners tile names the best team with a built deal instead of "no clear fit".
   - Trade partners page: every card ended in an empty "Open in calculator"; each now shows the best built deal with that
     team (finder, else none) with grade + Build trade, and teams with deals sort first.
   - Scout hub: three tiles; adds "Prospects to watch" (top 5 undrafted by starter odds, dvOdds) and redraws when the
     college file arrives (loadCfb only redrew Devy/War Room/player pages, so the tile said "loading" until revisited).
   - League rules: sections with nothing under the heading are hidden. ===== */
const a171=(a,f,t)=>a.k==="k"?{k:"k",id:a.id,y:a.y,r:a.r,orig:a.orig,from:f,to:t}:{k:"p",id:a.id,from:f,to:t};
const n171=a=>a.k==="k"?`${a.y} ${a.r===1?"1st":a.r===2?"2nd":a.r===3?"3rd":a.r+"th"}`:esc(a.p?a.p.name:(PL[a.id]||{}).name||"");
function g171Eval(L,x){const mi=mineIdx(L),sv=S.calc;try{S.calc={lid:L.id,sides:[mi,x.c.ti],assets:x.send.map(a=>a171(a,mi,x.c.ti)).concat(x.get.map(a=>a171(a,x.c.ti,mi)))};
  const R=calcEval();return R?R.find(r=>r.ti===mi):null;}catch(e){return null;}finally{S.calc=sv;}}
function d171Deal(L,x,showTeam){const mi=mineIdx(L),r=g171Eval(L,x),nm=n171,enc=(a,f,to)=>[a.k==="k"?"k:"+a.id:a.id,f,to];
  const bits=[];if(showTeam)bits.push(esc(x.c.t.name));if(r){if(Math.abs(r.lu)>=.1)bits.push(`lineup ${r.lu>0?"+":""}${f1(r.lu)} pts/wk`);bits.push(Math.abs(r.pct)<.02?"about even value":`value ${r.pct>0?"+":""}${Math.round(r.pct*100)}% to you`);}
  return `<div class="d171"><div class="m169g">${r?`<b class="m169gr">${r.g}</b>`:""}<div style="min-width:0"><div class="m169d">Send ${x.send.map(nm).join(" + ")} · get ${x.get.map(nm).join(" + ")}</div><div class="sub">${bits.join(" · ")}</div></div></div>
    <div class="m169b"><button class="btn sm" data-build='${esc(JSON.stringify({a:x.send.map(a=>enc(a,mi,x.c.ti)),b:x.get.map(a=>enc(a,x.c.ti,mi))}))}' data-bt="${x.c.ti}">Build trade</button></div></div>`;}
function d171Best(){let f=[];try{f=finder()||[];}catch(e){}const by=new Map();for(const x of f){if(!x||!x.c||!x.send||!x.get)continue;if(!by.has(x.c.ti))by.set(x.c.ti,x);}return {all:f,by};}
const T171=(go,b,s)=>h=>h.replace(new RegExp(`(<button class="tile" data-go="${go}"[^>]*>(?:(?!<\\/button>)[\\s\\S])*?)<div class="tb[^"]*">(?:(?!<\\/div>)[\\s\\S])*<\\/div><div class="tsb">(?:(?!<\\/div>)[\\s\\S])*<\\/div>`),`$1<div class="tb ell">${b}</div><div class="tsb">${s}</div>`);
vTrade=(function(prev){return function(){let h=prev();try{const L=S.L;if(!L||route()!=="trade")return h;
  const G=sig();if(!G.pre.length){let T=[];try{T=targetsAll(L);}catch(e){}if(T.length)h=T171("trade-pre",esc(T[0].p.name),`${T.length} target${T.length>1?"s":""} on other rosters`)(h);}
  const {by}=d171Best();let ps=[];try{ps=partners();}catch(e){}const bp=ps.find(x=>by.has(x.c.ti))||null;
  if(bp&&!(bp.s>0))h=T171("trade-partners",esc(bp.c.t.name),`${by.size} team${by.size>1?"s":""} with a deal that works`)(h);
  const top=[...by.values()].slice(0,3);
  if(top.length)h=`<section class="pan d171s"><div class="row sp"><h2>Best deals right now</h2><button class="btn ghost sm" data-go="trade-finder">All ideas</button></div>${top.map(x=>d171Deal(L,x,true)).join("")}</section>`+h.replace('<div class="tiles">','<div class="tiles mt">');}catch(e){console.error(e);}return h;};})(vTrade);
vPartners=(function(prev){return function(){let h=prev();try{const L=S.L;if(!L)return h;const {by}=d171Best();
  h=h.replace(/<div class="row" style="gap:8px"><button class="btn ghost sm" data-build='[^']*' data-bt="(\d+)">Open in calculator<\/button>(<button class="btn ghost sm" data-go="team-\d+">Their roster<\/button>)<\/div>/g,(m,ti,ros)=>{const x=by.get(+ti);
    return x?`<div class="d171w"><span class="eyebrow">Best deal with them</span>${d171Deal(L,x,false).replace('</button></div></div>',`</button>${ros}</div></div>`)}</div>`:`<div class="row" style="gap:8px"><span class="sub" style="flex:1">No deal that helps both teams right now.</span>${ros}</div>`;});
  const box=document.createElement("div");box.innerHTML=h;const list=box.querySelector(".lmore");if(list){const cards=[...list.children].filter(c=>c.classList.contains("scard"));
    if(cards.length){cards.sort((a,b)=>(b.querySelector(".d171")?1:0)-(a.querySelector(".d171")?1:0));cards.forEach((c,i)=>{c.removeAttribute("data-hid");if(i>=5)c.setAttribute("data-hid","");list.insertBefore(c,list.querySelector(".seemore")||null);});}
    h=box.innerHTML;}}catch(e){console.error(e);}return h;};})(vPartners);
vScoutLand=(function(prev){return function(){let h=prev();try{if(!CFB)return h+(CFBst==="loading"||CFBst==="idle"?`<section class="pan mt"><h2>Prospects to watch</h2><p class="sub">Loading college prospects…</p></section>`:"");
  let ps=Object.values(CFB.p).filter(p=>!p.drafted&&p.trend>=.35&&p.score>=60).sort((a,b)=>b.trend-a.trend).slice(0,5).map(p=>({p,o:dvOdds(p)})),ttl="Rising this season";
  if(!ps.length){ps=Object.values(CFB.p).filter(p=>!p.drafted&&p.score!=null).sort((a,b)=>b.score-a.score).slice(0,5).map(p=>({p,o:dvOdds(p)}));ttl="Prospects to watch";}if(!ps.length)return h;
  return h+`<section class="pan mt"><div class="row sp"><h2>${ttl}</h2><button class="btn ghost sm" data-go="devy">Devy Lab</button></div>${ps.map(({p,o})=>`<button class="tsr" data-go="cfb-${p.id}">${pos(p.pos)}<span class="tsn"><b class="ell">${esc(p.n)}</b><span class="sub ell">${esc(p.school||"")}${o!=null?` · starter odds ${dvOddsTxt(o,1)}`:""}</span></span><span class="tsb"><b class="num">${Math.round(p.score)}</b><span class="sub">devy score</span></span></button>`).join("")}</section>`;}catch(e){console.error(e);return h;}};})(vScoutLand);
loadCfb=(function(prev){return async function(){const r=await prev.apply(this,arguments);try{if(route()==="scout"&&CFB)render();}catch(e){}return r;};})(loadCfb);
render=(function(prev){return function(){const r=prev.apply(this,arguments);try{if(route()==="rules"){const v=$("#view");v&&v.querySelectorAll("section.pan").forEach(s=>{const h=s.querySelector("h2");if(h&&s.textContent.trim()===h.textContent.trim())s.remove();});}}catch(e){}return r;};})(render);
document.head.insertAdjacentHTML("beforeend",`<style>
.d171{padding:12px 0;border-top:1px solid var(--line)}.d171s .row.sp+.d171{border-top:0;padding-top:6px}
.d171w{margin-top:10px;padding-top:10px;border-top:1px solid var(--line)}.d171w .d171{border-top:0;padding:6px 0 0}
.tsb .sub{display:block;font-size:11px;text-align:right}
</style>`);
