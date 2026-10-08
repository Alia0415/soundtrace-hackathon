# SoundTrace 技术框架

## 当前边界

```text
小程序 / Web 客户端
        │  HTTPS: 创建任务、查询状态、获取音频 URL
        ▼
轻量 API（soundtrace_api.py）
        │  单机任务队列；后续可替换为 Redis + 独立 Worker
        ▼
音频流水线（soundtrace_mvp.py）
        ├─ 环境声清理
        ├─ AudioSep 命令适配 / DSP 降级
        ├─ 哼唱 F0 提取、音阶量化、旋律合成
        └─ 编排、混音、WAV 与分析结果输出
```

现阶段使用内存任务状态和单 Worker，保证共享输出目录不会并发冲突，适合单机演示。每个已完成任务的产物会复制到 `outputs/jobs/<job_id>/`。

## API

- `GET /health`：健康检查。
- `POST /v1/demo-jobs`：创建内置样例任务，请求体示例 `{"target":"birds","duration":42}`。
- `GET /v1/jobs/<job_id>`：读取任务状态和输出路径。

真实素材上传应在下一阶段增加对象存储直传：客户端获得签名 URL 后上传环境录音和哼唱，API 只接收对象 key，避免大文件经过业务服务。

## 演进路线

1. 将 AudioSep 部署为 GPU 推理服务，流水线通过稳定接口调用并记录模型版本。
2. 将 `JobStore` 与进程内队列替换为数据库、Redis 和独立 Worker，增加重试、超时和幂等键。
3. 输入文件进入对象存储，输出 WAV/封面通过 CDN 分发；服务只保存元数据。
4. 增加鉴权、内容安全、配额、可观测性和用户作品表，再接入小程序与社区发布。
