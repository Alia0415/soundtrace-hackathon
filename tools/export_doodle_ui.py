"""Publish generated UI boards; format export only, no image retouching."""
import json
import shutil
import zipfile
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'webapp' / 'assets' / 'ui-doodle-v1'

def export():
    spec = json.loads((DEST / 'prompts.json').read_text(encoding='utf-8-sig'))
    assets, missing = [], []
    for board in spec['boards']:
        latest = DEST / (board['id'] + '-v2.png')
        original = DEST / (board['id'] + '.png')
        source = latest if latest.is_file() else original
        if not source.is_file():
            missing.append(board['id'])
            continue
        webp = DEST / (board['id'] + '.webp')
        with Image.open(source) as image:
            size = image.size
            image.convert('RGB').save(webp, quality=92, method=4)
        assets.append({'id':board['id'], 'title':board['title'], 'category':board['category'],
                       'controls':board['controls'], 'png':source.name, 'webp':webp.name,
                       'width':size[0], 'height':size[1], 'revised':source == latest})
    result = {'generator':'built-in image_gen', 'count':len(assets), 'expected':len(spec['boards']),
              'assets':assets, 'missing':missing, 'deliverable':'static UI design proposals, not a running app'}
    (DEST / 'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    for filename in ('UI_DOODLE_DESIGN_SYSTEM.md','UI_REDESIGN_BRIEF.md'):
        shutil.copyfile(ROOT / 'docs' / filename, DEST / filename)
    rows = '\n'.join(f"| {a['id']} | {a['title']} | {a['controls']} |" for a in assets)
    readme = f'''# 声迹 · 黑白线描 UI 全站设计图

已完成 {len(assets)} / {len(spec['boards'])} 张独立设计图。

生成方式：内置 image_gen；用户截图作为风格参考。修订稿使用对应初稿进行定向修改。

PNG保留原始分辨率，WebP为同尺寸网页预览。设计图为静态视觉稿，正式页面未被替换。粒子与播放器在实现时复用原Mineradio引擎；地图使用真实底图和坐标，不能将设计图当作地图底图。

- `preview.html`：分类预览、放大与单张下载。
- `prompts.json`：完整生成提示词及定向修订记录。
- `manifest.json`：实际文件、分辨率、最终修订选择。
- `UI_DOODLE_DESIGN_SYSTEM.md`：色彩、字体、结构和动效方向。
- `UI_REDESIGN_BRIEF.md`：逐项功能清单；实现时按此核对输入、按键与条件状态。

设计示例日期、用户内容、计时、字符计数是占位。高级AI、识别服务与真实信件投递以实际服务状态为准。按键图形需要在实现中做成独立控件，不能把整张设计图直接当页面。

| 文件 | 设计图 | 功能核对 |
|---|---|---|
{rows}
'''
    (DEST / 'README.md').write_text(readme,encoding='utf-8')
    if not missing and len(assets) == len(spec['boards']):
        with zipfile.ZipFile(DEST / 'soundtrace-doodle-ui-designs.zip','w',zipfile.ZIP_DEFLATED) as archive:
            for a in assets:
                archive.write(DEST / a['png'], a['png'])
                archive.write(DEST / a['webp'], a['webp'])
            for filename in ('preview.html','README.md','manifest.json','prompts.json','UI_DOODLE_DESIGN_SYSTEM.md','UI_REDESIGN_BRIEF.md'):
                archive.write(DEST / filename,filename)
    print(json.dumps({'completed':len(assets),'missing':missing,'revised':sum(a['revised'] for a in assets)},ensure_ascii=False))
    return result

if __name__ == '__main__':
    export()
