"""Build reference-by-reference audit without changing product pages."""
import collections
import html
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'webapp/assets/ui-doodle-v1'
OUT = ROOT / 'webapp/assets/ui-application-audit'
OUT.mkdir(parents=True, exist_ok=True)
SHOTS = ROOT / 'docs/previews/ui-application-audit'

# Fidelity to the reference, separate from whether the underlying function exists.
rows = [
    (1, '主体已用', 'home', '手机首页海景和传声筒直接裁自 01；标题、录音入口、地图和导航为真实控件。', '有独立手机排布。示例内容和文字随功能更新，没有把整图铺成页面。'),
    (2, '主体已用', 'home', '电脑首页右侧海景、唱片和桌面物件直接裁自 02，左侧文字、右侧插画。', '有独立桌面排布；与手机版使用不同的插画裁切。'),
    (3, '部分应用', 'capture', '录音插画来自 03，但标题区复用了素材库插画；电脑为左右布局。', '手机有麦克风原图，但缺少稿中顶部 00:00 的独立计时；待录音按钮比例和位置仍不同。'),
    (4, '部分应用', 'recording', '录音状态、计时、停止按钮、音量反馈可用；插画沿用 03。', '04 的蓝色横向声波、红色停止环和录音中构图未采用。截图用模拟麦克风。'),
    (5, '未按稿落地', 'permission-error', '权限错误是录音页下方的提示条，并保留导入入口。', '05 的麦克风禁用图、专用标题和主次按键布局未采用，没有独立错误页。'),
    (6, '新流程替代', None, '录音结束后的重复填写表单已按你的要求取消，直接保存原声并留在素材库。', '06 不应整页恢复；填写信息放在后面的逐步选择和故事页。'),
    (7, '新流程替代', 'library', '原声保存后留在素材库，显示保存状态并提供生成日记入口。', '没有 07 的独立原声成功页；可以复用成功插画，但保留当前少跳转的流程。'),
    (8, '部分应用', 'library', '素材库标题插画来自 08，磁带使用提取后的物件；试听、保存、生成、素材列表可用。', '手机排列有适配，但未逐项还原 08；顶部示例音频区和录音等入口已按最新要求移除。'),
    (9, '部分应用', 'library', '电脑素材库是居中的当前音频和纵向素材列表，插画复用 08。', '09-v2 的左素材栏、中间大磁带、右侧示例栏三栏布局没有落地。右侧示例栏应继续删除。'),
    (10, '新流程替代', 'studio', '顶部“我的示例音频”上传、复用、替换、删除整组已移除。', '正式导入仅上传本地音频，演示版多一个演示音频按钮，10 的三个状态框不再恢复。'),
    (11, '部分应用', 'weather', '心情、天气、状态和音乐风格图标确实裁自 11。', '按新流程拆成天气→心情→状态→照片/笔记/位置→音乐，不能照旧稿把所有选择堆在一页。'),
    (12, '部分应用', 'editor', '播放、撤销重做、缩放、轨道编辑、混合控制、保存均有真实控件，使用唱片物件。', '12 的右上插画组合、蓝黄双轨视觉、工具和边景排布未完整采用；不能用静态第二轨冒充生成结果。'),
    (13, '部分应用', 'editor', '音乐微调已有手机堆叠布局、播放和轨道编辑，使用唱片物件。', '13-v2 顶部情境插画条、封面与播放区组合、间距及底部收藏布局尚未完整落地。'),
    (14, '部分应用', 'editor-advanced', '细调可展开，片段、出现位置、原声起终点可编辑；AI 按服务状态禁用。', '14-v2 的细调编排及 A/B、等待和失败状态未完整套用；辨认、提取、哼唱入口仍不可用。'),
    (15, '部分应用', 'music-save', '音乐保存弹窗使用唱片和六个手绘场景缩略图，保留真实输入和已有信息。', '15-v2 未整页采用；目前是弹窗，部分信息沿用前一步。改版需避免再次要求填重复选择题。'),
    (16, '新流程替代', 'music-success', '音乐保存成功自动进入收藏间，并显示同步社区和远方寄出按钮。', '16 的独立全屏成功页未采用；应保留后来指定的收藏间内成功交互，可只借用成功插画。'),
    (17, '主体已用', 'album', '手机专用房间背景由 17 清理而来：柜子在左、窗在右，照片和物件是可交互覆盖层。', '有独立手机背景；真实照片和其他场景是动态内容，不会把稿里的照片数量固定进去。'),
    (18, '主体已用', 'album', '电脑背景由 18-v2 清理而来：右立体柜、左照片绳，拖动投递箱原图也已接入。', '有独立电脑背景，拖动触发箱子；挂图数量和照片根据记忆变化，不是整图覆盖。'),
    (19, '未按稿落地', None, '源码保留简易物件说明弹窗及原生音频控件；可播放物件点击会直接进入沉浸聆听。', '19 的封面组合、手绘详情及播放器布局没落地；detail 虽登记在裁切表中，当前入口未实际渲染。'),
    (20, '未按稿落地', 'profile', '头像和背景上传、昵称、默认头像、签到、寄出信息均有功能。', '仍为通用白色弹窗，默认头像是 emoji；20 的海景横幅、手绘头像组和个人资料构图未应用。'),
    (21, '未按稿落地', 'listening', '电脑聆听保留 Mineradio 粒子、原播放器和右侧 3D 藏品选择。', '21 的白纸背景、左柜子和传声筒装饰未接入，目前仍是深色舞台。后续只改外围 UI，保留原粒子和播放器。'),
    (22, '未按稿落地', 'listening', '手机聆听保留原引擎、粒子、播放器和藏品操作。', '22 的白底上下排布、夹住的照片框、底部传声筒和信箱装饰未接入，目前不是这张手机稿构图。'),
    (23, '部分应用', 'map', '演示地图使用从 23 提取的手机西湖底图，有可点地标、详情、虚线路线和下方横向足迹。', '23 的脚印造型及部分边景和播放器细节未完整还原；演示已有虚线路线。正式高德 Key 未配置，真实地图仍待完成。'),
    (24, '部分应用', 'map', '演示地图使用从 24 提取的电脑西湖底图，有右侧足迹列表和地图详情。', '两端底图确实不同；正式真实地图和自定义手绘样式仍待高德配置、验收，不能用一张西湖图片代替全国地图。'),
    (25, '部分应用', 'community', '社区演示图文中的风景照片直接裁自 25；音频、喜欢和回应功能存在。', '手机顶部飞鸟和线条装饰未完整采用，间距和播放器仍不同；正式社区由真实发布填充。'),
    (26, '部分应用', 'community', '社区电脑左右传声筒和柜子边景直接来自 26，正文为真实动态。', '主要边景已用，但列表密度、标题、头像、播放器仍不同；手机不照搬电脑边景。'),
    (27, '部分应用', 'composer', '发布和回应在信息流内展开；27-v2 六张风景用于收藏场景和地图地标等。', '发布选择区仍用旧 scenes-v1 彩色插画；27 发布/回应双手机稿、回信边景、选择布局没整体落地。'),
    (28, '部分应用', 'inbox', '信箱和寄出使用了提取的手绘信箱物件，来信、寄出、音频、交换选项已有功能。', '28-v2 两个独立页面构图、来信纸张和海景未完整应用；正式信件功能已比旧稿的预留状态更新。'),
    (29, '未按稿落地', 'login', '登录和注册是通用弹窗，输入、显示密码、切换和提交存在。', '29-v2 登录传声筒、注册柜子和信箱、双页背景未接入，没有独立两端登录视觉。'),
    (30, '未按稿落地', 'account', '账号管理是通用弹窗，资料、密码、退出、许可、发布和删除记忆均有功能。', '30-v2 手绘物件列表缩略图、笔记本底部背景和独立账号页未应用，两端只是同一弹窗适配。'),
    (31, '未按稿落地', 'password', '修改密码和删除确认使用通用弹窗。', '31 的密码/垃圾桶插画、错误框和删除确认专用构图未采用。本次未填写密码或执行删除。'),
    (32, '未按稿落地', 'formal-map', '空态、处理中、失败和禁用由各组件文字/按钮反馈，部分空态复用信箱。', '32-v2 的专用插画、盒子、垃圾桶和失败布局未成为统一两端组件；已取消的示例状态不应恢复。'),
    (33, '部分应用', 'mood-other', '其他输入、选中和继续操作有功能，复用 11 的图标。', '33 不同天气/心情/状态的页面头图和输入提醒布局未逐项接入，当前每步都复用同一耳机头图。'),
]

