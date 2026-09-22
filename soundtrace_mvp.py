"""SoundTrace core-audio feasibility MVP. NumPy-only and offline-capable."""
from __future__ import annotations

import argparse
import json
import math
import os
import shlex
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 16000
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"


def write_wav(path: Path, audio: np.ndarray, sr: int = SR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    x = np.asarray(audio, dtype=np.float64)
    x = np.nan_to_num(x)
    peak = max(1.0, float(np.max(np.abs(x))) / 0.98)
    pcm = np.round(np.clip(x / peak, -1, 1) * 32767).astype("<i2")
    channels = 1 if pcm.ndim == 1 else pcm.shape[1]
    with wave.open(str(path), "wb") as f:
        f.setnchannels(channels)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(pcm.tobytes())


def read_wav(path: Path, target_sr: int = SR) -> np.ndarray:
    with wave.open(str(path), "rb") as f:
        channels, width, sr, n = f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()
        raw = f.readframes(n)
    if width == 1:
        x = (np.frombuffer(raw, np.uint8).astype(float) - 128) / 128
    elif width == 2:
        x = np.frombuffer(raw, "<i2").astype(float) / 32768
    elif width == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        v = b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16)
        x = ((v ^ 0x800000) - 0x800000).astype(float) / 8388608
    elif width == 4:
        x = np.frombuffer(raw, "<i4").astype(float) / 2147483648
    else:
        raise ValueError(f"Unsupported WAV sample width: {width}")
    x = x.reshape(-1, channels).mean(axis=1)
    if sr != target_sr:
        old = np.arange(len(x)) / sr
        new = np.arange(round(len(x) * target_sr / sr)) / target_sr
        x = np.interp(new, old, x)
    return x


