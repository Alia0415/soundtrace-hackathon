"""Real asynchronous instrumental generation. No synthetic-music fallback."""
import asyncio
import ipaddress
import json
import os
import socket
import time
import uuid
from urllib.parse import urlsplit, quote
import httpx
from soundtrace_network import trust_environment, provider_error
from fastapi import BackgroundTasks, HTTPException, Request


def music_config():
    provider = os.getenv('SOUNDTRACE_MUSIC_PROVIDER', 'mureka')
    enabled = (bool(os.getenv('SOUNDTRACE_MUREKA_KEY')) if provider == 'mureka' else
               bool(os.getenv('SOUNDTRACE_ACE_URL')) if provider == 'acestep' else False)
    return {'provider': provider, 'enabled': enabled}


STYLES = {'ambient': 'airy ambient, evolving pads', 'lofi': 'warm lo-fi, soft drums',
          'cinematic': 'cinematic score, expressive strings', 'piano': 'intimate acoustic piano',
          'folk': 'fingerpicked acoustic guitar', 'jazz': 'gentle jazz trio',
          'electronic': 'melodic electronica', 'orchestral': 'lush orchestral score',
          'rock': 'melodic soft rock', 'world': 'acoustic world music'}


def make_prompt(body):
    style = STYLES.get(body.get('style'), STYLES['ambient'])
    context = '；'.join(str(body.get(k) or '')[:160] for k in ('title', 'weather', 'mood', 'activity', 'notes'))
    return (f'Instrumental music diary, {style}. Memorable melody, natural dynamics, clear professional mix. '
            f'Gentle opening, developed musical phrase, resolved ending. No vocals. '
            f'Creative context: {context}. Musical direction: {str(body.get("prompt") or "")[:500]}')[:1024]


