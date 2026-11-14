/* ===== v172 (owner: Huddle "Week N awards" box overlapped the Last week box, and showed one league's awards on the
   all-leagues page). The awards card read awLS() = the league selected in the app. Now, with 2+ leagues, the Huddle card
   lists every league like "Last week": the award YOU won there (team awards first), else that league's top score.
   "All awards" opens a sheet with each league's full list and its own Share buttons (S._awLg points awLS at that league
   while sharing). One league keeps the old card. Cards on the Huddle get 14px between them. ===== */
awLS=(function(prev){return function(){const G=HX.data;if(S._awLg&&G){const z=G.LS.find(q=>q.id===S._awLg);if(z)return z;}return prev();};})(awLS);
function aw172All(){const G=HX.data;if(!G)return [];const out=[];
  for(const L of S.leagues){let x=G.LS.find(z=>z.id===L.id);if(!x&&L.demo)x=G.LS.slice().sort((a,b)=>b.season-a.season)[0];if(!x)continue;let A=null;try{A=awData(x);}catch(e){}if(A)out.push({L,x,A});}
  return out;}
function aw172With(id,fn){const sv=S._awLg;S._awLg=id;try{return fn();}finally{S._awLg=sv;}}
awCard=(function(prev){return function(){const all=aw172All();if(all.length<2)return prev();const w=Math.max(...all.map(z=>z.A.w));
  const row=(a,you)=>`<div class="awr${you?" mine":""}"><div><div class="awk">${esc(a.k)}${you?` <span class="aw172y">you</span>`:""}</div><div class="aww">${esc(a.who)}</div><div class="aws">${esc(a.sub||"")}</div></div><b class="num">${esc(a.val)}</b></div>`;
  const lines=all.map(({L,A})=>{const mine=A.team.concat(A.player).filter(a=>+a.rid===+A.myRid);const a=mine[0]||A.team[0];if(!a)return "";
    return `<div class="aw172l"><div class="pvlg">${esc(L.name)}${A.w!==w?` · week ${A.w}`:""}</div>${row(a,!!mine[0])}${mine.length>1?`<div class="aws aw172m">+${mine.length-1} more award${mine.length>2?"s":""} for you</div>`:""}</div>`;}).join("");
  const n=all.reduce((s,z)=>s+z.A.team.length+z.A.player.length,0);
  return `<section class="pan awcard"><div class="row sp"><h2>Week ${w} awards</h2><span class="tag">${all.length} leagues</span></div>${lines}
    <div class="row" style="gap:8px;margin-top:12px"><button class="btn sm" data-aw172all>All ${n} awards</button></div></section>`;};})(awCard);
document.addEventListener("click",e=>{const b=e.target.closest&&e.target.closest("[data-aw172all]");if(!b)return;e.preventDefault();e.stopPropagation();
  const all=aw172All();const body=all.map(({L})=>{const h=aw172With(L.id,()=>awCardFull());if(!h)return "";const t=document.createElement("div");t.innerHTML=h;const s=t.querySelector("section");if(!s)return "";
    s.querySelectorAll("[data-awshare]").forEach(x=>x.setAttribute("data-awlg",L.id));const hd=s.querySelector(".row.sp");if(hd)hd.outerHTML=`<h3 class="aw172h">${esc(L.name)}</h3>`;return `<div class="aw172s">${s.innerHTML}</div>`;}).join("");
  openSheet("Week awards",body);},true);
document.addEventListener("pointerdown",e=>{const b=e.target.closest&&e.target.closest("[data-awshare]");if(!b)return;S._awLg=b.dataset.awlg||null;clearTimeout(S._awT);S._awT=setTimeout(()=>{S._awLg=null;},8000);},true);
document.head.insertAdjacentHTML("beforeend",`<style>
#view .pvcard,#view .awcard,#view .wtop+.pan,#view .hdm+.pan{margin-top:14px}
.aw172l{padding:10px 0;border-top:1px solid var(--line)}.aw172l:first-of-type{border-top:0}.aw172l .awr{border:0;padding:4px 0 0}
.aw172y{display:inline-block;margin-left:6px;padding:1px 7px;border-radius:999px;font-size:10px;letter-spacing:.04em;background:color-mix(in srgb,var(--acc) 18%,transparent);color:var(--acc)}
.aw172m{margin-top:2px}
.aw172s+.aw172s{margin-top:18px;padding-top:14px;border-top:1px solid var(--line)}.aw172h{margin:0 0 6px;font-size:15px}
:root[data-theme="light"] .aw172y{color:#BF4706}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]) .aw172y{color:#BF4706}}
</style>`);
