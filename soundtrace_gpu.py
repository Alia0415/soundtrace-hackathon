"""声迹 SoundTrace GPU 服务 — MVP 体验版

流水线: 上传WAV → CLAP识别声源 → AudioSep提取 → 降噪(ClearerVoice/noisereduce)
        → ACE-Step生成伴奏 → 与提取声混合 → 成品试听

设计遵循 docs/ARCHITECTURE.md：
- 单 Worker 任务队列（GPU 串行，AudioSep/CLAP 与 ACE-Step 互斥占用显存）
- 产物按任务归档 outputs/service_jobs/<job_id>/
- AudioSep / ACE-Step 作为可替换推理模块的边界保留

启动: hackathon-env/Scripts/python.exe soundtrace_gpu.py  →  http://127.0.0.1:8090
"""
import os, sys, gc, json, time, uuid, queue, threading, traceback, re, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
AUDIOSEP_DIR = (WORKSPACE / "audio-denoise-tools" / "AudioSep").resolve()
ACESTEP_CKPT = (WORKSPACE / "music-arrangement-tools" / "ACE-Step" / "checkpoints"
                / "models" / "ACE-Step--ACE-Step-v1-3.5B" / "snapshots" / "master").resolve()
UPLOAD_DIR = ROOT / "outputs" / "service_uploads"
JOB_ROOT = ROOT / "outputs" / "service_jobs"
for d in (UPLOAD_DIR, JOB_ROOT):
    d.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import numpy as np
import torch

# PyTorch 2.6 torch.load weights_only 兼容补丁（AudioSep 的 CLAP 权重需要）
_orig_load = torch.load
def _patched_load(*a, **k):
    k.setdefault("weights_only", False)
    return _orig_load(*a, **k)
torch.load = _patched_load

import soundfile as sf
import librosa
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uvicorn

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
SPEECH_TARGETS = {"human speech", "singing", "crowd talking"}

LABELS = [
    ("flowing stream", "溪流"), ("ocean waves", "海浪"), ("rain", "雨声"),
    ("wind", "风声"), ("rustling leaves", "落叶沙沙"), ("birds singing", "鸟鸣"),
    ("insects chirping", "虫鸣"), ("footsteps", "脚步"), ("city traffic", "车流"),
    ("train passing", "火车"), ("human speech", "人声说话"), ("singing", "歌声"),
    ("crowd talking", "人群"), ("machine humming", "机器声"),
]

STYLE_PROMPTS = {
    "lofi": "lo-fi hip hop, mellow beats, warm vinyl texture, soft keys, relaxing, 75 bpm",
    "ambient": "ambient music, ethereal pads, slow evolving texture, peaceful, atmospheric",
    "cinematic": "cinematic light music, gentle strings, emotional piano, warm, nostalgic",
}
STYLE_NAMES = {"lofi": "Lo-fi 慢摇", "ambient": "氛围空间", "cinematic": "电影感"}

# T2: 中文查询词 → AudioSep/CLAP 英文查询词（按长度倒序匹配）
ZH2EN = {
    "溪流": "flowing stream", "流水": "flowing stream", "水声": "flowing stream",
    "河水": "flowing stream", "水流": "flowing stream", "倒水": "pouring water",
    "鸟鸣": "birds singing", "鸟叫": "birds singing", "鸟": "birds singing",
    "虫鸣": "insects chirping", "蝉鸣": "insects chirping",
    "风声": "wind blowing", "风": "wind blowing", "雨声": "rain", "下雨": "rain",
    "雷声": "thunderstorm", "打雷": "thunderstorm",
    "海浪": "ocean waves", "浪": "ocean waves", "水滴": "water drops dripping",
    "脚步声": "footsteps walking", "脚步": "footsteps walking",
    "车流": "city traffic", "车声": "city traffic", "马路": "city traffic",
    "火车": "train passing", "地铁": "train passing",
    "人声": "human speech", "说话": "human speech", "歌声": "singing", "唱歌": "singing",
    "钟声": "church bells ringing", "狗叫": "dog barking", "狗": "dog barking",
    "直升机": "helicopter flying", "柴火": "fire crackling", "篝火": "fire crackling",
    "落叶": "rustling leaves", "树叶": "rustling leaves",
}


