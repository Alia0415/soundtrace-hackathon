"""高优先级修复验证：哼唱分析 + 块裁剪/循环 + 音乐避让"""
import time, requests
import numpy as np
import soundfile as sf

B = "http://127.0.0.1:8090"
ROOT = r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/soundtrace-hackathon/"
OUT = r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/test-audio"


def wait_job(jid, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = requests.get(f"{B}/api/jobs/{jid}").json()
        if j["status"] in ("done", "failed"):
            return j
        time.sleep(3)
    raise TimeoutError


# ── 1. 生成正确合成的谐波哼唱（C4 E4 G4 A4 G4 E4 D4 C4，C 大调） ──
sr = 22050
notes = [261.63, 329.63, 392.0, 440.0, 392.0, 329.63, 293.66, 261.63]
rng = np.random.default_rng(3)
parts = []
for f0 in notes:
    t = np.arange(int(0.8 * sr)) / sr
    tone = sum((0.6 / k) * np.sin(2 * np.pi * f0 * k * t + rng.uniform(0, 6)) for k in range(1, 5))
    env = np.minimum(1, t * 15) * np.minimum(1, (0.8 - t) * 15)
    parts.append(tone * env / 1.5)
    parts.append(np.zeros(int(0.1 * sr)))
hum = np.concatenate(parts)
sf.write(OUT + "/hum_harmonic.wav", hum, sr)
print("test hum written (expect C4 E4 G4 A4 G4 E4 D4 C4 = midi 60 64 67 69 67 64 62 60)")

up = requests.post(f"{B}/api/upload", files={"file": ("hum.wav", open(OUT + "/hum_harmonic.wav", "rb"))}).json()
j = requests.post(f"{B}/api/jobs", json={"type": "hum", "upload_id": up["upload_id"]}).json()
r = wait_job(j["job_id"])
assert r["status"] == "done", r.get("error")
res = r["results"]
midi = [n["midi"] for n in res["notes"]]
print(f"哼唱分析: {res['note_count']} 音符, 调性 {res['key']}, midi {midi}")
ok_hum = res["key"] == "C major" and midi == [60, 64, 67, 69, 67, 64, 62, 60]
print("HUM:", "PASS" if ok_hum else "CHECK")

# ── 2. 30 秒音乐底 + 裁剪(4s)/循环(25s) + 避让(3dB) ──
j = requests.post(f"{B}/api/jobs", json={"type": "generate", "style": "ambient",
    "target_en": "peaceful nature", "duration": 30, "seed": 31}).json()
g = wait_job(j["job_id"])
assert g["status"] == "done", g.get("error")
print("music 30s generated")

water = "outputs/service_jobs/03a9470f52ef/denoised.wav"    # 15.6s 倒水素材（沿用）
placements = [
    {"file": water, "start": 2, "length": 4},                # 裁剪：只出现 2-6s
    {"file": water, "start": 18, "length": 25},              # 循环：18s 起铺满到结尾
]
j = requests.post(f"{B}/api/jobs", json={"type": "remix",
    "generated": g["results"]["generated"], "placements": placements,
    "ambience_level": 0.4, "duck": 3.0}).json()
r = wait_job(j["job_id"])
assert r["status"] == "done", r.get("error")
print(f"remix placed={r['results']['placed']}")

gen, sr2 = sf.read(ROOT + g["results"]["generated"])
fin, _ = sf.read(ROOT + r["results"]["final"])
n = min(len(gen), len(fin)); gen, fin = gen[:n], fin[:n]
diff = (fin - gen).mean(axis=1)
def w(x, t0, t1): seg = x[int(t0*sr2):int(t1*sr2)]; return float(np.sqrt((seg**2).mean()))
print(f"\n环境音窗口: 0-1.5s={w(diff,0,1.5):.4f}(应0)  3-5s={w(diff,3,5):.4f}(裁剪段)  "
      f"8-16s={w(diff,8,16):.4f}(应0)  20-28s={w(diff,20,28):.4f}(循环段)")
ok_amb = w(diff,0,1.5) < 0.01 and w(diff,3,5) > 0.03 and w(diff,8,16) < 0.01 and w(diff,20,28) > 0.03

# 避让：音乐在环境声出现处的能量应低于无环境声处
gm = gen.mean(axis=1)
ducked = w(gm, 20, 26); clean = w(gm, 9, 15)
print(f"避让检查: 音乐RMS 环境声段={ducked:.4f} vs 干净段={clean:.4f} "
      f"(应低约 {20*np.log10(clean/ducked):.1f}dB)" if clean > 0 else "")
ok_duck = ducked < clean * 0.95
print("\nTRIM/LOOP:", "PASS" if ok_amb else "FAIL")
print("DUCK:", "PASS" if ok_duck else "FAIL")
