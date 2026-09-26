"""迭代轮 1 验收：T1 宽频兜底 / T2 中文映射+标签过滤 / T4 提速 / T6 响度归一"""
import time, requests
import numpy as np
import soundfile as sf
import librosa

B = "http://127.0.0.1:8090"
ROOT = r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/soundtrace-hackathon/"
TEST = r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/test-audio/"
results = {}


def wait(jid, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = requests.get(f"{B}/api/jobs/{jid}").json()
        if j["status"] in ("done", "failed"):
            return j
        time.sleep(3)
    raise TimeoutError


def upload(path, name):
    return requests.post(f"{B}/api/upload", files={"file": (name, open(path, "rb"))}).json()


# ── T1: scene_mix(水声主导) 查 human voice → 应回退二步管线，产出高相关人声 ──
up = upload(TEST + "scene_mix.wav", "scene_mix.wav")
j = requests.post(f"{B}/api/jobs", json={"type": "extract", "upload_id": up["upload_id"],
                                         "target_en": "human voice"}).json()
r = wait(j["job_id"])
assert r["status"] == "done", r.get("error")
fb = r["results"].get("fallback", "")
print(f"T1 fallback: {fb or '(未触发)'}")
stem, sr = sf.read(ROOT + r["results"]["extracted"])
ref = librosa.load(TEST + "speech48k.wav", sr=sr, mono=True)[0]
n = min(len(stem), len(ref))
if stem.ndim > 1: stem = stem.mean(axis=1)
c = float(np.corrcoef(stem[:n], ref[:n])[0, 1])
results["T1"] = "PASS" if (c > 0.5 and fb) else "FAIL"
print(f"T1 人声相关: {c:.2f} → {results['T1']}")

# ── T2a: 中文"风声"查询自动映射 ──
up = upload(r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/test-materials/env-sounds-long/wind_15s.wav", "wind.wav")
j = requests.post(f"{B}/api/jobs", json={"type": "extract", "upload_id": up["upload_id"],
                                         "target_en": "风声"}).json()
r = wait(j["job_id"])
ok = r["status"] == "done" and r["results"].get("query_en") == "wind blowing"
results["T2a"] = "PASS" if ok else "FAIL"
print(f"T2a 中文映射: query_en={r['results'].get('query_en')} → {results['T2a']}")

# ── T2b: analyze 标签过滤（wind 素材不应出现低分凑数标签）──
r = requests.post(f"{B}/api/analyze/{up['upload_id']}").json()
tags = r["tags"]
top = tags[0]["score"]
filtered = all(t["score"] >= max(0.05, top * 0.45) for t in tags) and len(tags) <= 5
print(f"T2b 标签: {[(t['zh'], t['score']) for t in tags]}")
results["T2b"] = "PASS" if filtered and tags else "FAIL"

# ── T4: generate(卸载到CPU) 后再 analyze —— 模型恢复应 < 8s ──
j = requests.post(f"{B}/api/jobs", json={"type": "generate", "style": "ambient",
    "target_en": "peaceful nature", "duration": 15, "seed": 7}).json()
g = wait(j["job_id"])
assert g["status"] == "done", g.get("error")
up2 = upload(TEST + "scene_mix.wav", "scene_mix2.wav")
t0 = time.time()
r = requests.post(f"{B}/api/analyze/{up2['upload_id']}").json()
dt = time.time() - t0
results["T4"] = "PASS" if dt < 8.0 else "FAIL"
print(f"T4 恢复耗时: {dt:.1f}s（含推理）→ {results['T4']}")

# ── T6: remix 成品 RMS ∈ [0.13, 0.20] ──
gen_rel = g["results"]["generated"]
j = requests.post(f"{B}/api/jobs", json={"type": "remix", "generated": gen_rel,
    "placements": [{"file": "outputs/service_jobs/03a9470f52ef/denoised.wav", "start": 1, "length": 5}],
    "ambience_level": 0.35, "duck": 3}).json()
rm = wait(j["job_id"])
assert rm["status"] == "done", rm.get("error")
fin, _ = sf.read(ROOT + rm["results"]["final"])
rms = float(np.sqrt((fin ** 2).mean()))
results["T6"] = "PASS" if 0.13 <= rms <= 0.20 else "FAIL"
print(f"T6 成品 RMS: {rms:.3f} → {results['T6']}")

print("\n==== 迭代轮 1 验收汇总 ====")
for k, v in results.items():
    print(f"  {k}: {v}")
print("ALL PASS" if all(v == "PASS" for v in results.values()) else "HAS FAILURES")
