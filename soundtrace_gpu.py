"""声迹 SoundTrace GPU 服务 — MVP 体验版

流水线: 上传WAV → CLAP识别声源 → AudioSep提取 → 降噪(ClearerVoice/noisereduce)
        → ACE-Step生成伴奏 → 与提取声混合 → 成品试听

设计遵循 docs/ARCHITECTURE.md：
- 单 Worker 任务队列（GPU 串行，AudioSep/CLAP 与 ACE-Step 互斥占用显存）
- 产物按任务归档 outputs/service_jobs/<job_id>/
- AudioSep / ACE-Step 作为可替换推理模块的边界保留

启动: hackathon-env/Scripts/python.exe soundtrace_gpu.py  →  http://127.0.0.1:8090
"""
import os, sys, gc, json, time, uuid, queue, threading, traceback, re, shutil, base64, hmac, io
from pathlib import Path
import tempfile

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
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form
from urllib.parse import unquote
from soundtrace_storage import commit_work, preserve_audio, preserve_references, LOCK as STORAGE_LOCK
from fastapi.responses import HTMLResponse, Response
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


# T13: 情绪标签 → 生成 prompt 修饰词
MOOD_PROMPTS = {
    "宁静": "peaceful, serene, calm", "思念": "nostalgic, tender, wistful",
    "雀跃": "uplifting, bright, playful", "忧郁": "melancholic, soft, introspective",
    "治愈": "healing, warm, gentle", "冒险": "adventurous, driving, energetic",
}

# T12: 作品索引（声音地图的数据源）
WORKS_FILE = ROOT / "outputs" / "works.json"
_works_lock = STORAGE_LOCK


def register_work(entry: dict):
    with _works_lock:
        entry = {**entry, "audio": preserve_audio(ROOT, entry.get("audio"))}
        works = []
        if WORKS_FILE.exists():
            try:
                works = json.loads(WORKS_FILE.read_text(encoding="utf-8"))
            except Exception:
                works = []
        works.append(entry)
        WORKS_FILE.write_text(json.dumps(works, ensure_ascii=False, indent=1), encoding="utf-8")

app = FastAPI(title="SoundTrace MVP")


@app.middleware("http")
async def demo_access(request: Request, call_next):
    """Public demo access gate; localhost remains frictionless when unset."""
    password = os.getenv("SOUNDTRACE_DEMO_PASSWORD", "")
    if os.getenv("SOUNDTRACE_PUBLIC") == "1" and not password:
        return Response("Demo password is not configured", status_code=503)
    if password:
        supplied = request.headers.get("authorization", "")
        expected = "Basic " + base64.b64encode(
            f"{os.getenv('SOUNDTRACE_DEMO_USER', 'soundtrace')}:{password}".encode()
        ).decode()
        if not hmac.compare_digest(supplied, expected):
            return Response("Access restricted", status_code=401,
                            headers={"WWW-Authenticate": 'Basic realm="SoundTrace demo"'})
    return await call_next(request)

