import io
import tempfile
import unittest
import wave
from pathlib import Path

from soundtrace_storage import commit_work, preserve_references, read_json, write_json


class StudioStorageTests(unittest.TestCase):
    def test_saved_audio_and_legacy_references_survive_temp_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            out = io.BytesIO()
            with wave.open(out, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(44100)
                wav.writeframes(b'\x00\x00' * 4410)
            data = out.getvalue()
            item = commit_work(root, data, {'title': '雨天', 'collectible': 'photo'})
            self.assertEqual((root / item['audio']).read_bytes(), data)
            self.assertEqual(len(read_json(root / 'outputs/works.json', [])), 1)
            temp = root / 'outputs/service_jobs/a/old.wav'
            temp.parent.mkdir(parents=True)
            temp.write_bytes(data)
            write_json(root / 'outputs/materials.json', [{'id': 'a', 'audio': 'outputs/service_jobs/a/old.wav'}])
            preserve_references(root)
            kept = read_json(root / 'outputs/materials.json', [])[0]['audio']
            self.assertTrue(kept.startswith('outputs/library/retained/'))
            temp.unlink()
            self.assertEqual((root / kept).read_bytes(), data)


if __name__ == '__main__':
    unittest.main()
