"""Capture current UI in an isolated browser; no real user account or data writes."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime/test-deps'))
from playwright.sync_api import sync_playwright
OUT=ROOT/'docs/previews/ui-application-audit';OUT.mkdir(parents=True,exist_ok=True)
records=[];errors=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=True,args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream'])
 for device,w,h in [('desktop',1440,1000),('mobile',390,844)]:
  context=browser.new_context(viewport={'width':w,'height':h},permissions=['microphone'])
  page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  def shot(key,note=''):
   path=OUT/(key+'-'+device+'.png');page.screenshot(path=str(path),full_page=True)
   art=page.evaluate("""() => [...document.querySelectorAll('img,.raster-object,.scene-slide,.leaflet-image-layer,.profile-bg,.community-art,.scene-crop')].filter(e=>e.getBoundingClientRect().width&&e.getBoundingClientRect().height&&getComputedStyle(e).visibility!=='hidden').map(e=>({tag:e.tagName,cls:String(e.className),src:e.getAttribute('src')||getComputedStyle(e).backgroundImage})).filter(a=>a.src&&a.src!=='none')""")
   print(device,key,flush=True)
   records.append({'key':key,'device':device,'url':page.url,'screenshot':path.name,'note':note,'art':art})
  for route in ['','capture','studio','map','community','album']:
   page.goto('http://127.0.0.1:8093/demo'+('/'+route if route else ''),wait_until='networkidle');shot(route or 'home')
  page.locator('#stripAva').click();page.locator('#pNameIn').wait_for();shot('profile');page.locator('#closeModal').click()
  page.locator('.memory-object.vinyl').first.locator('.send-shortcut').click(force=True);page.locator('#modalTitle').wait_for();shot('send');page.locator('#closeModal').click()
  page.locator('#inboxBtn').click();page.locator('#modalTitle').wait_for();shot('inbox');page.locator('#closeModal').click()
  page.locator('#enterStage').click();page.locator('#listeningStage:not([hidden])').wait_for();page.wait_for_timeout(1500);shot('listening');page.locator('#stageClose').click()
  page.goto('http://127.0.0.1:8093/demo/map',wait_until='networkidle');page.locator('#list .footprint-open').first.click();page.locator('#mapMemory:not([hidden])').wait_for();shot('map-detail')
  page.goto('http://127.0.0.1:8093/demo/community',wait_until='networkidle');page.locator('#openCompose').click();shot('composer');page.locator('#composeCancel').click();page.locator('.community-post').first.get_by_role('button',name='回应',exact=False).click();shot('replies')
  page.goto('http://127.0.0.1:8093/demo/studio',wait_until='networkidle');page.get_by_role('button',name='演示音频',exact=True).click();page.get_by_role('button',name='生成音乐日记 →',exact=True).wait_for();shot('library');page.get_by_role('button',name='生成音乐日记 →',exact=True).click();shot('weather')
  page.get_by_role('button',name='晴天',exact=True).click();shot('mood');page.get_by_role('button',name='其他',exact=True).click();shot('mood-other');page.get_by_label('其他心情').fill('温柔');page.get_by_role('button',name='继续 →',exact=True).click();shot('activity');page.get_by_role('button',name='散步',exact=True).click();shot('story');page.get_by_label('给这一刻起个名字').fill('界面核对 · 湖边晚风');page.get_by_role('button',name='选择音乐 →',exact=True).click();shot('music-style');page.get_by_role('button',name='轻钢琴',exact=True).click();page.locator('.timeline').wait_for();shot('editor')
  page.get_by_role('button',name='细调 ＋',exact=True).click();shot('editor-advanced');page.get_by_role('button',name='收藏这段声音 ↗',exact=True).click();page.locator('.save-dialog[open]').wait_for();shot('music-save');page.get_by_role('button',name='保存这段记忆 ↗',exact=True).click();page.get_by_role('heading',name='这一刻，已收藏',exact=True).wait_for();shot('music-success')
  page.goto('http://127.0.0.1:8093/demo/capture',wait_until='networkidle');page.get_by_role('button',name='开始录音',exact=True).click();page.get_by_role('button',name='结束录音',exact=True).wait_for();shot('recording')
  context.close()
  # Controlled UI states, synthetic local responses only. No account creation or deletion.
  context=browser.new_context(viewport={'width':w,'height':h});page=context.new_page()
  page.add_init_script("navigator.mediaDevices.getUserMedia=()=>Promise.reject(Object.assign(new Error('audit denied'),{name:'NotAllowedError'}));")
  page.goto('http://127.0.0.1:8093/capture',wait_until='networkidle');page.get_by_role('button',name='开始录音',exact=True).click();page.locator('.error[role=alert]').wait_for();shot('permission-error','模拟拒绝权限，不代表用户设备状态')
  page.goto('http://127.0.0.1:8093/',wait_until='networkidle');page.locator('.st-account-button').click();page.locator('.st-account-dialog[open]').wait_for();shot('login');page.get_by_role('button',name='创建账号',exact=True).click();shot('register');page.get_by_role('button',name='关闭账号窗口',exact=True).click()
  page.goto('http://127.0.0.1:8093/map',wait_until='networkidle');shot('formal-map','当前未配置高德 Key 的真实空态')
  context.close()
  context=browser.new_context(viewport={'width':w,'height':h});page=context.new_page()
  def fake(r):
   path=r.request.url.split(':8093')[-1]
   if r.request.method!='GET':return r.fulfill(status=409,json={'detail':'UI audit: writes blocked'})
   if path=='/api/auth/session':return r.fulfill(json={'user':{'id':'audit-user','name':'界面核对','username':'audit'}})
   if path=='/api/memories':return r.fulfill(json={'memories':[{'id':'audit-memory','title':'湖边的一段声音'}]})
   return r.continue_()
  page.route('**/api/**',fake)
  page.goto('http://127.0.0.1:8093/',wait_until='networkidle');page.locator('.st-account-button').click();page.get_by_role('button',name='删除记忆',exact=True).wait_for();shot('account','模拟已登录和一条记忆，仅用于展示布局')
  page.get_by_role('button',name='删除记忆',exact=True).click();page.locator('.st-delete-dialog[open]').wait_for();shot('delete-confirm','仅打开确认窗，没有执行删除');page.locator('.st-delete-dialog').get_by_role('button',name='取消',exact=True).click();page.get_by_role('button',name='修改密码',exact=True).click();shot('password','未填写或提交任何密码')
  context.close()
 browser.close()
(OUT/'screenshots.json').write_text(json.dumps({'records':records,'page_errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
print('Captured',len(records),'screenshots. Page errors:',errors)