async def generate_music(body, stage):
    """Return validated-downstream audio bytes; endpoints/credentials never come from user input."""
    config = music_config()
    prompt = make_prompt(body)
    conditioned = bool(body.get('_source_audio'))
    query_kind = 'instrumental'
    async with httpx.AsyncClient(trust_env=trust_environment(), timeout=60, follow_redirects=False) as client:
        if config['provider'] == 'acestep':
            if conditioned:
                raise RuntimeError('当前 ACE 服务未接通素材条件生成，请使用 Mureka 音轨生成服务')
            base = os.environ['SOUNDTRACE_ACE_URL'].rstrip('/')
            headers = {'Authorization': 'Bearer ' + os.getenv('SOUNDTRACE_ACE_KEY', '')}
            params = {'prompt': prompt, 'lyrics': '[Instrumental]', 'task_type': 'text2music',
                      'thinking': os.getenv('SOUNDTRACE_ACE_THINKING', 'false').lower() == 'true', 'audio_format': 'wav', 'batch_size': 1,
                      'audio_duration': max(30, min(120, float(body.get('duration', 45)))),
                      'model': os.getenv('SOUNDTRACE_ACE_MODEL', 'acestep-v15-turbo'),
                      'lm_model_path': os.getenv('SOUNDTRACE_ACE_LM', 'acestep-5Hz-lm-0.6B'),
                      'inference_steps': int(os.getenv('SOUNDTRACE_ACE_STEPS', '8')), 'use_random_seed': True}
            response = await client.post(base + '/release_task', json=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
            if payload.get('code') != 200:
                raise RuntimeError('生成服务拒绝了请求，请检查模型配置')
            task = payload['data']['task_id']
        else:
            base = 'https://api.mureka.cn'
            headers = {'Authorization': 'Bearer ' + os.environ['SOUNDTRACE_MUREKA_KEY']}
            if conditioned:
                from soundtrace_media import convert
                stage('正在将所选声音素材提交给音乐模型')
                reference = await asyncio.to_thread(convert, body['_source_audio'], '.wav', True)
                upload = await client.post(base + '/v1/files/upload', headers=headers,
                                           data={'purpose': 'audio'}, files={'file': ('material.mp3', reference, 'audio/mpeg')})
                upload.raise_for_status()
                response = await client.post(base + '/v1/track/generate', headers=headers,
                                             json={'upload_audio_id': upload.json()['id'], 'generate_type': 'Instrumental',
                                                   'prompt': (prompt+' Follow the timing and musical character of the supplied audio.')[:1024]})
                query_kind = 'song'
            else:
                response = await client.post(base + '/v1/instrumental/generate', headers=headers,
                                         json={'model': os.getenv('SOUNDTRACE_MUREKA_MODEL', 'mureka-9.5'),
                                               'n': 1, 'prompt': prompt, 'stream': False})
            response.raise_for_status()
            task = response.json()['id']
        stage('服务已接收，正在编曲与合成', str(task))
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            await asyncio.sleep(3)
            if config['provider'] == 'acestep':
                response = await client.post(base + '/query_result', headers=headers, json={'task_id_list': [task]})
                response.raise_for_status()
                wrapper = response.json()
                if wrapper.get('code') != 200:
                    raise RuntimeError('无法查询生成任务，请检查音乐服务')
                result = wrapper['data'][0]
                if result['status'] == 2:
                    raise RuntimeError('模型生成失败，原声与笔记已保留')
                if result['status'] != 1:
                    continue
                choices = json.loads(result['result']) if isinstance(result['result'], str) else result['result']
                file = choices[0]['file']
                if not file.startswith('/v1/audio?'):
                    raise RuntimeError('音乐服务返回了无效音频地址')
                audio_url = base + file
            else:
                response = await client.get(base + '/v1/'+query_kind+'/query/' + quote(str(task), safe=''), headers=headers)
                response.raise_for_status()
                result = response.json()
                if result['status'] in ('failed', 'timeouted', 'cancelled'):
                    raise RuntimeError('音乐服务生成失败，原声与笔记已保留')
                if result['status'] != 'succeeded':
                    continue
                audio_url = result['choices'][0].get('wav_url')
                if not audio_url:
                    raise RuntimeError('服务未返回 WAV 音频，请检查账号下载权限')
                target = urlsplit(audio_url)
                if target.scheme != 'https' or not target.hostname or target.username or target.port not in (None, 443):
                    raise RuntimeError('音乐服务返回了无效下载地址')
                addresses = await asyncio.to_thread(socket.getaddrinfo, target.hostname, 443)
                if any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
                    raise RuntimeError('音乐下载地址无法验证')
            stage('编曲完成，正在保存音频', str(task))
            chunks, size = [], 0
            # Do not forward the provider's credential to the audio CDN.
            download_headers = headers if config['provider'] == 'acestep' else {}
            async with client.stream('GET', audio_url, headers=download_headers) as download:
                download.raise_for_status()
                async for chunk in download.aiter_bytes():
                    size += len(chunk)
                    if size > 60_000_000:
                        raise RuntimeError('生成音频超过保存上限')
                    chunks.append(chunk)
            return b''.join(chunks)
        raise RuntimeError('生成等待超时；请检查服务任务后再重试，避免重复计费')


def install_music(app, db, account, data, quota, validate_wav):
    with db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS music_jobs(
          id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          memory_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
          status TEXT NOT NULL, stage TEXT NOT NULL, payload TEXT NOT NULL,
          result TEXT, created REAL NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0)''')
        con.execute("UPDATE music_jobs SET status='failed',stage='服务重启中断了等待，请确认上游任务后再重试' WHERE status IN ('queued','running')")

    async def work(jid, owner, mid, body):
        def stage(message, upstream=''):
            with db() as con:
                con.execute("UPDATE music_jobs SET status='running',stage=?,result=? WHERE id=?", (message, json.dumps({'upstream_id': upstream}), jid))
        path = data / 'users' / owner / mid / ('generated-' + jid + '.wav')
        try:
            stage('正在向音乐服务提交任务')
            ref = body.get('source_ref')
            if ref:
                source = (data / ref.removeprefix('outputs/')).resolve()
                if not source.is_relative_to(data):
                    raise RuntimeError('声音素材路径无效')
                body = dict(body, _source_audio=source.read_bytes())
            content = await generate_music(body, stage)
            duration = validate_wav(content)
            ref = f'outputs/users/{owner}/{mid}/{path.name}'
            with db() as con:
                con.execute('BEGIN IMMEDIATE')
                row = con.execute('SELECT cancel_requested FROM music_jobs WHERE id=?', (jid,)).fetchone()
                if not row:
                    return
                if row['cancel_requested']:
                    con.execute("UPDATE music_jobs SET status='cancelled',stage='已放弃此版本' WHERE id=?", (jid,))
                    return
                used = con.execute('SELECT COALESCE(SUM(bytes),0) FROM media WHERE owner=?', (owner,)).fetchone()[0]
                if used + len(content) > quota:
                    raise RuntimeError('存储空间不足，请清理后重新制作')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                con.execute('INSERT INTO media VALUES(?,?,?,?,?,?)', (ref, owner, mid, len(content), 'audio/wav', 'generated'))
                result = {'generated': ref, 'duration': duration, 'provider': music_config()['provider'],
                          'source_ref': body.get('source_ref'), 'generation_mode': 'audio-conditioned' if body.get('_source_audio') and music_config()['provider']=='mureka' else 'text'}
                con.execute("UPDATE music_jobs SET status='done',stage='音乐已生成',result=? WHERE id=?", (json.dumps(result), jid))
        except Exception as error:
            path.unlink(missing_ok=True)
            # No upstream response bodies, tokens or URLs in user-visible errors.
            message = provider_error(error, '音乐服务')
            with db() as con:
                con.execute("UPDATE music_jobs SET status='failed',stage=? WHERE id=?", (message, jid))

    @app.post('/api/music/jobs', status_code=202)
    async def create(request: Request, background: BackgroundTasks):
        user = account(request)
        if not music_config()['enabled']:
            raise HTTPException(503, '音乐生成服务尚未配置，可以先微调原声')
        raw = await request.body()
        if len(raw) > 8000:
            raise HTTPException(413, '生成描述过长')
        try:
            body = json.loads(raw)
        except (ValueError, TypeError):
            raise HTTPException(400, '生成参数无效')
        if not isinstance(body, dict):
            raise HTTPException(400, '生成参数无效')
        mid = body.get('memory_id')
        try:
            body['duration'] = max(30, min(120, float(body.get('duration', 45))))
        except (TypeError, ValueError):
            raise HTTPException(400, '时长无效')
        jid = uuid.uuid4().hex
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            record = con.execute("SELECT payload FROM records WHERE id=? AND owner=? AND kind='memory'", (mid, user['id'])).fetchone()
            if not record:
                raise HTTPException(404, '声音素材不存在')
            ref = body.get('source_ref') or json.loads(record['payload'])['audio']
            if not isinstance(ref, str) or not con.execute("SELECT 1 FROM media WHERE ref=? AND owner=? AND record_id=? AND mime='audio/wav'", (ref,user['id'],mid)).fetchone():
                raise HTTPException(404, '所选声音素材不存在或无权使用')
            body['source_ref'] = ref
            body.pop('_source_audio', None)
            if con.execute("SELECT 1 FROM music_jobs WHERE owner=? AND status IN ('queued','running')", (user['id'],)).fetchone():
                raise HTTPException(409, '上一首音乐仍在制作，请稍候')
            limit = int(os.getenv('SOUNDTRACE_MUSIC_DAILY_LIMIT', '5'))
            count = con.execute('SELECT COUNT(*) FROM music_jobs WHERE owner=? AND created>?', (user['id'], time.time()-86400)).fetchone()[0]
            if count >= limit:
                raise HTTPException(429, '已达到今日音乐制作次数上限')
            con.execute('INSERT INTO music_jobs(id,owner,memory_id,status,stage,payload,created) VALUES(?,?,?,?,?,?,?)',
                        (jid, user['id'], mid, 'queued', '正在排队', json.dumps(body, ensure_ascii=False), time.time()))
        background.add_task(work, jid, user['id'], mid, body)
        return {'job_id': jid}

    @app.get('/api/music/jobs/{jid}')
    def read(jid: str, request: Request):
        user = account(request)
        with db() as con:
            row = con.execute('SELECT * FROM music_jobs WHERE id=? AND owner=?', (jid, user['id'])).fetchone()
        if not row:
            raise HTTPException(404)
        return {'job_id': jid, 'status': row['status'], 'stage': row['stage'],
                'results': json.loads(row['result']) if row['status'] == 'done' else None}

    @app.post('/api/music/jobs/{jid}/cancel')
    def cancel(jid: str, request: Request):
        user = account(request)
        with db() as con:
            count = con.execute('UPDATE music_jobs SET cancel_requested=1 WHERE id=? AND owner=?', (jid, user['id'])).rowcount
        if not count:
            raise HTTPException(404)
        return {'ok': True, 'detail': '已停止等待；上游已开始的生成可能继续运行和计费'}