app.mount("/outputs", StaticFiles(directory=ROOT / "outputs"), name="outputs")
app.mount("/assets", StaticFiles(directory=ROOT / "webapp" / "assets"), name="assets")
app.mount("/mineradio", StaticFiles(directory=ROOT / "third_party" / "Mineradio-paused-main" / "public", html=True), name="mineradio")
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
                     stage=None, ambience_level: float = 0.35,
                     melody_ref: Optional[Path] = None, ref_strength: float = 0.85):
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
    a2a = {}
    if melody_ref is not None and Path(melody_ref).exists():
        # T11: 哼唱参考驱动旋律（T8 实验验证 note-chroma 1.000）
        a2a = {"audio2audio_enable": True, "ref_audio_input": str(melody_ref),
               "ref_audio_strength": float(ref_strength)}
        say(f"以哼唱旋律为参考生成（强度 {ref_strength}）")
    pipe(audio_duration=float(duration), prompt=prompt, lyrics="[inst]",
         infer_step=27, guidance_scale=15.0, manual_seeds=[seed],
         save_path=str(gen_path), **a2a)
    del pipe; gc.collect(); torch.cuda.empty_cache()

    if ambience_path is None or not Path(ambience_path).exists():
        return prompt
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
    return prompt


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
    job["status"] = "running"
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
                # 素材索引（唱片册·素材库的磁带）
                mats = _load_json(MATERIALS_FILE, [])
                mats.append({"id": job["id"], "name": job["target_en"],
                             "audio": job["results"]["denoised"],
                             "raw": job["results"]["extracted"],
                             "created": time.time()})
                _save_json(MATERIALS_FILE, mats)
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
            # T12: 成品混音登记为作品（含元数据，地图数据源）
            meta = job.get("metadata") or {}
            if job.get("auto_register", True):
                register_work({"id": job["id"], "kind": "mix", "created": time.time(),
                           "title": meta.get("title") or f"声音明信片·{time.strftime('%m-%d %H:%M')}",
                           "metadata": meta,
                           "audio": f"outputs/service_jobs/{job['id']}/final_mix.wav"})
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
            melody = _resolve_media(job.get("melody_ref") or "")
            # T13: 情绪 → prompt 修饰词
            meta = job.get("metadata") or {}
            mood = (meta.get("mood") or "").strip()
            if mood in MOOD_PROMPTS:
                job["target_en"] = f"{job['target_en']}, {MOOD_PROMPTS[mood]}"
            job["stage"] = "加载生成模型（约30秒）"
            with _gpu_lock:
                prompt = generate_and_mix(job["style"], job["target_en"], job["duration"],
                                 job["seed"], jd / "generated.wav", amb, jd / "final_mix.wav",
                                 stage=lambda s: job.__setitem__("stage", s),
                                 ambience_level=job.get("ambience_level", 0.35),
                                 melody_ref=melody,
                                 ref_strength=job.get("ref_strength", 0.85))
            job["results"]["generated"] = f"outputs/service_jobs/{job['id']}/generated.wav"
            job["results"]["prompt"] = prompt
            # T12: 登记作品（供声音地图）
            if job.get("auto_register", True):
                register_work({"id": job["id"], "kind": "generated", "created": time.time(),
                           "title": meta.get("title") or f"{STYLE_NAMES.get(job['style'], '')}·{time.strftime('%m-%d')}",
                           "metadata": meta,
                           "audio": f"outputs/service_jobs/{job['id']}/generated.wav"})
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
        # Any previously saved work or extracted material must survive task cleanup.
        # If retention fails, skip this GC pass rather than removing referenced audio.
        try:
            preserve_references(ROOT)
        except OSError:
            continue
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
    auto_register: bool = True
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
    melody_ref: Optional[str] = None           # generate: 哼唱旋律参考（T11）
    ref_strength: float = 0.85                 # generate: audio2audio 强度
    metadata: Optional[dict] = None            # T12: {title, location, lat, lng, mood, story}


@app.get("/api/health")
def health():
    return {"status": "ok", "device": DEVICE,
            "pending_jobs": _queue.qsize(), "models_loaded": bool(_models["audiosep"])}


@app.get("/api/studio/health")
def studio_health():
    return {"editing": True, "storage": True, "ai": AUDIOSEP_DIR.exists() and ACESTEP_CKPT.exists()}


@app.post("/api/studio/works", status_code=201)
async def save_studio_work(request: Request):
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "请从声迹页面发起请求")
    encoded = request.headers.get("x-soundtrace-metadata", "%7B%7D")
    if len(encoded) > 24000:
        raise HTTPException(400, "作品信息过长")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 60 * 1024 * 1024:
            raise HTTPException(413, "音频文件过大")
    try:
        info = json.loads(unquote(encoded))
        if not isinstance(info, dict):
            raise ValueError("作品信息格式错误")
        return commit_work(ROOT, bytes(body), info)
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc


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


@app.get("/api/works")
def list_works():
    """T16: 声音地图数据源——全部已登记作品（含元数据与音频路径）"""
    try:
        works = json.loads(WORKS_FILE.read_text(encoding="utf-8"))
    except Exception:
        works = []
    for memory in _load_memories():
        if memory.get("music_audio"):
            works.append({"id": f"memory-vinyl-{memory['id']}", "memory_id": memory["id"],
                          "project": memory.get("project"), "title": memory["title"],
                          "kind": "mix", "collectible": "vinyl", "audio": memory["music_audio"],
                          "img": memory["cover_vinyl"], "cover": memory["cover_vinyl"],
                          "metadata": {"scene": memory.get("scene", "sea-window"),
                                       "location": memory.get("location"), "mood": memory.get("mood"),
                                       "story": memory.get("notes"), "weather": memory.get("weather"),
                                       "images": memory.get("images", []), "videos": memory.get("videos", []),
                                       "audio_files": memory.get("audio_files", []),
                                       "captured_at": memory.get("captured_at"),
                                       "lat": memory.get("lat"), "lng": memory.get("lng")},
                          "created": memory["created"]})
    return {"works": works[-100:]}


