"""Exercise redesigned controls against an isolated database and synthetic media."""
import io,sys,tempfile,threading,time,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime/test-deps'))
import uvicorn
from PIL import Image
from playwright.sync_api import sync_playwright
from soundtrace_public import create_app
with tempfile.TemporaryDirectory() as folder:
 server=uvicorn.Server(uvicorn.Config(create_app(folder),host='127.0.0.1',port=0,log_level='warning'))
 worker=threading.Thread(target=server.run,daemon=True);worker.start()
 for _ in range(100):
  if server.started:break
  time.sleep(.05)
 assert server.started
 base='http://127.0.0.1:'+str(server.servers[0].sockets[0].getsockname()[1])
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=True)
   context=browser.new_context(viewport={'width':390,'height':844});page=context.new_page();errors=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   assert context.request.post(base+'/api/auth/register',data={'username':'selected_ui','password':'Temporary-ui-pass-123'}).ok
   page.goto(base+'/album',wait_until='domcontentloaded');page.locator('#stripAva').click();page.locator('#pNameIn').wait_for()
   page.locator('#pNameIn').fill('海边的小声');page.locator('#pSave').click()
   page.wait_for_function("document.querySelector('#pName').textContent==='海边的小声'")
   avatar=page.locator('#pAvas button').nth(3);avatar.click()
   page.wait_for_function("document.querySelectorAll('#pAvas button')[3].getAttribute('aria-pressed')==='true'")
   assert page.locator('#pAvas button').count()==8
   image=io.BytesIO();Image.new('RGB',(320,200),'#00a8f0').save(image,format='PNG')
   file={'name':'synthetic.png','mimeType':'image/png','buffer':image.getvalue()}
   page.locator('#pAvaFile').set_input_files(file);page.locator('#pAva img').wait_for()
   page.locator('#pBgFile').set_input_files(file)
   page.wait_for_function("getComputedStyle(document.querySelector('#pBg')).backgroundImage.includes('/outputs/')")
   page.locator('#pCheckin').click();page.wait_for_function("document.querySelector('#pStats b').textContent.startsWith('1')")
   page.locator('#closeModal').click()
   page.goto(base+'/community',wait_until='domcontentloaded');page.locator('#openCompose').click()
   page.locator('#composeText').fill('UI 检查：海风与脚步');page.locator('#composeCovers button').nth(1).click()
   page.locator('.compose-submit').click();article=page.locator('.community-post').filter(has_text='UI 检查：海风与脚步');article.wait_for()
   article.locator('.community-like').click();page.wait_for_function("document.querySelector('.community-like').getAttribute('aria-pressed')==='true'")
   article.locator('.community-reply').click();page.locator('.community-replies textarea').fill('听见了海风')
   page.locator('.community-replies button[type=submit]').click();page.locator('.reply-list').filter(has_text='听见了海风').wait_for()
   page.get_by_role('button',name='关闭回应',exact=True).click()
   article.locator('.community-delete').click();page.locator('.st-delete-dialog').get_by_role('button',name='取消',exact=True).click();assert article.count()==1
   article.locator('.community-delete').click();page.locator('.st-delete-dialog').get_by_role('button',name='确认删除',exact=True).click();article.wait_for(state='detached')
   page.locator('.st-account-button').click();page.get_by_role('button',name='修改密码',exact=True).click()
   page.locator('input[name=current_password]').fill('Temporary-ui-pass-123');page.locator('input[name=password]').fill('Temporary-ui-new-456')
   page.get_by_role('button',name='显示密码',exact=True).last.click();assert page.locator('input[name=password]').get_attribute('type')=='text'
   page.get_by_role('button',name='保存新密码',exact=True).click();page.locator('.st-account-dialog[open]').wait_for(state='detached')
   assert not errors,errors
   browser.close();print('PASS: nickname, 8 avatars, avatar/background uploads, check-in, publish, like, reply, delete cancel/confirm, password change; no script errors')
 finally:
  server.should_exit=True;worker.join(timeout=5)
