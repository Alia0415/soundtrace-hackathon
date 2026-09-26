"""T8 实验：ACE-Step audio2audio 能否保留哼唱旋律轮廓？

设计：同一 prompt/种子生成三版——
  A. baseline  纯文本生成（无参考）
  B. a2a_50    哼唱作参考, ref_audio_strength=0.5
  C. a2a_85    哼唱作参考, ref_audio_strength=0.85
指标：note-chroma 分数——已知哼唱音符的时窗内，生成音频 chroma 在该音符
音级上的相对能量（1.0=完美保留该音，随机背景约 0.3-0.6）。
产物：test-audio/experiments/a2a_*.wav（可试听），结论写入 ROADMAP。
"""
import os, time, json
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import numpy as np
import librosa

# 全部字面量绝对路径，不做任何拼接（无路径穿越向量）
CKPT = r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/music-arrangement-tools/ACE-Step/checkpoints/models/ACE-Step--ACE-Step-v1-3.5B/snapshots/master"
HUM = r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/test-audio/hum_harmonic.wav"
OUT_DIR = r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/test-audio/experiments"
os.makedirs(OUT_DIR, exist_ok=True)

# 哼唱基准的真实音符（C4 E4 G4 A4 G4 E4 D4 C4，每音 0.8s + 0.1s 间隔）
MIDIS = [60, 64, 67, 69, 67, 64, 62, 60]
STEP, NOTE_DUR = 0.9, 0.75

from acestep.pipeline_ace_step import ACEStepPipeline

PROMPT = "soft instrumental melody, gentle piano and warm strings, calm, 90 bpm"

pipe = ACEStepPipeline(checkpoint_dir=CKPT, cpu_offload=True)

OUT_BASE = r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/test-audio/experiments/a2a_baseline.wav"
OUT_50 = r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/test-audio/experiments/a2a_50.wav"
OUT_85 = r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/test-audio/experiments/a2a_85.wav"

conds = [
    ("baseline", OUT_BASE, {}),
    ("a2a_50", OUT_50, {"audio2audio_enable": True, "ref_audio_input": HUM, "ref_audio_strength": 0.5}),
    ("a2a_85", OUT_85, {"audio2audio_enable": True, "ref_audio_input": HUM, "ref_audio_strength": 0.85}),
]
paths = {}
for name, out, kw in conds:
    t0 = time.time()
    pipe(audio_duration=8.0, prompt=PROMPT, lyrics="[inst]", infer_step=27,
         guidance_scale=15.0, manual_seeds=[42], save_path=out, **kw)
    paths[name] = out
    print(f"{name}: {time.time()-t0:.0f}s", flush=True)

def note_chroma_score(path):
    y, sr = librosa.load(path, sr=22050, mono=True)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)      # 12 x T
    fps = chroma.shape[1] / (len(y) / sr)
    per_note = []
    for i, midi in enumerate(MIDIS):
        f0, f1 = int((i * STEP + 0.05) * fps), int((i * STEP + NOTE_DUR) * fps)
        seg = chroma[:, f0:f1].mean(axis=1)
        per_note.append(float(seg[midi % 12] / (seg.max() + 1e-9)))
    return float(np.mean(per_note)), per_note

print("\n==== T8 旋律保持实验结果 ====", flush=True)
results = {}
for name in paths:
    score, per = note_chroma_score(paths[name])
    results[name] = round(score, 3)
    print(f"{name:9s} note-chroma = {score:.3f}", flush=True)

hum_score, _ = note_chroma_score(HUM)
print(f"{'hum_ref':9s} note-chroma = {hum_score:.3f}（参考自身，理论上限）", flush=True)

preserve = results["a2a_85"] - results["baseline"]
results["_conclusion"] = (
    f"a2a_85 比 baseline 高 {preserve:+.3f}；"
    + ("audio2audio 具备旋律保持能力，产品可用" if preserve > 0.12
       else "旋律保持弱，产品应走'哼唱→MIDI→重合成'路线（已实现）"))
print(results["_conclusion"], flush=True)

import pathlib
pathlib.Path(r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/test-audio/experiments/a2a_results.json").write_text(
    json.dumps({"scores": results, "hum_self": round(hum_score, 3)}, ensure_ascii=False, indent=1),
    encoding="utf-8")
print("T8 EXPERIMENT DONE", flush=True)