# ─────────────── 录音手记（记忆）：保存弹窗产物 + 封面生图 ───────────────
MEMORIES_FILE = ROOT / "outputs" / "memories.json"
MEMORY_DIR = ROOT / "outputs" / "memories"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
_STT = {"model": None}

_FONT_CANDIDATES = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc",
                    r"C:\Windows\Fonts\simhei.ttf"]


def _font(size: int):
    from PIL import ImageFont
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def make_cover(bg_path, title: str, sub: str, kind: str, out_path: Path):
    """生成磁带/唱片封面：有上传图片→图作背景+底部标签；无→白底黑字。
    kind: tape(4:3) | vinyl(1:1)"""
    from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
    W, H = (840, 630) if kind == "tape" else (800, 800)
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB")
        ratio = min(img.width / W, img.height / H)
        img = img.crop((int((img.width - W * ratio) / 2), int((img.height - H * ratio) / 2),
                        int((img.width + W * ratio) / 2), int((img.height + H * ratio) / 2))
                      ).resize((W, H))
        img = ImageEnhance.Color(img).enhance(1.12)
        img = ImageEnhance.Contrast(img).enhance(1.05)
        img = img.filter(ImageFilter.GaussianBlur(0.6))
    else:
        img = Image.new("RGB", (W, H), "#ffffff")        # 无图：白底黑字
    draw = ImageDraw.Draw(img, "RGBA")
    f_title, f_sub = _font(46), _font(26)
    label_h = 118
    draw.rectangle([0, H - label_h, W, H], fill=(255, 255, 255, 235))
    ink = (24, 44, 62, 255)
    draw.text((28, H - label_h + 16), (title or "一段声音")[:14], font=f_title, fill=ink)
    draw.text((30, H - 42), (sub or "")[:32], font=f_sub, fill=(90, 112, 130, 255))
    badge = "TAPE · 声音磁带" if kind == "tape" else "VINYL · 声音唱片"
    draw.rounded_rectangle([24, 22, 24 + 34 + len(badge) * 15, 62], radius=16,
                           fill=(20, 40, 60, 190))
    draw.text((34, 30), badge, font=_font(20), fill=(255, 255, 255, 230))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=92)
    return out_path


def _generate_memory_art(entry: dict, image_path: Path, mdir: Path, sub: str):
    """在后台基于用户图片和笔记生成唱片/磁带视觉，原图继续作为记忆背景。"""
    try:
        import requests
        from PIL import Image
        prompt = (
            "Create a square, painterly keepsake artwork inspired by this uploaded photo. "
            "Preserve the recognizable place and atmosphere, with warm light, tactile brush texture, "
            "clear focal subject and rich color. No letters, logos, cassette, record, frame or UI. "
            f"Sound: {entry['title'][:80]}. Memory: {entry.get('notes','')[:500]}. "
            f"Mood: {entry.get('mood','')[:60]}. Place: {entry.get('location','')[:100]}."
        )
        reference = mdir / "art_reference.png"
        with Image.open(image_path) as uploaded:
            uploaded.convert("RGB").save(reference, format="PNG")
        with reference.open("rb") as image_file:
            response = requests.post("https://api.openai.com/v1/images/edits",
                                     headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                                     data={"model": os.getenv("SOUNDTRACE_IMAGE_MODEL", "gpt-image-2.5-flare"),
                                           "prompt": prompt, "size": "1024x1024"},
                                     files={"image[]": (reference.name, image_file, "image/png")},
                                     timeout=180)
        response.raise_for_status()
        artwork = mdir / "generated_art.png"
        artwork.write_bytes(base64.b64decode(response.json()["data"][0]["b64_json"]))
        make_cover(artwork, entry["title"], sub, "tape", mdir / "cover_tape_ai.jpg")
        make_cover(artwork, entry["title"], sub, "vinyl", mdir / "cover_vinyl_ai.jpg")
        with STORAGE_LOCK:
            memories = _load_memories()
            for memory in memories:
                if memory["id"] == entry["id"]:
                    memory["cover_tape"] = f"outputs/memories/{entry['id']}/cover_tape_ai.jpg"
                    memory["cover_vinyl"] = f"outputs/memories/{entry['id']}/cover_vinyl_ai.jpg"
                    memory["art_status"] = "generated"
                    memory["artwork"] = f"outputs/memories/{entry['id']}/generated_art.png"
                    break
            _save_json(MEMORIES_FILE, memories)
    except Exception as exc:
        print(f"Memory artwork generation failed for {entry['id']}: {type(exc).__name__}: {exc}", flush=True)
        with STORAGE_LOCK:
            memories = _load_memories()
            for memory in memories:
                if memory["id"] == entry["id"]:
                    memory["art_status"] = "failed"
                    break
            _save_json(MEMORIES_FILE, memories)


