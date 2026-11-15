// v175 test: fake ESPN scoreboard + summary built around demo starters; checks the live game page and the matchup Live feed.
const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();const errs=[];
 for(const sch of ['dark','light']){
 const p=await b.newPage({viewport:{width:390,height:844},colorScheme:sch,deviceScaleFactor:2});p.on('pageerror',e=>errs.push(e.stack.slice(0,400)));p.on('console',m=>{if(m.type()==='error'&&!/net::|Failed to load/.test(m.text()))errs.push(m.text().slice(0,300))});
 let FIX=null;
 await p.route(/espn\.com/,r=>{const u=r.request().url();if(!FIX)return r.abort();if(/summary/.test(u))return r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(FIX.sum)});return r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(FIX.sb)});});
 await p.route(/sleeper\.app|sleepercdn/,r=>r.abort());
 await p.goto('http://localhost:8765/');await p.waitForTimeout(1200);await p.click('#gDemo');await p.waitForTimeout(2500);
 const info=await p.evaluate(()=>{const L=S.L,M=myMatchup(L);const pick=rows=>rows.filter(r=>r.p&&/^(QB|RB|WR|TE)$/.test(r.p.pos)).map(r=>({id:r.p.id,name:r.p.name,pos:r.p.pos,team:r.p.team}));
   return {me:pick(M.A.rows),opp:pick(M.B.rows),ids:Object.fromEntries(Object.entries(TEAMS).map(([k],i)=>[k,String(i+1)]))};});
 // choose a game: my top RB's team as HOME, opponent of it from schedule if possible else a team of an opponent starter
 const rb=info.me.find(x=>x.pos==="RB")||info.me[0];const H=rb.team;const oppP=info.opp.find(x=>x.team!==H)||info.opp[0];const A=oppP.team===H?Object.keys(info.ids).find(t=>t!==H&&t!=="FA"):oppP.team;
 const myWR=info.me.find(x=>x.team===H&&x.id!==rb.id&&/WR|TE/.test(x.pos));
 const sn=n=>{const s=n.split(" ");return s[0][0]+"."+s.slice(1).join(" ");};
 const id=t=>info.ids[t];
 const play=(o)=>Object.assign({id:String(Math.random()).slice(2,10),wallclock:new Date(Date.now()-o.ago*60000).toISOString(),period:{number:o.q},clock:{displayValue:o.c},type:{text:o.ty},statYardage:o.y},o.x);
 const sp=(team,ytez)=>({team:{id:id(team)},yardsToEndzone:ytez});
 const prev=[{id:"d1",team:{id:id(A)},offensivePlays:3,yards:52,timeElapsed:{displayValue:"1:40"},start:{text:`${A} 25`},result:"TD",plays:[
   play({ago:40,q:1,c:"12:10",ty:"Pass Reception",y:12,x:{text:`(12:10 - 1st) ${sn(oppP.name)} pass short right to X.Nobody to ${H} 40 for 12 yards (Y.Def).`,start:sp(A,75),end:sp(A,63)}}),
   play({ago:39,q:1,c:"11:30",ty:"Rush",y:40,x:{text:`(11:30 - 1st) ${sn(oppP.name)} left end to ${H} 23 for 40 yards (Z.Def).`,start:sp(A,63),end:sp(A,23)}}),
   play({ago:38,q:1,c:"10:55",ty:"Field Goal Good",y:0,x:{text:`(10:55 - 1st) K.Kicker 41 yard field goal is GOOD, Center-L.Snap, Holder-H.Old.`,start:sp(A,23),end:sp(A,23)}})]},
  {id:"d2",team:{id:id(H)},offensivePlays:4,yards:75,timeElapsed:{displayValue:"2:30"},start:{text:`${H} 25`},result:"TD",plays:[
   play({ago:30,q:1,c:"8:12",ty:"Rush",y:22,x:{text:`(8:12 - 1st) ${sn(rb.name)} up the middle to ${H} 47 for 22 yards (A.Def).`,start:sp(H,75),end:sp(H,53)}}),
   play({ago:29,q:1,c:"7:30",ty:"Pass Reception",y:31,x:{text:`(7:30 - 1st) (Shotgun) Q.Back pass deep left to ${myWR?sn(myWR.name):"R.Nobody"} to ${A} 22 for 31 yards (B.Def).`,start:sp(H,53),end:sp(H,22)}}),
   play({ago:28,q:1,c:"6:51",ty:"Rushing Touchdown",y:22,x:{text:`(6:51 - 1st) ${sn(rb.name)} left tackle for 22 yards, TOUCHDOWN.`,start:sp(H,22),end:sp(H,0),scoringPlay:true}}),
   play({ago:28,q:1,c:"6:51",ty:"Extra Point Good",y:0,x:{text:`K.Homekick extra point is GOOD, Center-L.Snap, Holder-H.Old.`,start:sp(H,15),end:sp(H,15)}})]},
  {id:"d3",team:{id:id(A)},offensivePlays:2,yards:5,timeElapsed:{displayValue:"0:50"},start:{text:`${A} 25`},result:"INT",plays:[
   play({ago:20,q:2,c:"14:10",ty:"Pass Incompletion",y:0,x:{text:`(14:10 - 2nd) ${sn(oppP.name)} pass incomplete short left to X.Nobody.`,start:sp(A,75),end:sp(A,75)}}),
   play({ago:19,q:2,c:"13:40",ty:"Pass Interception Return",y:0,x:{text:`(13:40 - 2nd) ${sn(oppP.name)} pass short middle intended for X.Nobody INTERCEPTED by D.Back at ${A} 30.`,start:sp(A,75),end:sp(A,70)}})]}];
 const cur={id:"d4",team:{id:id(H)},offensivePlays:4,yards:26,timeElapsed:{displayValue:"2:05"},start:{text:`${A} 30`},plays:[
   play({ago:10,q:2,c:"12:20",ty:"Rush",y:9,x:{text:`(12:20 - 2nd) ${sn(rb.name)} right guard to ${A} 21 for 9 yards (C.Def).`,start:sp(H,30),end:sp(H,21)}}),
   play({ago:8,q:2,c:"11:45",ty:"Pass Reception",y:8,x:{text:`(11:45 - 2nd) Q.Back pass short right to ${sn(rb.name)} to ${A} 13 for 8 yards (D.Def).`,start:sp(H,21),end:sp(H,13)}}),
   play({ago:6,q:2,c:"11:02",ty:"Rush",y:4,x:{text:`(11:02 - 2nd) ${sn(rb.name)} left end to ${A} 9 for 4 yards (E.Def).`,start:sp(H,13),end:sp(H,9)}}),
   play({ago:4,q:2,c:"10:20",ty:"Rush",y:5,x:{text:`(10:20 - 2nd) ${sn(rb.name)} up the middle to ${A} 4 for 5 yards (F.Def).`,start:sp(H,9),end:sp(H,4)}})]};
 const sit={down:3,distance:4,possession:id(H),possessionText:`${A} 4`,isRedZone:true,downDistanceText:`3rd & Goal at ${A} 4`};
 const comp=(st)=>({competitions:[{competitors:[{homeAway:"home",team:{abbreviation:H,id:id(H)},score:"7",records:[{summary:"6-2"}]},{homeAway:"away",team:{abbreviation:A,id:id(A)},score:"3",records:[{summary:"5-4"}]}],
   status:{type:{state:st,name:"STATUS_IN_PROGRESS",completed:false,shortDetail:"10:20 - 2nd",detail:"10:20 - 2nd Quarter"},period:2,displayClock:"10:20",clock:620},situation:sit}]});
 FIX={sb:{events:[Object.assign({id:"401999001"},comp("in"))]},sum:{header:{},boxscore:{players:[{team:{abbreviation:H,id:id(H)},statistics:[{name:'passing',labels:['C/ATT','YDS','AVG','TD','INT','SACKS','QBR','RTG'],athletes:[{athlete:{displayName:'Quinn Back',shortName:'Q. Back',position:{abbreviation:'QB'}},stats:['9/13','121','9.3','0','0','1-6','64.1','104.2']}]},{name:'rushing',labels:['CAR','YDS','AVG','TD','LONG'],athletes:[{athlete:{displayName:rb.name,shortName:sn(rb.name),position:{abbreviation:'RB'}},stats:['5','62','12.4','1','22']}]},{name:'receiving',labels:['REC','YDS','AVG','TD','LONG','TGTS'],athletes:[{athlete:{displayName:rb.name,shortName:sn(rb.name),position:{abbreviation:'RB'}},stats:['1','8','8.0','0','8','2']}].concat(myWR?[{athlete:{displayName:myWR.name,shortName:sn(myWR.name),position:{abbreviation:myWR.pos}},stats:['1','31','31.0','0','31','3']}]:[])},{name:'kicking',labels:['FG','PCT','LONG','XP','PTS'],athletes:[{athlete:{displayName:'Kyle Homekick',position:{abbreviation:'K'}},stats:['0/0','0.0','0','1/1','1']}]}]},{team:{abbreviation:A,id:id(A)},statistics:[{name:'passing',labels:['C/ATT','YDS','AVG','TD','INT','SACKS','QBR','RTG'],athletes:[{athlete:{displayName:oppP.name,shortName:sn(oppP.name),position:{abbreviation:'QB'}},stats:['1/3','12','4.0','0','1','0-0','12.0','39.6']}]},{name:'rushing',labels:['CAR','YDS','AVG','TD','LONG'],athletes:[{athlete:{displayName:oppP.name,shortName:sn(oppP.name),position:{abbreviation:'QB'}},stats:['1','40','40.0','0','40']}]}]}]},drives:{previous:prev,current:cur},winprobability:[.5,.48,.45,.52,.62,.71,.74,.7,.76,.78,.81,.84,.86].map((v,i)=>({homeWinPercentage:v,playId:String(i)}))}};
 console.log(sch,'game',A,'@',H,'| my RB',rb.name,'| opp',oppP.name);
 await p.evaluate(k=>{location.hash="gameday-"+k},A+"-"+H);await p.waitForTimeout(2500);
 const pg=await p.evaluate(()=>({bar:!!document.querySelector('.lg175bar'),field:!!document.querySelector('.lg175f'),rz:!!document.querySelector('.lg175card.rz'),iff:(document.querySelector('.lg175if')||{}).innerText,dd:(document.querySelector('.lg175dd')||{}).innerText,plays:document.querySelectorAll('.lg175pl').length,lit:[...document.querySelectorAll('.lg175pl .lg175fp:not(.mut)')].map(e=>e.innerText.replace(/\n/g,' ')).slice(0,6)}));
 console.log(JSON.stringify(pg));
 console.log('stats rows',await p.evaluate(()=>[...document.querySelectorAll('.lg176r summary')].map(x=>x.innerText.replace(/\n/g,' | '))));await p.evaluate(()=>{const d=document.querySelector('.lg176r');if(d)d.open=true;document.querySelector('.lg176').scrollIntoView();});await p.waitForTimeout(300);await p.screenshot({path:`${__dirname}/v176-${sch}.png`});await p.click('.lg176 [data-lg176]');await p.waitForTimeout(500);console.log('other team rows',await p.evaluate(()=>[...document.querySelectorAll('.lg176r summary')].map(x=>x.innerText.replace(/\n/g,' | '))));await p.screenshot({path:`${__dirname}/v175-game-${sch}.png`,fullPage:true});await p.evaluate(()=>window.scrollTo(0,0));await p.screenshot({path:`${__dirname}/v175-top-${sch}.png`});
 await p.evaluate(()=>{S.mxTab="feed";location.hash="matchup-0";});await p.waitForTimeout(2500);
 const fd=await p.evaluate(()=>({tabs:!!document.querySelector('.lg175tabs'),rows:[...document.querySelectorAll('.lg175pl')].map(r=>r.innerText.replace(/\n/g,' | ')).slice(0,6)}));console.log(JSON.stringify(fd,null,1));
 await p.screenshot({path:`${__dirname}/v175-feed-${sch}.png`,fullPage:true});
 await p.evaluate(()=>{S.mxTab="lineups";render();});await p.waitForTimeout(600);console.log('lineups tab ok',await p.evaluate(()=>!!document.querySelector('.lg175tabs')&&!document.querySelector('.lg175mx')));
 await p.close();}
 console.log(errs.length?[...new Set(errs)].join('\n'):'no errors');await b.close();})();
