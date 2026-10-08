# 声迹 ROADMAP — 自主迭代任务清单

规则：按优先级取任务 → 实现 → 跑验收 → 通过则勾选并 commit；失败最多重试 3 次。
状态标记：`[ ]` 待办 ｜ `[~]` 进行中 ｜ `[x]` 完成(日期) ｜ `[!]` 阻塞(原因)

## 待办（本轮）

（本轮已清空，见"已完成"）

## 已完成

- [x] **U1 交互重定义落地·网页端**（2026-09-27，全 API+页面验收 PASS）
      新定义见 docs/NORTH_STAR.md 顶部。交付：首页（顶栏用户/登录/签到+三入口+
      地图+底部导航）；唱片册（侧栏/照片墙/唱片架/磁带/拖拽信箱匿名交换/收件箱/
      联系方式交换）；社区；我的。新端点 user/checkin/photos/materials/exchange/feed。
      验收：6 页面 200、中文提取归档磁带、签到/寄出/社区同步全 PASS。
      踩坑：_seed_demo 调用先于定义致启动失败（移至 __main__）
- [x] **T12 作品元数据**（2026-09-26，verify_iter4.py）job.metadata（标题/地点/
      坐标/心情/故事）+ works.json 作品索引 + /api/works + UI 表单（📍一键坐标）
- [x] **T13 情绪→prompt**（2026-09-26）六情绪映射，prompt_used 透明化。
      验收：宁静→"peaceful, serene, calm" 进 prompt ✓
- [x] **T14 节拍对齐**（2026-09-26）/api/analyze-beat（实测 117.5 BPM/26 拍）
      + DAW「🥁节拍吸附」。踩坑：librosa 0.11 tempo 返回数组需 atleast_1d
- [x] **T15 小程序端最小闭环**（2026-09-26，代码级）miniprogram/ 完整可导入
      （录音→提取→生成→播放/转发）；服务改绑 0.0.0.0 支持真机；README 含步骤
- [x] **T16 声音地图 Web 版**（2026-09-26）/map 暗色地图（Leaflet+carto 免key）
      + 作品打点（故事/心情/试听弹窗）+ 时间序路线连线 + 路线连播。验收 200 ✓
- [x] **T17 移动端适配**（2026-09-26，代码级）≤720px 媒体查询
- [x] **T11 audio2audio 生成集成**（2026-09-26，verify_iter3.py）生成任务支持
      melody_ref/ref_strength；UI 哼唱复选框+强度选择（素材库含旋律时自动可选）。
      全链路 API 验收：hum→generate note-chroma **1.000**（>0.8）。
      产品意义：**"哼唱成为作品主旋律"正式上线**
- [x] **T8 audio2audio 旋律保持实验**（2026-09-26，experiment_a2a_melody.py）
      哼唱作参考生成：note-chroma **1.000**（理论上限）vs 无参考基线 0.564 →
      **哼唱可直接驱动生成旋律，产品路线打通**。产物：test-audio/experiments/a2a_*.wav；
      集成任务见 T11
- [x] **T9 服务启动预热**（2026-09-26）启动 20s 后后台加载 AudioSep；
      验收：60s 时 models_loaded=true，首次 analyze **1.81s**（原冷加载 ~15s）。
      踩坑记录：TaskStop 杀不掉旧 python 进程导致端口占用、新旧服务打架，
      排查方法 netstat+taskkill 清场（Windows 下 TaskStop 不杀子进程）
- [x] **T10 深度安全审计**（2026-09-26）Mimosa deep 扫描完成：**0 findings**，
      封印 sha256:1800e39b…（静态分析口径）
- [x] **T1 AudioSep 宽频噪声兜底**（2026-09-26，verify_iter1.py）
      实测：scene_mix 查 human voice，自动识别主导声源 water(0.98)→减法→重提取，
      人声相关 0.19→**0.88**。注意首版实现(减去劫持结果)曾把目标一起减没(0.04)，
      修正为按 CLAP 识别的主导声源名重提取干净背景再减。
- [x] **T4 模型切换提速**（2026-09-26）CPU 暂存恢复实测 **0.6s**（原冷加载 15-20s）
- [x] **T2 CLAP 词表工程**（2026-09-26）中文"风声"→"wind blowing" 映射可用；
      标签相对阈值过滤生效（top×0.45 且 ≥0.05，最多 5 个）
- [x] **T6 母带响度归一**（2026-09-26）remix 成品 RMS 0.160（目标区间 [0.13,0.20]）
- [x] **T3 素材降噪可选**（2026-09-26，代码级验收：tray 双地址+切换按钮+DAW 同步）
- [x] **T7 产物自动清理**（2026-09-26，代码级验收：10min 周期 24h TTL 后台线程）
- [x] **T5 前端状态持久化**（2026-09-26，代码级验收：localStorage 全量钩子 +
      node 语法检查通过；浏览器行为待用户手验"恢复上次进度"按钮）
- [x] T0-1 GPU 服务 + DAW 排布混音 + 哼唱链路（2026-09-26，commit 2a2d604）
- [x] T0-2 块裁剪/循环 + ducking 避让 + 格式通用化（2026-09-26，verify_high_priority.py 全 PASS）

## 待办（后续轮次）


      "用哼唱驱动旋律"选项（ref_audio_input=旋律轨, strength 可调）
      验收：带哼唱素材时 UI 出现该选项；生成结果 note-chroma > 0.8

## 阻塞（等待外部输入）

- [!] **P0 真实手机录音验收**：等素材（docs/P0_COLLECT_GUIDE.md）
      验收：3 名非成员 ≥2 人盲听通过

## 已完成

- [x] T0-1 GPU 服务 + DAW 排布混音 + 哼唱链路（2026-09-26，commit 2a2d604）
- [x] T0-2 块裁剪/循环 + ducking 避让 + 格式通用化（2026-09-26，verify_high_priority.py 全 PASS）
