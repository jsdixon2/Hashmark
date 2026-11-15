const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const errs=[];
for(const sch of ['dark','light']){const p=await b.newPage({viewport:{width:390,height:844},colorScheme:sch,deviceScaleFactor:2});p.on('pageerror',e=>errs.push(e.stack.slice(0,300)));p.on('console',m=>{if(m.type()==='error'&&!/net::|Failed to load/.test(m.text()))errs.push(m.text().slice(0,200))});
await p.route(/sleeper\.app|espn\.com|sleepercdn/,r=>r.abort());await p.goto('http://localhost:8765/');await p.waitForTimeout(1200);await p.click('#gDemo');await p.waitForTimeout(2000);
await p.evaluate(()=>{try{localStorage.removeItem('hm_tm177')}catch(e){};location.hash="tm"});await p.waitForTimeout(2500);
if(sch==='dark'){ // calibration: AI field, and a "smart greedy" human with chemistry awareness
 console.log(await p.evaluate(()=>{const rng=tm177Rng(42),ai=[];for(let i=0;i<300;i++)ai.push(tm177AI(rng));ai.sort((a,b)=>a-b);const q=f=>ai[Math.floor(f*ai.length)].toFixed(1);
  const recs=[];for(let g=0;g<60;g++){tm177New();const G=S.tm;let guard=0;while(Object.keys(G.slots).length<7&&guard++<30){tm177Roll(G,false);const ps=tm177Picks(G),used=new Set(ps.map(x=>x.pi));
    const c=TM177.d.T[G.cur].map((r,i)=>tm177Row(G.cur,i)).filter(x=>!used.has(x.pi)&&tm177Fit(x.pos,G.slots)).map(x=>({x,s:x.ppg+tm177Chem(ps.concat([x])).pts}));c.sort((a,b)=>b.s-a.s);
    if(G.rerolls>0&&c[0].s<14){G.rolls=G.rolls.filter(k=>k!==G.cur);tm177Roll(G,true);const ps2=tm177Picks(G);const c2=TM177.d.T[G.cur].map((r,i)=>tm177Row(G.cur,i)).filter(x=>!used.has(x.pi)&&tm177Fit(x.pos,G.slots)).sort((a,b)=>b.ppg-a.ppg);G.slots[tm177Fit(c2[0].pos,G.slots)]={k:G.cur,i:c2[0].i};}
    else G.slots[tm177Fit(c[0].x.pos,G.slots)]={k:G.cur,i:c[0].x.i};G.cur=null;}
   tm177Finish(G);recs.push([G.res.w,+G.res.tot.toFixed(1),G.res.bw]);}
  const ws=recs.map(r=>r[0]).sort((a,b)=>a-b);return {ai:{p10:q(.1),p50:q(.5),p90:q(.9)},humanWins:{min:ws[0],med:ws[30],max:ws[59],perfect:ws.filter(w=>w===17).length},tot:recs.map(r=>r[1]).sort((a,b)=>a-b).filter((_,i)=>i%10===0),bestWins:recs.map(r=>r[2]).sort((a,b)=>a-b).filter((_,i)=>i%10===0)};}));
 await p.evaluate(()=>{tm177New();render();});await p.waitForTimeout(300);}
// play through UI
for(let r=0;r<7;r++){await p.click('[data-tm177roll]');await p.waitForTimeout(250);if(r===3&&sch==='dark'){await p.screenshot({path:`${__dirname}/v177-sheet.png`,fullPage:true});}
  const btn=await p.$('[data-tm177p]');if(!btn){await p.click('[data-tm177re]');await p.waitForTimeout(200);}const b2=await p.$('[data-tm177p]');await b2.click();await p.waitForTimeout(250);
  if(r===3){await p.evaluate(()=>window.scrollTo(0,0));await p.screenshot({path:`${__dirname}/v177-board-${sch}.png`});}}
await p.waitForTimeout(500);console.log(sch,'result',await p.evaluate(()=>(document.querySelector('.tm177res')||{}).innerText));
await p.screenshot({path:`${__dirname}/v177-result-${sch}.png`,fullPage:true});
await p.evaluate(()=>{location.hash="scout"});await p.waitForTimeout(800);console.log('scout tile',await p.evaluate(()=>!!document.querySelector('.tm177land')));
await p.close();}
console.log(errs.length?[...new Set(errs)].join('\n'):'no errors');await b.close();})();
