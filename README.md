# 声迹 SoundTrace — 核心音频链路 MVP

本目录验证一条最短可运行链路：

1. 环境录音清理（高通、频谱门、归一化）
2. AudioSep 目标声音提取接口（未安装时使用提示词驱动的频段提取降级方案）
3. 哼唱基频提取、音阶量化、断音修复与旋律重合成
4. 环境采样切片、节奏编排与 30–60 秒立体声混音

当前机器没有系统 Python、FFmpeg、PyTorch 或 AudioSep。本 MVP 因而只依赖 Codex
自带 Python 3.12 和 NumPy；生成的 `outputs/soundtrace_demo.wav` 可直接播放。

## 一键复现

```powershell
$py = 'C:\Users\aliaying\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py .\soundtrace_mvp.py demo --duration 42
```

使用自己的单声道或立体声 PCM WAV（推荐 16/24/32-bit，任意采样率）：

```powershell
& $py .\soundtrace_mvp.py process --environment .\inputs\environment.wav --hum .\inputs\hum.wav --target "birds" --duration 45
```

输出包括清理后的环境声、目标声、修正旋律和最终混音，并在
`outputs/analysis.json` 记录检测音符、置信度、响度和所用后端。

## AudioSep 接入

代码中的 `extract_target()` 是边界清晰的替换点。若环境变量
`AUDIOSEP_COMMAND` 存在，会按模板调用外部 AudioSep：

```text
python inference.py --audio {input} --text {prompt} --output {output}
```

模板必须包含 `{input}`、`{prompt}`、`{output}`。当前降级后端只能按提示词选择
大致频段，能验证工程链路，不能证明语义目标分离的质量；真实 AudioSep 验证仍需安装
模型和权重后用同一组输入做 A/B。


## 技术框架与 API

仓库包含标准库 HTTP API、异步单 Worker 任务队列、按任务归档的音频产物和基础测试。它用于连接小程序/Web 原型，并为后续替换 Redis、对象存储和 GPU AudioSep 服务保留清晰边界。详细设计见 `docs/ARCHITECTURE.md`。

```powershell
$py = 'C:\Users\aliaying\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py .\soundtrace_api.py --port 8080
Invoke-RestMethod http://127.0.0.1:8080/health
$job = Invoke-RestMethod -Method Post -ContentType 'application/json' -Body '{"target":"birds","duration":42}' http://127.0.0.1:8080/v1/demo-jobs
Invoke-RestMethod "http://127.0.0.1:8080/v1/jobs/$($job.id)"
```

运行测试：

```powershell
& $py -m unittest discover -s tests -v
```