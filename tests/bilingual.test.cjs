const {chromium}=require('playwright');const assert=require('node:assert/strict');const path=require('node:path');
(async()=>{const b=await chromium.launch({headless:true,...(process.env.MTOOLS_BROWSER?{executablePath:process.env.MTOOLS_BROWSER}:{})});const p=await b.newPage({viewport:{width:1920,height:1080}});const errors=[];p.on('pageerror',e=>errors.push(e.message));try{
await p.goto('file:///'+path.resolve(__dirname,'../preview/MTools-Preview.html').replaceAll('\\','/'));await p.locator('.workflow-card').first().waitFor();
const titles=await p.locator('.card-title').allTextContents();const before=await p.locator('.cards').boundingBox();const detail=await p.locator('.detail').boundingBox();
await p.locator('[data-tab=settings]').click();await p.locator('[data-language-select]').selectOption('fa');await p.getByText('تنظیمات فضای کاری',{exact:true}).waitFor();
if(process.env.MTOOLS_SCREENSHOTS) await p.screenshot({path:path.resolve(process.env.MTOOLS_SCREENSHOTS,'MTools-Persian-Settings.png')});
await p.locator('[data-tab=workflows]').click();await p.getByText('ورک‌فلوهای شما',{exact:true}).waitFor();assert.deepEqual(await p.locator('.card-title').allTextContents(),titles);assert.equal((await p.locator('.cards').boundingBox()).x,before.x);assert.equal((await p.locator('.detail').boundingBox()).x,detail.x);assert.equal(await p.locator('.shell').evaluate(e=>getComputedStyle(e).direction),'ltr');
await p.locator('.card-main').first().click();if(process.env.MTOOLS_SCREENSHOTS) await p.screenshot({path:path.resolve(process.env.MTOOLS_SCREENSHOTS,'MTools-Persian-Workflows.png')});
await p.locator('[data-tab=projects]').click();await p.locator('[data-project-action=select]').first().click();const prompt=await p.locator('.project-prompt').textContent();if(process.env.MTOOLS_SCREENSHOTS) await p.screenshot({path:path.resolve(process.env.MTOOLS_SCREENSHOTS,'MTools-Persian-Projects.png')});
await p.locator('[data-tab=settings]').click();await p.locator('[data-language-select]').selectOption('en');await p.getByText('Workspace settings',{exact:true}).waitFor();await p.locator('[data-tab=projects]').click();assert.equal(await p.locator('.project-prompt').textContent(),prompt);
await p.locator('[data-tab=settings]').click();await p.locator('[data-language-select]').selectOption('fa');await p.reload();await p.getByText('ورک‌فلوهای شما',{exact:true}).waitFor();
for(const tab of ['reports','gallery','settings']){await p.locator(`[data-tab=${tab}]`).click();await p.waitForTimeout(150);}
assert.deepEqual(errors,[]);console.log('BILINGUAL PASS: reversible translations, persisted language, identical column positions, unchanged titles and prompts, all tabs, no JS errors');
}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
