"""The saved original, optional music, and collection indexes stay distinct."""
import io
import base64
import json
import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

import soundtrace_gpu as service


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 1600)
    return output.getvalue()


class MemoryFlowTests(unittest.TestCase):
  def test_generated_art_replaces_fallback_cover(self):
   with tempfile.TemporaryDirectory() as directory:
    folder = Path(directory)
    image = folder / "uploaded.png"
    Image.new("RGB", (40, 40), "#71aadd").save(image)
    entry = {"id": "demo", "title": "海边", "notes": "晚霞", "mood": "宁静", "location": "海港",
             "cover_tape": "fallback.jpg", "cover_vinyl": "fallback-vinyl.jpg"}
    index = folder / "memories.json"
    index.write_text(json.dumps([entry]), encoding="utf-8")
    generated = io.BytesIO()
    Image.new("RGB", (80, 80), "#ddaa71").save(generated, format="PNG")
    class FakeResponse:
     def raise_for_status(self): pass
     def json(self): return {"data": [{"b64_json": base64.b64encode(generated.getvalue()).decode()}]}
    with patch.object(service, "MEMORIES_FILE", index), patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch("requests.post", return_value=FakeResponse()) as request:
     service._generate_memory_art(entry, image, folder, "海港")
    saved = json.loads(index.read_text(encoding="utf-8"))[0]
    self.assertEqual(saved["art_status"], "generated")
    self.assertTrue((folder / "cover_tape_ai.jpg").is_file())
    self.assertTrue((folder / "cover_vinyl_ai.jpg").is_file())
    self.assertEqual(request.call_args.args[0], "https://api.openai.com/v1/images/edits")

  def test_public_demo_requires_password(self):
   client = TestClient(service.app)
   with patch.dict(os.environ, {"SOUNDTRACE_PUBLIC": "1", "SOUNDTRACE_DEMO_PASSWORD": ""}):
    self.assertEqual(client.get("/api/health").status_code, 503)
   with patch.dict(os.environ, {"SOUNDTRACE_PUBLIC": "1", "SOUNDTRACE_DEMO_PASSWORD": "example-secret"}):
    self.assertEqual(client.get("/api/health").status_code, 401)
    credentials = base64.b64encode(b"soundtrace:example-secret").decode()
    self.assertEqual(client.get("/api/health", headers={"Authorization": "Basic " + credentials}).status_code, 200)

  def test_memory_separates_tape_vinyl_and_photo(self):
   with tempfile.TemporaryDirectory() as directory:
    tmp_path = Path(directory)
    patches = [
        patch.object(service, "MEMORIES_FILE", tmp_path / "memories.json"),
        patch.object(service, "MEMORY_DIR", tmp_path / "memories"),
        patch.object(service, "WORKS_FILE", tmp_path / "works.json"),
        patch.object(service, "PHOTOS_FILE", tmp_path / "photos.json"),
        patch.object(service, "MATERIALS_FILE", tmp_path / "materials.json"),
        patch.dict(os.environ, {"OPENAI_API_KEY": ""}),
    ]
    for item in patches: item.start()
    try:
     self.check_flow(tmp_path)
    finally:
     for item in reversed(patches): item.stop()

  def check_flow(self, tmp_path):
    client = TestClient(service.app)
    image = io.BytesIO()
    Image.new("RGB", (40, 40), "#71aadd").save(image, format="PNG")
    original = wav_bytes()
    response = client.post(
        "/api/memories",
        data={"title": "潮声", "notes": "傍晚的海", "mood": "宁静", "location": "海边",
              "lat": "24.4", "lng": "118.1", "scene": "sea-window"},
        files=[("audio", ("raw.wav", original, "audio/wav")),
               ("images", ("sea.png", image.getvalue(), "image/png"))],
    )
    self.assertEqual(response.status_code, 200, response.text)
    memory = response.json()
    self.assertEqual(memory["art_status"], "needs_provider")
    self.assertEqual((tmp_path / "memories" / memory["id"] / "audio.wav").read_bytes(), original)
    self.assertTrue(any(m["id"] == f"mem_{memory['id']}" for m in client.get("/api/materials").json()["materials"]))
    self.assertTrue(any(p["id"].startswith(f"memory-photo-{memory['id']}") for p in client.get("/api/photos").json()["photos"]))
    self.assertFalse(client.get("/api/works").json()["works"])

    result = client.post(
        "/api/memories",
        data={"title": "潮声的歌", "scene": "sea-window"},
        files=[("audio", ("raw.wav", original, "audio/wav")),
               ("music_audio", ("music.wav", original, "audio/wav"))],
    )
    self.assertEqual(result.status_code, 200, result.text)
    saved = result.json()
    works = client.get("/api/works").json()["works"]
    self.assertTrue(any(w["id"] == f"memory-vinyl-{saved['id']}" and w["audio"] == saved["music_audio"] for w in works))
    self.assertEqual(saved["art_status"], "text_only")


if __name__ == "__main__":
    unittest.main()