manifest = json.loads((BASE / 'manifest.json').read_text(encoding='utf-8'))['assets']
screens = json.loads((SHOTS / 'screenshots.json').read_text(encoding='utf-8'))
for rec in screens['records']:
    src = SHOTS / rec['screenshot']
    im = Image.open(src).convert('RGB')
    im.thumbnail((1100, 3600))
    im.save(OUT / (src.stem + '.jpg'), quality=88)
assets = []
for n, status, current, evidence, gap in rows:
    a = dict(manifest[n - 1])
    a.update(number=n, status=status, current=current, evidence=evidence, gap=gap)
    assets.append(a)
counts = dict(collections.Counter(a['status'] for a in assets))
(OUT / 'audit.json').write_text(json.dumps({'date': '2026-10-08', 'assets': assets,
    'screenshots': screens['records'], 'counts': counts}, ensure_ascii=False, indent=2), encoding='utf-8')

md = [
    '# 全站设计图应用核对 · 2026-10-08', '',
    '核对范围：33 张最新 UI 设计稿（以 manifest.json 选定的修订 PNG 为准）、真实引用代码、电脑 1440×1000 和手机 390×844 的 64 张页面/弹窗截图。演示内容使用隔离浏览器，账号管理使用合成只读响应；没有修改真实账号、录音或发布数据。', '',
    '**“应用”指视觉、构图和素材实际进入页面；功能已存在不等于设计稿已应用，也不能以文件登记或打包作为证据。**', '',
    '## 结论', '',
    '- 主体已用：4 张（01、02、17、18）。',
    '- 部分应用：16 张（03、04、08、09、11–15、23–28、33）。',
    '- 未按稿落地：9 张（05、19–22、29–32）。',
    '- 已被新流程替代：4 张（06、07、10、16），不建议恢复旧流程。', '',
    '明确的电脑/手机配对稿有 7 组：首页 01/02、素材库 08/09、编辑 12/13、收藏 17/18、聆听 21/22、地图 23/24、社区 25/26。其余多为单端或状态拼版，不代表每页都有两份独立完成稿。', '',
    '## 逐图核对', '',
    '|编号|设计稿|结论|已经应用|未应用与两端差异|', '|---|---|---|---|---|',
]
for a in assets:
    md.append(f"|{a['number']:02d}|[{a['title']}]({(BASE/a['png']).as_posix()})|{a['status']}|{a['evidence']}|{a['gap']}|")
