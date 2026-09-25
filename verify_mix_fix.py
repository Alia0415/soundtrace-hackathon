"""验证环境音可闻性修复：真实素材 → 提取 → 生成 → 量化环境音在成品中的响度占比"""
import time, requests, sys
import numpy as np
import soundfile as sf

B = "http://127.0.0.1:8090"
AUDIO = r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/test-materials/env-sounds-long/pouring_water_15s.wav"


def wait_job(jid, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = requests.get(f"{B}/api/jobs/{jid}").json()
        if j["status"] in ("done", "failed"):
            return j
        time.sleep(3)
    raise TimeoutError


up = requests.post(f"{B}/api/upload",
                   files={"file": ("pouring_water.wav", open(AUDIO, "rb"))}).json()
print("uploaded:", up)

j = requests.post(f"{B}/api/jobs", json={
    "type": "extract", "upload_id": up["upload_id"],
    "target_en": "pouring water"}).json()
r = wait_job(j["job_id"])
assert r["status"] == "done", r.get("error")
print("extract done:", r["results"]["denoised"])

j = requests.post(f"{B}/api/jobs", json={
    "type": "generate", "style": "ambient", "target_en": "pouring water",
    "duration": 15, "seed": 11, "ambience": r["results"]["denoised"],
    "ambience_level": 0.35}).json()
g = wait_job(j["job_id"])
assert g["status"] == "done", g.get("error")
print("generate done")

base = r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/soundtrace-hackathon/"
gen, _ = sf.read(base + g["results"]["generated"])
fin, sr = sf.read(base + g["results"]["final"])
n = min(len(gen), len(fin)); gen, fin = gen[:n], fin[:n]
diff = fin - gen
rms = lambda x: float(np.sqrt((x ** 2).mean()))
db = 20 * np.log10(rms(diff) / rms(gen))
print(f"\n环境音相对音乐响度: {db:+.1f} dB  (修复前 -34.6dB, 目标约 -9dB)")
print(f"音乐RMS={rms(gen):.4f}  环境声贡献RMS={rms(diff):.4f}")
print("PASS" if -14 < db < -4 else "FAIL: 仍不可闻或过响")
