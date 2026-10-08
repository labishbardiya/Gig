const {chromium}=require('playwright');
const {server}=require('./ui_fixture.cjs');
(async()=>{
 const fixture=await server();
 try{
 const b=await chromium.launch({headless:true,channel:'chrome'});
 const p=await b.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.goto(fixture.url);
 await p.locator('#pairCode').fill(fixture.code);
 await p.locator('#pairForm button').click();
 await p.locator('#appScreen').waitFor({state:'visible'});
 for(const [name,width,height] of [['desktop',1440,1000],['mobile',390,844]]){
  await p.setViewportSize({width,height});
  await p.screenshot({path:`artifacts/white-${name}.png`,fullPage:true});
  if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('overflow '+name);
 }
 await p.locator('#audioReplies').click();
 if(await p.locator('#audioReplies').getAttribute('aria-pressed')!=='false')throw Error('audio toggle');
 await p.locator('#motionButton').click();
 if(!await p.locator('#ambientVideo').evaluate(v=>v.paused))throw Error('motion toggle');
 await p.locator('#textInput').fill('hi');await p.locator('#textForm button').click();
 await p.locator('.message.assistant').waitFor();
 if(errors.length)throw Error(errors.join('\n'));
 console.log('Desktop/mobile, pairing, text reply, audio and motion toggles passed.');
 await b.close();
 }finally{fixture.cleanup();}
})().catch(e=>{console.error(e);process.exit(1)});
