"""Consistent SQLite snapshot plus every referenced media file; no session cookies in export."""
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path


def backup(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    folder = destination / time.strftime('soundtrace-%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    try:
        with sqlite3.connect(source / 'soundtrace.sqlite3') as live, sqlite3.connect(folder / 'soundtrace.sqlite3') as snapshot:
            live.backup(snapshot)
            snapshot.execute('DELETE FROM sessions')
            snapshot.commit()
            refs = snapshot.execute('SELECT ref FROM media').fetchall()
        for (ref,) in refs:
            relative = Path(ref.removeprefix('outputs/'))
            target = (source / relative).resolve()
            if not target.is_relative_to(source) or not target.is_file():
                raise RuntimeError('Media changed during backup; retry during a quiet period')
            output = folder / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, output)
        (folder / 'manifest.json').write_text(json.dumps({'created': time.time(), 'media_count': len(refs)}), encoding='utf-8')
        return folder
    except Exception:
        shutil.rmtree(folder)
        raise


if __name__ == '__main__':
    print(backup(sys.argv[1], sys.argv[2]))
