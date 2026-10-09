# 声迹：演示空间与正式部署（2026-10-07）

## 已实现的入口与流程

- 正式版首页 `/`；正式页面左上角「声迹」返回 `/`。`/library` 为上传及分离素材的独立入口。
- 演示页 `/demo/studio`、`/demo/album`、`/demo/map`、`/demo/community` 共用已批准的手绘背景、物件、响应式布局和原 Mineradio 聆听效果。
- 演示空间含六条记忆、三条社区动态和一封来信。可试听、切换收藏场景、编辑示例资料、点赞、回应、录音/导入、制作、收藏、同步社区、寄出、在地图查看。演示的音乐为仓库内已有试听音频，**不是实时 AI 生成**。
- 示例与演示操作保存在当前浏览器独立 IndexedDB 中，刷新后保留；不会保存到正式数据库，不使用正式账号。页首「演示空间」菜单可重置或进入正式版。换浏览器会得到初始示例。
- 正式社区与正式地图不补入虚构示例。
- `/capture` 与 `/studio` 使用同一录音工作台。结束录音 → 自动保存原声到素材库（未登录会要求登录）→ 留在素材库 → 主动点「生成音乐日记」→ 天气 → 心情 → 状态 → 照片、笔记、可选定位 → 音乐风格 → 生成/微调 → 收藏。
- 已移除录音结束后的重复信息弹窗。音乐最后保存仍有可编辑的确认窗口。

## 正式地图：腾讯地图 JSAPI GL

正式网站使用腾讯地图，演示地图继续使用本地手绘示意图。后端 `/api/map/config` 返回启用状态、可选样式 ID 与代理路径，不返回 Key。浏览器通过 `/_TMapService` 的固定地址代理完成 SDK 鉴权；地图瓦片仍由腾讯官方服务加载。

真实录音位置继续按 WGS84 保存；绘制前经登录保护的 `/api/map/coordinates` 调用腾讯坐标转换接口（`type=1`）转为 GCJ02，每批最多 40 个位置。足迹视野覆盖全部已定位记忆，不限定城市；没有位置的记忆保留在列表。服务未配置或转换失败时显示重试入口，原有记忆与试听不受影响。

在部署平台的环境变量或服务器 `.env.production` 中设置：

```text
SOUNDTRACE_TENCENT_MAP_KEY=你的腾讯地图Key
SOUNDTRACE_TENCENT_MAP_SERVICE_KEY=
SOUNDTRACE_TENCENT_MAP_STYLE=
```

`SOUNDTRACE_TENCENT_MAP_KEY` 对应腾讯位置服务控制台中已开通 JSAPI GL 的 Key。坐标转换还需要 WebService 权限；如果同一个 Key 已开通两项权限，`SERVICE_KEY` 留空即可，否则填写另一个 WebService Key。按控制台要求配置正式域名/服务器 IP 访问限制；本地测试也需允许对应开发地址。项目名称（例如 soundtrail）只用于控制台管理，不是环境变量值。

`SOUNDTRACE_TENCENT_MAP_STYLE` 可留空，使用系统默认地图；自定义样式需在腾讯控制台为该 Key 发布后填写对应 `styleN`。旧 `SOUNDTRACE_AMAP_*` 配置已不再使用，不能填入腾讯 Key。

### 手绘标记与地图样式

地图上仍使用原有手绘照片圆球、记忆详情和音频控件。可在腾讯位置服务控制台为底图设置白色陆地、淡蓝水系、浅色道路及低对比度地名；不要用未发布的样式 ID。地理底图来自腾讯真实地图，示例页的手绘示意图不用于正式地理定位。

