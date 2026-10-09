"""Multi-user web service, independent of GPU dependencies and legacy personal data."""
import hashlib
import asyncio
import hmac
import io
import json
import math
import os
import re
import secrets
import shutil
import sqlite3
import time
import tempfile
import uuid
import wave
from collections import defaultdict, deque
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
SCENES = ('sea-window', 'rainy-city', 'autumn-lake', 'snow-mountain', 'spring-meadow', 'desert-dusk')
COOKIE = 'soundtrace_session'
SESSION_SECONDS = 30 * 86400
Image.MAX_IMAGE_PIXELS = 30_000_000


def create_app(data_dir=None, public_url=None):
    data = Path(data_dir or os.getenv('SOUNDTRACE_DATA_DIR', ROOT / 'data')).resolve()
    data.mkdir(parents=True, exist_ok=True)
    url = (public_url or os.getenv('SOUNDTRACE_PUBLIC_URL', '')).rstrip('/')
    if url and not url.startswith('https://'):
        raise ValueError('SOUNDTRACE_PUBLIC_URL must use HTTPS')
    quota = int(os.getenv('SOUNDTRACE_USER_QUOTA_MB', '1024')) * 1024 * 1024
    app = FastAPI(title='SoundTrace', docs_url=None, redoc_url=None)

    @app.exception_handler(ValueError)
    async def invalid_value(request, error):
        return JSONResponse({'detail': '提交内容格式不正确'}, status_code=400)

    async def json_body(request):
        content = await request.body()
        if len(content) > 64000:
            raise HTTPException(413, '文字信息过长')
        body = json.loads(content)
        if not isinstance(body, dict):
            raise HTTPException(400, '提交内容格式不正确')
        return body

    @contextmanager
    def db():
        connection = sqlite3.connect(data / 'soundtrace.sqlite3', timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    with db() as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.executescript('''
          CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL, profile TEXT NOT NULL, created REAL NOT NULL);
          CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, owner TEXT NOT NULL
            REFERENCES users(id) ON DELETE CASCADE, expires REAL NOT NULL);
          CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, owner TEXT NOT NULL
            REFERENCES users(id) ON DELETE CASCADE, kind TEXT NOT NULL, payload TEXT NOT NULL,
            created REAL NOT NULL, source_id TEXT REFERENCES records(id) ON DELETE CASCADE);
          CREATE INDEX IF NOT EXISTS records_owner_kind ON records(owner,kind,created);
          CREATE TABLE IF NOT EXISTS media(ref TEXT PRIMARY KEY, owner TEXT NOT NULL
            REFERENCES users(id) ON DELETE CASCADE, record_id TEXT REFERENCES records(id)
            ON DELETE CASCADE, bytes INTEGER NOT NULL, mime TEXT NOT NULL, role TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS post_media(post_id TEXT REFERENCES records(id) ON DELETE CASCADE,
            ref TEXT REFERENCES media(ref) ON DELETE CASCADE, PRIMARY KEY(post_id,ref));
          CREATE TABLE IF NOT EXISTS mailbox_members(owner TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE);
          CREATE TABLE IF NOT EXISTS letters(id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              recipient TEXT REFERENCES users(id) ON DELETE CASCADE, source_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
              kind TEXT NOT NULL, payload TEXT NOT NULL, created REAL NOT NULL, delivered REAL,
              UNIQUE(owner,source_id,kind));
          CREATE TABLE IF NOT EXISTS letter_media(letter_id TEXT REFERENCES letters(id) ON DELETE CASCADE,
              ref TEXT REFERENCES media(ref) ON DELETE CASCADE, PRIMARY KEY(letter_id,ref));
          CREATE TABLE IF NOT EXISTS likes(post_id TEXT REFERENCES records(id) ON DELETE CASCADE,
            owner TEXT REFERENCES users(id) ON DELETE CASCADE, PRIMARY KEY(post_id,owner));
        ''')

    def account(request, required=True):
        token = hashlib.sha256(request.cookies.get(COOKIE, '').encode()).hexdigest()
        with db() as con:
            user = con.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.owner '
                               'WHERE s.token=? AND s.expires>?', (token, time.time())).fetchone()
        if not user and required:
            raise HTTPException(401, '请登录后保存或发布')
        return dict(user) if user else None

    def profile(user):
        return {**json.loads(user['profile']), 'id': user['id'], 'username': user['username'], 'logged_in': True}

    def password_hash(password, salt=None):
        salt = salt or secrets.token_hex(16)
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return salt + ':' + digest

    def valid_password(value):
        if not isinstance(value, str) or not 10 <= len(value) <= 128:
            raise HTTPException(400, '密码请使用 10 到 128 个字符')
        return value

    def session(user_id):
        token = secrets.token_urlsafe(32)
        with db() as con:
            con.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
            con.execute('INSERT INTO sessions VALUES(?,?,?)',
                        (hashlib.sha256(token.encode()).hexdigest(), user_id, time.time() + SESSION_SECONDS))
        response = JSONResponse({'ok': True})
        response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True, secure=bool(url), samesite='lax')
        return response

    rates = defaultdict(deque)

    @app.middleware('http')
    async def boundaries(request, call_next):
        if url and request.headers.get('host') != urlsplit(url).netloc:
            return JSONResponse({'detail': '请求域名不匹配'}, 400)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            expected = url or str(request.base_url).rstrip('/')
            if (origin and origin != expected) or request.headers.get('sec-fetch-site') == 'cross-site':
                return JSONResponse({'detail': '请从声迹页面发起操作'}, 403)
            try:
                if int(request.headers.get('content-length', '0')) > 180 * 1024 * 1024:
                    return JSONResponse({'detail': '一次上传最多 180 MB'}, 413)
            except ValueError:
                return JSONResponse({'detail': '无效的请求大小'}, 400)
            now = time.monotonic()
            key = (request.client.host, 'auth' if request.url.path.startswith('/api/auth') else 'write')
            bucket = rates[key]
            while bucket and bucket[0] < now - 60:
                bucket.popleft()
            if len(bucket) >= (12 if key[1] == 'auth' else 40):
                return JSONResponse({'detail': '操作过于频繁，请稍后重试'}, 429, headers={'Retry-After': '60'})
            bucket.append(now)
            if len(rates) > 10000:
                for old in list(rates):
                    if not rates[old] or rates[old][-1] < now - 60:
                        del rates[old]
        try:
            response = await call_next(request)
        finally:
            for form in getattr(request.state, 'upload_forms', []):
                await form.close()
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'microphone=(self), geolocation=(self), camera=()'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        if request.url.path.startswith(('/api/', '/outputs/')):
            response.headers['Cache-Control'] = 'no-store'
        elif response.headers.get('content-type','').startswith('text/html'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/api/auth/session')
    def who(request: Request):
        user = account(request, False)
        return {'user': profile(user) if user else None}

    @app.post('/api/auth/register', status_code=201)
    async def register(request: Request):
        body = await json_body(request)
        username = str(body.get('username', '')).strip().lower()
        if not re.fullmatch(r'[a-z0-9_]{3,32}', username):
            raise HTTPException(400, '账号使用 3 到 32 位字母、数字或下划线')
        password = valid_password(body.get('password'))
        uid = uuid.uuid4().hex
        user_profile = {'name': str(body.get('name') or username)[:32], 'avatar': '🎧', 'streak': 0}
        try:
            with db() as con:
                con.execute('INSERT INTO users VALUES(?,?,?,?,?)',
                            (uid, username, password_hash(password), json.dumps(user_profile, ensure_ascii=False), time.time()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, '该账号已被使用')
        return session(uid)

    @app.post('/api/auth/login')
    async def login(request: Request):
        body = await json_body(request)
        username = str(body.get('username', '')).strip().lower()
        supplied = body.get('password', '')
        if not isinstance(supplied, str) or len(supplied) > 128:
            raise HTTPException(400, '账号或密码不正确')
        with db() as con:
            user = con.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        stored = user['password'] if user else password_hash('unused-password')
        if not hmac.compare_digest(password_hash(supplied, stored.split(':')[0]), stored) or not user:
            raise HTTPException(400, '账号或密码不正确')
        return session(user['id'])

    @app.post('/api/auth/logout')
    def logout(request: Request):
        with db() as con:
            con.execute('DELETE FROM sessions WHERE token=?',
                        (hashlib.sha256(request.cookies.get(COOKIE, '').encode()).hexdigest(),))
        response = JSONResponse({'ok': True})
        response.delete_cookie(COOKIE)
        return response

    @app.post('/api/auth/password')
    async def change_password(request: Request):
        user = account(request)
        body = await json_body(request)
        current = str(body.get('current_password', ''))
        if len(current) > 128 or not hmac.compare_digest(password_hash(current, user['password'].split(':')[0]), user['password']):
            raise HTTPException(400, '当前密码不正确')
        new = password_hash(valid_password(body.get('password')))
        with db() as con:
            con.execute('UPDATE users SET password=? WHERE id=?', (new, user['id']))
            con.execute('DELETE FROM sessions WHERE owner=?', (user['id'],))
        return session(user['id'])

    @app.get('/api/user')
    def get_user(request: Request):
        user = account(request, False)
        return profile(user) if user else {'name': '旅行者', 'avatar': '🎧', 'logged_in': False, 'streak': 0}

    def update_profile(uid, changes):
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT profile FROM users WHERE id=?', (uid,)).fetchone()
            values = {**json.loads(row['profile']), **changes}
            con.execute('UPDATE users SET profile=? WHERE id=?', (json.dumps(values, ensure_ascii=False), uid))
        return values

    @app.post('/api/user')
    async def edit_user(request: Request):
        user = account(request)
        body = await json_body(request)
        changes = {}
        for key, limit in (('name', 32), ('avatar', 8)):
            if key in body:
                value = str(body[key]).strip()
                if not value or len(value) > limit:
                    raise HTTPException(400, '昵称或头像内容不正确')
                changes[key] = value
        return {**update_profile(user['id'], changes), 'logged_in': True}

    @app.post('/api/user/checkin')
    def checkin(request: Request):
        user = account(request)
        values = profile(user)
        today = time.strftime('%Y-%m-%d', time.gmtime())
        if values.get('last_checkin') == today:
            return {**values, 'ok': False, 'msg': '今天已签到'}
        yesterday = time.strftime('%Y-%m-%d', time.gmtime(time.time() - 86400))
        changes = {'last_checkin': today, 'streak': values.get('streak', 0) + 1 if values.get('last_checkin') == yesterday else 1}
        return {**update_profile(user['id'], changes), 'ok': True, 'msg': '签到成功'}

    def ref_path(ref):
        return data / ref.removeprefix('outputs/')

    def own_records(request, kind):
        user = account(request, False)
        if not user:
            return []
        with db() as con:
            rows = con.execute('SELECT payload FROM records WHERE owner=? AND kind=? ORDER BY created DESC LIMIT 1000',
                               (user['id'], kind)).fetchall()
        return [json.loads(row['payload']) for row in rows]

    def owned_reference(con, user, ref):
        if not ref:
            return None
        if not isinstance(ref, str) or len(ref) > 500:
            raise HTTPException(400, '素材路径无效')
        if ref.startswith('assets/'):
            path = (ROOT / 'webapp' / ref).resolve()
            if path.is_relative_to(ROOT / 'webapp' / 'assets') and path.is_file():
                return ref
        row = con.execute('SELECT owner FROM media WHERE ref=?', (ref,)).fetchone()
        if not row or row['owner'] != user['id']:
            raise HTTPException(403, '只能发布自己上传的素材')
        return ref

    def publish(con, user, text, references, source=None):
        pid = uuid.uuid4().hex
        refs = {key: owned_reference(con, user, value) for key, value in references.items()}
        entry = {'id': pid, 'text': text[:2000], **refs, 'created': time.time()}
        con.execute('INSERT INTO records VALUES(?,?,?,?,?,?)', (pid, user['id'], 'post', json.dumps(entry, ensure_ascii=False), entry['created'], source))
        for ref in set(v for v in refs.values() if v and v.startswith('outputs/')):
            con.execute('INSERT INTO post_media VALUES(?,?)', (pid, ref))
        return entry

    @app.get('/api/feed')
    def feed(request: Request, before: float = float('inf')):
        user = account(request, False)
        with db() as con:
            rows = con.execute('SELECT r.*,u.profile FROM records r JOIN users u ON u.id=r.owner '
                               "WHERE r.kind='post' AND r.created<? ORDER BY r.created DESC LIMIT 50", (before,)).fetchall()
            counts = {row['id']: con.execute('SELECT COUNT(*) FROM likes WHERE post_id=?', (row['id'],)).fetchone()[0] for row in rows}
            liked = {row['id']: bool(user and con.execute('SELECT 1 FROM likes WHERE post_id=? AND owner=?', (row['id'], user['id'])).fetchone()) for row in rows}
        posts = []
        for row in rows:
            p = json.loads(row['profile'])
            posts.append({**json.loads(row['payload']), 'author': p['name'], 'avatar_img': p.get('avatar_img'),
                          'like_count': counts[row['id']], 'liked': liked[row['id']],
                          'mine': bool(user and user['id'] == row['owner'])})
        return {'posts': posts, 'next_before': rows[-1]['created'] if len(rows) == 50 else None}

    def existing_post(con, pid):
        if not con.execute("SELECT 1 FROM records WHERE id=? AND kind='post'", (pid,)).fetchone():
            raise HTTPException(404, '动态不存在')

    @app.post('/api/feed/{pid}/like')
    async def like_post(pid: str, request: Request):
        user = account(request)
        body = await json_body(request)
        with db() as con:
            existing_post(con, pid)
            if body.get('liked') is True:
                con.execute('INSERT OR IGNORE INTO likes VALUES(?,?)', (pid, user['id']))
            else:
                con.execute('DELETE FROM likes WHERE post_id=? AND owner=?', (pid, user['id']))
            count = con.execute('SELECT COUNT(*) FROM likes WHERE post_id=?', (pid,)).fetchone()[0]
        return {'liked': body.get('liked') is True, 'like_count': count}

    @app.get('/api/feed/{pid}/comments')
    def comments(pid: str, request: Request):
        user = account(request, False)
        with db() as con:
            existing_post(con, pid)
            rows = con.execute("SELECT r.*,u.profile FROM records r JOIN users u ON u.id=r.owner WHERE r.kind='comment' AND r.source_id=? ORDER BY r.created DESC LIMIT 50", (pid,)).fetchall()
        return {'comments': [{**json.loads(row['payload']), 'author': json.loads(row['profile'])['name'],
                'mine': bool(user and row['owner'] == user['id'])} for row in reversed(rows)]}

    @app.post('/api/feed/{pid}/comments', status_code=201)
    async def comment(pid: str, request: Request):
        user = account(request)
        body = await json_body(request)
        text = str(body.get('text', '')).strip()
        if not text or len(text) > 1000:
            raise HTTPException(400, '回应请使用 1 到 1000 字')
        entry = {'id': uuid.uuid4().hex, 'text': text, 'created': time.time()}
        with db() as con:
            existing_post(con, pid)
            con.execute('INSERT INTO records VALUES(?,?,?,?,?,?)', (entry['id'], user['id'], 'comment', json.dumps(entry, ensure_ascii=False), entry['created'], pid))
        return entry

    @app.delete('/api/comments/{cid}')
    def delete_comment(cid: str, request: Request):
        user = account(request)
        with db() as con:
            result = con.execute("DELETE FROM records WHERE id=? AND owner=? AND kind='comment'", (cid, user['id']))
            if not result.rowcount:
                raise HTTPException(404, '回应不存在')
        return {'ok': True}

    @app.post('/api/feed', status_code=201)
    async def post(request: Request):
        user = account(request)
        body = await json_body(request)
        text = str(body.get('text', '')).strip()
        if not text or len(text) > 2000:
            raise HTTPException(400, '请输入 1 到 2000 字的内容')
        with db() as con:
            return publish(con, user, text, {key: body.get(key) for key in ('audio', 'img')})

    @app.delete('/api/feed/{pid}')
    def delete_post(pid: str, request: Request):
        user = account(request)
        with db() as con:
            result = con.execute("DELETE FROM records WHERE id=? AND owner=? AND kind='post'", (pid, user['id']))
            if not result.rowcount:
                raise HTTPException(404, '动态不存在')
        return {'ok': True}

    @app.get('/api/memories')
    def memories(request: Request):
        return {'memories': own_records(request, 'memory')}

    @app.get('/api/memories/{mid}')
    def memory_detail(mid: str, request: Request):
        user = account(request)
        with db() as con:
            row = con.execute("SELECT payload FROM records WHERE id=? AND owner=? AND kind='memory'", (mid,user['id'])).fetchone()
        if not row:
            raise HTTPException(404, '声音素材不存在或无权访问')
        return json.loads(row['payload'])

    @app.get('/api/works')
    def works(request: Request):
        result = own_records(request, 'work')
        for m in own_records(request, 'memory'):
            if m.get('music_audio'):
                result.append({'id': 'memory-vinyl-' + m['id'], 'memory_id': m['id'], 'title': m['title'],
                               'kind': 'mix', 'collectible': 'vinyl', 'audio': m['music_audio'], 'img': m['cover_vinyl'],
                               'cover': m['cover_vinyl'], 'duration': m.get('music_duration',m['duration']), 'created': m['created'], 'metadata': {**m,'duration':m.get('music_duration',m['duration'])}})
        return {'works': result}

    @app.get('/api/materials')
    def materials(request: Request):
        return {'materials': [{'id': 'mem_' + m['id'], 'name': m['title'], 'audio': m['audio'],
                'cover': m['cover_tape'], 'memory': True, 'metadata': {**m, 'story': m.get('notes')}, 'created': m['created']}
                for m in own_records(request, 'memory')]}

    @app.get('/api/material-library')
    def material_library(request: Request):
        user = account(request)
        with db() as con:
            rows = con.execute("SELECT r.payload,m.ref,m.role,m.bytes FROM media m JOIN records r ON r.id=m.record_id WHERE m.owner=? AND r.kind='memory' AND m.mime='audio/wav' AND m.role IN ('memory','extracted') ORDER BY r.created DESC", (user['id'],)).fetchall()
        items = []
        for row in rows:
            memory = json.loads(row['payload'])
            if row['role'] != 'extracted' and row['ref'] != memory['audio']:
                continue
            info = memory.get('material_labels', {}).get(row['ref'], {})
            material_title = memory.get('material_title') or (Path(memory['original_filename']).stem if memory.get('original_filename') else memory['title'])
            items.append({**memory, 'material_id': row['ref'], 'audio': row['ref'],
                          'title': info.get('title', material_title), 'duration': info.get('duration', memory['duration']),
                          'material_kind': 'separated' if row['role']=='extracted' else 'original',
                          'original_title': material_title, 'bytes': row['bytes']})
        return {'materials': items}

    @app.get('/api/photos')
    def photos(request: Request):
        return {'photos': [{'id': f"memory-photo-{m['id']}-{i}", 'title': m['title'], 'img': ref,
                'audio': m['audio'], 'metadata': {**m, 'story': m.get('notes')}, 'created': m['created']}
                for m in own_records(request, 'memory') for i, ref in enumerate(m['images'])]}

    from soundtrace_uploads import install_uploads
    read_staged_audio, discard_staged_audio = install_uploads(app, db, account, data, quota)

    async def audio_from_form(form, key, user):
        uid = form.get(key + '_upload_id')
        return read_staged_audio(uid, user) if uid else await read_upload(form.get(key), 60_000_000)

    async def read_upload(upload, limit):
        if upload is None or not hasattr(upload, 'read'):
            raise HTTPException(400, '请选择文件')
        content = await upload.read(limit + 1)
        if not content or len(content) > limit:
            raise HTTPException(413, f'文件为空或超过 {limit // 1000000} MB')
        return content

    async def upload_form(request, **limits):
        form = await request.form(**limits)
        if not hasattr(request.state, 'upload_forms'):
            request.state.upload_forms = []
        request.state.upload_forms.append(form)
        return form

    def validate_wav(content):
        try:
            with wave.open(io.BytesIO(content)) as wav:
                frames, rate, channels, width = wav.getnframes(), wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
                if channels not in (1, 2) or width not in (2, 3, 4) or not 8000 <= rate <= 192000 or not .1 <= frames / rate <= 300:
                    raise ValueError()
                if len(wav.readframes(frames)) != frames * channels * width:
                    raise ValueError()
                return frames / rate
        except (wave.Error, EOFError, ValueError):
            raise HTTPException(400, '请提交完整的 PCM WAV，时长 0.1 秒到 5 分钟')

    def normalize_image(content, size=1800):
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.load()
                image = ImageOps.exif_transpose(image).convert('RGB')
                image.thumbnail((size, size))
                output = io.BytesIO()
                image.save(output, format='JPEG', quality=90)
                return output.getvalue()
        except Exception:
            raise HTTPException(400, '图片无法读取，请更换图片')

    def cover(folder, title, background, kind):
        size = (840, 630) if kind == 'tape' else (800, 800)
        image = ImageOps.fit(Image.open(background).convert('RGB'), size) if background else Image.new('RGB', size, 'white')
        font_paths = (os.getenv('SOUNDTRACE_FONT', ''), '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', r'C:\Windows\Fonts\msyh.ttc')
        font = next((ImageFont.truetype(p, 40) for p in font_paths if p and Path(p).is_file()), ImageFont.load_default())
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, size[1] - 100, size[0], size[1]), fill='white')
        draw.text((26, size[1] - 78), title[:18], font=font, fill='#182c3e')
        file = folder / f'cover_{kind}.jpg'
        image.save(file, quality=92)
        return file

    def commit_record(user, entry, kind, files, share=False):
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            used = con.execute('SELECT COALESCE(SUM(bytes),0) FROM media WHERE owner=?', (user['id'],)).fetchone()[0]
            if used + sum(file['bytes'] for file in files) > quota:
                raise HTTPException(413, '存储空间已满，请先删除不需要的记忆')
            con.execute('INSERT INTO records VALUES(?,?,?,?,?,NULL)',
                        (entry['id'], user['id'], kind, json.dumps(entry, ensure_ascii=False), entry['created']))
            for file in files:
                con.execute('INSERT INTO media VALUES(?,?,?,?,?,?)',
                            (file['ref'], user['id'], entry['id'], file['bytes'], file['mime'], 'memory'))
            if share:
                publish(con, user, entry.get('notes') or entry['title'],
                        {'audio': entry['audio'], 'img': (entry.get('images') or [entry.get('cover_tape') or entry.get('img')])[0]}, entry['id'])
        return entry

    @app.get('/api/studio/sample')
    def get_sample(request: Request):
        samples = own_records(request, 'sample')
        return {'sample': samples[0] if samples else None}

    @app.put('/api/studio/sample')
    async def save_sample(request: Request):
        user = account(request)
        form = await upload_form(request, max_files=1, max_fields=1)
        content = await read_upload(form.get('audio'), 50_000_000)
        duration = validate_wav(content)
        if not .25 <= duration <= 120:
            raise HTTPException(400, '示例音频时长需为 0.25 秒到 2 分钟')
        sid = uuid.uuid4().hex
        ref = f"outputs/users/{user['id']}/{sid}/sample.wav"
        target = ref_path(ref)
        entry = {'id': sid, 'name': str(form.get('name') or '我的示例音频').strip()[:120],
                 'audio': ref, 'duration': duration, 'created': time.time()}
        old_files = []
        try:
            target.parent.mkdir(parents=True)
            target.write_bytes(content)
            with db() as con:
                con.execute('BEGIN IMMEDIATE')
                old_files = con.execute("SELECT m.ref,m.bytes FROM media m JOIN records r ON r.id=m.record_id WHERE r.owner=? AND r.kind='sample'", (user['id'],)).fetchall()
                used = con.execute('SELECT COALESCE(SUM(bytes),0) FROM media WHERE owner=?', (user['id'],)).fetchone()[0]
                if used - sum(f['bytes'] for f in old_files) + len(content) > quota:
                    raise HTTPException(413, '存储空间已满，请先删除不需要的记忆')
                con.execute("DELETE FROM records WHERE owner=? AND kind='sample'", (user['id'],))
                con.execute('INSERT INTO records VALUES(?,?,?,?,?,NULL)',
                            (sid, user['id'], 'sample', json.dumps(entry, ensure_ascii=False), entry['created']))
                con.execute('INSERT INTO media VALUES(?,?,?,?,?,?)',
                            (ref, user['id'], sid, len(content), 'audio/wav', 'sample'))
        except Exception:
            shutil.rmtree(target.parent, ignore_errors=True)
            raise
        for file in old_files:
            ref_path(file['ref']).unlink(missing_ok=True)
        return {'sample': entry}

    @app.delete('/api/studio/sample')
    def delete_sample(request: Request):
        user = account(request)
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            files = con.execute("SELECT m.ref FROM media m JOIN records r ON r.id=m.record_id WHERE r.owner=? AND r.kind='sample'", (user['id'],)).fetchall()
            con.execute("DELETE FROM records WHERE owner=? AND kind='sample'", (user['id'],))
        for file in files:
            ref_path(file['ref']).unlink(missing_ok=True)
        return {'ok': True}

    @app.post('/api/memories', status_code=201)
    async def save_memory(request: Request):
        user = account(request)
        form = await upload_form(request, max_files=15, max_fields=24)
        raw = await audio_from_form(form, 'audio', user)
        duration = validate_wav(raw)
        mid = uuid.uuid4().hex
        folder = data / 'users' / user['id'] / mid
        folder.mkdir(parents=True)
        files = []

        def store(name, content, mime):
            (folder / name).write_bytes(content)
            ref = f"outputs/users/{user['id']}/{mid}/{name}"
            files.append({'ref': ref, 'bytes': len(content), 'mime': mime})
            return ref

        try:
            entry = {'id': mid, 'title': str(form.get('title') or form.get('notes') or '一段声音')[:80],
                     'created': time.time(), 'duration': duration, 'audio': store('audio.wav', raw, 'audio/wav'),
                     'music_audio': None, 'images': [], 'videos': [], 'audio_files': [], 'project': str(form.get('project', ''))[:24000]}
            for key, limit in (('notes', 1200), ('mood', 32), ('location', 100), ('weather', 100), ('activity', 32), ('music_prompt', 500), ('music_style', 32)):
                entry[key] = str(form.get(key, ''))[:limit]
            entry['scene'] = form.get('scene') if form.get('scene') in SCENES else SCENES[0]
            entry['captured_at'] = float(form.get('captured_at') or time.time())
            if not math.isfinite(entry['captured_at']):
                raise HTTPException(400, '时间无效')
            for key, bound in (('lat', 90), ('lng', 180)):
                value = form.get(key)
                entry[key] = float(value) if value not in (None, '') else None
                if entry[key] is not None and (not math.isfinite(entry[key]) or abs(entry[key]) > bound):
                    raise HTTPException(400, '地点坐标无效')
            if form.get('music_audio') is not None or form.get('music_audio_upload_id'):
                music = await audio_from_form(form, 'music_audio', user)
                entry['music_duration'] = validate_wav(music)
                entry['music_audio'] = store('music.wav', music, 'audio/wav')
            for key, count, limit in (('images', 6, 12_000_000), ('videos', 2, 60_000_000), ('audio_files', 4, 30_000_000)):
                uploads = form.getlist(key)
                if len(uploads) > count:
                    raise HTTPException(400, f'{key} 最多上传 {count} 个文件')
                for i, upload in enumerate(uploads):
                    content = await read_upload(upload, limit)
                    ext = Path(upload.filename or '').suffix.lower()
                    if key == 'images':
                        content, ext, mime = normalize_image(content), '.jpg', 'image/jpeg'
                    elif key == 'videos':
                        if ext not in ('.mp4', '.mov', '.webm') or not (content[4:8] == b'ftyp' or content[:4] == b'\x1aE\xdf\xa3'):
                            raise HTTPException(400, '视频请使用 MP4、MOV 或 WebM')
                        mime = 'video/webm' if ext == '.webm' else 'video/mp4'
                    else:
                        audio_types = {'.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4', '.ogg': 'audio/ogg', '.webm': 'audio/webm'}
                        if ext not in audio_types:
                            raise HTTPException(400, '补充音频格式不支持')
                        mime = audio_types[ext]
                    entry[key].append(store(f'{key}_{i}{ext}', content, mime))
            background = ref_path(entry['images'][0]) if entry['images'] else None
            for kind in ('tape', 'vinyl'):
                file = cover(folder, entry['title'], background, kind)
                entry[f'cover_{kind}'] = store(file.name, file.read_bytes(), 'image/jpeg')
            entry['art_status'] = 'photo_cover' if background else 'text_only'
            result = commit_record(user, entry, 'memory', files, str(form.get('share', '')).lower() == 'true')
            for key in ('audio_upload_id', 'music_audio_upload_id'):
                discard_staged_audio(form.get(key), user)
            return result
        except Exception:
            shutil.rmtree(folder)
            raise

    @app.post('/api/material-import', status_code=201)
    async def import_material(request: Request):
        from soundtrace_media import convert, FORMATS
        user = account(request)
        form = await upload_form(request, max_files=1, max_fields=5)
        upload = form.get('file')
        filename = str(form.get('filename') or getattr(upload, 'filename', '') or '')
        suffix = Path(filename).suffix.lower()
        if suffix not in FORMATS:
            raise HTTPException(400, '支持 MP4、MOV、WebM、MKV 视频及 WAV、MP3、M4A、FLAC、OGG 音频')
        raw = await audio_from_form(form, 'file', user)
        try:
            content = await asyncio.to_thread(convert, raw, suffix)
        except RuntimeError as error:
            raise HTTPException(400, str(error))
        duration = validate_wav(content)
        mid = uuid.uuid4().hex
        folder = data / 'users' / user['id'] / mid
        folder.mkdir(parents=True)
        files = []
        def store(name, blob, mime):
            (folder/name).write_bytes(blob)
            ref = f"outputs/users/{user['id']}/{mid}/{name}"
            files.append({'ref':ref, 'bytes':len(blob), 'mime':mime})
            return ref
        try:
            entry = {'id':mid, 'title':str(form.get('title') or Path(filename).stem or '上传素材')[:80],
                     'created':time.time(), 'captured_at':time.time(), 'duration':duration,
                     'audio':store('audio.wav',content,'audio/wav'), 'music_audio':None,
                     'images':[], 'videos':[], 'audio_files':[], 'scene':SCENES[0],
                     'lat':None, 'lng':None, 'notes':'', 'original_filename':Path(filename).name[:180]}
            entry['original_file'] = store('original'+suffix,raw,'application/octet-stream')
            entry['material_title'] = entry['title']
            entry['source_type'] = 'video' if suffix in ('.mp4','.mov','.webm','.mkv') else 'audio'
            for kind in ('tape','vinyl'):
                file = cover(folder,entry['title'],None,kind)
                entry['cover_'+kind] = store(file.name,file.read_bytes(),'image/jpeg')
            entry['art_status'] = 'text_only'
            result = commit_record(user,entry,'memory',files)
        except Exception:
            for file in folder.iterdir():
                file.unlink()
            folder.rmdir()
            raise
        discard_staged_audio(form.get('file_upload_id'),user)
        return result

    @app.post('/api/studio/works', status_code=201)
    async def save_work(request: Request):
        from urllib.parse import unquote
        user = account(request)
        encoded = request.headers.get('x-soundtrace-metadata', '{}')
        if len(encoded) > 24000:
            raise HTTPException(413, '作品信息过长')
        info = json.loads(unquote(encoded))
        if not isinstance(info, dict):
            raise HTTPException(400, '作品信息无效')
        content = await request.body()
        if len(content) > 60_000_000:
            raise HTTPException(413, '音频最多 60 MB')
        duration = validate_wav(content)
        wid = uuid.uuid4().hex
        ref = f"outputs/users/{user['id']}/{wid}/master.wav"
        folder = ref_path(ref).parent
        folder.mkdir(parents=True)
        ref_path(ref).write_bytes(content)
        scene = info.get('scene') if info.get('scene') in SCENES else SCENES[0]
        metadata = {key: str(info.get(key, ''))[:600] for key in ('title', 'location', 'story')}
        metadata['scene'] = scene
        for key, bound in (('lat', 90), ('lng', 180)):
            value = info.get(key)
            if isinstance(value, (int, float)) and math.isfinite(value) and abs(value) <= bound:
                metadata[key] = value
        entry = {'id': wid, 'title': metadata['title'] or '此刻的声音', 'audio': ref, 'duration': duration,
                 'kind': 'mix', 'collectible': 'vinyl', 'metadata': metadata, 'img': f'assets/scenes-v1/{scene}.png',
                 'created': time.time(), 'project': info.get('project'), 'version': info.get('version', 'draft')}
        try:
            return commit_record(user, entry, 'work', [{'ref': ref, 'bytes': len(content), 'mime': 'audio/wav'}], info.get('share') is True)
        except Exception:
            shutil.rmtree(folder)
            raise

    @app.post('/api/memories/{mid}/music')
    async def save_diary_music(mid: str, request: Request):
        user = account(request)
        memory_detail(mid, request)
        form = await upload_form(request, max_files=7, max_fields=24)
        content = await audio_from_form(form, 'music_audio', user)
        music_duration = validate_wav(content)
        uploads = form.getlist('images')
        if len(uploads) > 6:
            raise HTTPException(400, '最多保存 6 张照片')
        pictures = [normalize_image(await read_upload(upload, 12_000_000)) for upload in uploads]
        folder = data / 'users' / user['id'] / mid
        written = []
        removed = []
        def store(name, raw, mime):
            ref = f"outputs/users/{user['id']}/{mid}/{name}"
            ref_path(ref).write_bytes(raw)
            written.append({'ref':ref,'bytes':len(raw),'mime':mime})
            return ref
        try:
            with db() as con:
                con.execute('BEGIN IMMEDIATE')
                row = con.execute("SELECT payload FROM records WHERE id=? AND owner=? AND kind='memory'", (mid,user['id'])).fetchone()
                if not row:
                    raise HTTPException(404, '声音素材已被删除')
                entry = json.loads(row['payload'])
                entry.setdefault('material_title',Path(entry['original_filename']).stem if entry.get('original_filename') else entry['title'])
                entry['music_duration'] = music_duration
                source_ref = form.get('music_source_ref')
                if source_ref is not None:
                    if not isinstance(source_ref,str) or not con.execute("SELECT 1 FROM media WHERE ref=? AND owner=? AND record_id=? AND mime='audio/wav'",(source_ref,user['id'],mid)).fetchone():
                        raise HTTPException(400, '创作素材不存在或无权使用')
                    entry['music_source_ref'] = source_ref
                if len(entry.get('images',[])) + len(pictures) > 6:
                    raise HTTPException(400, '原有照片与新照片合计不能超过 6 张')
                for key, limit in (('title',80),('notes',1200),('mood',32),('weather',100),('activity',32),('location',100),('music_prompt',500),('music_style',32),('project',24000)):
                    if key in form:
                        value = str(form[key]).strip()[:limit]
                        if key != 'title' or value:
                            entry[key] = value
                if form.get('scene') in SCENES:
                    entry['scene'] = form['scene']
                if str(form.get('include_location','')).lower() == 'false':
                    entry['lat'] = entry['lng'] = None
                    entry['location'] = ''
                else:
                    for key,bound in (('lat',90),('lng',180)):
                        if form.get(key) not in (None,''):
                            try:
                                value = float(form[key])
                            except (TypeError,ValueError):
                                raise HTTPException(400, '地点坐标无效')
                            if not math.isfinite(value) or abs(value)>bound:
                                raise HTTPException(400, '地点坐标无效')
                            entry[key] = value
                old_refs = [entry.get('music_audio'),entry.get('cover_tape'),entry.get('cover_vinyl')]
                for old in filter(None,old_refs):
                    referenced = con.execute('SELECT 1 FROM post_media WHERE ref=? UNION ALL SELECT 1 FROM letter_media WHERE ref=? LIMIT 1',(old,old)).fetchone()
                    if not referenced:
                        removed.append(old)
                entry['music_audio'] = store('music-'+uuid.uuid4().hex+'.wav',content,'audio/wav')
                for pic in pictures:
                    entry.setdefault('images',[]).append(store('photo-'+uuid.uuid4().hex+'.jpg',pic,'image/jpeg'))
                if form.get('background_mode') in ('photo', 'stylized'):
                    entry['background_mode'] = form['background_mode']
                art_ref = entry.get('scene_art') if entry.get('background_mode') == 'stylized' and entry.get('scene_art_source') == entry.get('background_source') else None
                background = ref_path(art_ref or entry.get('background_source') or entry['images'][0]) if entry.get('images') else None
                with tempfile.TemporaryDirectory(dir=folder) as temp:
                    for kind in ('tape','vinyl'):
                        file = cover(Path(temp), entry['title'], background, kind)
                        entry['cover_'+kind] = store(kind+'-'+uuid.uuid4().hex+'.jpg',file.read_bytes(),'image/jpeg')
                entry['art_status'] = 'stylized' if art_ref else 'photo_cover' if background else 'text_only'
                entry['music_updated_at'] = time.time()
                used = con.execute('SELECT COALESCE(SUM(bytes),0) FROM media WHERE owner=?',(user['id'],)).fetchone()[0]
                reclaim = sum((con.execute('SELECT bytes FROM media WHERE ref=?',(ref,)).fetchone() or [0])[0] for ref in removed)
                if used-reclaim+sum(f['bytes'] for f in written)>quota:
                    raise HTTPException(413,'存储空间已满，请先删除不需要的记忆')
                for file in written:
                    con.execute('INSERT INTO media VALUES(?,?,?,?,?,?)',(file['ref'],user['id'],mid,file['bytes'],file['mime'],'memory'))
                for ref in removed:
                    con.execute('DELETE FROM media WHERE ref=?',(ref,))
                con.execute('UPDATE records SET payload=? WHERE id=?',(json.dumps(entry,ensure_ascii=False),mid))
                if str(form.get('share','')).lower() == 'true':
                    if not con.execute("SELECT 1 FROM records WHERE source_id=? AND kind='post'",(mid,)).fetchone():
                        publish(con,user,entry['notes'] or entry['title'],{'audio':entry['music_audio'],'img':(entry['images'] or [entry['cover_vinyl']])[0]},mid)
        except Exception:
            for file in written:
                ref_path(file['ref']).unlink(missing_ok=True)
            raise
        for ref in removed:
            ref_path(ref).unlink(missing_ok=True)
        discard_staged_audio(form.get('music_audio_upload_id'), user)
        return entry

    @app.post('/api/memories/{mid}/publish')
    def publish_memory(mid: str, request: Request):
        user = account(request)
        with db() as con:
            row = con.execute("SELECT payload FROM records WHERE id=? AND owner=? AND kind='memory'", (mid, user['id'])).fetchone()
            if not row:
                raise HTTPException(404, '记忆不存在')
            m = json.loads(row['payload'])
            existing = con.execute("SELECT payload FROM records WHERE source_id=? AND kind='post'", (mid,)).fetchone()
            references = {'audio': m.get('music_audio') or m['audio'], 'img': (m['images'] or [m.get('cover_vinyl') if m.get('music_audio') else m['cover_tape']])[0]}
            entry = json.loads(existing['payload']) if existing else publish(con, user, m['notes'] or m['title'], references, mid)
            entry.update(text=m['notes'] or m['title'], title=m['title'], images=m.get('images',[]), **references)
            con.execute('DELETE FROM post_media WHERE post_id=?',(entry['id'],))
            for ref in set([references['audio'],references['img'],*entry['images']]):
                owned_reference(con,user,ref)
                con.execute('INSERT INTO post_media VALUES(?,?)',(entry['id'],ref))
            con.execute('UPDATE records SET payload=? WHERE id=?',(json.dumps(entry,ensure_ascii=False),entry['id']))
            return entry

    @app.delete('/api/memories/{mid}')
    def delete_memory(mid: str, request: Request):
        user = account(request)
        with db() as con:
            row = con.execute("SELECT id FROM records WHERE id=? AND owner=? AND kind IN ('memory','work')", (mid, user['id'])).fetchone()
            if not row:
                raise HTTPException(404, '记忆不存在')
            con.execute('DELETE FROM records WHERE id=?', (mid,))
        folder = data / 'users' / user['id'] / mid
        if folder.is_dir():
            shutil.rmtree(folder)
        return {'ok': True}

    @app.post('/api/user/{role}')
    async def profile_image(role: str, request: Request):
        if role not in ('avatar', 'background'):
            raise HTTPException(404)
        user = account(request)
        form = await upload_form(request, max_files=1)
        content = normalize_image(await read_upload(form.get('file'), 12_000_000), 400 if role == 'avatar' else 1600)
        ref = f"outputs/users/{user['id']}/profile/{uuid.uuid4().hex}.jpg"
        target = ref_path(ref)
        target.parent.mkdir(parents=True, exist_ok=True)
        old = None
        try:
            with db() as con:
                con.execute('BEGIN IMMEDIATE')
                used = con.execute('SELECT COALESCE(SUM(bytes),0) FROM media WHERE owner=?', (user['id'],)).fetchone()[0]
                if used + len(content) > quota:
                    raise HTTPException(413, '存储空间已满')
                values = json.loads(con.execute('SELECT profile FROM users WHERE id=?', (user['id'],)).fetchone()[0])
                old = values.get(role + '_img')
                values[role + '_img'] = ref
                target.write_bytes(content)
                con.execute('INSERT INTO media VALUES(?,?,NULL,?,?,?)', (ref, user['id'], len(content), 'image/jpeg', role))
                con.execute('UPDATE users SET profile=? WHERE id=?', (json.dumps(values), user['id']))
                if old:
                    con.execute('DELETE FROM media WHERE ref=? AND owner=?', (old, user['id']))
        except Exception:
            target.unlink(missing_ok=True)
            raise
        if old:
            ref_path(old).unlink(missing_ok=True)
        return {role + '_img': ref}

    @app.get('/outputs/{path:path}')
    def media(path: str, request: Request):
        ref = 'outputs/' + path
        with db() as con:
            row = con.execute('SELECT * FROM media WHERE ref=?', (ref,)).fetchone()
            shared = con.execute('SELECT 1 FROM post_media WHERE ref=? LIMIT 1', (ref,)).fetchone()
        if not row:
            # Only checked-in seed sounds are available to guests; no legacy personal files.
            seed = (ROOT / 'outputs' / path).resolve()
            if path.startswith('seeds/') and seed.is_relative_to(ROOT / 'outputs' / 'seeds') and seed.suffix == '.wav' and seed.is_file():
                return FileResponse(seed, media_type='audio/wav')
            raise HTTPException(404)
        user = account(request, False)
        with db() as con:
            delivered = bool(user and con.execute('SELECT 1 FROM letter_media lm JOIN letters l ON l.id=lm.letter_id WHERE lm.ref=? AND l.recipient=? LIMIT 1',(ref,user['id'])).fetchone())
        if not shared and not delivered and row['role'] != 'avatar' and (not user or user['id'] != row['owner']):
            raise HTTPException(404)
        target = ref_path(ref).resolve()
        if not target.is_relative_to(data) or not target.is_file():
            raise HTTPException(404)
        return FileResponse(target, media_type=row['mime'])

    @app.get('/api/health')
    @app.get('/api/studio/health')
    def health():
        with db() as con:
            con.execute('SELECT 1').fetchone()
        from soundtrace_music import music_config
        from soundtrace_art import art_config
        from soundtrace_processing import processing_config
        config = music_config()
        return {'editing': True, 'storage': True, 'accounts': True, 'ai': config['enabled'], 'music_provider': config['provider'], 'image_generation': art_config()['enabled'], 'sound_analysis': processing_config()['enabled'], 'stem_separation': processing_config()['stem_separation'], 'local_humming': True, 'speech_to_text': os.getenv('SOUNDTRACE_ENABLE_STT') == '1'}

    @app.get('/api/inbox')
    @app.get('/api/exchange')
    def letters_list(request: Request):
        user = account(request,False)
        if not user:
            return {'items':[]}
        inbound = request.url.path.endswith('/inbox')
        with db() as con:
            rows = con.execute('SELECT * FROM letters WHERE '+('recipient' if inbound else 'owner')+'=? ORDER BY created DESC',(user['id'],)).fetchall()
        return {'items':[{**json.loads(row['payload']),'id':row['id'],'dir':'in' if inbound else 'out',
                         'from':'远方的旅人','to':'远方的旅人','status':'delivered' if row['recipient'] else 'waiting',
                         'created':row['created']} for row in rows]}

    @app.post('/api/memories/{mid}/send')
    async def send_memory(mid: str, request: Request):
        user = account(request)
        options = await request.json()
        if not isinstance(options,dict):
            raise HTTPException(400,'寄送选项无效')
        kind = options.get('kind','vinyl')
        if kind not in ('vinyl','tape','photo'):
            raise HTTPException(400,'物件类型无效')
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute("SELECT payload FROM records WHERE id=? AND owner=? AND kind='memory'",(mid,user['id'])).fetchone()
            if not row:
                raise HTTPException(404,'记忆不存在')
            memory = json.loads(row['payload'])
            if options.get('receive_mail') is True:
                con.execute('INSERT OR IGNORE INTO mailbox_members VALUES(?)',(user['id'],))
                # Only people who actively join the exchange can receive another person's memory.
                pending = con.execute('SELECT id FROM letters WHERE recipient IS NULL AND owner<>? ORDER BY created LIMIT 1',(user['id'],)).fetchone()
                if pending:
                    con.execute('UPDATE letters SET recipient=?,delivered=? WHERE id=?',(user['id'],time.time(),pending['id']))
            elif options.get('receive_mail') is False:
                con.execute('DELETE FROM mailbox_members WHERE owner=?',(user['id'],))
            existing = con.execute('SELECT * FROM letters WHERE owner=? AND source_id=? AND kind=?',(user['id'],mid,kind)).fetchone()
            if existing:
                return {'id':existing['id'],'status':'delivered' if existing['recipient'] else 'waiting'}
            recipient = con.execute('SELECT owner FROM mailbox_members WHERE owner<>? ORDER BY RANDOM() LIMIT 1',(user['id'],)).fetchone()
            lid = uuid.uuid4().hex
            payload = {'title':memory['title'],'story':memory.get('notes',''),'kind':kind,
                       'allow_reuse':options.get('allow_reuse') is True,
                       'audio':memory.get('music_audio') if kind=='vinyl' and memory.get('music_audio') else memory['audio'],
                       'img':(memory.get('images') or [memory.get('cover_vinyl' if kind=='vinyl' else 'cover_tape')])[0]}
            now = time.time()
            con.execute('INSERT INTO letters VALUES(?,?,?,?,?,?,?,?)',(lid,user['id'],recipient['owner'] if recipient else None,mid,kind,json.dumps(payload,ensure_ascii=False),now,now if recipient else None))
            for ref in set(filter(None,(payload['audio'],payload['img']))):
                con.execute('INSERT INTO letter_media VALUES(?,?)',(lid,ref))
        return {'id':lid,'status':'delivered' if recipient else 'waiting'}

    @app.post('/api/transcribe')
    async def transcribe(request: Request):
        account(request)
        if os.getenv('SOUNDTRACE_ENABLE_STT') != '1':
            raise HTTPException(503, '语音识别服务尚未启用，可以直接输入文字')
        from faster_whisper import WhisperModel
        form = await upload_form(request, max_files=1)
        audio = await read_upload(form.get('file'), 10_000_000)
        if not hasattr(app.state, 'whisper'):
            app.state.whisper = WhisperModel(os.getenv('SOUNDTRACE_WHISPER_MODEL', 'small'), device='cpu', compute_type='int8')
        from starlette.concurrency import run_in_threadpool
        def recognize():
            segments, _ = app.state.whisper.transcribe(io.BytesIO(audio), language='zh', vad_filter=True)
            return {'text': ''.join(s.text for s in segments).strip()}
        return await run_in_threadpool(recognize)

    @app.post('/api/upload')
    @app.post('/api/analyze-beat')
    def ai_unavailable(request: Request):
        account(request)
        raise HTTPException(503, 'AI 音乐服务尚未连接，录音、编辑、保存与发布仍可使用')

    from soundtrace_music import install_music
    from soundtrace_art import install_art
    from soundtrace_maps import install_maps
    from soundtrace_processing import install_processing
    install_processing(app, db, account, data, quota, validate_wav)
    install_music(app, db, account, data, quota, validate_wav)
    install_art(app, db, account, data, quota, normalize_image, cover)
    install_maps(app, account)

    app.mount('/assets', StaticFiles(directory=ROOT / 'webapp' / 'assets'), name='assets')
    app.mount('/mineradio', StaticFiles(directory=ROOT / 'third_party' / 'Mineradio-paused-main' / 'public'), name='mineradio')
    pages = {'/': 'home.html', '/capture': 'index.html', '/studio': 'index.html', '/library': 'index.html', '/album': 'album-room.html',
             '/map': 'map.html', '/community': 'community.html'}

    @app.get('/me')
    def me():
        from fastapi.responses import RedirectResponse
        return RedirectResponse('/album?profile=1')

    @app.get('/source')
    def source_archive():
        archive = ROOT / 'public-source.zip'
        if not archive.is_file():
            archive = ROOT / 'runtime' / 'releases' / 'soundtrace-public.zip'
        if not archive.is_file():
            raise HTTPException(404, '源码归档尚未生成')
        return FileResponse(archive, media_type='application/zip', filename='soundtrace-source.zip')

    def page_endpoint(file, demo=False):
        def page():
            html = (ROOT / 'webapp' / file).read_text(encoding='utf-8')
            html = html.replace('src="assets/', 'src="/assets/').replace('href="assets/', 'href="/assets/')
            html = html.replace('src="mineradio/', 'src="/mineradio/')
            runtime = '<script src="/assets/soundtrace-demo.js?v=5"></script>' if demo else ''
            html = html.replace('<head>', '<head>' + runtime + '<script src="/assets/soundtrace-account.js?v=5" defer></script>', 1)
            if demo:
                html = html.replace('href="/" aria-label="声迹首页"', 'href="/demo" aria-label="声迹演示"')
                html = html.replace('class="doodle-brand" href="/"', 'class="doodle-brand" href="/demo"')
                html = html.replace('class="brand" href="/"', 'class="brand" href="/demo"')
                html = html.replace('<title>', '<title>演示 · ', 1)
            return HTMLResponse(html)
        return page

    for route, file in pages.items():
        app.add_api_route(route, page_endpoint(file), methods=['GET'], include_in_schema=False)
        app.add_api_route('/demo' + (route if route != '/' else ''), page_endpoint(file, True), methods=['GET'], include_in_schema=False)

    app.state.data_dir = data
    return app


app = create_app()
