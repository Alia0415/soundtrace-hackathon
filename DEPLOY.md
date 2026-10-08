# 声迹正式网站部署

完整待提供资源与照片手绘生成说明，见 [上线资源清单](docs/LAUNCH_RESOURCES.md)。演示入口、真实地图与音乐生成配置，见 [演示与正式版说明](docs/DEMO_AND_PRODUCTION.md)。

正式入口为 `soundtrace_public:app`，保留现有页面和播放器，独立于旧 GPU 单人服务。真实账号、服务器端会话、SQLite 数据库与媒体文件均存到持久磁盘。每位用户只能读取自己的资料、收藏和地图；访客可以浏览社区，登录后可以保存和发布。未发布的录音、照片、视频和背景需要本人登录才能访问。

## 已实现

- 注册、登录、退出、修改密码；scrypt 密码哈希与 HttpOnly 会话 Cookie。
- 上传头像和背景、修改昵称；后台不接受 `logged_in=true` 作为登录凭证。
- 保存原声、工作台编辑后的音乐、图片、视频、补充音频、笔记、时间、天气和坐标。
- 导入页只提供“上传本地音频”；演示版额外提供“演示音频”。上传后可试听、保存到素材库并主动制作日记。顶部旧示例音频面板已移除。浏览器先解码为 PCM WAV，再由服务端校验时长与存储配额。
- 录音结束自动保存原声到素材库，移除重复信息表单。点击“生成音乐日记”后依次选择天气、心情、状态，填写照片/笔记/可选位置，选择音乐方向，生成并微调。音乐更新同一条记忆，保留原声和原有图片/视频。
- `/demo` 为独立的浏览器演示空间；演示收藏、地图、社区、寄出均不写入正式数据库。左上角「声迹」进入演示，演示空间提供返回正式版入口。
- 正式地图集成高德 JS API 2.0、服务器安全密钥代理、WGS84 到 GCJ02 转换及全足迹视野；需要配置地图 Key 和样式 ID。
- 真实音乐支持 Mureka 国内纯音乐 API 或 ACE-Step 1.5 XL 自部署 API。接口凭据仅在服务器保存；不使用本地循环合成器替代模型结果。配置说明见上方文档。
- 磁带保存原声；唱片保存工作台混音；照片进入收藏，真实坐标进入个人地图。
- 未登录时，保存操作弹出登录窗口，登录完成后继续原来的保存请求。
- 发布到社区、删除自己的动态、删除记忆及文件；删除动态后私有录音不再允许访客读取。
- 每人默认 1 GB 上限，上传大小和写入频率受限，站外请求不能修改数据。
- 旧 `outputs/user.json` 和录音索引不直接公开，也不会自动放进新用户账号。

## 部署资源

需要一台可持续运行 Docker 的 Linux 云服务器、持久化磁盘，以及解析到该服务器的域名。录音、编辑、保存和发布不需要 GPU。资源配置按实际访问量监测调整。

目前没有部署目标或平台授权，不能声称已经产生公网地址。提供云平台名称、服务器地址及域名即可；通过已有 SSH 配置或平台授权登录，不把密码或密钥发到聊天里。

## 上线

把部署包解压到服务器；源码包包含上游 LICENSE、NOTICE、完整代码及修改说明，可从 `/source` 下载。Docker 构建时会自动运行 `python tools/package_public.py` 生成对应源码归档，无需预先生成或提交 `runtime/releases/soundtrace-public.zip`；直接从 GitHub 拉取代码即可构建。若需要单独导出部署包，可在本地运行该命令。然后复制 `deploy/production.env.example` 为 `.env.production`，填入真实域名：

```text
SOUNDTRACE_DOMAIN=soundtrace.example.com
SOUNDTRACE_USER_QUOTA_MB=1024
```

域名 A 记录指向服务器 IP；如果没有 IPv6，不设置 AAAA。服务器开放 80、443：

```bash
docker compose --env-file .env.production up -d --build
docker compose --env-file .env.production logs --tail=100 app proxy
```

Docker 构建会重建 React 工作台。Caddy 自动申请 HTTPS 证书，正式会话 Cookie 设为 Secure。应用端口仅在 Docker 内部网络使用。数据保存到 `soundtrace_data` 持久卷，更新容器保留数据；不要执行 `docker compose down -v`。证书也使用独立持久卷。

参考：[Caddy HTTPS 文档](https://caddyserver.com/docs/quick-starts/https)、[FastAPI Cookie 文档](https://fastapi.tiangolo.com/advanced/response-cookies/)。

## 本地检查正式版本

```powershell
python -m pip install -r requirements-public.txt
python -m uvicorn soundtrace_public:app --host 127.0.0.1 --port 8093
```

打开 `http://127.0.0.1:8093`。本地不设置 `SOUNDTRACE_PUBLIC_URL`；正式环境由 Compose 设置为 HTTPS 域名。8090 的旧预览和 8092 的 GPU 服务仍是单人开发服务，不应直接公开。

```powershell
python -m unittest discover -s tests -p test_public_site.py -v
```

## 备份与恢复

```bash
docker compose --env-file .env.production exec -T app python tools/backup_public.py /data /data/backups
docker compose --env-file .env.production cp app:/data/backups ./backups
```

备份使用 SQLite 在线备份 API，复制索引引用的全部文件，并清除会话凭证。如果复制时有文件被删除，则备份失败并要求重试，不留下不完整备份。将导出的备份再保存到另一台机器或对象存储；同一磁盘上的备份无法应对磁盘损坏。备份仍包含密码哈希和个人媒体，应限制读取权限。

参考：[SQLite Backup API](https://www.sqlite.org/backup.html)。

恢复时停止应用，把备份中的 `soundtrace.sqlite3` 和 `users/` 恢复到持久卷根目录，再启动应用。恢复后用户重新登录。定时异地备份需要部署目标提供后配置。

## AI 服务与账号功能边界

普通录音、音轨编辑、保存与发布可独立运行。音乐任务具有账号与原声归属校验、并发/每日次数限制、持久任务状态及音频配额。未配置音乐凭据时只微调原声；照片手绘已接国内豆包 Seedream 图生图协议；需配置 SOUNDTRACE_ARK_KEY 与 SOUNDTRACE_IMAGE_MODEL。未配置时使用用户原照片，无照片则白底文字。

语音识别默认关闭。启用时需在镜像安装 faster-whisper 和模型，设置 `SOUNDTRACE_ENABLE_STT=1` 及 `SOUNDTRACE_WHISPER_MODEL`。用户名密码账号支持修改密码；邮件验证、自动找回密码、管理员审核界面尚未实现。匿名信件在主动加入交换的用户之间真实匹配；暂时无人匹配时排队，不伪报送达。

公网验收还需在实际服务器验证 Docker 构建、域名 HTTPS、手机录音权限、重启后数据保留、异地备份和两位真实用户的数据隔离。本机未安装 Docker，所以容器构建需在部署主机完成验证。
