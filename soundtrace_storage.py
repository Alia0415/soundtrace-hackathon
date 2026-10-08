"""Durable studio works. Standard-library only; independent of GPU/model imports."""
import hashlib
import io
import json
import math
import shutil
import threading
import time
import wave
from pathlib import Path

LOCK = threading.RLock()
SCENES = ('sea-window', 'rainy-city', 'autumn-lake', 'snow-mountain', 'spring-meadow', 'desert-dusk')


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(path)


def preserve_audio(root, reference):
    """Copy referenced temporary audio before the task-directory GC can remove it."""
    if not isinstance(reference, str):
        return reference
    root = Path(root).resolve()
    source = (root / reference.lstrip('/')).resolve()
    if not source.is_relative_to(root) or not source.is_file():
        return reference
    rel = source.relative_to(root).as_posix()
    if not rel.startswith(('outputs/service_jobs/', 'outputs/service_uploads/')):
        return reference
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:24]
    dest = root / 'outputs' / 'library' / 'retained' / (digest + source.suffix)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copyfile(source, dest)
    return dest.relative_to(root).as_posix()


def preserve_references(root):
    with LOCK:
        for name in ('works', 'materials', 'photos', 'feed', 'exchanges'):
            file = Path(root) / 'outputs' / (name + '.json')
            records = read_json(file, [])
            changed = False
            for item in records:
                for key in ('audio', 'raw'):
                    old = item.get(key)
                    new = preserve_audio(root, old)
                    if old != new:
                        item[key] = new
                        changed = True
            if changed:
                write_json(file, records)


def commit_work(root, data, info):
    if len(data) > 60 * 1024 * 1024:
        raise ValueError('音频文件过大')
    try:
        with wave.open(io.BytesIO(data)) as wav:
            frames, rate = wav.getnframes(), wav.getframerate()
            if wav.getnchannels() not in (1, 2) or wav.getsampwidth() not in (2, 3, 4):
                raise ValueError('请使用 PCM WAV 音频')
            if len(wav.readframes(frames)) != frames * wav.getnchannels() * wav.getsampwidth():
                raise ValueError('音频文件不完整')
            duration = frames / rate
    except (wave.Error, EOFError, ZeroDivisionError) as exc:
        raise ValueError('请提交有效的 WAV 音频') from exc
    if not .1 <= duration <= 300:
        raise ValueError('请保存 0.1 秒到 5 分钟以内的作品')
    metadata = {key: str(info.get(key) or default)[:limit] for key, default, limit in (
        ('title', '此刻的声音', 80), ('location', '', 100), ('story', '', 600))}
    metadata['scene'] = info.get('scene') if info.get('scene') in SCENES else SCENES[0]
    lat, lng = info.get('lat'), info.get('lng')
    if all(isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n) for n in (lat, lng)) and abs(lat) <= 90 and abs(lng) <= 180:
        metadata.update(lat=lat, lng=lng)
    collectible = info.get('collectible') if info.get('collectible') in ('vinyl', 'tape', 'photo') else 'vinyl'
    identity = json.dumps({**metadata, 'collectible': collectible}, ensure_ascii=False, separators=(',', ':'))
    wid = hashlib.sha256(data + identity.encode()).hexdigest()[:24]
    root = Path(root)
    folder = root / 'outputs' / 'library' / wid
    entry = dict(id=wid, kind='mix', collectible=collectible, title=metadata['title'],
                 created=time.time(), metadata=metadata, audio=f'outputs/library/{wid}/master.wav',
                 duration=duration, img=f"assets/scenes-v1/{metadata['scene']}.png",
                 version='ai' if info.get('version') == 'ai' else 'draft')
    with LOCK:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'master.wav').write_bytes(data)
        write_json(folder / 'project.json', {**entry, 'edit': info.get('project')})
        works_file = root / 'outputs' / 'works.json'
        works = read_json(works_file, [])
        existing = next((w for w in works if w.get('id') == wid), None)
        if existing is None:
            works.append(entry)
            write_json(works_file, works)
        if info.get('share') is True:
            feed_file = root / 'outputs' / 'feed.json'
            feed = read_json(feed_file, [])
            if not any(p.get('id') == f'studio-{wid}' for p in feed):
                feed.append(dict(id=f'studio-{wid}', text=metadata['story'] or metadata['title'],
                                 kind=collectible, audio=entry['audio'], img=entry['img'], author='我', created=entry['created']))
                write_json(feed_file, feed)
        return existing or entry