def zh2en(text: str):
    """含中文时映射为英文查询词；返回 (查询词, 是否翻译)"""
    if not re.search(r"[\u4e00-\u9fff]", text):
        return text, False
    for zh in sorted(ZH2EN, key=len, reverse=True):
        if zh in text:
            return ZH2EN[zh], True
    return text, False


def finalize_mix(mix, target_rms: float = 0.16):
    """母带响度归一：RMS 对齐目标响度后再做逐采样限幅。"""
    r = float(np.sqrt(np.mean(mix ** 2)))
    if r > 1e-6:
        mix = mix * (target_rms / r)
    over = np.abs(mix) > 0.98
    if over.any():
        mix[over] = 0.98 * np.sign(mix[over])
    return mix

app = FastAPI(title="SoundTrace MVP")
app.mount("/outputs", StaticFiles(directory=ROOT / "outputs"), name="outputs")
_gpu_lock = threading.Lock()
_models = {"audiosep": None, "audiosep_cpu": None, "clearvoice": None, "text_emb": None}
_jobs = {}
_queue = queue.Queue()


# ─────────────────────────── 模型管理（互斥显存） ───────────────────────────

def load_audiosep():
    """AudioSep + CLAP。GPU 上无实例时优先从 CPU 暂存恢复（秒级），
    否则冷启动构建（首次约 15s）。import 需在仓库目录下进行（CLAP 权重为相对路径）。"""
    if _models["audiosep"] is not None:
        return _models["audiosep"]
    if _models["audiosep_cpu"] is not None:
        model = _models["audiosep_cpu"].to(DEVICE)
        _models["audiosep"] = model
        _models["audiosep_cpu"] = None
        return model
    cwd = os.getcwd()
    os.chdir(AUDIOSEP_DIR)
    try:
        if str(AUDIOSEP_DIR) not in sys.path:
            sys.path.insert(0, str(AUDIOSEP_DIR))
        from pipeline import build_audiosep
        model = build_audiosep(
            config_yaml="config/audiosep_base.yaml",
            checkpoint_path="checkpoint/audiosep_base_4M_steps.ckpt",
            device=DEVICE)
    finally:
        os.chdir(cwd)
    _models["audiosep"] = model
    return model


def unload_audiosep():
    """为 ACE-Step 腾显存：移到 CPU 暂存（而不是销毁），下次加载只需 .to(cuda)。"""
    m = _models["audiosep"]
    if m is not None:
        m.to("cpu")
        _models["audiosep_cpu"] = m
        _models["audiosep"] = None
        gc.collect(); torch.cuda.empty_cache()


def clap_tags(wav_path: str, topk: int = 6):
    model = load_audiosep()
    enc = model.query_encoder
    if _models["text_emb"] is None:
        embs = []
        for en, _ in LABELS:
            e = enc.get_query_embed(modality="text", text=[en], device=DEVICE)
            embs.append(e.squeeze(0).cpu())
        _models["text_emb"] = torch.stack(embs)
    t = _models["text_emb"]
    t = t / t.norm(dim=-1, keepdim=True)
    y, _ = librosa.load(wav_path, sr=32000, mono=True)
    a = enc.get_query_embed(modality="audio",
                            audio=torch.from_numpy(y).unsqueeze(0).float().to(DEVICE),
                            device=DEVICE)
    a = (a / a.norm(dim=-1, keepdim=True)).cpu()
    sims = (a @ t.T).squeeze(0)
    order = torch.argsort(sims, descending=True)[:topk]
    tags = [{"en": LABELS[i][0], "zh": LABELS[i][1], "score": round(float(sims[i]), 3)}
            for i in order.tolist()]
    # T2: 相对阈值过滤低分凑数项（如 top 0.20 时的 0.09 级"人声说话"）
    top = tags[0]["score"] if tags else 0
    return [t for t in tags if t["score"] >= max(0.05, top * 0.45)][:5]


def audiosep_extract(in_path: str, text: str, out_path: str):
    from pipeline import separate_audio
    separate_audio(_models["audiosep"], in_path, text, out_path, DEVICE)


