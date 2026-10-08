"""Annotated UI regressions; demo storage and fake microphone only."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime/test-deps'))
from playwright.sync_api import sync_playwright
OUT=ROOT/'docs/previews/ui-comments-v4';OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=True,args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream'])
 for width,height in [(986,651),(1440,1000),(390,844),(320,760)]:
  if len(sys.argv)>1 and width!=int(sys.argv[1]):continue
  context=browser.new_context(viewport={'width':width,'height':height},permissions=['microphone']);page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  def shot(key):
   page.evaluate("async()=>await Promise.race([Promise.all([...document.images].map(i=>i.decode().catch(()=>{}))),new Promise(r=>setTimeout(r,1000))])")
   page.screenshot(path=str(OUT/f'{key}-{width}.png'),full_page=key not in ['listening','generation-failed'])
  page.goto('http://127.0.0.1:8093/demo/community',wait_until='domcontentloaded');page.locator('.community-post').first.wait_for()
  assert page.locator('.community-tabs').bounding_box()['y']+page.locator('.community-tabs').bounding_box()['height']<=page.locator('.community-post').first.bounding_box()['y']+1
  for action in ['.community-delete','.community-share']:
   button=page.locator(action).first;button.scroll_into_view_if_needed()
   assert button.evaluate("e=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}")
  page.evaluate('scrollTo(0,0)');shot('community')
  page.goto('http://127.0.0.1:8093/demo/map',wait_until='domcontentloaded');page.locator('.atlas-pin').first.wait_for();assert page.locator('#mapMemory').is_hidden();shot('map')
  page.locator('.atlas-pin').first.click();assert page.locator('#mapMemory').is_visible()
  if width<=760:assert page.locator('#mapMemory').bounding_box()['width']<=210
  shot('map-detail');page.get_by_role('button',name='关闭足迹详情').click();assert page.locator('#mapMemory').is_hidden()
  page.goto('http://127.0.0.1:8093/demo',wait_until='domcontentloaded');shot('home');page.get_by_role('link',name='录一段声音',exact=True).click();page.get_by_role('button',name='开始录音',exact=True).wait_for();shot('capture')
  assert page.get_by_text('准备好了',exact=True).count()==1
  page.get_by_role('button',name='开始录音',exact=True).click();page.get_by_role('button',name='结束录音',exact=True).wait_for();page.wait_for_timeout(1000);shot('recording');page.get_by_role('button',name='结束录音',exact=True).click();page.locator('.raw-generate img').wait_for();shot('raw-success')
  page.get_by_role('button',name='留在素材库',exact=True).click();shot('library')
  page.get_by_role('button',name='生成音乐日记 →',exact=True).click();page.get_by_role('button',name='晴天',exact=True).click();page.get_by_role('button',name='平静',exact=True).click();page.get_by_role('button',name='散步',exact=True).click();page.get_by_role('button',name='选择音乐 →',exact=True).click()
  if width==390:page.route('**/outputs/seeds/seed_vinyl.wav',lambda r:r.fulfill(status=503,body='simulated generation audio failure'))
  page.get_by_role('button',name='轻钢琴',exact=True).click();page.locator('.timeline').wait_for()
  if width==390:
   page.locator('.music-generation-failure').wait_for();page.locator('.music-generation-failure').scroll_into_view_if_needed();shot('generation-failed');assert page.locator('.music-generation-failure img[src$="import-error.webp"]').count()==1
   page.unroute('**/outputs/seeds/seed_vinyl.wav');page.get_by_role('button',name='重试生成音乐',exact=True).click();page.locator('.music-generation-failure').wait_for(state='hidden');page.locator('.timeline [data-track-id=music]').first.wait_for()
  page.evaluate('scrollTo(0,0)');shot('editor')
  assert page.get_by_role('button',name='撤销编辑').locator('img').count()==1
  try:page.get_by_role('button',name='播放',exact=True).click(timeout=10000)
  except Exception:
   print('Playback diagnosis:',width,errors,page.locator('.notice').inner_text(),page.locator('.error').all_inner_texts(),flush=True);raise
  page.get_by_role('button',name='暂停',exact=True).wait_for();page.get_by_role('button',name='暂停',exact=True).click();page.get_by_role('button',name='回到开头').click()
  page.goto('http://127.0.0.1:8093/demo/album',wait_until='domcontentloaded');page.locator('#enterStage').click();page.locator('#listeningStage.engine-ready').wait_for(timeout=30000);page.wait_for_timeout(2000);shot('listening')
  if width<=760:
   frame=page.locator('#mineradioEngine').bounding_box();assert frame['width']<=width*.72 and frame['height']<=height*.59,frame
   tabs=page.locator('.stage-shelf-tabs').bounding_box();assert tabs['y']+tabs['height']<frame['y'],(tabs,frame)
  assert not errors,errors
  context.close()
  context=browser.new_context(viewport={'width':width,'height':height});page=context.new_page()
  page.add_init_script("navigator.mediaDevices.getUserMedia=()=>Promise.reject(Object.assign(new Error('simulated denied'),{name:'NotAllowedError'}))")
  page.goto('http://127.0.0.1:8093/capture',wait_until='domcontentloaded');page.get_by_role('button',name='开始录音',exact=True).click();page.locator('.capture-error-detail').wait_for();shot('permission-error');assert page.get_by_role('link',name='导入已有音频',exact=True).locator('img[src$="permission-import-button.webp"]').count()==1
  print('PASS',width,height,flush=True);context.close()
 browser.close()