md += [
    '', '## 正式版和演示版', '',
    '- 首页、收藏间和输入控件共享 UI；演示版有本地示例，正式版展示真实账号内容。',
    '- 演示地图已用手机/电脑两张手绘西湖底图；正式版走高德 API，当前 Key 未配置，显示服务提示，正式多地点手绘地图仍待接入和验收。',
    '- 社区设计风格示例只在演示版；正式社区由用户真实发布填充。',
    '- 收藏背景正式版使用真实照片；手绘生成服务待配置。无照片时显示白底文字，不能用固定设计图覆盖用户真实记忆。',
    '- 音频导入正式版只有“上传本地音频”，演示版另加“演示音频”，顶部示例音频框两版都已删除。', '',
    '## 其他尚未使用的资产', '',
    '早期 diary-options-generated-v1 的 26 张彩色手绘心情/天气/状态插画，目前未用于现行选择页。现行页面采用 11 号黑白线描稿的图标裁切。这批为旧风格可选资产，不属于遗漏的页面设计。', '',
    '## 选择和后续修改', '',
    '[打开设计图与当前页面对照、分别按端选择](http://127.0.0.1:8093/assets/ui-application-audit/preview.html)', '',
    '对照页可勾选网页端或手机端，导出 JSON 清单；也可直接回复“网页端用 09、12、21；手机端用 13、20、22”。两端分别修改，未选页面保持现状。此页只记录选择，不会自动修改产品 UI。', '',
    '建议优先：聆听 21/22、素材库 08/09、音乐编辑 12/13、个人资料 20、账号 29/30/31。地图和社区可再决定补齐程度。', '',
    '## 当前截图证据', '',
    '截图位于 docs/previews/ui-application-audit；screenshots.json 记录路由、端及可见素材引用；audit.json 记录全部 33 张结论。', '',
]
for r in screens['records']:
    md.append(f"- [{r['key']} · {r['device']}]({(SHOTS/r['screenshot']).as_posix()})" + (f"：{r['note']}" if r['note'] else ''))