def load_clearvoice():
    """ClearerVoice 权重目录随 CWD（./clearvoice/checkpoints），chdir 到已有缓存处复用"""
    if _models["clearvoice"] is not None:
        return _models["clearvoice"]
    from clearvoice import ClearVoice
    cache_cwd = WORKSPACE / "test-audio"          # 首次测试时权重落在这里
    cache_cwd.mkdir(exist_ok=True)
    cwd = os.getcwd(); os.chdir(cache_cwd)
    try:
        _models["clearvoice"] = ClearVoice(
            task="speech_enhancement", model_names=["MossFormer2_SE_48K"])
    finally:
        os.chdir(cwd)
    return _models["clearvoice"]


def denoise(stem_path: Path, target_en: str, out_path: Path):
    if target_en in SPEECH_TARGETS:
        cv = load_clearvoice()
        out = cv(input_path=str(stem_path), online_write=False)
        enh = np.asarray(out).squeeze()
        sf.write(str(out_path), enh, 48000 if enh.ndim == 1 else 48000)
        return "clearvoice_mossformer2_48k"
    import noisereduce as nr
    y, sr = sf.read(str(stem_path))
    if y.ndim > 1:
        y = y.mean(axis=1)
    out = nr.reduce_noise(y=y, sr=sr, stationary=False, prop_decrease=0.8)
    sf.write(str(out_path), out, sr)
    return "noisereduce"


