"""Build a deployment archive from an explicit allowlist, excluding all personal data."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ['soundtrace_public.py', 'soundtrace_storage.py', 'soundtrace_music.py', 'soundtrace_maps.py', 'soundtrace_art.py', 'requirements-public.txt', 'Dockerfile', '.dockerignore', 'compose.yaml',
         'DEPLOY.md', 'docs/MINERADIO_ADAPTATION.md', 'docs/DIARY_ASSETS.md', 'studio/package.json', 'studio/package-lock.json',
         'studio/vite.config.js', 'tools/backup_public.py', 'tools/package_public.py', 'docs/DEMO_AND_PRODUCTION.md', 'docs/LAUNCH_RESOURCES.md']
DIRECTORIES = ['webapp', 'studio/src', 'deploy', 'outputs/seeds', 'third_party/Mineradio-paused-main']


def package():
    target = ROOT / 'runtime' / 'releases' / 'soundtrace-public.zip'
    target.parent.mkdir(parents=True, exist_ok=True)
    paths = [ROOT / name for name in FILES]
    paths += [file for name in DIRECTORIES for file in (ROOT / name).rglob('*') if file.is_file()
              and not any(part in ('.git', 'node_modules', '__pycache__') for part in file.parts)
              and not file.name.startswith('.env') and file.suffix.lower() not in ('.log', '.sqlite3', '.pyc', '.zip')]
    paths += [file for file in (ROOT / 'third_party' / 'Mineradio-paused-main').glob('*')
              if file.is_file() and file.name.lower().startswith(('license', 'copying'))]
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(set(paths)):
            if file.name.startswith('.env') or file.suffix.lower() in ('.log', '.sqlite3'):
                raise RuntimeError('Private configuration or data found in deployment allowlist')
            archive.write(file, file.relative_to(ROOT).as_posix())
    return {'file': str(target), 'bytes': target.stat().st_size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(package(), ensure_ascii=False))
