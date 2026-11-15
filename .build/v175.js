/* ===== v175 (owner "go" on live mockups A + C, 2026-11-15). Live NFL game page + Live feed on the fantasy matchup.
   Data: ESPN public scoreboard (already used for the game clock; now also keeps event id + situation) and ESPN's public
   per-game summary (site.api.espn.com .../nfl/summary?event=ID: header, drives with plays, winprobability). No key,
   no sportsbook data. Fetched only while a game page or the matchup Live feed is open, at most every 25 s per game, and
   on the v130 30-second refresh (lv130Refresh wrapper).
   A · route gameday-<AWAY>-<HOME>: game chips, symmetric score bar (team pill, score, clock, score, team pill; record
       under each pill, possession ball beside the record), down & distance with down markers, broadcast-angle field
       (away end zone left, home right; blue line of scrimmage, yellow first-down or goal line, shaded to-go area, the
       current drive as a straight line with a dot per play, last-play label), red zone (red glow, shaded 20->goal,
       "& Goal", RED ZONE tag, "If X scores here" with points and your win chance before -> after), ESPN win
       probability chart, play feed with each play's fantasy points for players in your leagues (orange = your starter,
       grey = your bench, red = your opponent's starter), parsed from ESPN's play text and scored in that league's
       scoring (approximate: bonuses for distance/first downs only when the league uses them).
   C · Matchup page in live mode: "Lineups | Live feed" toggle; Live feed = every play from every game that moved this
       matchup (your starters / their starters), points and the change in your win chance.
   Gameday cards open the live page once the game has started (pregame keeps the edges sheet). ===== */
const LG175={sb:null,sbAt:0,sum:{},at:{},inflight:{}};
const LG175_SB="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard";
const LG175_SUM=id=>`https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=${id}`;
function lg175Ab(a){try{return gcAb(a);}catch(e){return a;}}
/* scoreboard: event list keyed "AWAY-HOME" */
function lg175Parse(j){const out={};for(const ev of (j&&j.events)||[]){const c=(ev.competitions||[])[0];if(!c)continue;const cs=c.competitors||[];
  const H=cs.find(x=>x.homeAway==="home"),A=cs.find(x=>x.homeAway==="away");if(!H||!A)continue;const ab=x=>lg175Ab(x.team&&x.team.abbreviation);
  const st=(c.status||ev.status||{}),ty=st.type||{};
  out[ab(A)+"-"+ab(H)]={id:ev.id,a:ab(A),h:ab(H),aid:String(A.team&&A.team.id),hid:String(H.team&&H.team.id),as:A.score,hs:H.score,
    arec:((A.records||A.record||[])[0]||{}).summary||"",hrec:((H.records||H.record||[])[0]||{}).summary||"",state:ty.state,detail:ty.shortDetail||ty.detail||"",
    period:st.period,clock:st.displayClock,sit:c.situation||null,name:ty.name||""};}
  return out;}
async function lg175LoadSB(force){if(!force&&LG175.sb&&Date.now()-LG175.sbAt<25000)return LG175.sb;
  try{const urls=[LG175_SB,`${LG175_SB}?seasontype=2&week=${S.week||1}&dates=${S.season||new Date().getFullYear()}`];
    const rs=await Promise.allSettled(urls.map(u=>fetch(u,{cache:"no-store"}).then(r=>r.ok?r.json():Promise.reject(r.status))));
    const m=Object.assign({},LG175.sb||{});for(const r of rs)if(r.status==="fulfilled")Object.assign(m,lg175Parse(r.value));LG175.sb=m;LG175.sbAt=Date.now();}catch(e){}
  return LG175.sb;}
async function lg175LoadSum(id,force){if(!id)return null;const t=LG175.at[id]||0;if(!force&&LG175.sum[id]&&Date.now()-t<25000)return LG175.sum[id];
  if(LG175.inflight[id])return LG175.inflight[id];
  LG175.inflight[id]=fetch(LG175_SUM(id),{cache:"no-store"}).then(r=>r.ok?r.json():null).then(j=>{if(j){LG175.sum[id]=j;LG175.at[id]=Date.now();}return LG175.sum[id]||null;}).catch(()=>LG175.sum[id]||null).finally(()=>{delete LG175.inflight[id];});
  return LG175.inflight[id];}
/* ---- play parsing ---- */
function lg175Norm(s){return String(s||"").toLowerCase().replace(/\b(jr|sr|ii|iii|iv|v)\b\.?/g,"").replace(/[^a-z]/g,"");}
function lg175Index(teams){const k=teams.join(",");if(LG175._ix&&LG175._ix.k===k)return LG175._ix.m;const m=new Map();
  for(const p of Object.values(PL)){if(!p||!teams.includes(p.team)||!p.name)continue;const parts=p.name.split(" ");const first=parts[0]||"",last=parts.slice(1).join(" ");
    const key=(first[0]||"").toLowerCase()+lg175Norm(last);if(!m.has(key))m.set(key,[]);m.get(key).push(p);const lk="*"+lg175Norm(last);if(!m.has(lk))m.set(lk,[]);m.get(lk).push(p);}
  LG175._ix={k,m};return m;}
function lg175Find(abbr,teams){if(!abbr)return null;const mm=/^([A-Z][a-z]?)\.\s?(.+)$/.exec(abbr.trim());if(!mm)return null;const ix=lg175Index(teams);
  const c=ix.get(mm[1][0].toLowerCase()+lg175Norm(mm[2]));if(c&&c.length)return c.sort((a,b)=>(b.val||0)-(a.val||0))[0];
  const c2=ix.get("*"+lg175Norm(mm[2]));return c2&&c2.length===1?c2[0]:null;}
