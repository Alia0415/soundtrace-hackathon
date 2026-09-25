"""SoundTrace MVP 服务全流程自动化测试：上传 → 识别 → 提取降噪 → 生成混音"""
import sys, time, requests

BASE = "http://127.0.0.1:8090"
AUDIO = r"D:/360MoveData/Users/sunry/Desktop/腾讯音乐黑客松/test-audio/scene_mix.wav"


def wait_job(jid, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = requests.get(f"{BASE}/api/jobs/{jid}").json()
        print(f"  [{j['status']}] {j['stage']} ({j['elapsed']}s)", flush=True)
        if j["status"] in ("done", "failed"):
            return j
        time.sleep(3)
    raise TimeoutError(jid)


print("1) health")
print("  ", requests.get(f"{BASE}/api/health").json(), flush=True)

print("2) upload scene_mix.wav")
with open(AUDIO, "rb") as f:
    up = requests.post(f"{BASE}/api/upload", files={"file": ("scene_mix.wav", f)}).json()
print("  ", up, flush=True)

print("3) analyze (CLAP tagging)")
t0 = time.time()
r = requests.post(f"{BASE}/api/analyze/{up['upload_id']}").json()
print(f"   took {time.time()-t0:.0f}s; top tags:", flush=True)
for t in r["tags"][:4]:
    print(f"     {t['zh']}({t['en']}) {t['score']}", flush=True)

print("4) extract 'flowing stream'")
j = requests.post(f"{BASE}/api/jobs", json={
    "type": "extract", "upload_id": up["upload_id"], "target_en": "flowing stream"}).json()
res = wait_job(j["job_id"])
print("   results:", res.get("results") or res.get("error"), flush=True)
denoised = res["results"]["denoised"]

print("5) generate (ambient, 15s, with ambience mix)")
j = requests.post(f"{BASE}/api/jobs", json={
    "type": "generate", "style": "ambient", "target_en": "flowing stream",
    "duration": 15, "seed": 7, "ambience": denoised}).json()
res = wait_job(j["job_id"], timeout=900)
print("   results:", res.get("results") or res.get("error"), flush=True)
print("SERVICE TEST DONE")