依据：[腾讯 JSAPI GL](https://lbs.qq.com/webApi/javascriptGL/glGuide/glOverview)、[官方 Key 代理说明](https://lbs.qq.com/webApi/javascriptGL/glGuide/glKeyDelegate)、[腾讯官方 SDK 资料](https://github.com/TencentLBS/tencentmap-map-assistant/tree/main/references/jsapi-guide/jsapigl/docs)。

本机验证（2026-10-09）：真实腾讯 Key 鉴权、WGS84 转换、跨城市标记及详情操作已通过。当前测试网络无法连接 `rt*.map.gtimg.com` 底图瓦片域名，截图底图为空白；因此完整底图显示仍需在部署网络验收，不能以标记测试代替。模拟测试覆盖未配置、转换失败时保留足迹列表，以及演示地图隔离。

## 音乐：Mureka 素材条件生成

**正式素材创作使用 Mureka 音轨生成 API。最终音质需实际试听，任务成功不等于风格与素材保真度已达到预期。**

| 方案 | 产品适用性 | 当前判断 |
| --- | --- | --- |
| Mureka 国内 API | 纯音乐、商业托管、无需用户部署 GPU | 已接音轨生成与声部分离。音轨接口不接受 model 参数；`SOUNDTRACE_MUREKA_MODEL` 仅供旧文本纯音乐接口使用。需同一 Mureka Key 及可用额度 |
| ACE-Step 1.5 | 开源服务、音轨可控、可自行部署 | 旧协议仅支持文本生成，尚不满足当前素材条件创作；正式素材请求会明确提示不支持。部署见 [开源声音处理](OPEN_SOURCE_AUDIO.md) |
| LeVo 2 | 完整歌曲、歌词准确性、人声 | 值得用于未来人声歌曲功能；暂未引入其不同的推理服务，不把未接通功能显示成可用 |
| MiniMax Music3 | 新的开源整曲模型 | 可作为后续试听对照；新用户无法直接新开旧付费音乐 API，暂未接入其私有协议 |

来源：[Mureka 国内纯音乐接口](https://platform.mureka.cn/docs/api/operations/post-v1-instrumental-generate.html)、[任务查询](https://platform.mureka.cn/docs/api/operations/get-v1-instrumental-query-%7Btask_id%7D.html)、[ACE-Step 官方项目](https://github.com/ace-step/ACE-Step-1.5)、[官方 API](https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/API.md)、[GPU 配置](https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/GPU_COMPATIBILITY.md)、[LeVo 2](https://github.com/levo-demo/LeVo)、[MiniMax 官方 API 变更](https://platform.minimax.io/docs/guides/music-generation)。

### 接入行为

- `/api/music/jobs`：登录用户创建任务；必须属于自己的原声记忆。一人同时一个任务，默认每 24 小时最多 5 次。
- `/api/music/jobs/{id}`：仅所有者可读；保存排队、生成、下载、成功、失败状态。
- 当前 Mureka 流程会把用户所选原声或分离声部上传为模型输入，通过 `/v1/track/generate` 同时提交 `upload_audio_id`、`generate_type=Instrumental` 与文字要求。原素材仍独立保留，生成音乐作为另一音轨，可调现场声与音乐比例。不发送精准位置。
- 成功 WAV 下载到用户私有空间、计入配额；浏览器保存混音后进入同一条记忆，唱片含音乐，磁带保留原声。
- 不将本地循环合成器冒充生成结果。服务未配置时仅原声微调；演示版明确使用示例音乐。
- 停止等待会放弃使用该版本，但服务已接收的任务可能继续运行/计费；无自动重新提交的收费重试。重启中断任务不会自动重新生成。
- 素材库已接 Mureka 人声/乐器声部分离，结果分别存储。鸟鸣、雨声等文字指定声源提取仍依赖另行部署的 AudioSep 服务；未配置时不可用，不把乐器分轨当成环境声定向提取。

### 本地配置

复制 `deploy/production.env.example` 为根目录 `.env.production`，填写密钥和服务地址；此文件被 Git/部署包排除。关闭旧的 8093 服务，再运行 `tools/start-local.ps1`。本地脚本只读取 `SOUNDTRACE_*` 配置，不输出凭据，并保持本地 HTTP，不套用正式域名。

云部署用 `docker compose --env-file .env.production up -d --build`，域名指向服务器，Caddy 提供 HTTPS，数据库与媒体保存到持久卷。发布前通过 `python tools/package_public.py` 更新许可要求的源码包。当前后台任务适用于单进程部署；扩容需要独立任务队列和共享存储。

## 真正公开上线还需要你提供/确认

本清单的合并更新版本见 [完整上线资源清单](LAUNCH_RESOURCES.md)，包含本轮照片手绘服务、实际照片和每项功能的接入状态。

1. **域名和国内可访问服务器**：实际部署目标、DNS 权限；HTTPS 是移动端录音的必要条件。若使用中国大陆服务器，需按服务商要求完成备案手续。
2. **腾讯地图配置**：JSAPI GL Key、WebService 权限、正式域名/IP 访问限制；样式 ID 可选。
3. **音乐服务**：Mureka Key 与预算，或已部署的 ACE-Step 服务 URL/API Key。GPU 服务只允许网站后端访问。先用西湖晚风、雨夜、鸟鸣三组上下文做实际试听验收。
4. **持久化与备份**：现有 SQLite + 媒体持久卷可供单实例初期使用。提供服务器磁盘、备份目的地；规模化再接 COS/OSS、共享数据库及任务队列。
5. **公开社区运营配置**：社区规则、举报处理联系人、内容审核服务/后台、隐私政策及账号恢复方式。公开注册与真实发布已存在，但这些运营能力需补齐后正式开放。
6. **生成封面/语音识别**：本轮的音乐和地图配置不能替代封面生图与语音识别凭据；照片图生图已接豆包 Seedream，需提供方舟 Key 与可用模型 ID（详见 [完整资源清单](LAUNCH_RESOURCES.md)），语音识别需启用独立部署的 faster-whisper 或提供托管识别服务。

已有公网服务；新素材条件生成版本需要重新部署并再次验收。腾讯地图与音乐的真实联调结果见下方；图片生成状态与素材生成相互独立。


## 2026-10-09 实际联调补充

- 新素材链路已完成真实后端联调：20 秒视频导入，分成人声、贝斯、鼓、伴奏及其他声音，选择分离声部加文字提交 Mureka，得到 25.104 秒生成音乐，保存作品成功。同一数据目录下重启后，账号及 6 段素材可读取。该证据不代表公网重部署持久化已经通过，也不代表环境声定向提取已实现。
- 本机 Windows 系统代理会中断 httpx 与腾讯瓦片连接。服务端可在私有环境配置 `SOUNDTRACE_HTTP_TRUST_ENV=false`，仅作用于本产品，不修改系统代理。默认 true 保留既有代理行为。浏览器请求腾讯底图仍经过浏览器自己的网络配置，服务端设置不能代替浏览器的代理规则；公网上线需单独验证底图。
- Seedream Key 认证通过，但 `doubao-seedream-5-0-pro-260628` 的图片生成返回 HTTP 404。需在方舟核对实际可调用模型/接入点及权限，不能据模型列表中存在该名称就声称生图可用。
- 腾讯地图最终重新加载后已实际显示道路底图与声音标记，并保存验收截图；之前出现过网络连接失败，不能把一次恢复当作公网稳定性验收。
- 新增公共网络模块已加入 Docker COPY 和源码归档白名单。详细验收见 `docs/PRODUCT_AUDIT_20261009.txt`。
