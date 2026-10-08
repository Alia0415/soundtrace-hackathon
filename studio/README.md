# 声迹声音工作台

工作台位于 `/studio`。用户可以录音或导入音频，选择即时配乐、编辑波形、调整现场与音乐的比例，再将混音保存为唱片、磁带或照片。草稿保存在浏览器 IndexedDB；正式作品和编辑参数保存在 `outputs/library/`，并登记到 `outputs/works.json`。

## 构建

在仓库根目录运行：

```powershell
cd studio
npm ci
npm run build
```

构建产物写入 `webapp/assets/studio/`，由本地预览服务提供。

## 启动本地服务

在仓库根目录的第一个终端启动现有的 CUDA 服务：

```powershell
& '..\hackathon-env\Scripts\python.exe' -m uvicorn soundtrace_gpu:app --host 127.0.0.1 --port 8091
```

在第二个终端启动页面及保存接口：

```powershell
$env:SOUNDTRACE_AI_URL = 'http://127.0.0.1:8091'
node tools/preview-server.cjs
```

打开 `http://127.0.0.1:8090/studio`。没有 AI 服务时，本地录音、即时配乐、编辑、导出及收藏仍可使用。Python 服务依赖仓库同级的 `audio-denoise-tools/AudioSep` 和 `music-arrangement-tools/ACE-Step` 模型目录。

## 验证

```powershell
cd studio
npm test
```

从仓库根目录运行 `python -m unittest discover -s tests -p 'test_studio_storage.py' -v` 可检查作品留存逻辑。