function lg175Parse1(pl,teams){const raw=String(pl.text||"");const typ=String((pl.type&&pl.type.text)||"");
  if(/NO PLAY|No Play/.test(raw)&&!/TOUCHDOWN/.test(raw))return {raw,typ,ev:[]};
  const t=raw.replace(/\([^)]*\)/g," ").replace(/\s+/g," ").trim();const names=[...t.matchAll(/\b([A-Z][a-z]?\.\s?[A-Z][A-Za-z'’\-]+(?:\s(?:St\.\s)?[A-Z][A-Za-z'’\-]+)?)/g)].map(m=>m[1]);
  const yds=(()=>{if(pl.statYardage!=null&&isFinite(+pl.statYardage))return +pl.statYardage;const m=/for (-?\d+) yards?/.exec(t);if(m)return +m[1];return /no gain/.test(t)?0:0;})();
  const td=/TOUCHDOWN/.test(t)&&!/NULLIFIED|REVERSED/.test(t),two=/TWO-POINT/.test(t),twoOK=two&&/SUCCEEDS/.test(t);const ev=[];const P=n=>lg175Find(n,teams);
  if(/field goal is GOOD/i.test(t)&&names[0]){const d=+((/(\d+) yard field goal/.exec(t)||[])[1]||0);ev.push({p:P(names[0]),k:"fg",d});}
  else if(/extra point is GOOD/i.test(t)&&names[0])ev.push({p:P(names[0]),k:"xp"});
  else if(/ pass /.test(" "+t+" ")||/ sacked /.test(t)){const qb=P(names[0]);
    if(/ sacked /.test(t)){ev.push({p:qb,k:"sack"});}
    else if(/INTERCEPTED/.test(t))ev.push({p:qb,k:"int"});
    else if(/incomplete/.test(t))ev.push({p:qb,k:"inc"});
    else{const rx=/ to ([A-Z][a-z]?\.\s?[A-Z][A-Za-z'’\-]+(?:\s(?:St\.\s)?[A-Z][A-Za-z'’\-]+)?)/.exec(t);const wr=rx?P(rx[1]):P(names[1]);
      if(two){if(twoOK){ev.push({p:qb,k:"p2"});ev.push({p:wr,k:"r2"});}}else{ev.push({p:qb,k:"pass",y:yds,td});ev.push({p:wr,k:"rec",y:yds,td});}}}
  else if(names[0]&&/(left|right|up the middle|scrambles|rush|guard|tackle|end|kneels)/i.test(t)&&!/punts|kicks|kickoff/i.test(t)){const rb=P(names[0]);
    if(two){if(twoOK)ev.push({p:rb,k:"u2"});}else if(!/kneels/.test(t))ev.push({p:rb,k:"rush",y:yds,td});}
  if(/FUMBLES/.test(t)){const fm=/([A-Z][a-z]?\.\s?[A-Z][A-Za-z'’\-]+) FUMBLES/.exec(t);const rec=/RECOVERED by ([A-Z]{2,3})-/.exec(t);
    const fp=fm&&P(fm[1]);if(fp&&rec&&lg175Ab(rec[1])!==fp.team)ev.push({p:fp,k:"fum"});}
  return {raw,typ,ev:ev.filter(e=>e.p),yds,td};}
function lg175Pts(e,sc){sc=sc||{};const g=(k,d)=>sc[k]!=null?+sc[k]:d;let v=0;const y=e.y||0;
  if(e.k==="rush"){v=y*g("rush_yd",.1)+g("rush_att",0)+(e.td?g("rush_td",6):0);}
  else if(e.k==="rec"){const pos=e.p&&e.p.pos;v=g("rec",1)+(pos==="TE"?g("bonus_rec_te",0):pos==="RB"?g("bonus_rec_rb",0):pos==="WR"?g("bonus_rec_wr",0):0)+y*g("rec_yd",.1)+(e.td?g("rec_td",6):0);}
  else if(e.k==="pass"){v=y*g("pass_yd",.04)+g("pass_cmp",0)+(e.td?g("pass_td",4):0);}
  else if(e.k==="inc")v=g("pass_inc",0);else if(e.k==="int")v=g("pass_int",-1);else if(e.k==="sack")v=g("pass_sack",0);
  else if(e.k==="fum")v=g("fum_lost",-2);else if(e.k==="p2")v=g("pass_2pt",2);else if(e.k==="r2")v=g("rec_2pt",2);else if(e.k==="u2")v=g("rush_2pt",2);
  else if(e.k==="xp")v=g("xpm",1);else if(e.k==="fg"){const d=e.d||0;v=d>=50?g("fgm_50p",5):d>=40?g("fgm_40_49",4):d>=30?g("fgm_30_39",3):d>=20?g("fgm_20_29",3):g("fgm_0_19",3);}
  return Math.round(v*100)/100;}
/* who cares about a player in which league: mine starter / mine bench / opponent starter (this week's matchup) */
function lg175Roles(){const k=(S.leagues||[]).map(L=>L.id+":"+(L._mut||0)).join(",")+"|"+S.week;if(LG175._r&&LG175._r.k===k&&Date.now()-LG175._r.t<20000)return LG175._r.m;const m=new Map();
  for(const L of S.leagues||[]){if(L.rip)continue;let M=null;try{M=myMatchup(L);}catch(e){}if(!M)continue;
    const add=(p,role)=>{if(!p)return;if(!m.has(p.id))m.set(p.id,[]);m.get(p.id).push({L,role,M});};
    M.A.rows.forEach(r=>add(r.p,"me"));(M.A.bench||[]).forEach(p=>add(p,"bench"));M.B.rows.forEach(r=>add(r.p,"opp"));}
  LG175._r={k,m,t:Date.now()};return m;}
function lg175Wp(M,dA,dB){try{const pa=M.A.proj+dA,pb=M.B.proj+dB;if(S.mode==="live"&&M.left){const [ra,rb]=M.left;
    const va=LV123.s*(pa*WP.k+WP.c)**2*Math.pow(Math.max(0,ra),LV123.p),vb=LV123.s*(pb*WP.k+WP.c)**2*Math.pow(Math.max(0,rb),LV123.p),sd=Math.sqrt(va+vb),d=pa-pb;
    return sd<.25?(d>0?1:d<0?0:.5):1/(1+Math.exp(-1.7*WP.b*d/sd));}return winProb(pa,pb);}catch(e){return null;}}
function lg175Plays(sum){const out=[];const dr=(sum&&sum.drives)||{};const all=[...(dr.previous||[])];if(dr.current&&!all.some(d=>d.id===dr.current.id))all.push(dr.current);
  for(const d of all)for(const p of d.plays||[])out.push(Object.assign({},p,{_drive:d}));
  if(!out.length)for(const p of (sum&&sum.plays)||[])out.push(p);return out;}
function lg175Clock(p){const q=p.period&&p.period.number,c=p.clock&&p.clock.displayValue;return q?`${q>4?"OT":"Q"+q}${c?" "+c:""}`:"";}
function lg175Last(n){const s=String(n||"").split(" ").filter(w=>!/^(Jr\.?|Sr\.?|II|III|IV|V)$/.test(w));return s.slice(1).join(" ")||s[0]||"";}
function lg175Head(pa){const e=pa.ev[0];if(!e)return null;const n=e.p.name.split(" "),sn=(n[0][0]||"")+". "+n.slice(1).join(" ");const y=e.y;
  if(e.k==="rush")return `${sn} ${y} yd ${pa.td?"TD run":"rush"}`;if(e.k==="pass"){const r=pa.ev[1];return r?`${(r.p.name.split(" ")[0][0]||"")}. ${r.p.name.split(" ").slice(1).join(" ")} ${y} yd ${pa.td?"TD catch":"catch"}`:`${sn} ${y} yd pass`;}
  if(e.k==="rec")return `${sn} ${y} yd ${pa.td?"TD catch":"catch"}`;if(e.k==="int")return `${sn} intercepted`;if(e.k==="inc")return `${sn} incomplete`;if(e.k==="sack")return `${sn} sacked`;if(e.k==="fg")return `${sn} ${e.d} yd field goal`;if(e.k==="xp")return `${sn} extra point`;
  if(e.k==="fum")return `${sn} fumble lost`;if(/2$/.test(e.k))return `${sn} two-point conversion`;return null;}
/* ---- field ---- */
function lg175X(yd,y){const t=(y-22)/118,g=66-36*t,w=2.28+.72*t;return g+w*yd;}
function lg175Field(G,sum){const sit=G.sit||(sum&&sum.situation)||null;const dr=sum&&sum.drives&&(sum.drives.current||(sum.drives.previous||[]).slice(-1)[0]);
  const offId=sit&&sit.possession?String(sit.possession):dr&&dr.team?String(dr.team.id):null;const offHome=offId&&offId===G.hid,offAway=offId&&offId===G.aid;
  // absolute yard from the away goal line (left)
  let ball=null;const pt=sit&&sit.possessionText;if(pt){const m=/([A-Z]{2,3})\s+(\d+)/.exec(pt);if(m){const side=lg175Ab(m[1]),yd=+m[2];ball=side===G.a?yd:side===G.h?100-yd:null;}else if(/50/.test(pt))ball=50;}
  const abs=(pp,which)=>{const s=pp&&pp[which];if(!s||s.yardsToEndzone==null)return null;const team=s.team&&s.team.id?String(s.team.id):offId;return team===G.hid?+s.yardsToEndzone:100-(+s.yardsToEndzone);};
  const plays=dr?(dr.plays||[]):[];const spots=[];const st=abs(plays[0],"start");if(st!=null)spots.push(st);for(const p of plays){const e=abs(p,"end");if(e!=null)spots.push(e);}
  if(ball==null&&spots.length)ball=spots[spots.length-1];if(ball==null)return "";
  const dir=offHome?-1:offAway?1:0,dist=sit&&sit.distance!=null?+sit.distance:null,goal=dir&&dist!=null&&(dir>0?ball+dist>=100:ball-dist<=0);
  const fd=dir&&dist!=null?(goal?(dir>0?100:0):ball+dir*dist):null,toGo=dir?(dir>0?100-ball:ball):null,rz=sit&&sit.isRedZone!=null?!!sit.isRedZone:toGo!=null&&toGo<=20;
  const L=(yd,c,w)=>`<line x1="${lg175X(yd,22).toFixed(1)}" y1="22" x2="${lg175X(yd,140).toFixed(1)}" y2="140" stroke="${c}" stroke-width="${w||3}"/>`;
  const poly=(a,b,f)=>`<polygon points="${lg175X(a,22).toFixed(1)},22 ${lg175X(b,22).toFixed(1)},22 ${lg175X(b,140).toFixed(1)},140 ${lg175X(a,140).toFixed(1)},140" fill="${f}"/>`;
  const [ac1]=tcol(G.a),[hc1]=tcol(G.h),Y=100;const lines=[10,20,30,40,50,60,70,80,90].map(v=>`<line x1="${lg175X(v,22).toFixed(1)}" y1="22" x2="${lg175X(v,140).toFixed(1)}" y2="140"/>`).join("");
  const rzPoly=rz&&dir?(dir>0?poly(80,100,"rgba(255,59,74,.16)"):poly(0,20,"rgba(255,59,74,.16)")):"";
  const drv=spots.length>1?`<line x1="${lg175X(spots[0],Y).toFixed(1)}" y1="${Y}" x2="${lg175X(ball,Y).toFixed(1)}" y2="${Y}" stroke="#FF6B1A" stroke-width="3" stroke-linecap="round" opacity=".55"/>${spots.slice(1,-1).map(v=>`<circle cx="${lg175X(v,Y).toFixed(1)}" cy="${Y}" r="3.2" fill="#FF6B1A"/>`).join("")}<circle cx="${lg175X(spots[0],Y).toFixed(1)}" cy="${Y}" r="4.5" fill="none" stroke="#FF6B1A" stroke-width="2"/>`:"";
  const bx=lg175X(ball,Y);const last=plays.length?lg175Head(lg175Parse1(plays[plays.length-1],[G.a,G.h])):null;const lw=last?Math.min(150,last.length*6.2+18):0,lx=Math.max(4,Math.min(356-lw,bx-lw/2));
  const nums=[10,20,30,40,50,60,70,80,90].map(v=>`<text x="${lg175X(v,22).toFixed(1)}" y="16"${rz&&dir&&((dir>0&&v===80)||(dir<0&&v===20))?' fill="#FF6B7A"':""}>${v>50?100-v:v}</text>`).join("");
  const svg=`<svg class="lg175f" viewBox="0 0 360 150" width="100%"><defs><linearGradient id="lg175g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1E3B2A"/><stop offset="1" stop-color="#14281C"/></linearGradient><clipPath id="lg175c"><polygon points="44,22 316,22 360,140 0,140"/></clipPath></defs>
   <polygon points="44,22 316,22 360,140 0,140" fill="url(#lg175g)"/><g clip-path="url(#lg175c)"><polygon points="44,22 66,22 30,140 0,140" fill="${ac1}" opacity=".9"/><polygon points="294,22 316,22 360,140 330,140" fill="${hc1}" opacity=".9"/>
   ${rzPoly}<g stroke="rgba(255,255,255,.22)" stroke-width="1">${lines}</g>${fd!=null?poly(Math.min(ball,fd),Math.max(ball,fd),"rgba(255,210,62,.2)")+L(fd,"#FFD23E"):""}${L(ball,"#4DA3FF")}${drv}</g>
   <g class="lg175num" font-weight="700" font-size="11" text-anchor="middle">${nums}</g>
   <g font-weight="800" font-size="13" fill="#fff" letter-spacing="3" text-anchor="middle" dominant-baseline="central"><text x="35" y="81" transform="rotate(-69.5 35 81)">${esc(G.a)}</text><text x="325" y="81" transform="rotate(69.5 325 81)">${esc(G.h)}</text></g>
   <ellipse cx="${bx.toFixed(1)}" cy="${Y}" rx="8" ry="5.5" fill="#8B4A23" stroke="#E0A06A"/><line x1="${(bx-4).toFixed(1)}" y1="${Y}" x2="${(bx+4).toFixed(1)}" y2="${Y}" stroke="#fff"/>
   ${last?`<rect x="${lx.toFixed(1)}" y="${Y+10}" width="${lw.toFixed(0)}" height="20" rx="10" fill="rgba(11,12,14,.85)"/><text x="${(lx+lw/2).toFixed(1)}" y="${Y+24}" font-size="11" font-weight="700" fill="#F2F1EC" text-anchor="middle">${esc(last)}</text>`:""}</svg>`;
  const ord=n=>["","1st","2nd","3rd","4th"][n]||"";const down=sit&&sit.down>0?sit.down:null;
  const dd=down?`<div class="lg175dd"><span class="lg175big">${ord(down)} <b>&amp; ${goal?"Goal":dist}</b></span><span class="lg175downs">${[1,2,3,4].map(i=>`<i class="${i<down?"u":i===down?"c":""}"></i>`).join("")}</span>${rz?'<span class="lg175rz">RED ZONE</span>':""}</div>`:"";
  const offAb=offHome?G.h:offAway?G.a:"";const sub=`<div class="lg175sub">${dir<0?"← ":""}${offAb?esc(offAb)+" driving":""}${pt?` · ball at ${esc(pt)}`:""}${dir>0?" →":""}</div>`;
  const leg=`<div class="lg175leg"><span style="--c:#4DA3FF">line of scrimmage</span>${fd!=null?`<span style="--c:#FFD23E">${goal?"goal line":"1st down"}</span>`:""}${spots.length>1?'<span style="--c:#FF6B1A">this drive</span>':""}</div>`;
  const dsum=dr?`<div class="lg175drv"><span>Drive: <b>${dr.offensivePlays!=null?dr.offensivePlays+" plays · ":""}${dr.yards!=null?dr.yards+" yds":""}${dr.timeElapsed&&dr.timeElapsed.displayValue?" · "+esc(dr.timeElapsed.displayValue):""}</b></span>${dr.start&&dr.start.text?`<span>started at ${esc(dr.start.text)}</span>`:""}</div>`:"";
  return {html:dd+sub+svg+leg,dsum,rz,goal,offAb,toGo,dir};}
/* "If X scores here": your (or their) starter on the offense with the most projected points in one of your matchups */
function lg175IfScores(G,F){if(!F||!F.rz||!F.offAb)return "";const R=lg175Roles();let best=null;
  for(const [id,arr] of R){const p=PL[id];if(!p||p.team!==F.offAb||!/^(QB|RB|WR|TE)$/.test(p.pos))continue;for(const x of arr){if(x.role==="bench")continue;const pr=wkProj(p)||0;if(!best||pr>best.pr)best={p,x,pr};}}
  if(!best)return "";const sc=best.x.L.scoring||{},td=best.p.pos==="QB"?(sc.pass_td!=null?+sc.pass_td:4):(best.p.pos==="RB"?(sc.rush_td!=null?+sc.rush_td:6):(sc.rec_td!=null?+sc.rec_td:6)+(sc.rec!=null?+sc.rec:1));
  const pts=td+(F.toGo||0)*(best.p.pos==="QB"?.04:.1),M=best.x.M,me=best.x.role==="me",w0=lg175Wp(M,0,0),w1=me?lg175Wp(M,pts,0):lg175Wp(M,0,pts);
  return `<div class="lg175if${me?"":" op"}"><div><div class="t">If ${esc(lg175Last(best.p.name))} scores here</div><div class="s">${me?"your starter":"their starter"} in ${esc(best.x.L.name)}${w0!=null&&w1!=null?` · win chance ${pc(w0)} → ${pc(w1)}`:""}</div></div><b>${me?"+":"−"}${f1(pts)}</b></div>`;}
function lg175WP(G,sum){const wp=(sum&&sum.winprobability)||[];if(wp.length<2)return "";const n=wp.length,W=340,H=110,pts=wp.map((x,i)=>[i/(n-1)*W,(1-(+x.homeWinPercentage||0))*H]);
  const path="M"+pts.map(p=>p[0].toFixed(1)+" "+p[1].toFixed(1)).join(" L"),last=wp[n-1],hp=+last.homeWinPercentage||0,lead=hp>=.5?G.h:G.a,lp=hp>=.5?hp:1-hp;
  return `<section class="pan mt"><div class="row sp"><h2>Win probability</h2><span class="tag">ESPN</span></div><div class="lg175wp"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><line x1="0" y1="${H/2}" x2="${W}" y2="${H/2}" stroke="var(--line)" stroke-dasharray="3 4"/><path d="${path} L${W} ${H} L0 ${H}Z" fill="color-mix(in srgb,var(--acc) 12%,transparent)"/><path d="${path}" fill="none" stroke="var(--acc)" stroke-width="2.5" vector-effect="non-scaling-stroke"/></svg>
   <span class="lg175wpl">${esc(lead)} ${Math.round(lp*100)}%</span></div><div class="lg175wpx"><span>${esc(G.h)} up</span><span>${esc(G.a)} up</span></div></section>`;}
function lg175PlayRow(pl,G,opt){const pa=lg175Parse1(pl,[G.a,G.h]);const R=lg175Roles();let tag="",cls="";
  for(const e of pa.ev){const arr=R.get(e.p.id);if(!arr)continue;const x=arr.find(z=>z.role==="me")||arr.find(z=>z.role==="opp")||arr[0];const v=lg175Pts(e,x.L.scoring);if(!v)continue;
    const c=x.role==="me"?"me":x.role==="opp"?"op":"bn";if(!tag||c==="me"){tag=`<div class="lg175fp ${c}">${v>0?"+":""}${f1(v)}<small>${c==="me"?"you":c==="op"?"opponent":"bench"}${(S.leagues||[]).length>1?" · "+esc(lgShort?lgShort(x.L):x.L.name):""}</small></div>`;cls=c;}}
  const head=lg175Head(pa)||pa.typ||"Play";const chip=pa.td?'<span class="lg175chip td">TD</span>':/1st down/i.test(pa.raw)?"":"";
  const sub=pa.raw.replace(/^\(\d+:\d+ - \w+\)\s*/,"").slice(0,120);
  return `<div class="lg175pl${cls==="me"?" hl":""}"><span class="lg175q">${esc(lg175Clock(pl))}</span><div><div class="pt">${chip}${esc(head)}</div><div class="ps">${esc(sub)}</div></div>${tag||'<div class="lg175fp mut">—</div>'}</div>`;}
/* ---- page A ---- */
function vLiveGame(key){const [a,h]=key.split("-");const sb=LG175.sb||{};const G=sb[key];if(!LG175.sb||Date.now()-LG175.sbAt>25000)lg175LoadSB().then(()=>{if(route()==="gameday-"+key)bgRender();});
  if(!G)return `<section class="pan"><p class="sub">${LG175.sb?"ESPN isn't listing this game right now.":"Loading the game…"}</p></section>`;
  const sum=LG175.sum[G.id];if(!sum||Date.now()-(LG175.at[G.id]||0)>25000)lg175LoadSum(G.id).then(()=>{if(route()==="gameday-"+key)bgRender();});
  const live=G.state==="in",chips=Object.values(sb).filter(x=>x.state!=="pre").sort((x,y)=>(y.state==="in")-(x.state==="in")).slice(0,8).map(x=>`<button class="lg175chipg${x.a+"-"+x.h===key?" on":""}" data-go="gameday-${x.a}-${x.h}">${tbadge(x.a,"sm")}<b class="num">${esc(String(x.as??""))}</b><span class="${x.state==="in"?"lg175lvt":"sub"}">${x.state==="in"?"● "+esc(`${+x.period>4?"OT":"Q"+(x.period||"")} ${x.clock||""}`):"Final"}</span><b class="num">${esc(String(x.hs??""))}</b>${tbadge(x.h,"sm")}</button>`).join("");
  const offId=G.sit&&G.sit.possession?String(G.sit.possession):null;const F=live?lg175Field(G,sum):"";
  const qn=+G.period||0,qtxt=/half/i.test(G.name+G.detail)?"Half":/END_PERIOD/i.test(G.name)?`End Q${qn}`:`${qn>4?"OT":"Q"+qn} ${G.clock||""}`;const clk=live?`<div class="clock"><i class="dot"></i>${esc(qtxt)}</div>`:`<div class="sub">${esc(G.detail||"")}</div>`;
  const bar=`<div class="lg175bar"><div class="side"><div class="tcol">${tbadge(G.a)}<small>${offId===G.aid?'<i class="ballic"></i>':""}${esc(G.arec)}</small></div><span class="sc${+G.as<+G.hs?" dim":""}">${esc(String(G.as??0))}</span></div>
   <div class="ctr">${clk}</div><div class="side r"><div class="tcol">${tbadge(G.h)}<small>${offId===G.hid?'<i class="ballic"></i>':""}${esc(G.hrec)}</small></div><span class="sc${+G.hs<+G.as?" dim":""}">${esc(String(G.hs??0))}</span></div></div>`;
  const card=`<section class="pan lg175card${F&&F.rz?" rz":""}">${bar}${F?F.html:""}${F?lg175IfScores(G,F):""}${F?F.dsum:""}</section>`;
  const plays=sum?lg175Plays(sum).filter(p=>p.text).reverse():[];
  const feed=plays.length?`<section class="pan mt"><div class="row sp"><h2>Plays</h2><span class="tag">your players lit</span></div>${lst(plays.slice(0,120).map(p=>lg175PlayRow(p,G)),25,"")}</section>`:`<section class="pan mt"><p class="sub">${sum?"No plays yet.":"Loading plays…"}</p></section>`;
  return `<div class="lg175chips">${chips}</div>${card}${lg175WP(G,sum)}${feed}<p class="sub mt">Live data from ESPN. Fantasy points per play are worked out from the play description in each league's scoring, so they can differ slightly from Sleeper's final numbers.</p>`;}
vHome=(function(prev){return function(){const r=route();if(/^gameday-[A-Z]{2,3}-[A-Z]{2,3}$/.test(r))return vLiveGame(r.slice(8));return prev();};})(vHome);
pageTitle=(function(prev){return function(r){if(/^gameday-[A-Z]{2,3}-[A-Z]{2,3}$/.test(r)){const [a,h]=r.slice(8).split("-");return {eb:["Huddle","Gameday"],h:`${a} @ ${h}`};}return prev(r);};})(pageTitle);
LABEL=(function(prev){return function(r){if(/^gameday-[A-Z]{2,3}-[A-Z]{2,3}$/.test(r))return r.slice(8).replace("-"," @ ");return prev(r);};})(LABEL);
tabOf=(function(prev){return function(r){return /^gameday-/.test(r)?"gameday":prev(r);};})(tabOf);
/* Gameday cards: started games open the live page */
document.addEventListener("click",e=>{const gm=e.target.closest&&e.target.closest("[data-game]");if(!gm)return;const key=gm.dataset.game;const [a,h]=key.split("-");
  const gs=(()=>{try{return gameState(a);}catch(e){return null;}})();const G=LG175.sb&&LG175.sb[key];const started=(G&&G.state&&G.state!=="pre")||(gs&&gs.st&&gs.st!=="pre"&&S.mode==="live");
  if(!started)return;e.stopPropagation();e.preventDefault();go("gameday-"+key);},true);
/* ---- C: matchup Live feed ---- */
async function lg175Feed(L){const M=myMatchup(L);if(!M)return null;await lg175LoadSB();const sb=LG175.sb||{};const mine=new Set(M.A.rows.filter(r=>r.p).map(r=>r.p.id)),theirs=new Set(M.B.rows.filter(r=>r.p).map(r=>r.p.id));
  const teams=new Set([...mine,...theirs].map(id=>PL[id]&&PL[id].team).filter(Boolean));const games=Object.values(sb).filter(G=>G.state!=="pre"&&(teams.has(G.a)||teams.has(G.h)));
  await Promise.all(games.map(G=>lg175LoadSum(G.id)));const out=[];
  for(const G of games){const sum=LG175.sum[G.id];if(!sum)continue;lg175Plays(sum).forEach((pl,i)=>{const pa=lg175Parse1(pl,[G.a,G.h]);for(const e of pa.ev){const me=mine.has(e.p.id),op=theirs.has(e.p.id);if(!me&&!op)continue;const v=lg175Pts(e,L.scoring);if(!v)continue;
      out.push({G,pl,pa,e,v,me,ts:Date.parse(pl.wallclock||"")||0,i});}});}
  out.sort((x,y)=>(y.ts-x.ts)||(y.i-x.i));return {M,rows:out};}
function lg175FeedHtml(L,F){if(!F)return `<section class="pan"><p class="sub">Loading the live feed…</p></section>`;const M=F.M;
  const rows=F.rows.slice(0,80).map(x=>{const dw=x.me?lg175Wp(M,x.v,0)-lg175Wp(M,0,0):lg175Wp(M,0,x.v)-lg175Wp(M,0,0);const head=lg175Head(x.pa)||x.pa.typ;
    return `<div class="lg175pl${x.me?" hl":""}" data-go="gameday-${x.G.a}-${x.G.h}" role="link"><span class="lg175q">${esc(x.e.p.team)} ${esc(lg175Clock(x.pl))}</span><div><div class="pt">${x.pa.td?'<span class="lg175chip td">TD</span>':""}${esc(head)}</div><div class="ps">${esc(x.G.a)} @ ${esc(x.G.h)} · ${x.me?"your":"their"} ${esc(x.e.p.pos)}</div></div><div class="lg175fp ${x.me?"me":"op"}">${x.v>0?"+":""}${f1(x.v)}<small>${isFinite(dw)?(Math.round(dw*100)===0?"win ±0%":`win ${dw>0?"+":"−"}${Math.abs(Math.round(dw*100))}%`):""}</small></div></div>`;});
  return `<section class="pan">${rows.length?lst(rows,25,""):`<p class="sub">No scoring plays for either lineup yet. Plays show here as soon as your or their starters touch the ball.</p>`}</section><p class="sub mt">Points per play are worked out from ESPN's play descriptions in this league's scoring (Sleeper's official numbers can differ slightly). Win change = how much that play alone moved your win chance.</p>`;}
document.addEventListener("click",e=>{const b=e.target.closest&&e.target.closest("[data-mxt]");if(!b)return;e.stopPropagation();S.mxTab=b.dataset.mxt;render();},true);
vMatchup=(function(prev){return function(li){const h=prev(li);try{const L=S.leagues[li];if(!L||L.gl)return h;const anyStarted=Object.values(LG175.sb||{}).some(G=>G.state!=="pre")||(()=>{try{return liveSet().size>0;}catch(e){return false;}})();
  if(!LG175.sb)lg175LoadSB().then(()=>{if(/^matchup/.test(route()))bgRender();});if(!anyStarted&&S.mxTab!=="feed")return h;
  const tabs=`<div class="seg sm lg175tabs"><button data-mxt="lineups" class="${S.mxTab!=="feed"?"on":""}">Lineups</button><button data-mxt="feed" class="${S.mxTab==="feed"?"on":""}">Live feed</button></div>`;
  if(S.mxTab!=="feed")return tabs+h;const k=L.id;LG175.feed=LG175.feed||{};const F=LG175.feed[k];
  if(!F||Date.now()-F.at>25000){lg175Feed(L).then(v=>{LG175.feed[k]={v,at:Date.now()};if(/^matchup/.test(route())&&S.mxTab==="feed")bgRender();}).catch(()=>{});}
  const M=myMatchup(L);const hdr=M?`<section class="pan lg175mx"><div class="lg175mxr"><div><div class="n">You</div><div class="lg175mxs">${f1(M.A.live!=null?M.A.live:M.A.proj)}</div><div class="n">proj ${f1(M.A.proj)}</div></div><div class="ctr">${M.A.live!=null?'<span class="lg175lv"><i class="dot"></i>LIVE</span>':'<span class="sub">proj</span>'}</div><div style="text-align:right"><div class="n ell">${esc(M.B.t.name)}</div><div class="lg175mxs dim">${f1(M.B.live!=null?M.B.live:M.B.proj)}</div><div class="n">proj ${f1(M.B.proj)}</div></div></div><div class="bar"><i style="width:${PCT(M.wpA)}%"></i></div><div class="sub" style="margin-top:6px">${pc(M.wpA)} win chance</div></section>`:"";
  return tabs+hdr+lg175FeedHtml(L,F&&F.v);}catch(e){console.error(e);return h;}};})(vMatchup);
/* refresh with the 30 s live scheduler */
lv130Refresh=(function(prev){return async function(){const r=await prev.apply(this,arguments);try{const rt=route();
  if(/^gameday-[A-Z]{2,3}-[A-Z]{2,3}$/.test(rt)){await lg175LoadSB(true);const G=LG175.sb&&LG175.sb[rt.slice(8)];if(G)await lg175LoadSum(G.id,true);bgRender();}
  else if(/^matchup-/.test(rt)&&S.mxTab==="feed"){const L=S.leagues[+rt.slice(8)];if(L){LG175.feed=LG175.feed||{};LG175.feed[L.id]={v:await lg175Feed(L),at:Date.now()};bgRender();}}}catch(e){}return r;};})(lv130Refresh);
document.head.insertAdjacentHTML("beforeend",`<style>
.lg175chips{display:flex;gap:8px;overflow-x:auto;padding-bottom:8px;margin:0 -2px 6px;scrollbar-width:none}.lg175chips::-webkit-scrollbar{display:none}
.lg175chipg{flex:none;display:flex;align-items:center;gap:7px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:7px 9px;font-size:13px}
.lg175chipg.on{border-color:var(--acc)}.lg175chipg .lg175lvt{color:#FF3B4A;font-weight:700;font-size:11px}.lg175chipg .sub{font-size:11px}
.lg175card{position:relative;overflow:hidden}.lg175card.rz{box-shadow:inset 0 0 0 1.5px rgba(255,59,74,.6),0 0 24px rgba(255,59,74,.12)}
.lg175bar{display:grid;grid-template-columns:1fr 92px 1fr;align-items:center}.lg175bar .side{display:flex;align-items:center;justify-content:space-between;gap:8px}.lg175bar .side.r{flex-direction:row-reverse}
.lg175bar .tcol{display:flex;flex-direction:column;align-items:center;gap:5px;width:64px}.lg175bar .tcol small{color:var(--muted);font-size:12px;display:flex;align-items:center;gap:5px;min-height:14px}
.lg175bar .sc{font:700 42px/1 var(--fd,inherit);font-variant-numeric:tabular-nums;width:56px;text-align:center}.lg175bar .sc.dim{opacity:.5}.lg175bar .ctr{text-align:center}
.lg175bar .clock,.lg175lv{color:#FF3B4A;font-weight:700;font-size:13px;display:inline-flex;align-items:center;gap:6px;justify-content:center}
.lg175bar .dot,.lg175lv .dot{width:7px;height:7px;border-radius:50%;background:#FF3B4A;animation:lg175p 1.6s infinite}@keyframes lg175p{0%{box-shadow:0 0 0 0 rgba(255,59,74,.6)}70%{box-shadow:0 0 0 7px rgba(255,59,74,0)}}
.ballic{display:inline-block;width:12px;height:8px;border-radius:50%/60%;background:#8B4A23;border:1px solid #C9773F}
.lg175dd{display:flex;align-items:center;justify-content:center;gap:10px;margin:14px 0 2px;flex-wrap:wrap}.lg175big{font:800 22px/1 var(--fd,inherit)}.lg175big b{color:#FFD23E}.lg175num{fill:var(--muted)}
:root[data-theme="light"] .lg175big b{color:#A86E00}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]) .lg175big b{color:#A86E00}}
.lg175downs{display:flex;gap:4px}.lg175downs i{width:18px;height:6px;border-radius:3px;background:var(--line)}.lg175downs i.u{background:var(--muted)}.lg175downs i.c{background:#FFD23E}
.lg175rz{font:800 10px/1 inherit;letter-spacing:.08em;color:#fff;background:#FF3B4A;border-radius:6px;padding:4px 7px}
.lg175sub{text-align:center;color:var(--muted);font-size:12px;margin-top:6px}.lg175f{display:block;margin-top:10px}
.lg175leg{display:flex;gap:14px;justify-content:center;color:var(--muted);font-size:11px;margin-top:8px;flex-wrap:wrap}.lg175leg span:before{content:"";display:inline-block;width:10px;height:3px;border-radius:2px;margin-right:5px;vertical-align:middle;background:var(--c)}
.lg175drv{display:flex;justify-content:space-between;color:var(--muted);font-size:12px;margin-top:10px;gap:8px}.lg175drv b{color:var(--ink);font-weight:600}
.lg175if{display:flex;justify-content:space-between;align-items:center;gap:10px;background:var(--panel2);border-radius:14px;padding:10px 12px;margin-top:12px;box-shadow:inset 3px 0 0 var(--acc)}
.lg175if .t{font-weight:600}.lg175if .s{color:var(--muted);font-size:12px}.lg175if b{color:var(--acc);font-size:20px;white-space:nowrap}.lg175if.op{box-shadow:inset 3px 0 0 var(--bad)}.lg175if.op b{color:var(--bad)}
.lg175wp{position:relative;height:110px}.lg175wp svg{width:100%;height:100%}.lg175wpl{position:absolute;right:0;top:0;font-weight:700;font-size:13px}
.lg175wpx{display:flex;justify-content:space-between;color:var(--muted);font-size:11px;margin-top:4px}
.lg175pl{display:grid;grid-template-columns:52px 1fr auto;gap:10px;padding:11px 0;border-top:1px solid var(--line);align-items:start}.lg175pl:first-child{border-top:0;padding-top:2px}
.lg175pl.hl{background:linear-gradient(90deg,color-mix(in srgb,var(--acc) 10%,transparent),transparent)}
.lg175q{font-size:11px;color:var(--muted);padding-top:2px;font-variant-numeric:tabular-nums}.lg175pl .pt{font-weight:600;font-size:14px}.lg175pl .ps{font-size:12px;color:var(--muted);margin-top:2px}
.lg175fp{font-weight:700;font-size:13px;text-align:right;white-space:nowrap}.lg175fp small{display:block;font-weight:500;font-size:10.5px;color:var(--muted)}.lg175fp.me{color:var(--acc)}.lg175fp.op{color:var(--bad)}.lg175fp.bn,.lg175fp.mut{color:var(--muted)}
.lg175chip{display:inline-block;font:700 10px/1.4 inherit;letter-spacing:.05em;border-radius:6px;padding:1px 6px;margin-right:6px;vertical-align:1px}.lg175chip.td{background:var(--acc);color:#111}
.lg175tabs{margin-bottom:12px}.lg175mx .bar{height:8px;border-radius:4px;background:var(--panel2);overflow:hidden;margin-top:10px}.lg175mx .bar i{display:block;height:100%;background:linear-gradient(90deg,#FF6B1A,#FF9A57)}
.lg175mxr{display:grid;grid-template-columns:1fr auto 1fr;align-items:end;gap:6px}.lg175mxr .n{font-size:12px;color:var(--muted)}.lg175mxs{font:700 34px/1.1 var(--fd,inherit);font-variant-numeric:tabular-nums}.lg175mxs.dim{opacity:.55}
:root[data-theme="light"] .lg175fp.me,:root[data-theme="light"] .lg175if b{color:#BF4706}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]) .lg175fp.me,:root:not([data-theme="dark"]) .lg175if b{color:#BF4706}}
</style>`);
