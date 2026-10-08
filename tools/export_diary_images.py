"""Export imagegen PNG masters to the requested square PNG/WebP delivery formats."""
import json
import zipfile
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'webapp' / 'assets' / 'diary-options-generated-v1'

def export():
    plan = json.loads((DEST / 'prompts.json').read_text(encoding='utf-8'))
    completed = []
    missing = []
    for asset in plan['assets']:
        source = DEST / (asset['id'] + '-master.png')
        if not source.is_file():
            missing.append(asset['id'])
            continue
        with Image.open(source) as image:
            if image.width != image.height or 'A' not in image.getbands():
                raise ValueError(f'{source.name}: expected square PNG with alpha')
            image = image.convert('RGBA')
            alpha = image.getchannel('A')
            if alpha.getextrema()[0] != 0 or alpha.getbbox() is None:
                raise ValueError(f'{source.name}: transparency or foreground missing')
            # Format export only: no retouching, segmentation, background removal, or image compositing.
            delivery = image.resize((512, 512), Image.Resampling.LANCZOS)
            delivery.save(DEST / (asset['id'] + '.png'))
            delivery.save(DEST / (asset['id'] + '.webp'), quality=90, method=6)
            completed.append({**asset, 'master_dimensions':[image.width,image.height],
                              'alpha_bounds':alpha.getbbox(), 'png':asset['id']+'.png','webp':asset['id']+'.webp'})
    manifest = {'generator':'built-in image_gen','count':len(completed),'expected':len(plan['assets']),
                'format':'512x512 PNG and WebP with alpha; original PNG masters preserved',
                'assets':completed,'missing':missing}
    (DEST / 'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    readme = f'''# 声迹：独立手绘选择页资产 v1

生成方式：内置 image_gen，每个资产单独调用生成，没有从拼图裁切。

完成 {len(completed)} / 26：心情8张、天气7张、状态10张、通用其他1张。

- `名称-master.png`：保留生成的高清透明原图。
- `名称.png`：512×512透明PNG。
- `名称.webp`：512×512透明WebP网页版本。
- `prompts.json`：完整提示词集。
- `manifest.json`：文件名、中文含义、原图尺寸、透明度检查和完成清单。
- `preview.html`：按类别查看全部资产并下载各个文件。预览棋盘格不在图片里。

素材保存为新版本，现有SVG占位和网页交互未覆盖。接入时可把 DiarySetup.jsx 中的 ChoiceArt 图片引用改为 `/assets/diary-options-generated-v1/${{id}}.webp`。
'''
    (DEST / 'README.md').write_text(readme,encoding='utf-8')
    if not missing:
        with zipfile.ZipFile(DEST / 'soundtrace-diary-assets-v1.zip','w',zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(DEST.iterdir()):
                if file.is_file() and file.suffix in ('.png','.webp','.json','.md','.html'):
                    archive.write(file,file.name)
    return manifest

if __name__ == '__main__':
    result=export()
    print(json.dumps({'completed':result['count'],'missing':result['missing']},ensure_ascii=False))
