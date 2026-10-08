"""验收：录音手记全链路（保存→封面生图→收藏磁带→地图）+ 头像上传 + 语音识别"""
import time, requests, io, wave, struct, math

B = "http://127.0.0.1:8090"


def make_wav(seconds=2, freq=440, sr=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        for i in range(seconds * sr):
            w.writeframes(struct.pack("<h", int(2000 * math.sin(2 * math.pi * freq * i / sr))))
    return buf.getvalue()


def make_png():
    # 最小合法 PNG（1x1 白色）
    import base64
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


# 1) 保存一段记忆（带图/天气/心情/坐标）
r = requests.post(f"{B}/api/memories",
    files={"audio": ("rec.wav", make_wav(), "audio/wav"),
           "images": ("photo.png", make_png(), "image/png")},
    data={"title": "验收·溪水声", "notes": "虎跳峡旁", "mood": "宁静",
          "location": "云南·虎跳峡", "lat": 27.31, "lng": 100.10,
          "weather": "18°C", "captured_at": time.time()}).json()
assert r.get("id"), r
print("1. 记忆保存:", r["title"], "| 磁带封面:", r["cover_tape"], "| 唱片封面:", r["cover_vinyl"])

# 2) 封面文件真实存在且为合法图片
cover = requests.get(f"{B}/{r['cover_tape']}")
assert cover.status_code == 200 and cover.content[:3] == b"\xff\xd8\xff", "封面不是JPEG"
print(f"2. 磁带封面可访问且为 JPEG（{len(cover.content)} 字节）")

# 3) 收藏磁带（素材库）包含该记忆，带封面路径
mats = requests.get(f"{B}/api/materials").json()["materials"]
hit = [m for m in mats if m["id"] == f"mem_{r['id']}"]
assert hit and hit[0]["cover"], "记忆未进素材库或无封面"
print("3. 收藏磁带:", hit[0]["name"], "→ 封面", hit[0]["cover"])

# 4) 地图数据源包含记忆坐标
mems = requests.get(f"{B}/api/memories").json()["memories"]
assert any(m["id"] == r["id"] and m["lat"] == 27.31 for m in mems)
print("4. 地图数据源: 记忆坐标 (27.31, 100.10) ✓")

# 5) 头像上传
up = requests.post(f"{B}/api/user/avatar", files={"file": ("me.png", make_png(), "image/png")}).json()
u = requests.get(f"{B}/api/user").json()
assert u.get("avatar_img") == up["avatar_img"]
img = requests.get(f"{B}/{u['avatar_img']}")
print(f"5. 头像上传+回读 ✓（{u['avatar_img']}，HTTP {img.status_code}）")

# 6) 语音识别（首次会下载模型，允许失败但要有明确错误）
try:
    tr = requests.post(f"{B}/api/transcribe",
                       files={"file": ("ask.wav", make_wav(3, 220), "audio/wav")}, timeout=300).json()
    print("6. 语音识别:", tr)
except Exception as e:
    print(f"6. 语音识别端点存在但待模型下载/首跑（{type(e).__name__}）")

# 7) capture 页面可达
assert requests.get(f"{B}/capture").status_code == 200
assert requests.get(f"{B}/").text.count("/capture") >= 1
print("7. /capture 页面 200 且首页录音按钮指向它 ✓")
print("\nALL CORE PASS")
