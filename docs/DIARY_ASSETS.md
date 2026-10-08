# 音乐日记选择页：图片资产清单

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
| `mood-calm.webp` | 平静 | 水面与小舟 |
| `mood-happy.webp` | 开心 | 花束与阳光 |
| `mood-excited.webp` | 兴奋 | 飞起的纸飞机 |
| `mood-missing.webp` | 思念 | 信封与远方灯火 |
| `mood-sad.webp` | 低落 | 雨窗与一朵花 |
| `mood-tired.webp` | 疲惫 | 靠枕与一杯茶 |
| `mood-hopeful.webp` | 期待 | 初升太阳与嫩芽 |
| `mood-nostalgic.webp` | 怀念 | 旧相片与唱片 |
| `weather-sunny.webp` | 晴天 | 阳光与白云 |
| `weather-cloudy.webp` | 多云 | 层叠云朵 |
| `weather-rainy.webp` | 下雨 | 雨滴与雨伞 |
| `weather-snowy.webp` | 下雪 | 雪花与小屋 |
| `weather-foggy.webp` | 有雾 | 薄雾中的树 |
| `weather-windy.webp` | 有风 | 风中的叶片 |
| `weather-night.webp` | 夜晚 | 月亮与星光 |
| `activity-work.webp` | 工作 | 桌面与台灯 |
| `activity-study.webp` | 学习 | 书本与铅笔 |
| `activity-walk.webp` | 散步 | 小路与步履 |
| `activity-hike.webp` | 徒步 | 山峦与背包 |
| `activity-date.webp` | 约会 | 双人咖啡与花 |
| `activity-travel.webp` | 旅行 | 行李箱与远方 |
| `activity-commute.webp` | 通勤 | 车窗与沿途风景 |
| `activity-home.webp` | 独处 | 窗边扶手椅 |
| `activity-exercise.webp` | 运动 | 运动鞋与水壶 |
| `activity-gathering.webp` | 聚会 | 圆桌与小串灯 |
| `other.webp` | 其他 | 留白与手写笔 |

## 可选增强资产

先不必制作十种音乐风格的封面、选中/未选中两套图或动画，当前音乐方向用轻量文字标签即可。若需要丰富选择页，可另做 1 张无文字横幅（1600 × 600），画面为窗边的声音手记、磁带与植物，主体不要影响标题阅读。

## 当前流程

录音结束 → 保存原声到账号素材库 → 点击“生成音乐日记” → 选择心情、天气、状态（每组含其他输入）→ 选择音乐方向/填写自由描述 → 进入编辑。

本地音乐是原创程序合成草稿，十种方向有不同节奏和编配；心情、天气和状态会影响和声与速度。自由描述保存到日记并用于后续 AI 任务，当前正式服务未接入 AI，不能声称自由文本已经被模型理解。生成音乐保存时更新同一条记忆，保留原声、坐标、照片和视频，不重复创建素材。
