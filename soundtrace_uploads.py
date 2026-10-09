"""Bounded, authenticated staging for audio that exceeds gateway request limits."""
import re
import time
import uuid

from fastapi import HTTPException, Request

CHUNK = 4_000_000
LIMIT = 60_000_000


def install_uploads(app, db, account, data, quota):
    folder = data / 'pending-audio'
    folder.mkdir(exist_ok=True)
    with db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS audio_uploads(
            id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            size INTEGER NOT NULL, received INTEGER NOT NULL, created REAL NOT NULL)''')

    def cleanup(con):
        for row in con.execute('SELECT id FROM audio_uploads WHERE created<?', (time.time()-3600,)).fetchall():
            (folder / row['id']).unlink(missing_ok=True)
            con.execute('DELETE FROM audio_uploads WHERE id=?', (row['id'],))

    @app.post('/api/audio-uploads', status_code=201)
    async def start(request: Request):
        user = account(request)
        raw = await request.body()
        if len(raw) > 1000:
            raise HTTPException(413, '上传参数过长')
        import json
        body = json.loads(raw)
        size = body.get('size') if isinstance(body, dict) else None
        if type(size) is not int or not 1 <= size <= LIMIT:
            raise HTTPException(400, '音频最多 60 MB')
        uid = uuid.uuid4().hex
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            cleanup(con)
            pending = con.execute('SELECT COUNT(*),COALESCE(SUM(size),0) FROM audio_uploads WHERE owner=?', (user['id'],)).fetchone()
            used = con.execute('SELECT COALESCE(SUM(bytes),0) FROM media WHERE owner=?', (user['id'],)).fetchone()[0]
            if pending[0] >= 4 or used + pending[1] + size > quota:
                raise HTTPException(413, '暂存空间不足，请稍后重试或清理收藏')
            con.execute('INSERT INTO audio_uploads VALUES(?,?,?,?,?)', (uid, user['id'], size, 0, time.time()))
        return {'upload_id': uid, 'chunk_size': CHUNK}

    @app.put('/api/audio-uploads/{uid}/{index}')
    async def part(uid: str, index: int, request: Request):
        user = account(request)
        if not re.fullmatch(r'[0-9a-f]{32}', uid) or index < 0:
            raise HTTPException(400, '上传编号无效')
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > CHUNK:
                raise HTTPException(413, '上传分段过大')
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT * FROM audio_uploads WHERE id=? AND owner=? AND created>?', (uid, user['id'], time.time()-3600)).fetchone()
            if not row:
                raise HTTPException(404, '上传已过期，请重新保存')
            offset = index * CHUNK
            if offset > row['received'] or offset >= row['size'] or len(content) != min(CHUNK, row['size']-offset):
                raise HTTPException(400, '上传分段不完整或顺序错误')
            path = folder / uid
            with path.open('r+b' if path.exists() else 'w+b') as file:
                file.seek(offset)
                file.write(content)
            received = max(row['received'], offset+len(content))
            con.execute('UPDATE audio_uploads SET received=? WHERE id=?', (received, uid))
        return {'received': received}

    def read(uid, user):
        if not isinstance(uid, str) or not re.fullmatch(r'[0-9a-f]{32}', uid):
            raise HTTPException(400, '上传编号无效')
        with db() as con:
            row = con.execute('SELECT * FROM audio_uploads WHERE id=? AND owner=? AND created>?', (uid, user['id'], time.time()-3600)).fetchone()
            if not row:
                raise HTTPException(404, '上传不存在或已过期')
            if row['received'] != row['size']:
                raise HTTPException(400, '音频尚未上传完整')
            content = (folder / uid).read_bytes()
            if len(content) != row['size']:
                raise HTTPException(400, '音频尚未上传完整')
        return content

    def discard(uid, user):
        if not uid:
            return
        with db() as con:
            if con.execute('DELETE FROM audio_uploads WHERE id=? AND owner=?', (uid, user['id'])).rowcount:
                (folder / uid).unlink(missing_ok=True)

    return read, discard
