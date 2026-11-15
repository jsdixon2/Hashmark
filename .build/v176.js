/* ===== v176 (owner: "add expandable player stats on the live game view"). Live game page gets a "Player stats" card from
   the ESPN summary's boxscore.players (already in the same response): team switch (S.lg176T), one row per player with a
   one-line summary and his fantasy points (from the box score totals, in the league where he's on your matchup, else
   the selected league's scoring), your / your opponent's / your bench players tagged and first; tap a row to expand the
   full lines (passing, rushing, receiving, fumbles, kicking). ===== */
const LG176_CATS=[["passing","Passing"],["rushing","Rushing"],["receiving","Receiving"],["fumbles","Fumbles"],["kicking","Kicking"]];
function lg176Num(v){const n=parseFloat(String(v).replace(/,/g,""));return isFinite(n)?n:0;}
function lg176Box(G,sum){const out={};for(const T of ((sum&&sum.boxscore&&sum.boxscore.players)||[])){const ab=lg175Ab(T.team&&T.team.abbreviation);if(!ab)continue;const P=new Map();
  for(const c of T.statistics||[]){const nm=c.name||"";if(!LG176_CATS.some(x=>x[0]===nm))continue;const labels=c.labels||[],keys=c.keys||[];
    for(const a of c.athletes||[]){const at=a.athlete||{},id=at.id||at.displayName;if(!id)continue;let e=P.get(id);if(!e){e={name:at.displayName||at.shortName||"",short:at.shortName||"",pos:(at.position&&at.position.abbreviation)||"",team:ab,cats:{},s:{}};P.set(id,e);}
      const st=a.stats||[];e.cats[nm]={labels,stats:st};const g=lab=>{const i=labels.indexOf(lab);return i>=0?st[i]:null;};
      if(nm==="passing"){const ca=String(g("C/ATT")||"0/0").split("/");e.s.cmp=lg176Num(ca[0]);e.s.att=lg176Num(ca[1]);e.s.py=lg176Num(g("YDS"));e.s.ptd=lg176Num(g("TD"));e.s.int=lg176Num(g("INT"));}
      else if(nm==="rushing"){e.s.car=lg176Num(g("CAR"));e.s.ry=lg176Num(g("YDS"));e.s.rtd=lg176Num(g("TD"));}
      else if(nm==="receiving"){e.s.rec=lg176Num(g("REC"));e.s.wy=lg176Num(g("YDS"));e.s.wtd=lg176Num(g("TD"));e.s.tgt=lg176Num(g("TGTS"));}
      else if(nm==="fumbles"){e.s.fl=lg176Num(g("LOST"));}
      else if(nm==="kicking"){const fg=String(g("FG")||"0/0").split("/"),xp=String(g("XP")||"0/0").split("/");e.s.fgm=lg176Num(fg[0]);e.s.xpm=lg176Num(xp[0]);e.s.kpts=lg176Num(g("PTS"));}}}
  out[ab]=[...P.values()];}
  return out;}
function lg176Pts(e,sc){sc=sc||{};const g=(k,d)=>sc[k]!=null?+sc[k]:d,s=e.s;let v=0;
  v+=(s.py||0)*g("pass_yd",.04)+(s.ptd||0)*g("pass_td",4)+(s.int||0)*g("pass_int",-1)+(s.cmp||0)*g("pass_cmp",0);
  v+=(s.ry||0)*g("rush_yd",.1)+(s.rtd||0)*g("rush_td",6)+(s.car||0)*g("rush_att",0);
  const bon=e.pos==="TE"?g("bonus_rec_te",0):e.pos==="RB"?g("bonus_rec_rb",0):e.pos==="WR"?g("bonus_rec_wr",0):0;
  v+=(s.rec||0)*(g("rec",1)+bon)+(s.wy||0)*g("rec_yd",.1)+(s.wtd||0)*g("rec_td",6)+(s.fl||0)*g("fum_lost",-2);
  if(s.kpts!=null&&!(s.py||s.ry||s.wy))v+=(s.xpm||0)*g("xpm",1)+(s.fgm||0)*3;
  return Math.round(v*10)/10;}
function lg176Line(e){const s=e.s,b=[];if(s.att)b.push(`${s.cmp}/${s.att}, ${s.py} yds${s.ptd?`, ${s.ptd} TD`:""}${s.int?`, ${s.int} INT`:""}`);
  if(s.car)b.push(`${s.car} car, ${s.ry} yds${s.rtd?`, ${s.rtd} TD`:""}`);if(s.rec!=null&&(s.rec||s.tgt))b.push(`${s.rec}${s.tgt?"/"+s.tgt:""} rec, ${s.wy} yds${s.wtd?`, ${s.wtd} TD`:""}`);
  if(s.kpts!=null&&!b.length)b.push(`${s.fgm} FG, ${s.xpm} XP`);if(s.fl)b.push(`${s.fl} fumble lost`);return b.join(" · ");}