def normalize(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    p = float(np.max(np.abs(x))) if len(x) else 0
    return x * (peak / p) if p > 1e-9 else x


def fft_filter(x: np.ndarray, low: float = 0, high: float = SR / 2, sr: int = SR) -> np.ndarray:
    n = len(x)
    spec = np.fft.rfft(x)
    freq = np.fft.rfftfreq(n, 1 / sr)
    edge = 80.0
    lo = np.clip((freq - low) / edge, 0, 1) if low else np.ones_like(freq)
    hi = np.clip((high - freq) / edge, 0, 1) if high < sr / 2 else np.ones_like(freq)
    return np.fft.irfft(spec * lo * hi, n)


def clean_environment(x: np.ndarray, sr: int = SR) -> np.ndarray:
    """Remove rumble and stationary noise with an overlap-add spectral gate."""
    x = fft_filter(x - np.mean(x), 55, 7600, sr)
    frame, hop = 1024, 256
    win = np.hanning(frame)
    padded = np.pad(x, (frame, frame))
    starts = range(0, len(padded) - frame + 1, hop)
    specs = np.array([np.fft.rfft(padded[s:s + frame] * win) for s in starts])
    noise = np.percentile(np.abs(specs), 18, axis=0)
    mag = np.abs(specs)
    gain = np.clip((mag - 1.35 * noise) / (mag + 1e-8), 0.12, 1.0)
    gain = 0.7 * gain + 0.3 * np.roll(gain, 1, axis=0)
    out = np.zeros_like(padded)
    weight = np.zeros_like(padded)
    for i, s in enumerate(starts):
        y = np.fft.irfft(specs[i] * gain[i], frame) * win
        out[s:s + frame] += y
        weight[s:s + frame] += win * win
    out = out[frame:frame + len(x)] / np.maximum(weight[frame:frame + len(x)], 1e-5)
    return normalize(out, 0.88)


def extract_target(x: np.ndarray, prompt: str, work: Path, sr: int = SR) -> tuple[np.ndarray, str]:
    """Use external AudioSep when configured; otherwise apply a transparent DSP fallback."""
    template = os.environ.get("AUDIOSEP_COMMAND")
    if template:
        inp, out = work / "audiosep_input.wav", work / "audiosep_target.wav"
        write_wav(inp, x, sr)
        cmd = template.format(input=str(inp), prompt=prompt, output=str(out))
        subprocess.run(shlex.split(cmd), check=True)
        return read_wav(out, sr), "audiosep"
    p = prompt.lower()
    if any(k in p for k in ("bird", "鸟", "chirp", "铃", "bell")):
        band = (1200, 7200)
    elif any(k in p for k in ("traffic", "车", "train", "地铁", "engine")):
        band = (60, 1200)
    elif any(k in p for k in ("voice", "人声", "speech")):
        band = (140, 3800)
    else:
        band = (100, 6500)
    return normalize(fft_filter(x, *band, sr), 0.85), f"dsp_bandpass_{band[0]}_{band[1]}"


def pitch_track(x: np.ndarray, sr: int = SR) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Autocorrelation F0 tracker tuned for humming (C3–C6)."""
    frame, hop = 1024, 160
    times, hz, conf = [], [], []
    lo, hi = int(sr / 1047), int(sr / 130)
    for s in range(0, max(1, len(x) - frame), hop):
        y = x[s:s + frame]
        if len(y) < frame:
            break
        y = (y - np.mean(y)) * np.hanning(frame)
        rms = math.sqrt(float(np.mean(y * y)))
        ac = np.correlate(y, y, mode="full")[frame - 1:]
        ac /= ac[0] + 1e-9
        lag = lo + int(np.argmax(ac[lo:hi]))
        c = float(ac[lag])
        times.append((s + frame / 2) / sr)
        hz.append(sr / lag if rms > 0.008 and c > 0.28 else 0)
        conf.append(c if rms > 0.008 else 0)
    return np.array(times), np.array(hz), np.array(conf)


def correct_melody(times: np.ndarray, hz: np.ndarray) -> np.ndarray:
    midi = np.zeros_like(hz)
    voiced = hz > 0
    midi[voiced] = 69 + 12 * np.log2(hz[voiced] / 440)
    # C major; snap to nearest permitted pitch class.
    allowed = np.array([0, 2, 4, 5, 7, 9, 11])
    for i in np.where(voiced)[0]:
        candidates = np.arange(48, 85)
        candidates = candidates[np.isin(candidates % 12, allowed)]
        midi[i] = candidates[np.argmin(np.abs(candidates - midi[i]))]
    # Median smoothing removes octave glitches while retaining phrase gaps.
    smoothed = midi.copy()
    for i in range(2, len(midi) - 2):
        vals = midi[i - 2:i + 3]
        vals = vals[vals > 0]
        if len(vals) >= 3:
            smoothed[i] = np.median(vals)
    return smoothed


def synth_melody(midi: np.ndarray, duration: float, sr: int = SR) -> np.ndarray:
    n = int(duration * sr)
    if not len(midi):
        return np.zeros(n)
    idx = np.minimum((np.arange(n) / sr / 0.01).astype(int), len(midi) - 1)
    notes = midi[idx]
    freq = np.where(notes > 0, 440 * 2 ** ((notes - 69) / 12), 0)
    phase = np.cumsum(2 * np.pi * freq / sr)
    tone = (0.78 * np.sin(phase) + 0.18 * np.sin(2 * phase) + 0.04 * np.sin(3 * phase))
    gate = (notes > 0).astype(float)
    kernel = np.ones(320) / 320
    gate = np.convolve(gate, kernel, mode="same")
    return normalize(tone * gate, 0.78)


def loop_to(x: np.ndarray, n: int) -> np.ndarray:
    if not len(x):
        return np.zeros(n)
    return np.tile(x, math.ceil(n / len(x)))[:n]


def arrange_mix(environment: np.ndarray, target: np.ndarray, melody: np.ndarray, duration: float, sr: int = SR) -> np.ndarray:
    n = int(duration * sr)
    env, tgt, mel = loop_to(environment, n), loop_to(target, n), loop_to(melody, n)
    t = np.arange(n) / sr
    fade = np.minimum(np.clip(t / 2.5, 0, 1), np.clip((duration - t) / 3.0, 0, 1))
    # Sidechain-like target pulses make environmental identity audible without masking melody.
    pulse = 0.62 + 0.38 * np.maximum(0, np.sin(2 * np.pi * 1.75 * t)) ** 5
    left = (0.34 * env + 0.25 * tgt * pulse + 0.48 * mel) * fade
    right = (0.34 * np.roll(env, 170) + 0.25 * np.roll(tgt, 420) * pulse + 0.48 * mel) * fade
    stereo = np.column_stack([left, right])
    # Soft limiter.
    return np.tanh(stereo * 1.25) * 0.88


def make_demo_inputs(duration: float = 12, sr: int = SR) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(20260922)
    n, t = int(duration * sr), np.arange(int(duration * sr)) / sr
    # Stylised rainy street: filtered rain, low traffic, footsteps, bird calls.
    rain = rng.normal(0, 1, n)
    rain = rain - np.r_[0, rain[:-1]] * 0.72
    traffic = 0.32 * np.sin(2 * np.pi * (68 + 5 * np.sin(2 * np.pi * .08 * t)) * t)
    env = 0.14 * rain + traffic
    for at in np.arange(0.7, duration, 1.15):
        i = int(at * sr); size = min(int(.16 * sr), n - i)
        if size > 0:
            env[i:i + size] += .65 * rng.normal(size=size) * np.exp(-np.arange(size) / (sr * .035))
    for at, f in [(1.8, 2100), (2.2, 2700), (6.4, 2350), (9.1, 2900)]:
        i = int(at * sr); size = min(int(.32 * sr), n - i)
        if size > 0:
            tt = np.arange(size) / sr
            env[i:i + size] += .55 * np.sin(2 * np.pi * (f + 480 * tt) * tt) * np.exp(-tt * 7)
    # Intentionally drifting/noisy hummed phrase in C major.
    phrase = [(60,.55),(62,.55),(64,1.05),(0,.25),(64,.5),(67,.55),(69,1.1),(0,.3),
              (67,.5),(64,.55),(62,.55),(60,1.2),(0,.45)]
    hum = np.zeros(n); pos = 0
    for note, dur in phrase:
        size = min(int(dur * sr), n - pos)
        if size <= 0: break
        tt = np.arange(size) / sr
        if note:
            base = 440 * 2 ** ((note - 69) / 12)
            drift = 1 + .018 * np.sin(2 * np.pi * .35 * tt + note) + .009 * np.sin(2 * np.pi * 5.2 * tt)
            phase = np.cumsum(2 * np.pi * base * drift / sr)
            amp = np.minimum(1, tt / .08) * np.minimum(1, (dur - tt) / .1)
            hum[pos:pos + size] = .65 * (np.sin(phase) + .18 * np.sin(2 * phase)) * amp
        pos += size
    hum += .025 * rng.normal(size=n)
    return normalize(env), normalize(hum)


def run(environment: np.ndarray, hum: np.ndarray, prompt: str, duration: float) -> dict:
    OUT.mkdir(exist_ok=True)
    clean = clean_environment(environment)
    target, backend = extract_target(clean, prompt, OUT)
    times, hz, conf = pitch_track(hum)
    midi = correct_melody(times, hz)
    melody = synth_melody(midi, max(len(hum) / SR, 0.1))
    mix = arrange_mix(clean, target, melody, duration)
    files = {
        "environment_clean": OUT / "01_environment_clean.wav",
        "target": OUT / "02_target_sound.wav",
        "melody_corrected": OUT / "03_melody_corrected.wav",
        "mix": OUT / "soundtrace_demo.wav",
    }
    write_wav(files["environment_clean"], clean)
    write_wav(files["target"], target)
    write_wav(files["melody_corrected"], melody)
    write_wav(files["mix"], mix)
    voiced = midi[midi > 0]
    analysis = {
        "sample_rate": SR, "duration_seconds": duration, "target_prompt": prompt,
        "target_backend": backend, "pitch_frames": int(len(hz)),
        "voiced_frames": int(np.sum(hz > 0)), "median_pitch_confidence": round(float(np.median(conf[hz > 0])) if np.any(hz > 0) else 0, 3),
        "corrected_midi_notes": [int(v) for v in voiced[::max(1, len(voiced)//32)]],
        "outputs": {k: str(v.relative_to(ROOT)) for k, v in files.items()},
        "limitation": "DSP band-pass is not semantic separation" if backend.startswith("dsp_") else None,
    }
    (OUT / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    return analysis


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("demo"); d.add_argument("--duration", type=float, default=42); d.add_argument("--target", default="birds")
    q = sub.add_parser("process"); q.add_argument("--environment", type=Path, required=True); q.add_argument("--hum", type=Path, required=True)
    q.add_argument("--duration", type=float, default=45); q.add_argument("--target", default="interesting foreground sound")
    args = p.parse_args()
    if not 30 <= args.duration <= 60:
        p.error("--duration must be between 30 and 60 seconds")
    if args.command == "demo":
        env, hum = make_demo_inputs()
        (ROOT / "inputs").mkdir(exist_ok=True)
        write_wav(ROOT / "inputs" / "demo_environment.wav", env)
        write_wav(ROOT / "inputs" / "demo_hum.wav", hum)
    else:
        env, hum = read_wav(args.environment), read_wav(args.hum)
    print(json.dumps(run(env, hum, args.target, args.duration), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
