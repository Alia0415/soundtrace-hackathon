# 声迹：独立手绘选择页资产 v1

生成方式：内置 image_gen，每个资产单独调用生成，没有从拼图裁切。

完成 26 / 26：心情8张、天气7张、状态10张、通用其他1张。

- `名称-master.png`：保留生成的高清透明原图。
- `名称.png`：512×512透明PNG。
- `名称.webp`：512×512透明WebP网页版本。
- `prompts.json`：完整提示词集。
- `manifest.json`：文件名、中文含义、原图尺寸、透明度检查和完成清单。
- `preview.html`：按类别查看全部资产并下载各个文件。预览棋盘格不在图片里。

素材保存为新版本，现有SVG占位和网页交互未覆盖。接入时可把 DiarySetup.jsx 中的 ChoiceArt 图片引用改为 `/assets/diary-options-generated-v1/${id}.webp`。
