"""Refresh only the reviewed comparison images from verified browser captures."""
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'webapp/assets/ui-selected-v3'
SHOTS=ROOT/'docs/previews/ui-comments-v4'
for device,width in [('desktop',1440),('mobile',390)]:
 for key in ['home','capture','community','library','editor','raw-success','recording','listening','map','map-detail','permission-error']:
  # The map gallery now shows the requested collapsed entry state.
  source=SHOTS/f'{"map" if key=="map-detail" else key}-{width}.png'
  if not source.exists():continue
  with Image.open(source) as im:im.convert('RGB').save(DEST/f'{key}-{device}.jpg',quality=82,optimize=True)
with Image.open(SHOTS/'generation-failed-390.png') as im:im.convert('RGB').save(DEST/'generation-failed-mobile.jpg',quality=82,optimize=True)
p=DEST/'preview.html';s=p.read_text(encoding='utf-8')
if '20 条批注' not in s:
 s=s.replace('<main>','<p style="padding:0 24px;max-width:1400px;margin:auto">已更新 20 条批注：指定按钮直接使用原稿整图，地图默认收起，手机粒子窗口居中缩小，社区装饰不遮挡操作。<a href="/demo/community">社区实测 →</a>　<a href="/demo/map">地图实测 →</a></p><main>')
 s=s.replace('</main>','<article><h2>音乐生成失败 · 手机端 · 晕倒磁带</h2><p>通过浏览器模拟一次音乐读取失败，展示真实失败状态。重试后可恢复播放；原声与编辑均保留。</p><img src="generation-failed-mobile.jpg" style="max-width:390px" alt="音乐生成失败与重试按钮"></article></main>')
p.write_text(s,encoding='utf-8')
print('Updated annotated comparison images')
