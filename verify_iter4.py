"""迭代轮 4 验收：T12 元数据 / T13 情绪映射 / T14 节拍分析"""
import time, requests

B = "http://127.0.0.1:8090"
results = {}


def wait(jid, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = requests.get(f"{B}/api/jobs/{jid}").json()
        if j["status"] in ("done", "failed"):
            return j
        time.sleep(3)
    raise TimeoutError


# T13 + T12: 带情绪与元数据生成
j = requests.post(f"{B}/api/jobs", json={
    "type": "generate", "style": "ambient", "target_en": "flowing stream",
    "duration": 15, "seed": 5,
    "metadata": {"title": "验收·雪线以南", "location": "云南·虎跳峡",
                 "lat": 27.31, "lng": 100.10, "mood": "宁静",
                 "story": "徒步第二天，溪水声陪我走了十里。"}}).json()
g = wait(j["job_id"])
assert g["status"] == "done", g.get("error")
prompt = g["results"].get("prompt", "")
results["T13"] = "PASS" if "peaceful, serene, calm" in prompt else "FAIL"
print(f"T13 prompt_used: {prompt} → {results['T13']}")

# T12: /api/works 应包含该作品与完整元数据
w = requests.get(f"{B}/api/works").json()["works"]
hit = [x for x in w if x.get("title") == "验收·雪线以南"]
ok = hit and hit[-1]["metadata"]["mood"] == "宁静" and hit[-1]["metadata"]["lat"] == 27.31
results["T12"] = "PASS" if ok else "FAIL"
print(f"T12 works 命中: {bool(hit)}, 元数据完整: {bool(ok)} → {results['T12']}")

# T14: 节拍分析
gen_file = g["results"]["generated"]
bt = requests.post(f"{B}/api/analyze-beat", json={"file": gen_file}).json()
ok = 40 <= bt["bpm"] <= 200 and len(bt["beats"]) >= 4
results["T14"] = "PASS" if ok else "FAIL"
print(f"T14 bpm={bt['bpm']}, 拍点 {len(bt['beats'])} 个 → {results['T14']}")

# 附: /map 页面可达
code = requests.get(f"{B}/map").status_code
print(f"/map 页面: HTTP {code}")
results["T16_page"] = "PASS" if code == 200 else "FAIL"

print("\n==== 迭代轮 4 验收 ====")
for k, v in results.items():
    print(f"  {k}: {v}")
print("ALL PASS" if all(v == "PASS" for v in results.values()) else "HAS FAILURES")
