"""迭代轮 3 验收（T11）：哼唱驱动生成产品化——全链路 API 验证
流程：哼唱上传→hum 分析→melody_ref 生成→note-chroma > 0.8
"""
import time, requests
import numpy as np
import librosa

B = "http://127.0.0.1:8090"
ROOT = r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/soundtrace-hackathon/"
HUM = r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/test-audio/hum_harmonic.wav"
MIDIS = [60, 64, 67, 69, 67, 64, 62, 60]
STEP, NOTE_DUR = 0.9, 0.75


def wait(jid, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = requests.get(f"{B}/api/jobs/{jid}").json()
        if j["status"] in ("done", "failed"):
            return j
        time.sleep(3)
    raise TimeoutError


up = requests.post(f"{B}/api/upload", files={"file": ("hum.wav", open(HUM, "rb"))}).json()
j = requests.post(f"{B}/api/jobs", json={"type": "hum", "upload_id": up["upload_id"]}).json()
r = wait(j["job_id"])
assert r["status"] == "done", r.get("error")
melody = r["results"]["melody"]
print(f"hum 分析: {r['results']['key']}, {r['results']['note_count']} 音符 → {melody}")

j = requests.post(f"{B}/api/jobs", json={
    "type": "generate", "style": "cinematic", "target_en": "peaceful nature, C major key",
    "duration": 8.0, "seed": 42, "melody_ref": melody, "ref_strength": 0.85}).json()
g = wait(j["job_id"])
assert g["status"] == "done", g.get("error")
gen = ROOT + g["results"]["generated"]
print(f"melody-driven 生成完成: {g['results']['generated']}")


def note_chroma_score(path):
    y, sr = librosa.load(path, sr=22050, mono=True)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    fps = chroma.shape[1] / (len(y) / sr)
    per = []
    for i, midi in enumerate(MIDIS):
        f0, f1 = int((i * STEP + 0.05) * fps), int((i * STEP + NOTE_DUR) * fps)
        seg = chroma[:, f0:f1].mean(axis=1)
        per.append(float(seg[midi % 12] / (seg.max() + 1e-9)))
    return float(np.mean(per))


score = note_chroma_score(gen)
print(f"生成结果 note-chroma = {score:.3f}（验收 > 0.8）")
print("T11:", "PASS" if score > 0.8 else "FAIL")
