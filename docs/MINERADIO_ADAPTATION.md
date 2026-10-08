# 声迹 × Mineradio 接入说明

上游源码：[XxHuberrr/Mineradio-paused](https://github.com/XxHuberrr/Mineradio-paused)，快照提交 `d43de565acabfdc1a9c9820a27e81a98ccbebcef`，存放在 `third_party/Mineradio-paused-main/`，保留其 `LICENSE`、`NOTICE` 和完整源码。原始 `public/index.html`、粒子模块、播放器模块及其原始 CSS 均未改动。

## 当前结构

| 部分 | 文件 | 用途 |
| --- | --- | --- |
| 原版粒子和播放器 | `third_party/Mineradio-paused-main/public/` | 以原有 `index-loader.js` 和全套模块运行；通过独立入口显示在聆听页 |
| 接入入口 | `public/soundtrace-engine.html`、`css/soundtrace-engine.css`、`js/soundtrace-bridge.js` | 复制原始 HTML 入口，收起上游首页等不相关界面；用消息桥将声迹音频队列交给原版播放器 |
| 声迹页面 | `webapp/home.html`、`index.html`、`album-room.html`、`map.html`、`community.html`、`me.html` | 统一暗场、星点和浮动导航；保留声迹原有功能与 API |
| 声迹视觉样式 | `webapp/assets/soundtrace-shell.css`、`soundtrace-sections.css`、`soundtrace-frameless.css`、`album-mineradio.css` | 用无框内容区、细分隔线和场景画面替代大量玻璃卡片；收藏间独立使用横向场景卡片 |
| 3D 藏品架 | `webapp/assets/mineradio-port/memory-shelf.js` | 移植上游 `04-shelf` 场景的弧形布局、错峰入场、视差和选取；卡片绘制改成无框照片、唱片、磁带素材 |

流程：FastAPI 输出作品、照片、素材 → `album-room.js` 组装藏品队列 → 同源 iframe 里的 `soundtrace-bridge.js` 映射为 Mineradio 本地曲目 → 原版 `playQueueAt` 播放 → 原版粒子、播放器与藏品架随状态变化。上游登录、云音乐接口和桌面壳没有接入声迹。窄屏和 WebGL 不可用时，3D 藏品架用可访问的普通列表替代。

收藏间横向滑动六个场景，场景卡片随滚动轻微旋转，滚动到目标场景时重挂同一组交互物件并切换对应素材；页面没有“换场景”按钮。聆听页保留原版粒子与播放器，粒子直接展示当前藏品的封面形态，旁边提供无框 3D 藏品切换。桥接脚本只对本站 `/assets/` 封面使用直达地址，让原版粒子从藏品图取色、成形；其他封面仍走上游逻辑。页面不再于粒子画面上叠加第二张大图。

声音地图新增声景漫游与我的足迹两种视图：前者是六个画风统一的场景组成的可拖动圆盘，点选后可进入对应收藏场景；后者仍展示作品真实经纬度和路线。声景圆盘没有给虚构场景编造地理坐标。灵感参考 [Radio Garden](https://radio.garden/) 的空间探索、[Sonar](https://www.behance.net/gallery/243849175/Sonar-App-Design) 的雷达式发现，以及 [Rotational Music App](https://www.behance.net/gallery/62169521/Rotational-Music-App-2017) 的旋转切换与音乐响应。

## 验证与预览

- `/album?listen=1&demo=1` 使用仓库内 `outputs/soundtrace_demo.wav` 验证播放；这是显式演示入口，不会替换普通用户作品。
- 浏览器可能阻止进入页面时的自动播放；此时点击原版播放器的播放键即可。原版节奏分析弹窗在声迹嵌入入口中自动收起，避免遮挡聆听画面。
- 当前 `outputs/works.json` 中两条作品指向的生成音频文件在此工作区缺失；这些记录在普通页面可见，但文件恢复前无法播放。演示入口已验证音频时长和进度推进。
- 若本机原有 Python 3.11 环境不可用，可运行 `node tools/preview-server.cjs` 在 8090 端口检查页面。它只读地提供页面和现有 JSON 数据，创作、发布与保存仍需 FastAPI 服务。

## 许可

上游 `package.json` 标注 `GPL-3.0-only`；本项目的上游代码副本、桥接入口和派生藏品架都应按该许可处理。公开发布或分发前，需要保留许可与修改说明，并明确整个衍生作品的源码提供方式。上游 `NOTICE` 对名称、Logo 与视觉表达另有声明，发布时需一并核对。
