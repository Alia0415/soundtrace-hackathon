# SoundTrace 技術棧驗證 — 2026-09-29

## 結論

本機記憶房間與純 Python DSP 原型分別跑通；目前並不是前端接上 GPU AI 的完整產品。GPU 環境、模型、前後端整合與正式部署仍未完成。以下結果只涵蓋本次本機驗證，不能當作零 bug 或所有裝置皆相容的保證。

## 各層狀態

| 層 | 實際技術 | 本次結果 |
| --- | --- | --- |
| 記憶房間 | React 19.2、Vite 6.4.2、CSS/SVG | 正式 build 通過，4173 生產預覽完整操作通過；5173 開發預覽保留 |
| 本機音訊 | Web Audio / OfflineAudioContext、PCM WAV | 匯入、融合、播放、下載通過；輸出 24 秒、24 kHz、双聲道 |
| 本機儲存 | IndexedDB、localStorage | 素材、三瓶選擇、記憶球名稱與音訊刷新後恢復，恢復的作品能播放 |
| Python DSP | Python、NumPy | 實際生成 30 秒双聲道音訊，經 HTTP 下载並讀取 WAV 驗證 |
| Python API | 標準庫 HTTP server、記憶體佇列 | 健康檢查、建立／查詢任務、輸入拒絕、受限音檔下載通過 |
| GPU 舊服務 | FastAPI、PyTorch、AudioSep/CLAP、ACE-Step | 無法實跑：缺少模型與必要依賴；只完成源碼與 Python 語法檢查 |
| Sites 打包 | Worker + static assets | 打包產物及路由測試通過；未執行雲端發布 |
| Docker/Nginx | 舊版靜態前端 | Docker CLI 不存在，未實跑容器；Dockerfile 仍複製 deploy/tencent-pages，不是 memory-room-demo |

## 本次修復

1. API 收到 `[]`、`null`、數字等合法但非物件的 JSON 時，原先會 AttributeError 並斷線。改為回傳 400。
2. API 接受負數或任意大的 Content-Length，讀取可能掛起。現在先驗證，負數 400，超過 64 KiB 413。
3. API 任務完成後僅回傳檔案路徑，HTTP 取用返回 404。補上成功任務輸出白名單下載，拒絕未列出與越界路徑。
4. 瀏覽器混音僅用左聲道估算音量，右聲道單獨有聲的立體聲會被設為零增益。改為計算所有聲道的 RMS，加入聲道交換與靜音回歸測試。
5. 素材播放用相對 URL 與 Audio.src 的絕對 URL 比較，暫停後可能重建播放器而從頭開始。改為先正規化為絕對 URL。記憶球播放／暫停與刷新後播放已驗證；相對素材的時間點恢復由程式碼檢查確認，未量測播放秒數。

## 測試證據

- `npm run build` 成功。
- `npm test`：6/6 通過（音訊正規化、WAV 格式、Worker 路由與打包）。
- `python -m unittest discover -s tests -v`：10/10 通過。新增案例先在修復前重現失敗，再驗證修復。
- 真實 Worker 測試在臨時目錄執行，不覆寫倉庫示例；驗證 30 秒、双聲道、DSP 降級後端與 HTTP 下載。
- `py_compile soundtrace_mvp.py soundtrace_api.py soundtrace_gpu.py` 通過；GPU 語法通過不等於依賴與推理能運作。
- 正式版浏览器走查：推門、開櫃、匯入右聲道音訊、拒絕損壞 WAV、三瓶選取、拒絕第四瓶、倒入後禁用已倒瓶、融合、播放／暫停、命名收藏、下載、刷新與恢复播放。
- 真實下載檔：2,304,044 bytes；24.0 秒；24,000 Hz；2 聲道；峰值約 0.95001、RMS 約 0.09770；不是靜音檔。
- 測試使用 `http://127.0.0.1:4173` 的獨立網站來源，未覆蓋 5173 原有素材與收藏。
- 測試頁捕獲的 console error：0。
- `git diff --check` 通過。修改尚未提交或推送。

## 尚未接通／驗證的範圍

- `memory-room-demo/src/audio.js` 只讀素材並在瀏覽器混音，没有呼叫 `/api/jobs` 或 `/v1/demo-jobs`；暫無 AI 作曲、語義分離。
- `pyproject.toml` 只宣告 NumPy；它不是 GPU 服務完整依賴清單。当前 bundled Python 没有 torch、soundfile、librosa、fastapi、uvicorn、clearvoice、noisereduce、acestep、multipart；Anaconda 也沒有 torch、librosa、acestep。
- 舊啟動 bat 指向的 `../hackathon-env/Scripts/python.exe` 不存在，AudioSep 目錄與 ACE-Step checkpoints 也不存在。
- Docker 入口仍是舊前端。發布新介面前須明確選擇 Sites 打包或更新 Docker 建置入口。
- Python API 任務僅存記憶體，重啟會遺失任務索引；尚無帳號鑑權、雲端資料庫、跨裝置同步或完整作品歷史。記憶房間只保留最近一顆收藏球。
- 未驗證實體手機觸控、Safari/iOS、GPU 推理音質、外部 AudioSep 命令、雲端部署與多使用者負載。

## 下一個整合步驟

先確定可用 GPU 服務與模型部署位置，補齊可重現依賴；再將記憶池接到真實素材上傳、任務查詢與音訊下載接口。已有本機混音可作為服務失敗時的明確降級方案。
