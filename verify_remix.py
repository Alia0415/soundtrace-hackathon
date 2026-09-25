"""验证多素材 DAW 散点混音：两段环境声按指定位置出现，其余时段应无环境音"""
import time, requests
import numpy as np
import soundfile as sf

B = "http://127.0.0.1:8090"
ROOT = r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/soundtrace-hackathon/"
MATS = [(r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/test-materials/env-sounds-long/pouring_water_15s.wav", "pouring water", 2.0),
        (r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/test-materials/env-sounds-long/chirping_birds_15s.wav", "birds singing", 8.0)]


def wait_job(jid, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = requests.get(f"{B}/api/jobs/{jid}").json()
        if j["status"] in ("done", "failed"):
            return j
        time.sleep(3)
    raise TimeoutError


stems = []
for path, tgt, _ in MATS:
    up = requests.post(f"{B}/api/upload", files={"file": ("m.wav", open(path, "rb"))}).json()
    j = requests.post(f"{B}/api/jobs", json={"type": "extract", "upload_id": up["upload_id"], "target_en": tgt}).json()
    r = wait_job(j["job_id"])
    assert r["status"] == "done", r.get("error")
    stems.append(r["results"]["denoised"])
    print(f"extracted: {tgt}")

j = requests.post(f"{B}/api/jobs", json={"type": "generate", "style": "ambient",
    "target_en": "peaceful nature", "duration": 15, "seed": 23}).json()
g = wait_job(j["job_id"])
assert g["status"] == "done", g.get("error")
print("music generated")

placements = [{"file": s, "start": st} for (_, _, st), s in zip(MATS, stems)]
j = requests.post(f"{B}/api/jobs", json={"type": "remix",
    "generated": g["results"]["generated"], "placements": placements,
    "ambience_level": 0.45}).json()
r = wait_job(j["job_id"])
assert r["status"] == "done", r.get("error")
print(f"remix done, placed={r['results']['placed']}")

gen, sr = sf.read(ROOT + g["results"]["generated"])
fin, _ = sf.read(ROOT + r["results"]["final"])
n = min(len(gen), len(fin)); gen, fin = gen[:n], fin[:n]
diff = (fin - gen).mean(axis=1)

def w_rms(t0, t1):
    seg = diff[int(t0*sr):int(t1*sr)]
    return float(np.sqrt((seg**2).mean()))

print("\n各时间窗的环境音能量（RMS）：")
print(f"  0-2s   (应≈0 无环境音): {w_rms(0,2):.4f}")
print(f"  3-7s   (倒水声区)     : {w_rms(3,7):.4f}")
print(f"  6.5-8s (间隙)         : {w_rms(6.7,7.9):.4f}")
print(f"  9-14s  (鸟鸣声区)     : {w_rms(9,14):.4f}")
ok = w_rms(3,7) > 0.02 and w_rms(9,14) > 0.02 and w_rms(0,2) < w_rms(3,7)*0.3
print("\nPASS：环境音按摆放位置分散出现，非全程持续" if ok else "FAIL：检查混音逻辑")
