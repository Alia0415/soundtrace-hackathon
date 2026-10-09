"""Authenticated multi-user boundary for the existing private AudioSep/CLAP worker."""
import asyncio
import json
import os
import re
import time
import uuid
from urllib.parse import urlsplit

import httpx
from fastapi import BackgroundTasks, HTTPException, Request


def processing_config():
    return {'enabled': bool(os.getenv('SOUNDTRACE_GPU_URL', '').strip()), 'provider': 'audiosep-clap'}


class ProcessingCancelled(Exception):
    pass


async def process_audio(content, kind, target, stage):
    base = os.environ['SOUNDTRACE_GPU_URL'].rstrip('/')
    url = urlsplit(base)
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.query or url.fragment:
        raise RuntimeError('声音处理服务地址配置无效')
    password = os.getenv('SOUNDTRACE_GPU_PASSWORD', '')
    auth = httpx.BasicAuth(os.getenv('SOUNDTRACE_GPU_USER', 'soundtrace'), password) if password else None
    async with httpx.AsyncClient(timeout=120, follow_redirects=False, auth=auth) as client:
        stage('正在向私有声音处理服务提交原声')
        response = await client.post(base + '/api/upload', files={'file': ('original.wav', content, 'audio/wav')})
        response.raise_for_status()
        upload_id = response.json()['upload_id']
        if not isinstance(upload_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]+\.wav', upload_id):
            raise RuntimeError('声音服务返回了无效素材编号')
        stage('正在辨认声音' if kind == 'analyze' else '正在分离声源')
        if kind == 'analyze':
            response = await client.post(base + '/api/analyze/' + upload_id)
            response.raise_for_status()
            tags = response.json()['tags']
            if not isinstance(tags, list):
                raise RuntimeError('声音服务返回了无效标签')
            return {'tags': [{'en': str(t.get('en', ''))[:120], 'zh': str(t.get('zh', ''))[:120]}
                             for t in tags[:12] if isinstance(t, dict)]}
        response = await client.post(base + '/api/jobs', json={'type': 'extract', 'upload_id': upload_id,
                                                               'target_en': target, 'auto_register': False})
        response.raise_for_status()
        jid = response.json()['job_id']
        if not isinstance(jid, str) or not re.fullmatch(r'[a-zA-Z0-9_-]+', jid):
            raise RuntimeError('声音服务返回了无效任务编号')
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            stage('正在分离声源，原声将保留')
            await asyncio.sleep(2)
            response = await client.get(base + '/api/jobs/' + jid)
            response.raise_for_status()
            result = response.json()
            if result['status'] == 'failed':
                raise RuntimeError('声源处理失败，原声已保留，请检查模型后重试')
            if result['status'] != 'done':
                continue
            ref = result['results'].get('denoised') or result['results'].get('extracted')
            if not isinstance(ref, str) or not re.fullmatch(r'outputs/service_jobs/' + re.escape(jid) + r'/[a-zA-Z0-9_-]+\.wav', ref):
                raise RuntimeError('声音服务返回了无效音频路径')
            stage('正在保存处理结果')
            chunks, size = [], 0
            async with client.stream('GET', base + '/' + ref) as download:
                download.raise_for_status()
                async for chunk in download.aiter_bytes():
                    size += len(chunk)
                    if size > 60_000_000:
                        raise RuntimeError('处理结果超过保存上限')
                    chunks.append(chunk)
            return {'audio': b''.join(chunks)}
        raise RuntimeError('声音处理超时，原声已保留')


