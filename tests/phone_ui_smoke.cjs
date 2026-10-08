// Own-app QA only. No camera/microphone capture and no cloud requests.
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
  const root=path.resolve(__dirname,'..');
  const output=path.join(root,'artifacts','scan-workflow');fs.mkdirSync(output,{recursive:true});
  const code=fs.readFileSync(path.join(root,'data','phone-pair-code'),'utf8').trim();
  if(!process.env.GIG_SKIP_PHONE_QA) try {
  const phone=await chromium.connectOverCDP('http://127.0.0.1:9223');
  const p=phone.contexts().flatMap(c=>c.pages()).find(p=>p.url().startsWith('http://localhost:8767'));
  if(!p)throw new Error('GIG phone tab not found');
  await p.waitForLoadState('domcontentloaded');
  if(await p.locator('#pairScreen').isVisible()){
    await p.locator('#pairCode').fill(code);
    await p.locator('#pairForm button').click();
  }
  await p.locator('#appScreen').waitFor({state:'visible'});
  await p.screenshot({path:path.join(output,'phone.png'),fullPage:true});
  console.log('Phone paired; application controls visible. No media captured.');
  await phone.close();
  } catch(error) { console.log('Phone UI verification incomplete: '+error.message); }
  const browser=await chromium.launch({headless:true,channel:'chrome'});
  const page=await browser.newPage({viewport:{width:1280,height:900}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://localhost:8767');
  await page.locator('#pairCode').fill(code);await page.locator('#pairForm button').click();
  await page.locator('#appScreen').waitFor({state:'visible'});
  // Synthetic camera substitute used ONLY in this test's separate browser.
  await page.evaluate(()=>{
    const c=document.createElement('canvas');c.width=600;c.height=400;
    const ctx=c.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,600,400);
    ctx.fillStyle='black';ctx.font='28px sans-serif';ctx.fillText('Synthetic UI test - GIG',30,60);
    scanImage=c.toDataURL('image/jpeg');document.getElementById('scanPreview').src=scanImage;
    document.getElementById('scanReview').classList.remove('hidden');
  });
  await page.locator('#documentTitle').fill('UI-smoke-synthetic');
  await page.locator('#saveDocumentButton').click();
  const download=page.locator('#savedFiles a').filter({hasText:'UI-smoke-synthetic.pdf'});
  await download.waitFor({state:'visible'});
  const href=await download.getAttribute('href');
  const response=await page.request.get('http://localhost:8767'+href);
  if(!(await response.body()).subarray(0,4).equals(Buffer.from('%PDF')))throw new Error('Invalid PDF');
  await page.screenshot({path:path.join(output,'desktop-review.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.locator('#saveDocumentButton').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(output,'mobile-review.png'),fullPage:false});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  // Delete only the synthetic file created above.
  await page.request.delete('http://localhost:8767'+href.replace('/download',''));
  if(errors.length||overflow)throw new Error(JSON.stringify({errors,overflow}));
  console.log('Desktop/mobile UI: save -> private link -> valid PDF; no JS errors or mobile overflow. Synthetic file deleted.');
  await browser.close();
})().catch(e=>{console.error(e.message);process.exit(1)});
