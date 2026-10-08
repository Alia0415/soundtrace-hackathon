"""Original vector placeholders for the diary selector. Replace with final illustration assets."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'webapp' / 'assets' / 'diary-options'
ART = {
 'mood-calm': ('平静','水面与小舟','<path d="M38 88h84l-15 20H53z"/><path d="M78 45v39h31z"/><path d="M30 122q25-12 50 0t50 0"/>'),
 'mood-happy': ('开心','花束与阳光','<path d="m62 83 18 48 18-48"/><circle cx="63" cy="63" r="15"/><circle cx="97" cy="63" r="15"/><circle cx="80" cy="44" r="15"/><path d="M70 96h20"/>'),
 'mood-excited': ('兴奋','飞起的纸飞机','<path d="m28 69 104-31-29 82-24-30z"/><path d="m79 90 53-52M56 118l-15 8"/>'),
 'mood-missing': ('思念','信封与远方灯火','<rect x="30" y="64" width="100" height="60" rx="5"/><path d="m30 65 50 35 50-35M99 41h24"/><circle cx="111" cy="35" r="8"/>'),
 'mood-sad': ('低落','雨窗与一朵花','<rect x="35" y="28" width="90" height="104" rx="4"/><path d="M80 28v104M35 80h90M53 47l-5 11M107 48l-5 11M63 102v22"/><circle cx="63" cy="97" r="9"/>'),
 'mood-tired': ('疲惫','靠枕与一杯茶','<rect x="25" y="47" width="60" height="69" rx="18"/><path d="M101 77h28v29q-14 15-28 0zM129 82q20 8 0 18M104 54q-8 8 0 16"/>'),
 'mood-hopeful': ('期待','初升太阳与嫩芽','<path d="M25 88h110M48 88a32 32 0 0 1 64 0M80 40V27M38 53l-9-8M122 53l9-8M80 134v-31q-30-22-33 0 12 18 33 10M80 115q30-31 33-8-7 17-33 15"/>'),
 'mood-nostalgic': ('怀念','旧相片与唱片','<path d="m28 40 66-7 9 96-66 7zM40 97l15-28 20 13 10-13"/><circle cx="112" cy="80" r="31"/><circle cx="112" cy="80" r="10"/>'),
 'weather-sunny': ('晴天','阳光与白云','<circle cx="75" cy="65" r="27"/><path d="M75 22v-8M75 108v8M32 65h-8M118 65h8M44 34l-7-7M106 96l7 7"/><path d="M92 119h39q18-20-4-25-8-25-29-10-25-5-22 19z"/>'),
 'weather-cloudy': ('多云','层叠云朵','<path d="M40 94h78q24-27-7-35-12-37-44-14-39-6-38 24-27 8 11 25zM37 120h81"/>'),
 'weather-rainy': ('下雨','雨滴与雨伞','<path d="M27 83a53 53 0 0 1 106 0q-13-13-27 0-13-13-26 0-13-13-26 0-14-13-27 0zM80 32v89q0 22-17 9M35 26l-4 9M119 20l-4 9"/>'),
 'weather-snowy': ('下雪','雪花与小屋','<path d="m40 89 40-36 40 36v42H40zM69 131V99h22v32M27 29v26M14 42h26M18 33l18 18M18 51l18-18M119 28v20M109 38h20"/>'),
 'weather-foggy': ('有雾','薄雾中的树','<path d="M80 29v77M80 29 54 69h52M80 45l-34 43h68M25 105h110M34 119h96M48 132h65"/>'),
 'weather-windy': ('有风','风中的叶片','<path d="M25 57h85q25 0 12-23M25 80h97q25 0 12 23M30 103h49M69 115q17 5 31-9-2 31-23 31-13-4-8-22z"/>'),
 'weather-night': ('夜晚','月亮与星光','<path d="M93 28q-36 51 23 75-52 30-74-13-25-45 51-62zM120 28v18M111 37h18M126 119v12M120 125h12"/>'),
 'activity-work': ('工作','桌面与台灯','<path d="M24 109h112M37 109v28M124 109v28M92 106V75l25-29M105 37l24 14-19 16-18-11z"/><rect x="40" y="68" width="41" height="28" rx="3"/><path d="M48 106h25M61 96v10"/>'),
 'activity-study': ('学习','书本与铅笔','<path d="M27 41q27-9 53 6 27-15 53-6v78q-27-9-53 6-27-15-53-6zM80 47v78M43 66h21M43 82h21M98 66h21M98 82h21"/>'),
 'activity-walk': ('散步','小路与步履','<path d="M63 139q-37-41 17-62t5-48M34 107q6-17 15-12t-1 18-14-6M111 75q6-17 15-12t-1 18-14-6"/>'),
 'activity-hike': ('徒步','山峦与背包','<path d="m20 96 40-62 42 62M82 95l30-47 28 47M47 54l13 8 13-8"/><rect x="55" y="85" width="52" height="53" rx="12"/><path d="M70 85v-8h22v8M65 112h32v17H65z"/>'),
 'activity-date': ('约会','双人咖啡与花','<path d="M28 83h36v28q-18 20-36 0zM64 88q17 9 0 18M95 83h36v28q-18 20-36 0zM95 88q-17 9 0 18M80 68V48"/><circle cx="80" cy="37" r="12"/>'),
 'activity-travel': ('旅行','行李箱与远方','<rect x="43" y="53" width="76" height="76" rx="10"/><path d="M66 53V35h30v18M58 67v48M104 67v48M55 129v9M107 129v9M23 43l14-9M128 35l14 9"/>'),
 'activity-commute': ('通勤','车窗与沿途风景','<rect x="29" y="27" width="102" height="106" rx="14"/><rect x="40" y="41" width="80" height="49" rx="4"/><path d="M40 79l25-22 29 17 26-22M39 112h82M49 134l-7 10M111 134l7 10"/><circle cx="49" cy="105" r="4"/><circle cx="111" cy="105" r="4"/>'),
 'activity-home': ('独处','窗边扶手椅','<rect x="83" y="29" width="50" height="58" rx="3"/><path d="M108 29v58M83 58h50M39 75V54q20-12 40 0v21M29 76h60v39H29zM38 115v19M80 115v19"/>'),
 'activity-exercise': ('运动','运动鞋与水壶','<path d="M26 106l13-33q22 28 56 35 20 5 20 18H24zM51 92l12-12M64 99l10-11"/><rect x="103" y="47" width="27" height="50" rx="7"/><path d="M111 47V35h11v12"/>'),
 'activity-gathering': ('聚会','圆桌与小串灯','<ellipse cx="80" cy="100" rx="48" ry="17"/><path d="M80 117v23M28 32q52 40 104 0M48 43v14M80 52v14M112 43v14M53 95v-13h13v13M94 95V82h13v13"/>'),
 'other': ('其他','留白与手写笔','<path d="M39 28h64l20 21v87H39zM103 28v22h20M56 66h40M56 84h23M76 119l5-16 35-35 11 11-35 35z"/>'),
}

def generate():
    DEST.mkdir(parents=True, exist_ok=True)
    rows=[]
    for asset,(label,subject,shapes) in ART.items():
        background = '#edf8fa' if asset.startswith('weather') else '#fff5e5' if asset.startswith('activity') else '#edf5fc'
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160"><circle cx="80" cy="80" r="69" fill="{background}"/><ellipse cx="80" cy="136" rx="47" ry="5" fill="#b7dce8" opacity=".35"/><g fill="#d8edf2" stroke="#367995" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">{shapes}</g></svg>'
        (DEST/f'{asset}.svg').write_text(svg,encoding='utf-8')
        rows.append(f'| `{asset}.webp` | {label} | {subject} |')
    doc='''# 音乐日记选择页：图片资产清单

页面和占位插画已经实现。当前是原创 SVG 占位，不是最终 AI 插画。

## 必做资产：26 张

- 心情 8 张、天气 7 张、状态 10 张、通用“其他”1 张。
- 每张独立文件，建议 512 × 512；主体居中，占画面约 65–75%，四周保留空白。
- 透明背景，交付 PNG 原图和 WebP 网页版；不含文字、边框、按钮、选中勾号。
- 延续参考图的温暖手绘笔触、海天蓝、奶油白、柔和金色；作为小图标时减少细节。不同组可有少量色彩变化，保持笔触、光源和视角一致。
- 文案、选中态和勾号由页面绘制，图片只负责表现内容。
- 放到 `webapp/assets/diary-options/`，文件名见下表。交付后统一修改 `studio/src/DiarySetup.jsx` 中 ChoiceArt 的图片路径为 `.webp`，重新构建。无需更改选项和交互。

| 文件名 | 选项 | 画面建议 |
|---|---|---|
'''+ '\n'.join(rows)+'''

## 可选增强资产

先不必制作十种音乐风格的封面、选中/未选中两套图或动画，当前音乐方向用轻量文字标签即可。若需要丰富选择页，可另做 1 张无文字横幅（1600 × 600），画面为窗边的声音手记、磁带与植物，主体不要影响标题阅读。

## 当前流程

录音结束 → 保存原声到账号素材库 → 点击“生成音乐日记” → 选择心情、天气、状态（每组含其他输入）→ 选择音乐方向/填写自由描述 → 进入编辑。

本地音乐是原创程序合成草稿，十种方向有不同节奏和编配；心情、天气和状态会影响和声与速度。自由描述保存到日记并用于后续 AI 任务，当前正式服务未接入 AI，不能声称自由文本已经被模型理解。生成音乐保存时更新同一条记忆，保留原声、坐标、照片和视频，不重复创建素材。
'''
    (ROOT/'docs'/'DIARY_ASSETS.md').write_text(doc,encoding='utf-8')
    print(f'Generated {len(ART)} SVG placeholders and docs/DIARY_ASSETS.md')

if __name__=='__main__':
    generate()