def _load_memories():
    try:
        return json.loads(MEMORIES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


@app.get("/api/memories")
def get_memories():
    return {"memories": _load_memories()[::-1]}


@app.post("/api/memories")
async def save_memory(audio: UploadFile = File(...),
                      title: str = Form(""), notes: str = Form(""),
                      mood: str = Form(""), location: str = Form(""),
                      lat: float = Form(0), lng: float = Form(0),
                      weather: str = Form(""), captured_at: float = Form(0),
                      scene: str = Form("sea-window"),
                      project: str = Form(""), share: bool = Form(False),
                      music_audio: UploadFile = File(None),
                      images: list[UploadFile] = File(None),
                      videos: list[UploadFile] = File(None),
                      audio_files: list[UploadFile] = File(None)):
    """录音手记保存：原声 + 图片 + 时间/天气/心情/地点 → 生成磁带/唱片封面。
    磁带保存录音原声；唱片（生成音乐时）复用同一封面并携带全部信息。"""
    raw_audio = await audio.read()
    if not raw_audio or len(raw_audio) > 60_000_000 or raw_audio[:4] != b"RIFF" or raw_audio[8:12] != b"WAVE":
        raise HTTPException(400, "请上传不超过 60 MB 的 WAV 原声")
    if len(images or []) > 6 or len(videos or []) > 2 or len(audio_files or []) > 4:
        raise HTTPException(400, "最多上传 6 张图片、2 段视频和 4 段补充音频")
    if lat and not -90 <= lat <= 90 or lng and not -180 <= lng <= 180:
        raise HTTPException(400, "地点坐标无效")
    mid = uuid.uuid4().hex[:12]
    mdir = MEMORY_DIR / mid
    mdir.mkdir(parents=True, exist_ok=True)
    audio_path = mdir / "audio.wav"
    audio_path.write_bytes(raw_audio)
    music_path = None
    if music_audio is not None:
        generated = await music_audio.read()
        if not generated or len(generated) > 60_000_000 or generated[:4] != b"RIFF" or generated[8:12] != b"WAVE":
            raise HTTPException(400, "生成音乐需要不超过 60 MB 的 WAV 文件")
        music_path = mdir / "music.wav"
        music_path.write_bytes(generated)
    img_paths = []
    for i, f in enumerate(images or []):
        data = await f.read()
        if not data:
            continue
        if len(data) > 12_000_000:
            raise HTTPException(413, "每张图片需小于 12 MB")
        try:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
        except Exception as exc:
            raise HTTPException(400, "图片文件无法读取，请换一张图片") from exc
        ext = (f.filename or "x.jpg").split(".")[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
            ext = "jpg"
        p = mdir / f"img_{i}.{ext}"
        p.write_bytes(data)
        img_paths.append(p)
    video_paths = []
    for i, f in enumerate(videos or []):
        data = await f.read()
        ext = (f.filename or "").rsplit(".", 1)[-1].lower()
        if len(data) > 60_000_000:
            raise HTTPException(413, "每段视频需小于 60 MB")
        if data and ext in ("mp4", "webm", "mov"):
            p = mdir / f"video_{i}.{ext}"
            p.write_bytes(data)
            video_paths.append(p)
    extra_audio_paths = []
    for i, f in enumerate(audio_files or []):
        data = await f.read()
        ext = (f.filename or "").rsplit(".", 1)[-1].lower()
        if len(data) > 30_000_000:
            raise HTTPException(413, "每段补充音频需小于 30 MB")
        if data and ext in ("wav", "mp3", "m4a", "ogg", "webm"):
            p = mdir / f"extra_{i}.{ext}"
            p.write_bytes(data)
            extra_audio_paths.append(p)
    rel = lambda p: f"outputs/memories/{mid}/{p.name}"
    sub = " · ".join(x for x in [location, weather, mood,
                                 time.strftime("%Y-%m-%d %H:%M", time.localtime(captured_at or time.time()))] if x)
    make_cover(img_paths[0] if img_paths else None, title or notes[:14], sub, "tape",
               mdir / "cover_tape.jpg")
    make_cover(img_paths[0] if img_paths else None, title or notes[:14], sub, "vinyl",
               mdir / "cover_vinyl.jpg")
    entry = {"id": mid, "title": title[:80] or notes[:14] or "一段声音", "notes": notes[:1200],
             "mood": mood, "location": location, "lat": lat or None, "lng": lng or None,
             "weather": weather, "captured_at": captured_at or time.time(),
             "audio": rel(audio_path),
             "music_audio": rel(music_path) if music_path else None,
             "images": [rel(p) for p in img_paths],
             "videos": [rel(p) for p in video_paths],
             "audio_files": [rel(p) for p in extra_audio_paths],
             "scene": scene if scene in ("sea-window", "rainy-city", "autumn-lake", "snow-mountain", "spring-meadow", "desert-dusk") else "sea-window",
             "project": project[:24000] if project else None,
             "cover_tape": rel(mdir / "cover_tape.jpg"),
             "cover_vinyl": rel(mdir / "cover_vinyl.jpg"),
             "created": time.time(),
             "art_status": "pending" if img_paths and os.getenv("OPENAI_API_KEY") else
                           "needs_provider" if img_paths else "text_only"}
    with STORAGE_LOCK:
        items = _load_memories()
        items.append(entry)
        _save_json(MEMORIES_FILE, items)
    if entry["art_status"] == "pending":
        threading.Thread(target=_generate_memory_art,
                         args=(entry.copy(), img_paths[0], mdir, sub), daemon=True).start()
    if share:
        post_feed(entry["notes"] or entry["title"], kind="tape", audio=entry["audio"],
                  img=entry["images"][0] if entry["images"] else entry["cover_tape"])
    return entry


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """『这是什么声音』的语音识别输入（faster-whisper 本地，懒加载）"""
    if _STT["model"] is None:
        try:
            from faster_whisper import WhisperModel
            _STT["model"] = WhisperModel(os.getenv("SOUNDTRACE_WHISPER_MODEL", "base"),
                                         device="cpu", compute_type="int8",
                                         download_root=str(ROOT / "outputs" / "whisper"))
        except Exception as exc:
            raise HTTPException(503, "语音识别模型尚未准备好，请直接输入文字或稍后重试") from exc
    data = await file.read()
    if not data or len(data) > 10_000_000:
        raise HTTPException(400, "语音输入需小于 10 MB")
    with tempfile.NamedTemporaryFile(suffix=".wav", dir=ROOT / "outputs", delete=False) as handle:
        handle.write(data)
        tmp = Path(handle.name)
    try:
        segments, _ = _STT["model"].transcribe(str(tmp), language="zh", beam_size=1)
        return {"text": "".join(s.text for s in segments).strip()}
    finally:
        tmp.unlink(missing_ok=True)


def _save_user_image(data: bytes, stem: str, max_side: int) -> Path:
    from PIL import Image
    try:
        with Image.open(io.BytesIO(data)) as original:
            image = original.convert("RGB")
            image.thumbnail((max_side, max_side))
            folder = ROOT / "outputs" / "user"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{stem}-{uuid.uuid4().hex[:8]}.jpg"
            image.save(path, "JPEG", quality=88)
            return path
    except Exception as exc:
        raise HTTPException(400, "图片无法读取，请选择 JPG、PNG 或 WebP") from exc


@app.post("/api/user/avatar")
async def upload_avatar(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 8_000_000:
        raise HTTPException(413, "头像需小于 8 MB")
    p = _save_user_image(data, "avatar", 512)
    u = get_user()
    u["avatar_img"] = f"outputs/user/{p.name}"
    _save_json(USER_FILE, u)
    return {"avatar_img": u["avatar_img"]}


@app.post("/api/user/background")
async def upload_background(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 12_000_000:
        raise HTTPException(413, "背景图片需小于 12 MB")
    p = _save_user_image(data, "background", 1600)
    u = get_user()
    u["background_img"] = f"outputs/user/{p.name}"
    _save_json(USER_FILE, u)
    return {"background_img": u["background_img"]}


class BeatReq(BaseModel):
    file: str


@app.post("/api/analyze-beat")
def analyze_beat(req: BeatReq):
    """T14: 节拍分析——返回 BPM 与拍点时间，供 DAW 吸附"""
    p = _resolve_media(req.file)
    if p is None:
        raise HTTPException(404, "file not found")
    y, sr = librosa.load(str(p), sr=22050, mono=True)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])       # 新版 librosa 返回数组
    times = librosa.frames_to_time(beats, sr=sr)
    return {"bpm": round(float(tempo), 1),
            "beats": [round(float(t), 3) for t in times]}


@app.get("/map")
def map_page():
    return HTMLResponse((ROOT / "webapp" / "map.html").read_text(encoding="utf-8"))


# ─────────────── 新交互层（照片墙/素材/信箱/社区/用户） ───────────────
PHOTOS_FILE = ROOT / "outputs" / "photos.json"
MATERIALS_FILE = ROOT / "outputs" / "materials.json"
EXCHANGES_FILE = ROOT / "outputs" / "exchanges.json"
FEED_FILE = ROOT / "outputs" / "feed.json"
USER_FILE = ROOT / "outputs" / "user.json"
PHOTO_DIR = ROOT / "outputs" / "photos"
PHOTO_DIR.mkdir(parents=True, exist_ok=True)
SEED_DIR = ROOT / "outputs" / "seeds"
SEED_DIR.mkdir(parents=True, exist_ok=True)
_new_lock = STORAGE_LOCK


def _load_json(p, default):
    with _new_lock:
        try:
            return json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:
            return default


def _save_json(p, data):
    with _new_lock:
        Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _seed_demo():
    """收件箱/社区演示种子（无则建）"""
    src = WORKSPACE / "test-materials" / "env-sounds-long"
    for f, name in [("pouring_water_15s.wav", "seed_tape_water.wav"),
                    ("chirping_birds_15s.wav", "seed_tape_birds.wav")]:
        s, d = src / f, SEED_DIR / name
        if s.exists() and not d.exists():
            shutil.copy(s, d)
    if not (SEED_DIR / "seed_vinyl.wav").exists():
        gens = sorted(JOB_ROOT.glob("*/generated.wav"), key=lambda p: p.stat().st_mtime)
        if gens:
            shutil.copy(gens[-1], SEED_DIR / "seed_vinyl.wav")
    _existing_feed = _load_json(FEED_FILE, []) or []
    if not any(p.get("img") for p in _existing_feed):
        # 社区示例内容（旅人经历图文，案例图为场景资产）
        _save_json(FEED_FILE, _existing_feed + [
            {"id": "seedp1", "text": "在喀纳斯待了三天，每天清晨湖面起雾。录了一段水声和鸟鸣，回来做成了这张《雾中晨走》。",
             "img": "assets/scenes-v1/autumn-lake.png", "audio": "outputs/seeds/seed_tape_water.wav",
             "author": "背包的北落", "created": time.time() - 86400 * 3},
            {"id": "seedp2", "text": "重庆的雨夜，出租屋窗外全是我听不懂的川音。把车流声交给了 AI，它还给我一首 lo-fi。",
             "img": "assets/scenes-v1/rainy-city.png", "audio": "outputs/seeds/seed_vinyl.wav",
             "author": "山城客", "created": time.time() - 86400 * 2},
            {"id": "seedp3", "text": "玉龙雪山的缆车上不敢说话，怕错过风声。海拔 4506 米，这是我录过最安静的一段。",
             "img": "assets/scenes-v1/snow-mountain.png", "audio": None,
             "author": "雪线以南", "created": time.time() - 86400},
            {"id": "seedp4", "text": "呼伦贝尔的花野，风把歌声吹得很远。哼了一段不成调的旋律，AI 帮我补完了它。",
             "img": "assets/scenes-v1/spring-meadow.png", "audio": None,
             "author": "骑马的浪人", "created": time.time() - 3600 * 5},
        ])
    ex = _load_json(EXCHANGES_FILE, None)
    if ex is None:
        _save_json(EXCHANGES_FILE, [
            {"id": "seed1", "dir": "in", "kind": "tape", "title": "一段溪水声",
             "from": "雪山下的旅人", "audio": "outputs/seeds/seed_tape_water.wav",
             "story": "虎跳峡旁录的，水很急。希望它成为你的一段伴奏。",
             "allow_reuse": True, "created": time.time() - 86400},
            {"id": "seed2", "dir": "in", "kind": "vinyl", "title": "《雾中晨走》",
             "from": "匿名", "audio": "outputs/seeds/seed_vinyl.wav",
             "story": "用海边风声做的，送给你。", "allow_reuse": False,
             "created": time.time() - 3600},
        ])


class PhotoIn(BaseModel):
    title: str = "一张声音记忆"
    story: str = ""
    audio: Optional[str] = None              # root 相对音频路径
    mood: Optional[str] = None


@app.post("/api/photos")
async def add_photo(info: PhotoIn, file: UploadFile = File(...)):
    """照片墙上的一张照片：图片 + 故事 + 关联录音"""
    data = await file.read()
    if len(data) > 12_000_000:
        raise HTTPException(400, "图片过大（>12MB）")
    ext = (file.filename or "x.jpg").split(".")[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
        ext = "jpg"
    pid = uuid.uuid4().hex[:12]
    (PHOTO_DIR / f"{pid}.{ext}").write_bytes(data)
    photos = _load_json(PHOTOS_FILE, [])
    photos.append({"id": pid, "title": info.title, "story": info.story,
                   "mood": info.mood, "audio": info.audio,
                   "img": f"outputs/photos/{pid}.{ext}", "created": time.time()})
    _save_json(PHOTOS_FILE, photos)
    return {"id": pid}


@app.get("/api/photos")
def get_photos():
    photos = _load_json(PHOTOS_FILE, [])
    for memory in _load_memories():
        for index, image in enumerate(memory.get("images", [])):
            photos.append({"id": f"memory-photo-{memory['id']}-{index}", "title": memory["title"],
                           "img": image, "audio": memory["audio"], "created": memory["created"],
                           "metadata": {"scene": memory.get("scene", "sea-window"),
                                        "story": memory.get("notes"), "mood": memory.get("mood"),
                                        "location": memory.get("location"), "weather": memory.get("weather")}})
    return {"photos": photos[::-1]}


@app.get("/api/materials")
def get_materials():
    """素材库（磁带）：提取完成的素材索引 + 录音手记（带封面，存原声）"""
    mats = _load_json(MATERIALS_FILE, [])
    for m in _load_memories():
        mats.append({"id": f"mem_{m['id']}", "name": m["title"], "audio": m["audio"],
                     "cover": m["cover_tape"], "memory": True,
                     "metadata": {"scene": m.get("scene", "sea-window"),
                                  "location": m.get("location"), "mood": m.get("mood"),
                                  "story": m.get("notes"), "lat": m.get("lat"), "lng": m.get("lng"),
                                  "images": m.get("images", []), "videos": m.get("videos", []),
                                  "audio_files": m.get("audio_files", []),
                                  "weather": m.get("weather"),
                                  "captured_at": m.get("captured_at")},
                     "created": m.get("created")})
    return {"materials": mats[::-1]}


@app.get("/capture")
def capture_page():
    return HTMLResponse((ROOT / "webapp" / "capture.html").read_text(encoding="utf-8"))


@app.get("/api/inbox")
def get_inbox():
    return {"items": [x for x in _load_json(EXCHANGES_FILE, []) if x["dir"] == "in"][::-1]}


@app.get("/api/exchange")
def get_exchanges():
    return {"items": _load_json(EXCHANGES_FILE, [])}


class ExchangeIn(BaseModel):
    kind: str                                  # photo | vinyl | tape
    title: str
    audio: Optional[str] = None
    img: Optional[str] = None
    sync_feed: bool = False
    allow_reuse: bool = False


@app.post("/api/exchange")
def send_exchange(req: ExchangeIn):
    """把照片/唱片/磁带投进信箱：匿名寄给一位匹配用户，可选同步社区"""
    eid = uuid.uuid4().hex[:12]
    entry = {"id": eid, "dir": "out", "kind": req.kind, "title": req.title,
             "audio": req.audio, "img": req.img, "to": "喜好匹配的旅人",
             "allow_reuse": req.allow_reuse, "created": time.time()}
    ex = _load_json(EXCHANGES_FILE, [])
    ex.append(entry)
    _save_json(EXCHANGES_FILE, ex)
    if req.sync_feed:
        post_feed(req.title + "（已寄出）", kind=req.kind,
                  audio=req.audio, img=req.img, note="匿名交换 · 同步动态")
    return entry


@app.post("/api/exchange/{eid}/contact")
def request_contact(eid: str):
    """对收到的匿名信件发起联系方式交换请求（演示：标记状态）"""
    ex = _load_json(EXCHANGES_FILE, [])
    for x in ex:
        if x["id"] == eid:
            x["contact"] = "requested"
    _save_json(EXCHANGES_FILE, ex)
    return {"status": "requested", "note": "对方同意后你们将互换站内联系方式（演示）"}


def post_feed(text, kind=None, audio=None, img=None, note=None, author=None):
    feed = _load_json(FEED_FILE, [])
    feed.append({"id": uuid.uuid4().hex[:10], "text": text, "kind": kind,
                 "audio": audio, "img": img, "note": note,
                 "author": author or _load_json(USER_FILE, {}).get("name", "我"),
                 "created": time.time()})
    _save_json(FEED_FILE, feed)


class FeedIn(BaseModel):
    text: str
    audio: Optional[str] = None
    img: Optional[str] = None


@app.post("/api/feed")
def add_feed(req: FeedIn):
    post_feed(req.text, audio=req.audio, img=req.img)
    return {"ok": True}


@app.get("/api/feed")
def get_feed():
    return {"posts": _load_json(FEED_FILE, [])[::-1]}


@app.get("/api/user")
def get_user():
    u = _load_json(USER_FILE, {})
    if not u:
        u = {"name": "旅行者_" + uuid.uuid4().hex[:4], "avatar": "🎧", "streak": 0,
             "last_checkin": None, "logged_in": False}
        _save_json(USER_FILE, u)
    return u


class UserIn(BaseModel):
    name: Optional[str] = None
    avatar: Optional[str] = None
    logged_in: Optional[bool] = None


@app.post("/api/user")
def set_user(req: UserIn):
    u = get_user()
    if req.name is not None:
        name = req.name.strip()
        if not name or len(name) > 32:
            raise HTTPException(400, "昵称请填写 1 到 32 个字")
        u["name"] = name
    if req.avatar is not None:
        u["avatar"] = req.avatar
    if req.logged_in is not None:
        u["logged_in"] = req.logged_in
    _save_json(USER_FILE, u)
    return u


@app.post("/api/user/checkin")
def checkin():
    u = get_user()
    today = time.strftime("%Y-%m-%d")
    if u.get("last_checkin") == today:
        return {"ok": False, "msg": "今天已签到", **u}
    u["last_checkin"] = today
    u["streak"] = (u.get("streak", 0) + 1) if time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400)) == u.get("prev_date") else 1
    u["prev_date"] = today
    _save_json(USER_FILE, u)
    return {"ok": True, "msg": f"签到成功，连续 {u['streak']} 天", **u}


@app.get("/")
def index():
    return HTMLResponse((ROOT / "webapp" / "home.html").read_text(encoding="utf-8"))


@app.get("/studio")
def studio():
    return HTMLResponse((ROOT / "webapp" / "index.html").read_text(encoding="utf-8"))


@app.get("/album")
def album_page():
    return HTMLResponse((ROOT / "webapp" / "album-room.html").read_text(encoding="utf-8"))


@app.get("/community")
def community_page():
    return HTMLResponse((ROOT / "webapp" / "community.html").read_text(encoding="utf-8"))


@app.get("/me")
def me_page():
    # “我的”与收藏间功能合并为一页
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/album?profile=1")


if __name__ == "__main__":
    _seed_demo()
    # 0.0.0.0：允许手机/小程序在同一局域网访问（真机调试必需）
    print(f"SoundTrace MVP 服务启动: http://127.0.0.1:8090  (device={DEVICE})")
    uvicorn.run(app, host="0.0.0.0", port=8090, log_level="warning")