def install_processing(app, db, account, data, quota, validate_wav):
    with db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS sound_jobs(
            id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            memory_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
            status TEXT NOT NULL, stage TEXT NOT NULL, result TEXT, created REAL NOT NULL,
            cancel_requested INTEGER NOT NULL DEFAULT 0)''')
        con.execute("UPDATE sound_jobs SET status='failed',stage='服务重启，原声已保留，请重试' WHERE status IN ('queued','running')")

    async def work(jid, owner, mid, ref, kind, target):
        output = data / 'users' / owner / mid / ('extracted-' + jid + '.wav')
        def stage(message):
            with db() as con:
                row = con.execute('SELECT cancel_requested FROM sound_jobs WHERE id=?', (jid,)).fetchone()
                if not row or row['cancel_requested']:
                    raise ProcessingCancelled()
                con.execute("UPDATE sound_jobs SET status='running',stage=? WHERE id=?", (message, jid))
        try:
            stage('正在读取原声')
            source = (data / ref.removeprefix('outputs/')).resolve()
            if not source.is_relative_to(data):
                raise RuntimeError('原声音频路径无效')
            result = await process_audio(source.read_bytes(), kind, target, stage)
            stage('正在保存结果')
            with db() as con:
                con.execute('BEGIN IMMEDIATE')
                row = con.execute('SELECT cancel_requested FROM sound_jobs WHERE id=?', (jid,)).fetchone()
                if not row or row['cancel_requested']:
                    raise ProcessingCancelled()
                if 'audio' in result:
                    content = result['audio']; duration = validate_wav(content)
                    used = con.execute('SELECT COALESCE(SUM(bytes),0) FROM media WHERE owner=?', (owner,)).fetchone()[0]
                    if used + len(content) > quota:
                        raise RuntimeError('存储空间不足，原声已保留')
                    output.parent.mkdir(parents=True, exist_ok=True); output.write_bytes(content)
                    out_ref = f'outputs/users/{owner}/{mid}/{output.name}'
                    con.execute('INSERT INTO media VALUES(?,?,?,?,?,?)', (out_ref, owner, mid, len(content), 'audio/wav', 'extracted'))
                    result = {'denoised': out_ref, 'duration': duration}
                con.execute("UPDATE sound_jobs SET status='done',stage='处理完成',result=? WHERE id=?", (json.dumps(result, ensure_ascii=False), jid))
        except ProcessingCancelled:
            output.unlink(missing_ok=True)
            with db() as con:
                con.execute("UPDATE sound_jobs SET status='cancelled',stage='已停止等待，原声已保留' WHERE id=?", (jid,))
        except Exception as error:
            output.unlink(missing_ok=True)
            message = str(error) if isinstance(error, RuntimeError) else '声音处理服务连接失败，请检查服务配置或模型'
            with db() as con:
                con.execute("UPDATE sound_jobs SET status='failed',stage=? WHERE id=?", (message, jid))

    @app.post('/api/sound/jobs', status_code=202)
    async def create(request: Request, background: BackgroundTasks):
        user = account(request)
        if not processing_config()['enabled']:
            raise HTTPException(503, '声音辨识与提取服务尚未配置；哼唱转旋律可在本机使用')
        raw = await request.body()
        if len(raw) > 4000:
            raise HTTPException(413, '参数过长')
        body = json.loads(raw)
        if not isinstance(body, dict) or body.get('type') not in ('analyze', 'extract') or not isinstance(body.get('memory_id'), str):
            raise HTTPException(400, '声音处理参数无效')
        target = body.get('target', '')
        if not isinstance(target, str) or len(target) > 120 or (body['type'] == 'extract' and not target.strip()):
            raise HTTPException(400, '请填写不超过 120 字的目标声源')
        mid, jid = body['memory_id'], uuid.uuid4().hex
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            record = con.execute("SELECT payload FROM records WHERE id=? AND owner=? AND kind='memory'", (mid, user['id'])).fetchone()
            if not record:
                raise HTTPException(404, '声音素材不存在')
            if con.execute("SELECT 1 FROM sound_jobs WHERE owner=? AND status IN ('queued','running')", (user['id'],)).fetchone():
                raise HTTPException(409, '上一段声音仍在处理，请稍候')
            count = con.execute('SELECT COUNT(*) FROM sound_jobs WHERE owner=? AND created>?', (user['id'], time.time()-86400)).fetchone()[0]
            if count >= int(os.getenv('SOUNDTRACE_SOUND_DAILY_LIMIT', '10')):
                raise HTTPException(429, '已达到今日声音处理次数上限')
            con.execute('INSERT INTO sound_jobs(id,owner,memory_id,status,stage,created) VALUES(?,?,?,?,?,?)',
                        (jid, user['id'], mid, 'queued', '正在排队', time.time()))
        background.add_task(work, jid, user['id'], mid, json.loads(record['payload'])['audio'], body['type'], target)
        return {'job_id': jid}

    @app.get('/api/sound/jobs/{jid}')
    def read(jid: str, request: Request):
        user = account(request)
        with db() as con:
            row = con.execute('SELECT * FROM sound_jobs WHERE id=? AND owner=?', (jid, user['id'])).fetchone()
        if not row:
            raise HTTPException(404)
        return {'job_id': jid, 'status': row['status'], 'stage': row['stage'],
                'results': json.loads(row['result']) if row['status'] == 'done' else None}

    @app.post('/api/sound/jobs/{jid}/cancel')
    def cancel(jid: str, request: Request):
        user = account(request)
        with db() as con:
            count = con.execute('UPDATE sound_jobs SET cancel_requested=1 WHERE id=? AND owner=?', (jid, user['id'])).rowcount
        if not count:
            raise HTTPException(404)
        return {'ok': True}