function lg176Card(G,sum){const box=lg176Box(G,sum);if(!box[G.a]&&!box[G.h])return "";const R=lg175Roles();
  const cnt=t=>(box[t]||[]).filter(e=>{const p=lg175Find(e.short||(e.name[0]+"."+e.name.split(" ").slice(1).join(" ")),[t])||lg176Match(e);return p&&R.has(p.id);}).length;
  let T=S.lg176T&&S.lg176T.k===G.id?S.lg176T.t:(cnt(G.a)>cnt(G.h)?G.a:G.h);
  const rows=(box[T]||[]).map(e=>{const p=lg176Match(e);const arr=p?R.get(p.id):null;const x=arr?(arr.find(z=>z.role==="me")||arr.find(z=>z.role==="opp")||arr[0]):null;const sc=x?x.L.scoring:(S.L&&S.L.scoring);
    return {e,p,x,pts:lg176Pts(e,sc),role:x?x.role:null};}).filter(r=>lg176Line(r.e)).sort((a,b)=>((b.role==="me")-(a.role==="me"))||((b.role==="opp")-(a.role==="opp"))||((b.role==="bench")-(a.role==="bench"))||(b.pts-a.pts));
  const tbl=c=>{const C=r=>r.e.cats[c[0]];return ""};
  const row=r=>{const e=r.e,cls=r.role==="me"?"me":r.role==="opp"?"op":r.role==="bench"?"bn":"";const lab=r.role==="me"?"yours":r.role==="opp"?"opponent":r.role==="bench"?"your bench":"";
    const det=LG176_CATS.filter(([k])=>e.cats[k]).map(([k,n])=>{const c=e.cats[k];return `<div class="lg176cat"><span class="eyebrow">${n}</span><div class="lg176g">${c.labels.map((l,i)=>`<div><b class="num">${esc(String(c.stats[i]??"–"))}</b><span>${esc(l)}</span></div>`).join("")}</div></div>`;}).join("");
    return `<details class="lg176r${cls?" "+cls:""}"><summary><span class="lg176n"><b>${e.pos?`<span class="lg176pos">${esc(e.pos)}</span> `:""}${esc(e.name)}</b><span class="sub">${esc(lg176Line(e))}</span></span><span class="lg175fp ${cls||"mut"}">${f1(r.pts)}<small>${lab?lab+((S.leagues||[]).length>1&&r.x?" · "+esc(lgShort(r.x.L)):""):"pts"}</small></span></summary>
      <div class="lg176d">${det}${r.p?`<button class="btn ghost sm" data-go="player-${r.p.id}">Player card</button>`:""}</div></details>`;};
  return `<section class="pan mt lg176"><div class="row sp"><h2>Player stats</h2><div class="seg sm">${[G.a,G.h].map(t=>`<button data-lg176="${t}|${G.id}" class="${t===T?"on":""}">${esc(t)}</button>`).join("")}</div></div>
   ${rows.length?lst(rows.map(row),12,""):`<p class="sub">No stats yet.</p>`}<p class="sub mt">Tap a player for his full line. Points use his league's scoring when he's in one of your matchups.</p></section>`;}
function lg176Match(e){const teams=[e.team];const nm=lg175Norm(e.name);for(const p of Object.values(PL)){if(p&&p.team===e.team&&lg175Norm(p.name)===nm)return p;}
  const sh=e.short||(e.name?e.name[0]+". "+e.name.split(" ").slice(1).join(" "):"");return lg175Find(sh.replace(/^([A-Z])\.\s?/,"$1."),teams);}
document.addEventListener("click",e=>{const b=e.target.closest&&e.target.closest("[data-lg176]");if(!b)return;e.stopPropagation();const [t,k]=b.dataset.lg176.split("|");S.lg176T={t,k};render();},true);
vLiveGame=(function(prev){return function(key){let h=prev(key);try{const G=LG175.sb&&LG175.sb[key];const sum=G&&LG175.sum[G.id];if(!sum)return h;const c=lg176Card(G,sum);if(!c)return h;
  const i=h.indexOf('<section class="pan mt"><div class="row sp"><h2>Plays</h2>');return i>=0?h.slice(0,i)+c+h.slice(i):h+c;}catch(e){console.error(e);return h;}};})(vLiveGame);
document.head.insertAdjacentHTML("beforeend",`<style>
.lg176 .row.sp{align-items:center}.lg176r{border-top:1px solid var(--line)}.lg176r:first-of-type{border-top:0}
.lg176r summary{list-style:none;display:flex;justify-content:space-between;align-items:center;gap:10px;padding:10px 0;cursor:pointer}.lg176r summary::-webkit-details-marker{display:none}
.lg176n{display:flex;flex-direction:column;min-width:0}.lg176n b{font-weight:600}.lg176n .sub{font-size:12px}
.lg176pos{font:700 10px/1 inherit;background:var(--panel2);border-radius:6px;padding:3px 5px;color:var(--muted);vertical-align:1px}
.lg176r.me summary{background:linear-gradient(90deg,color-mix(in srgb,var(--acc) 10%,transparent),transparent)}
.lg176r[open] summary .lg175fp:after{content:""}.lg176d{padding:2px 0 12px}
.lg176cat{margin-top:8px}.lg176cat .eyebrow{display:block;margin-bottom:4px}.lg176g{display:grid;grid-template-columns:repeat(auto-fill,minmax(58px,1fr));gap:6px}
.lg176g div{background:var(--panel2);border-radius:10px;padding:6px 4px;text-align:center;display:flex;flex-direction:column}.lg176g b{font-size:14px}.lg176g span{font-size:10px;color:var(--muted);letter-spacing:.04em}
.lg176d .btn{margin-top:10px}
</style>`);
