// Live-launch measurement with a fake Sleeper (scratchpad/mock), 5 leagues, CPU throttled (argv[2], default 4x).
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const M=process.env.MOCK_DIR||path.join(__dirname,'mock'),rd=f=>{try{return fs.readFileSync(path.join(M,f));}catch(e){return null;}};
const THR=+(process.argv[2]||4),SECS=+(process.argv[3]||35);
function api(u){const p=new URL(u).pathname.replace(/^\/v1/,'');let m;
  if(p==='/state/nfl')return JSON.stringify({season:"2026",league_season:"2026",display_week:10,week:10,season_type:"regular"});
  if(p==='/user/jackdixon')return JSON.stringify({user_id:"u_me",display_name:"jackdixon"});
  if(p==='/user/u_me/leagues/nfl/2026')return rd('leagues.json');
  if(p==='/players/nfl')return rd('players.json');
  if((m=p.match(/^\/stats\/nfl\/regular\/2026\/(\d+)$/)))return rd(`stats_2026_${m[1]}.json`)||'{}';
  if((m=p.match(/^\/stats\/nfl\/regular\/(\d{4})$/)))return rd(`stats_${m[1]}.json`)||'{}';
  if((m=p.match(/^\/projections\/nfl\/regular\/2026\/(\d+)$/)))return rd(`proj_2026_${m[1]}.json`)||'{}';
  if((m=p.match(/^\/league\/([^/]+)\/(rosters|users)$/)))return rd(`lg_${m[1]}_${m[2]}.json`)||'[]';
  if((m=p.match(/^\/league\/([^/]+)\/matchups\/(\d+)$/)))return rd(`lg_${m[1]}_mu_${m[2]}.json`)||'[]';
  if((m=p.match(/^\/league\/([^/]+)\/transactions\/(\d+)$/)))return rd(`lg_${m[1]}_tx_${m[2]}.json`)||'[]';
  if((m=p.match(/^\/league\/([^/]+)$/)))return JSON.stringify(JSON.parse(rd('leagues.json')).find(l=>l.league_id===m[1])||{});
  return '[]';}
(async()=>{const b=await chromium.launch();const ctx=await b.newContext({viewport:{width:390,height:844},serviceWorkers:'block'});
 const calls={};await ctx.route(/api\.sleeper\.app/,r=>{const u=r.request().url();const k=new URL(u).pathname.replace(/\d+/g,'#');calls[k]=(calls[k]||0)+1;setTimeout(()=>r.fulfill({status:200,contentType:'application/json',body:api(u)}),60);});
 await ctx.route(/espn\.com|sleepercdn|fonts\.g/,r=>r.abort());
 await ctx.addInitScript(()=>{try{localStorage.setItem('hm_user','jackdixon');}catch(e){}
   window.__m={lt:[],lag:[],ev:[],live:null,t0:performance.now()};
   try{new PerformanceObserver(l=>{for(const e of l.getEntries())__m.lt.push([Math.round(e.startTime),Math.round(e.duration)]);}).observe({type:'longtask',buffered:true});}catch(e){}
   try{new PerformanceObserver(l=>{for(const e of l.getEntries())if(e.name==='click'||e.name==='pointerdown')__m.ev.push([Math.round(e.startTime),Math.round(e.processingStart-e.startTime),Math.round(e.duration)]);}).observe({type:'event',buffered:true,durationThreshold:16});}catch(e){}
   let last=performance.now();setInterval(()=>{const n=performance.now();__m.lag.push([Math.round(n),Math.round(n-last-50)]);last=n;if(__m.live==null&&typeof S!=='undefined'&&S.mode==='live')__m.live=Math.round(n);},50);});
 for(const run of ['first launch (empty caches)','reopen (caches + snapshot)']){
  const p=await ctx.newPage();const cdp=await ctx.newCDPSession(p);await cdp.send('Emulation.setCPUThrottlingRate',{rate:THR});
  const prof=run.startsWith('reopen');if(prof){await cdp.send('Profiler.enable');await cdp.send('Profiler.setSamplingInterval',{interval:2000});await cdp.send('Profiler.start');}
  const t0=Date.now();console.error('goto',run);await p.goto('http://localhost:8765/',{waitUntil:'commit'});console.error('loaded',Date.now()-t0);
  // taps on the dock every 2 s, alternating Huddle / Team, like a user trying to move around
  const taps=[];for(let s=2;s<=SECS-3;s+=2){await p.waitForTimeout(2000);const sel=(s/2)%2?'.dock [data-hub="team"]':'.dock [data-hub="home"]';const tt=Date.now();
    try{await p.click(sel,{timeout:2500,force:true});}catch(e){}taps.push([s,Date.now()-tt]);}
  await p.waitForTimeout(1500);
  const m=await p.evaluate(()=>({...__m,mode:S.mode,leagues:(S.leagues||[]).length,fcp:(performance.getEntriesByName('first-contentful-paint')[0]||{}).startTime}));
  let top=[];if(prof){const {profile}=await cdp.send('Profiler.stop');const self={},byId={};for(const n of profile.nodes)byId[n.id]=n;
    profile.samples.forEach((id,i)=>{const n=byId[id];const f=n.callFrame;const k=(f.functionName||'(anon)')+(f.url.includes('index.html')||f.url.endsWith('/')?':'+f.lineNumber:' '+(f.url.split('/').pop()||f.url));self[k]=(self[k]||0)+(profile.timeDeltas[i]||0)/1000;});
    top=Object.entries(self).filter(([k])=>!/\(idle\)|\(program\)|\(garbage/.test(k)).sort((a,b)=>b[1]-a[1]).slice(0,22).map(([k,v])=>[k,Math.round(v)]);
    const gc=Object.entries(self).filter(([k])=>/garbage/.test(k)).reduce((t,[,v])=>t+v,0);top.push(['(garbage collector)',Math.round(gc)]);}
  const lt=m.lt.filter(x=>x[0]<SECS*1000),bins=[0,0,0,0,0,0,0,0];lt.forEach(([s,d])=>{bins[Math.min(7,Math.floor(s/5000))]+=d;});
  console.log(`\n=== ${run} · CPU ${THR}x slower · mode ${m.mode} · leagues ${m.leagues}`);
  console.log(` first paint ${Math.round(m.fcp)} ms · live data ready at ${m.live} ms`);
  console.log(` main thread blocked (long tasks) per 5 s window: ${bins.map((v,i)=>`${i*5}-${i*5+5}s ${Math.round(v)}ms`).join(' | ')}`);
  console.log(` longest freezes: ${lt.slice().sort((a,b)=>b[1]-a[1]).slice(0,6).map(([s,d])=>`${d}ms@${(s/1000).toFixed(1)}s`).join(', ')}`);
  console.log(` tap delay (input -> handler starts, Event Timing): ${m.ev.map(([s,dl,du])=>`${(s/1000).toFixed(0)}s:${dl}/${du}ms`).join(' ')}`);
  console.log(` tap -> click returned (Playwright): ${taps.map(([s,d])=>`${s}s:${d}`).join(' ')}`);
  if(top.length){console.log(' CPU self time, reopen (ms, throttled):');top.forEach(([k,v])=>console.log('   ',String(v).padStart(6),k));}
  await p.close();}
 console.log('\nSleeper calls (both launches):',JSON.stringify(calls));await b.close();})();
