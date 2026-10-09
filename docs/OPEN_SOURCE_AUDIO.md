# 开源声音处理与公网部署

网站可以公开部署，模型服务由网站后端调用。访客的浏览器不直接访问 GPU 服务，也不会收到服务密钥。网站仍使用 `soundtrace_public:app`；不要把旧单人 GPU 服务直接作为公网网站。

## 当前接入范围

| 功能 | 实现 | 部署条件与验证状态 |
| --- | --- | --- |
| 哼唱转旋律 | Spotify Basic Pitch 在浏览器 Worker 中识别音符，再合成可编辑旋律轨 | 模型与网站一起打包，无须音乐 API 或服务器 GPU。已用真实模型识别测试旋律，验证取消、重试、播放与保存；未覆盖真人录音及全部手机机型。 |
| 完整音乐生成 | ACE-Step 1.5 官方 REST API | 已验证接口协议；实际模型生成仍须部署模型与权重并验收。 |
| 声音辨识与提取 | 现有 `soundtrace_gpu.py` 的 CLAP / AudioSep，新增正式账号接口 | 已验证协议、用户隔离、结果下载、配额与取消；没有在本机执行 GPU 模型推理。 |

哼唱旋律是音符转写与音色合成，不等于完整歌曲创作。识别在当前设备进行，不会为识别而把录音发送到外部模型 API；原声上传、收藏和作品保存仍按网站原有流程进行。首次使用要从本站下载模型与运行代码，低性能手机或长录音会较慢。录音需要 HTTPS 和浏览器麦克风许可。

## 仅部署网站及哼唱功能

按 [网站部署说明](../DEPLOY.md) 配置域名、HTTPS 和持久磁盘即可。`Dockerfile` 自动打包 Basic Pitch 的模型、权重和许可证；浏览器从同域 `/assets/studio/models/basic-pitch/` 加载，无须访问模型托管网站。未配置模型服务时，完整 AI 音乐、辨识和提取仍会显示不可用。

## 同一 NVIDIA Linux 主机部署 ACE-Step

服务器须具备兼容的 NVIDIA 驱动、Docker GPU 支持、足够的模型磁盘空间，并能下载上游依赖与权重。当前开发机为 Intel Iris Xe / 约 16 GB 内存，没有 NVIDIA GPU，也没有 Docker，因此下面的容器配置尚未进行实际构建与推理验收。

复制 `deploy/production.env.example` 为 `.env.production`，配置域名，并为 `SOUNDTRACE_ACE_KEY` 设置随机密钥。密钥不应提交到 Git。然后执行：

```bash
docker compose --env-file .env.production -f compose.yaml -f deploy/compose.acestep.yaml up -d --build
docker compose --env-file .env.production -f compose.yaml -f deploy/compose.acestep.yaml logs --tail=100 acestep app
```

覆盖文件固定上游源码提交 `ca1e85fe9430179831e6bc6be790c332190a3866`，使用官方 Dockerfile、Turbo 模型、8 步推理，并关闭额外语言模型。模型服务没有映射公网端口；网站通过容器网络访问它，密钥只保存在服务器。首启模型下载可能很久，健康检查失败时先查看下载和初始化日志。网站与模型服务独立启动，模型未就绪时生成会失败，原声仍保留。

后续更新也要使用相同两个 `-f` 文件。`down -v` 会删除持久卷，不要用于常规升级。

如果网站运行在已有云托管容器，而 GPU 在另一台服务器，不使用这个同机覆盖文件；在网站平台配置：

```text
SOUNDTRACE_MUSIC_PROVIDER=acestep
SOUNDTRACE_ACE_URL=http://模型服务器的私网地址:8001
SOUNDTRACE_ACE_KEY=与模型服务ACESTEP_API_KEY相同的密钥
SOUNDTRACE_ACE_MODEL=acestep-v15-turbo
SOUNDTRACE_ACE_THINKING=false
SOUNDTRACE_ACE_STEPS=8
```

跨公网调用时使用 HTTPS 和访问限制；优先使用私网互通。网站云容器的服务端口与健康检查端口均应为 **8080**，与 Dockerfile 的启动端口一致。

## AudioSep / CLAP 服务

目前接入的是仓库中已有私有工作服务的协议，并非新增了一套已验证的一键 AudioSep 安装包。先按 [AudioSep 官方说明](https://github.com/Audio-AGI/AudioSep) 安装依赖与权重，并使现有 `soundtrace_gpu.py` 的 AudioSep 路径、模型配置与环境匹配。此旧服务还引用了原开发工作区中的依赖目录，不能只运行正式网站镜像就自动获得分离能力。

GPU 服务配置 `SOUNDTRACE_PUBLIC=1`、`SOUNDTRACE_DEMO_USER=soundtrace` 和非空的 `SOUNDTRACE_DEMO_PASSWORD`，监听可供网站后端访问的私网地址。在正式网站配置：

```text
SOUNDTRACE_GPU_URL=http://声音处理服务器的私网地址:8090
SOUNDTRACE_GPU_USER=soundtrace
SOUNDTRACE_GPU_PASSWORD=与GPU服务相同的密码
SOUNDTRACE_SOUND_DAILY_LIMIT=10
```

正式接口校验录音归属，每人同时最多一个任务，默认每天最多 10 次；只下载该次上游任务目录内的 WAV，校验后存入用户私有空间。取消会停止网站等待并阻止结果落库，上游已开始的推理可能继续。成功分离不会覆盖原声；用户在工作台试听并保存混音。`/api/health` 的能力字段仅表示已配置，不代表模型就绪，必须实际完成一次辨识和提取验收。

## 部署后验收

1. 用真实手机录制短哼唱，识别旋律，播放、保存，确认原声仍可访问。
2. 用真实 ACE-Step 生成任务确认排队、完成、试听与保存，不能以协议模拟测试代替。
3. 用已知鸟鸣或环境录音测试 CLAP 辨识、AudioSep 提取；试听目标声源，确认没有只返回原音。
4. 用另一账号验证私有录音和处理结果无法读取，再验证主动发布后的访问。
5. 重启网站，确认收藏仍在；中断处理应可重试。GPU 内存、磁盘与多用户排队容量需在目标主机测量。

上游依据：[Basic Pitch TypeScript](https://github.com/spotify/basic-pitch-ts)、[ACE-Step 官方 Docker 配置](https://github.com/ace-step/ACE-Step-1.5/blob/ca1e85fe9430179831e6bc6be790c332190a3866/docker-compose.yml)、[API 模型初始化](https://github.com/ace-step/ACE-Step-1.5/blob/ca1e85fe9430179831e6bc6be790c332190a3866/acestep/api/startup_model_init.py)。Basic Pitch 随包附带 Apache-2.0 LICENSE；其他服务及权重的许可按上游文件保留和核对。