(ROOT / 'docs/UI_DESIGN_APPLICATION_AUDIT.md').write_text('\n'.join(md), encoding='utf-8')

body = []
esc = lambda s: html.escape(s, quote=True)
for a in assets:
    matched = [r for r in screens['records'] if r['key'] == a['current']] if a['current'] else []
    evidence = ''.join(f'<figure class="live {r["device"]}"><figcaption>当前{("网页端" if r["device"]=="desktop" else "手机端")}</figcaption><a href="{Path(r["screenshot"]).stem}.jpg" target="_blank"><img src="{Path(r["screenshot"]).stem}.jpg" loading="lazy" alt="当前{esc(a["title"])}"></a></figure>' for r in matched)
    if not evidence:
        evidence = '<p class="none">当前没有对应独立页面，请阅读原因，避免恢复已取消的操作。</p>'
    body.append(f'<article data-status="{esc(a["status"])}" data-id="{esc(a["id"])}"><header><h2>{a["number"]:02d} · {esc(a["title"])}</h2><span class="badge">{esc(a["status"])}</span></header><div class="compare"><figure><figcaption>最终稿 · {esc(a["png"])}</figcaption><a href="/assets/ui-doodle-v1/{esc(a["png"])}" target="_blank"><img src="/assets/ui-doodle-v1/{esc(a["webp"])}" loading="lazy" alt="设计稿：{esc(a["title"])}"></a></figure>{evidence}</div><p><b>已应用：</b>{esc(a["evidence"])}</p><p><b>待核对：</b>{esc(a["gap"])}</p><div class="choices"><label><input type="checkbox" data-device="desktop"> 网页端加入修改清单</label><label><input type="checkbox" data-device="mobile"> 手机端加入修改清单</label></div></article>')

page = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>声迹 · 设计图应用核对</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f6f7;color:#21252b;font:15px/1.7 system-ui,'Microsoft YaHei',sans-serif}main{max-width:1420px;margin:auto;padding:30px 24px}h1{font-size:30px;margin:0 0 10px}h2{font-size:21px;margin:0}.intro{max-width:1080px}.tools{position:sticky;top:0;z-index:2;background:#fffef7ee;padding:14px;display:flex;align-items:center;flex-wrap:wrap;gap:12px;border-bottom:1px solid #ddd;backdrop-filter:blur(8px)}button,select{min-height:44px;padding:8px 14px;border:1px solid #9cabb5;background:#fff;color:#20252c;border-radius:7px;font:inherit;cursor:pointer}button.primary{background:#087cb3;color:white;border-color:#087cb3}article{background:white;margin:22px 0;padding:22px;border-radius:10px;border:1px solid #e1e5e8}article>header{display:flex;gap:15px;justify-content:space-between;align-items:center;margin-bottom:14px}.badge{padding:4px 10px;background:#eaf5fb;border-radius:6px;white-space:nowrap;font-size:13px}.compare{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}figure{margin:0;background:#f3f4f5;padding:12px;min-width:0;display:flex;flex-direction:column;align-items:center}figcaption{font-size:12px;color:#50606b;margin-bottom:10px;overflow-wrap:anywhere;text-align:center}figure>a{display:flex;align-items:flex-start;justify-content:center;width:100%;height:450px;overflow:auto}figure img{max-width:100%;max-height:450px;object-fit:contain;height:auto}article p{margin:16px 0}.choices{display:flex;gap:24px;flex-wrap:wrap;border-top:1px solid #eee;padding-top:14px}label{display:flex;align-items:center;gap:8px;min-height:44px;cursor:pointer}input[type=checkbox]{width:19px;height:19px;accent-color:#087cb3}a{color:#087cb3}button:focus-visible,a:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #00a8f0;outline-offset:3px}.none{padding:30px;background:#fafafa}.hint{color:#58666e;font-size:13px}.summary{display:flex;gap:14px;flex-wrap:wrap}article[hidden]{display:none}@media(max-width:760px){main{padding:22px 14px}h1{font-size:24px}.compare{grid-template-columns:1fr}figure>a{height:auto;max-height:500px}figure img{max-height:500px}article{padding:16px}article>header{align-items:flex-start}h2{font-size:18px}.tools{position:relative}.choices{gap:6px;flex-direction:column}}
</style></head><body><main><h1>声迹 · 全站设计图应用核对</h1><div class="intro"><p>2026-10-08 · 33 张最终稿，64 张当前电脑/手机截图。功能存在与设计稿正式应用分开核对。</p><p class="summary"><b>主体已用 4</b><b>部分应用 16</b><b>未按稿落地 9</b><b>新流程替代 4</b></p><p>正式地图未配置高德 Key；手绘西湖对照是演示版。首页、素材库、编辑、收藏、聆听、地图、社区共 7 组有明确两端配对稿，其余多为单端或状态拼版。</p><p class="hint">这里只做对照和选择，不会修改产品页面或发送个人信息。选择仅保存在本浏览器；点开图片可查看完整原图。账号和权限截图来自隔离模拟状态。</p></div><div class="tools"><label>范围 <select id="filter"><option>全部</option><option>未按稿落地</option><option>部分应用</option><option>主体已用</option><option>新流程替代</option><option>已选</option></select></label><button id="export" class="primary">导出两端修改清单</button><span id="count" role="status"></span><a href="/assets/ui-doodle-v1/preview.html">原设计图总览 ↗</a></div>'''
page += ''.join(body)
page += '''<section><h2>额外资产说明</h2><p>早期 26 张彩色手绘心情/天气/状态图标未用于现行页面，当前采用 11 号稿的黑白线描图标。<a href="/assets/diary-options-generated-v1/preview.html">查看旧图标资产 ↗</a></p><p>真实地图、正式照片和手绘模型属于接入工作，不能用固定设计图代替真实用户内容。</p></section></main><script>
const storageKey='soundtrace-ui-application-audit-selections-v1';let selected={};try{selected=JSON.parse(localStorage.getItem(storageKey)||'{}')}catch{}const articles=[...document.querySelectorAll('article')];function update(){let count=0;articles.forEach(a=>{a.querySelectorAll('input').forEach(i=>{const key=a.dataset.id+':'+i.dataset.device;i.checked=!!selected[key];if(i.checked)count++});const f=document.querySelector('#filter').value;a.hidden=f==='已选'?!a.querySelector('input:checked'):f!=='全部'&&a.dataset.status!==f});document.querySelector('#count').textContent='已选 '+count+' 项（按端计数）'}articles.forEach(a=>a.querySelectorAll('input').forEach(i=>i.addEventListener('change',()=>{selected[a.dataset.id+':'+i.dataset.device]=i.checked;try{localStorage.setItem(storageKey,JSON.stringify(selected))}catch{}update()})));document.querySelector('#filter').addEventListener('change',update);document.querySelector('#export').onclick=()=>{const changes=articles.flatMap(a=>[...a.querySelectorAll('input:checked')].map(i=>({design:a.dataset.id,device:i.dataset.device,title:a.querySelector('h2').textContent,status:a.dataset.status})));const url=URL.createObjectURL(new Blob([JSON.stringify({product:'声迹',audit_date:'2026-10-08',changes,note:'仅为选择清单，尚未执行产品 UI 修改'},null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='声迹-两端UI修改清单.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};update();</script></body></html>'''
(OUT / 'preview.html').write_text(page, encoding='utf-8')
print('Built audit report and gallery:', counts)