def generate_and_mix(style: str, target_en: str, duration: float, seed: int,
                     gen_path: Path, ambience_path: Optional[Path], mix_path: Path,
                     stage=None, ambience_level: float = 0.35):
    def say(s):
        if stage:
            stage(s)
    unload_audiosep()                                  # 为 ACE-Step 腾显存
    if _models["clearvoice"] is not None:
        _models["clearvoice"] = None; gc.collect(); torch.cuda.empty_cache()
    from acestep.pipeline_ace_step import ACEStepPipeline
    pipe = ACEStepPipeline(checkpoint_dir=str(ACESTEP_CKPT), cpu_offload=True)
    prompt = f"{STYLE_PROMPTS[style]}, {target_en} atmosphere"
    say(f"生成伴奏中（{STYLE_NAMES[style]}·{duration:.0f}s，约需 {duration*4:.0f}~{duration*6:.0f} 秒）")
    pipe(audio_duration=float(duration), prompt=prompt, lyrics="[inst]",
         infer_step=27, guidance_scale=15.0, manual_seeds=[seed],
         save_path=str(gen_path))
    del pipe; gc.collect(); torch.cuda.empty_cache()

    if ambience_path is None or not Path(ambience_path).exists():
        return
    say("混入环境声中")
    # 将提取出的环境声铺在生成伴奏下：响度自适应归一到音乐 RMS 的
    # ambience_level 倍（默认 0.35 ≈ -9dB，清晰可闻且不压过音乐），
    # 再循环铺满、淡入淡出
    gen, sr = sf.read(str(gen_path))
    if gen.ndim == 1:
        gen = np.stack([gen, gen], axis=1)
    amb, asr = sf.read(str(ambience_path))
    if amb.ndim > 1:
        amb = amb.mean(axis=1)
    amb = librosa.resample(amb, orig_sr=asr, target_sr=sr)

    def rms(x):
        return float(np.sqrt(np.mean(x ** 2))) or 1e-8

    target_rms = rms(gen) * float(ambience_level)
    amb = amb / rms(amb) * target_rms        # 响度对齐，素材多安静都可闻
    reps = int(np.ceil(len(gen) / len(amb))) or 1
    amb = np.tile(amb, reps)[:len(gen)]
    fade = min(int(2 * sr), len(amb) // 4)
    if fade:
        amb[:fade] *= np.linspace(0, 1, fade)
        amb[-fade:] *= np.linspace(1, 0, fade)
    mix = gen + amb[:, None]
    sf.write(str(mix_path), finalize_mix(mix), sr)


def _resolve_media(rel_path: str) -> Optional[Path]:
    """把 'outputs/...' 的 root 相对路径解析为绝对路径（缺省在 outputs/ 下找）"""
    if not rel_path:
        return None
    p = ROOT / rel_path if rel_path.startswith("outputs") else ROOT / "outputs" / rel_path
    return p if p.exists() else None


def mix_placements(gen_path: Path, placements: list, level: float, out_path: Path,
                   duck_db: float = 0.0):
    """按摆放位置把多段环境声渲染进伴奏。

    placements: [{file, start, length?}]，length 缺省为素材全长；
    length 超过素材时长时自动循环补齐（拖长音频块即循环）。
    duck_db > 0 时按环境声包络把音乐压低最多 duck_db dB（侧链避让）。
    """
    gen, sr = sf.read(str(gen_path))
    if gen.ndim == 1:
        gen = np.stack([gen, gen], axis=1)

    def rms(x):
        return float(np.sqrt(np.mean(x ** 2))) or 1e-8

    target_rms = rms(gen) * float(level)
    total = len(gen)
    amb_total = np.zeros(total)
    used = 0
    for pl in placements or []:
        src = _resolve_media(pl.get("file", ""))
        if src is None:
            continue
        a, asr = sf.read(str(src))
        if a.ndim > 1:
            a = a.mean(axis=1)
        a = librosa.resample(a, orig_sr=asr, target_sr=sr)
        a = a / rms(a) * target_rms
        want = float(pl.get("length", 0) or 0) * sr        # 0 = 素材全长
        need = int(want) if want > 0 else len(a)
        if need > len(a):                                   # 循环补齐
            reps = int(np.ceil(need / len(a)))
            a = np.tile(a, reps)
        a = a[:need]
        start = max(0, int(float(pl.get("start", 0)) * sr))
        n = min(len(a), total - start)
        if n <= 0:
            continue
        seg = a[:n].copy()
        fade = min(int(0.6 * sr), n // 3) or n
        seg[:fade] *= np.linspace(0, 1, fade)
        seg[-fade:] *= np.linspace(1, 0, fade)
        amb_total[start:start + n] += seg
        used += 1

    # 侧链避让：按环境声包络压低音乐，让环境声在混合频段里可闻
    if duck_db > 0 and np.any(amb_total):
        from scipy.ndimage import gaussian_filter1d
        env = np.abs(amb_total)
        env = gaussian_filter1d(env, sigma=int(0.15 * sr))
        peak = env.max()
        if peak > 1e-6:
            env = np.clip(env / peak, 0, 1) ** 0.7
            gain = 10 ** (-duck_db * env / 20)
            gen = gen * gain[:, None]

    mix = gen + amb_total[:, None]
    sf.write(str(out_path), finalize_mix(mix), sr)
    return used


# ─────────────────────────── 哼唱旋律分析 ───────────────────────────

_KH_MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_KH_MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
_PC = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def analyze_hum(upload_path: Path, jd: Path) -> dict:
    """哼唱 → 音符序列 + 调性 + 重合成旋律。返回结果字典并写 wav。"""
    y, sr = librosa.load(str(upload_path), sr=22050, mono=True)
    # 轻度降噪（哼唱含人声成分，用频谱减法保守压稳态噪声）
    try:
        import noisereduce as nr
        y = nr.reduce_noise(y=y, sr=sr, stationary=True, prop_decrease=0.5)
    except Exception:
        pass
    f0, voiced, _ = librosa.pyin(y, fmin=librosa.note_to_hz("C3"),
                                 fmax=librosa.note_to_hz("C6"), sr=sr)
    times = librosa.times_like(f0, sr=sr)
    v = ~np.isnan(f0)
    if v.sum() < 10:
        raise RuntimeError("未检测到哼唱内容（音高帧过少），请靠近麦克风重录")

    # 分段：有声连续段内，音高偏移持续 >70 音分即切分新音符
    notes = []
    seg_f, seg_t0 = [], None
    def flush(t_end):
        if len(seg_f) >= 4 and seg_t0 is not None:      # >= ~90ms
            notes.append((seg_t0, t_end, float(np.median(seg_f))))
    prev = None
    for i in np.where(v)[0]:
        if prev is None or times[i] - times[prev] > 0.18 or \
           abs(1200 * np.log2(f0[i] / np.median(seg_f[-5:] + [f0[i]]))) > 70:
            if prev is not None:
                flush(times[prev])
            seg_f, seg_t0 = [float(f0[i])], times[i]
        else:
            seg_f.append(float(f0[i]))
        prev = i
    flush(times[prev])
    if not notes:
        raise RuntimeError("哼唱音符过短，请每音至少唱 0.15 秒")

    # 调性识别：音级时长直方图 × Krumhansl 模板
    hist = np.zeros(12)
    for _, dur, hz in notes:
        hist[int(round(librosa.hz_to_midi(hz))) % 12] += dur
    if hist.sum() > 0:
        hist = hist / hist.max()
    key_i = int(np.argmax(np.array([np.corrcoef(hist, np.roll(_KH_MAJ, k))[0, 1] for k in range(12)])
                          + [np.corrcoef(hist, np.roll(_KH_MIN, k))[0, 1] for k in range(12)]))
    is_minor = key_i >= 12
    tonic = key_i % 12
    key_name = f"{_PC[tonic]} {'minor' if is_minor else 'major'}"
    scale = {0, 2, 4, 5, 7, 9, 11} if not is_minor else {0, 2, 3, 5, 7, 8, 10}

    # 量化到调内音级，八度限制 C3(48)-C6(84)
    q_notes = []
    for t0, t1, hz in notes:
        midi = int(round(librosa.hz_to_midi(hz)))
        midi = max(48, min(84, midi))
        pc = midi % 12
        if pc not in scale:                               # 吸附到最近的调内音
            best = min(scale, key=lambda s: min(abs(pc - s), 12 - abs(pc - s)))
            midi += best - pc if abs(best - pc) <= 6 else (best - pc - 12 if best - pc > 6 else best - pc + 12)
        q_notes.append({"start": round(t0, 2), "dur": round(t1 - t0, 2),
                        "midi": midi, "hz": round(float(librosa.midi_to_hz(midi)), 1)})
    # 合并相邻同音（滑音切分过度时）
    merged = []
    for n in q_notes:
        if merged and n["midi"] == merged[-1]["midi"] and n["start"] - (merged[-1]["start"] + merged[-1]["dur"]) < 0.05:
            merged[-1]["dur"] = round(n["start"] + n["dur"] - merged[-1]["start"], 2)
        else:
            merged.append(dict(n))

    # 重合成：三次谐波 + ADSR 包络的柔和旋律
    out = np.zeros(int(times[-1] * sr) + int(sr * 0.5))
    for n in merged:
        i0, i1 = int(n["start"] * sr), int((n["start"] + n["dur"]) * sr)
        t = np.arange(i1 - i0) / sr
        f = n["hz"]
        tone = 0.6 * np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t) \
             + 0.12 * np.sin(2 * np.pi * 3 * f * t)
        a = min(int(0.03 * sr), len(t) // 3)
        r = min(int(0.08 * sr), len(t) // 3)
        envl = np.ones(len(t))
        if a: envl[:a] = np.linspace(0, 1, a)
        if r: envl[-r:] = np.linspace(1, 0, r)
        out[i0:i1] += tone * envl * 0.7
    synth = jd / "melody_synth.wav"
    sf.write(str(synth), out / max(1.0, np.abs(out).max() / 0.8), sr)
    return {"notes": merged, "key": key_name, "note_count": len(merged),
            "melody": f"outputs/service_jobs/{jd.name}/melody_synth.wav"}


# ─────────────────────────── 任务队列（单 Worker） ───────────────────────────

def run_job(job: dict):
    jd = JOB_ROOT / job["id"]; jd.mkdir(parents=True, exist_ok=True)
    try:
        if job["type"] == "extract":
            job["stage"] = "加载分离模型（首次约20秒）"
            upload = UPLOAD_DIR / job["upload_id"]
            with _gpu_lock:
                load_audiosep()
                query, translated = zh2en(job["target_en"])
                if translated:
                    job["results"]["query_zh"] = job["target_en"]
                    job["target_en"] = query
                    job["results"]["query_en"] = query
                job["stage"] = f"AudioSep 提取：{job['target_en']}"
                stem = jd / "extracted.wav"
                audiosep_extract(str(upload), job["target_en"], str(stem))

                # T1 宽频主导兜底：提取结果与输入高度相关说明目标被主导声源
                # （水声/风声类宽频噪声）劫持。注意不能直接减去劫持结果——
                # 它可能混有目标成分；正确做法（已验证）是按"主导声源名"重新
                # 提取一份干净的背景，减去后在残差上重提目标。
                mix32 = librosa.load(str(upload), sr=32000, mono=True)[0]
                s1 = librosa.load(str(stem), sr=32000, mono=True)[0]
                n = min(len(mix32), len(s1)); m32, s1 = mix32[:n], s1[:n]
                c1 = float(np.corrcoef(m32, s1)[0, 1])
                if c1 > 0.85:
                    job["stage"] = "检测到主导噪声，执行减法二步管线"
                    # 主导声源候选：CLAP 对劫持结果的识别 + 常见宽频声源
                    try:
                        dom_tags = clap_tags(str(stem), topk=3)
                    except Exception:
                        dom_tags = []
                    cands = [t["en"] for t in dom_tags] + \
                            ["sound of water flowing", "wind blowing", "city traffic"]
                    best, best_c, best_stem = None, -1, None
                    for q in dict.fromkeys(cands):          # 去重保序
                        cp = jd / "dominant.wav"
                        audiosep_extract(str(upload), q, str(cp))
                        sc = librosa.load(str(cp), sr=32000, mono=True)[0][:n]
                        if len(sc) < n:
                            continue
                        cc = float(np.corrcoef(m32, sc)[0, 1])
                        if cc > best_c:
                            best, best_c, best_stem = q, cc, sc
                    if best_stem is not None:
                        alpha = float(np.dot(m32, best_stem) / np.dot(best_stem, best_stem))
                        residual = m32 - alpha * best_stem
                        peak = np.abs(residual).max()
                        if peak > 0.99:
                            residual *= 0.99 / peak
                        res_path = jd / "residual.wav"
                        sf.write(str(res_path), residual, 32000)
                        stem2 = jd / "extracted2.wav"
                        audiosep_extract(str(res_path), job["target_en"], str(stem2))
                        s2 = librosa.load(str(stem2), sr=32000, mono=True)[0][:n]
                        r2 = float(np.sqrt(np.mean(s2 ** 2))) if len(s2) == n else 0.0
                        if r2 > 1e-4:
                            job["results"]["fallback"] = (
                                f"broadband_subtraction (dominant='{best}' {best_c:.2f}, "
                                f"target corr to mix {c1:.2f}->{float(np.corrcoef(m32, s2)[0,1]):.2f})")
                            stem = stem2

                job["results"]["extracted"] = f"outputs/service_jobs/{job['id']}/{stem.name}"
                job["stage"] = "降噪增强"
                backend = denoise(stem, job["target_en"], jd / "denoised.wav")
                job["results"]["denoised"] = f"outputs/service_jobs/{job['id']}/denoised.wav"
                job["results"]["denoise_backend"] = backend
        elif job["type"] == "remix":
            # 纯 CPU 混音：伴奏 + 多段环境声按摆放位置渲染
            gen = _resolve_media(job.get("generated") or "")
            if gen is None:
                raise RuntimeError("generated track not found")
            job["stage"] = f"渲染混音（{len(job.get('placements') or [])} 段环境声）"
            jd_out = jd / "final_mix.wav"
            used = mix_placements(gen, job.get("placements") or [],
                                  job.get("ambience_level", 0.35), jd_out,
                                  duck_db=job.get("duck", 0.0))
            job["results"]["final"] = f"outputs/service_jobs/{job['id']}/final_mix.wav"
            job["results"]["placed"] = used
        elif job["type"] == "hum":
            # 哼唱旋律分析（纯 CPU）：F0→调性量化→重合成
            upload = UPLOAD_DIR / job["upload_id"]
            job["stage"] = "哼唱音高分析中"
            res = analyze_hum(upload, jd)
            job["results"].update(res)
        elif job["type"] == "generate":
            amb = None
            if job.get("ambience"):
                p = ROOT / "outputs" / job["ambience"].split("outputs/", 1)[1]
                if p.exists():
                    amb = p
            job["stage"] = "加载生成模型（约30秒）"
            with _gpu_lock:
                generate_and_mix(job["style"], job["target_en"], job["duration"],
                                 job["seed"], jd / "generated.wav", amb, jd / "final_mix.wav",
                                 stage=lambda s: job.__setitem__("stage", s),
                                 ambience_level=job.get("ambience_level", 0.35))
            job["results"]["generated"] = f"outputs/service_jobs/{job['id']}/generated.wav"
            if amb is not None:
                job["results"]["final"] = f"outputs/service_jobs/{job['id']}/final_mix.wav"
        job["status"] = "done"
    except Exception:
        job["error"] = traceback.format_exc(limit=3)
        job["status"] = "failed"
    finally:
        job["finished"] = time.time()


def worker():
    while True:
        job = _queue.get()
        run_job(job)


threading.Thread(target=worker, daemon=True).start()


def _gc_loop():
    """T7: 每 10 分钟清理超过 24h 的上传与任务产物。"""
    while True:
        time.sleep(600)
        cutoff = time.time() - 24 * 3600
        for d in (UPLOAD_DIR, JOB_ROOT):
            for p in list(d.iterdir()):
                try:
                    if p.stat().st_mtime < cutoff:
                        if p.is_dir():
                            shutil.rmtree(p, ignore_errors=True)
                        else:
                            p.unlink()
                except OSError:
                    pass


threading.Thread(target=_gc_loop, daemon=True).start()


def _warmup():
    """T9: 启动 20 秒后后台预热 AudioSep（拿锁，失败静默重试），
    让用户的首次识别请求从 ~15s 降到秒级。"""
    for _ in range(3):
        time.sleep(20)
        try:
            with _gpu_lock:
                load_audiosep()
            print("warmup: audiosep ready", flush=True)
            return
        except Exception as e:
            print(f"warmup retry: {e}", flush=True)


threading.Thread(target=_warmup, daemon=True).start()


# ─────────────────────────── API ───────────────────────────

class JobReq(BaseModel):
    type: str
    upload_id: Optional[str] = None
    target_en: str = "interesting sound"
    target_zh: Optional[str] = None
    style: str = "ambient"
    duration: float = 30.0
    seed: int = 42
    ambience: Optional[str] = None
    ambience_level: float = 0.35
    generated: Optional[str] = None            # remix: 伴奏轨（root 相对路径）
    placements: Optional[list] = None          # remix: [{file, start, length?}]
    duck: float = 0.0                          # remix: 音乐避让深度 dB


@app.get("/api/health")
def health():
    return {"status": "ok", "device": DEVICE,
            "pending_jobs": _queue.qsize(), "models_loaded": bool(_models["audiosep"])}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    data = await file.read()
    uid = f"{uuid.uuid4().hex[:12]}.wav"
    path = UPLOAD_DIR / uid
    path.write_bytes(data)
    try:
        info = sf.info(str(path))
    except Exception:
        path.unlink(missing_ok=True)
        raise HTTPException(400, "仅支持 WAV 格式（录音请用页面内录制按钮，会自动转 WAV）")
    return {"upload_id": uid, "duration": round(info.duration, 1), "sr": info.samplerate}


@app.post("/api/analyze/{upload_id}")
def analyze(upload_id: str):
    path = UPLOAD_DIR / upload_id
    if not path.exists():
        raise HTTPException(404, "upload not found")
    with _gpu_lock:
        tags = clap_tags(str(path))
    return {"tags": tags}


@app.post("/api/jobs")
def create_job(req: JobReq):
    job = {"id": uuid.uuid4().hex[:12], "status": "queued", "stage": "排队中",
           "created": time.time(), "results": {}, **req.dict()}
    _jobs[job["id"]] = job
    _queue.put(job)
    return {"job_id": job["id"]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "no such job")
    out = {k: job.get(k) for k in ("id", "status", "stage", "results", "error")}
    out["elapsed"] = round(time.time() - job["created"], 1)
    return out


@app.get("/")
@app.get("/home.html")
def index():
    return HTMLResponse((ROOT / "webapp" / "home.html").read_text(encoding="utf-8"))


@app.get("/memories")
@app.get("/memories.html")
def memories():
    return HTMLResponse((ROOT / "webapp" / "memories.html").read_text(encoding="utf-8"))


@app.get("/studio")
@app.get("/index.html")
def studio():
    return HTMLResponse((ROOT / "webapp" / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    print(f"SoundTrace MVP 服务启动: http://127.0.0.1:8090  (device={DEVICE})")
    uvicorn.run(app, host="127.0.0.1", port=8090, log_level="warning")
