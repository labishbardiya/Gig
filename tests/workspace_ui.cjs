const {chromium}=require('playwright');
const {server}=require('./ui_fixture.cjs');

(async()=>{
  const fixture=await server();
  try{
  const browser=await chromium.launch({headless:true,channel:'chrome'});
  const page=await browser.newPage({viewport:{width:390,height:844}});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto(fixture.url);
  await page.locator('#pairCode').fill(fixture.code);
  await page.locator('#pairForm button').click();
  await page.locator('#chatTitle').waitFor({state:'visible'});
  await page.locator('#openSidebar').click();
  if(!await page.locator('#workspaceSidebar').evaluate(e=>e.classList.contains('mobile-open')))throw Error('navigation failed');
  await page.locator('#newChatButton').click();
  await page.locator('#openSidebar').click();
  await page.locator('#memoryButton').click();
  await page.locator('.memory-form input').fill('Remember my project is GIG');
  await page.locator('.memory-form button').click();
  await page.locator('.memory-row').first().waitFor();
  await page.locator('#openSidebar').click();
  await page.locator('#tasksButton').click();
  if(await page.locator('.agent-form button').isEnabled())throw Error('agent tasks should be gated');
  await page.waitForTimeout(250);
  if(await page.locator('#workspaceSidebar').evaluate(e=>e.classList.contains('mobile-open')))throw Error('navigation did not close');
  await page.screenshot({path:'artifacts/workspace-mobile.png'});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('mobile overflow');
  await page.setViewportSize({width:1440,height:900});
  await page.screenshot({path:'artifacts/workspace-desktop.png'});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('desktop overflow');
  if(errors.length)throw Error(errors.join('\n'));
  console.log('Workspace chats, memory, gated tasks and responsive layout passed.');
  await browser.close();
  }finally{fixture.cleanup();}
})().catch(error=>{console.error(error);process.exit(1)});
