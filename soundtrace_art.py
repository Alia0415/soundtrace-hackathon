"""Private photo-to-illustration jobs using the domestic Seedream image API."""
import asyncio
import base64
import json
import os
import time
import uuid

import httpx
from fastapi import BackgroundTasks, HTTPException, Request


def art_config():
    return {'enabled': bool(os.getenv('SOUNDTRACE_ARK_KEY')),
            'provider': 'seedream', 'model': os.getenv('SOUNDTRACE_IMAGE_MODEL', 'doubao-seedream-5-0-pro-260628')}


def make_prompt(memory):
    # Coordinates and location names are deliberately excluded from the model request.
    context = '；'.join(str(memory.get(k) or '')[:160] for k in ('title', 'notes', 'weather', 'mood', 'activity'))
    return ('将参考照片转为声迹的手绘风景插画。必须保留照片中的真实建筑、地貌、物体位置和拍摄视角，'
            '不添加照片中不存在的地标，不改变人物身份。白色纸张质感，灵动自然的黑色手绘线条，'
            '少量天蓝色与暖黄色点缀，清爽留白，简洁、温柔。画面完整呈现参考照片的景物，'
            '主体位于中央安全区域，适合横竖屏裁切。输出一张完整风景画，不画界面、按钮、卡片、'
            '相框、唱片、磁带或文字标签，不拼图。以下仅为情境描述：' + context)


async def generate_art(photo, memory):
    """One reference image, one output; private photos never need public URLs."""
    payload = {'model': art_config()['model'], 'prompt': make_prompt(memory),
               'image': 'data:image/jpeg;base64,' + base64.b64encode(photo).decode(),
               'size': '2K', 'response_format': 'b64_json', 'watermark': True,
               'stream': False}
    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10), follow_redirects=False) as client:
        async with client.stream('POST', 'https://ark.cn-beijing.volces.com/api/v3/images/generations',
                                 headers={'Authorization': 'Bearer ' + os.environ['SOUNDTRACE_ARK_KEY']}, json=payload) as response:
            response.raise_for_status()
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) > 32_000_000:
                    raise RuntimeError('生成图片过大，已保留原照片')
    result = json.loads(chunks)
    outputs = result.get('data', [])
    if len(outputs) != 1 or not isinstance(outputs[0].get('b64_json'), str):
        raise RuntimeError('生图服务未返回单张图片，已保留原照片')
    try:
        content = base64.b64decode(outputs[0]['b64_json'], validate=True)
    except (ValueError, TypeError):
        raise RuntimeError('生图服务返回的图片无效，已保留原照片')
    if not content or len(content) > 20_000_000:
        raise RuntimeError('生图服务返回的图片无效，已保留原照片')
    return content


def install_art(app, db, account, data, quota, normalize_image, cover):
    with db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS art_jobs(
          id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          memory_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
          source TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
          result TEXT, created REAL NOT NULL)''')
        con.execute("UPDATE art_jobs SET status='failed',stage='服务重启中断了生成；原照片已保留，请确认上游计费后再重试' WHERE status IN ('queued','running')")

    def own_memory(con, mid, owner):
        row = con.execute("SELECT payload FROM records WHERE id=? AND owner=? AND kind='memory'", (mid, owner)).fetchone()
        if not row:
            raise HTTPException(404, '记忆不存在或无权访问')
        return json.loads(row['payload'])

    def photo_ref(con, memory, owner, index):
        if type(index) is not int or index < 0 or index >= len(memory.get('images', [])):
            raise HTTPException(400, '请选择这段记忆中的照片')
        ref = memory['images'][index]
        if not con.execute('SELECT 1 FROM media WHERE ref=? AND owner=? AND record_id=?', (ref, owner, memory['id'])).fetchone():
            raise HTTPException(404, '参考照片不存在')
        return ref

    async def work(jid, owner, mid, source, memory):
        folder = data / 'users' / owner / mid / ('art-' + jid)
        try:
            with db() as con:
                if not con.execute('SELECT 1 FROM art_jobs WHERE id=?', (jid,)).fetchone():
                    return
                con.execute("UPDATE art_jobs SET status='running',stage='正在根据原照片绘制' WHERE id=?", (jid,))
            photo = (data / source.removeprefix('outputs/')).read_bytes()
            content = await generate_art(photo, memory)
            content = await asyncio.to_thread(normalize_image, content, 2400)
            with db() as con:
                con.execute('BEGIN IMMEDIATE')
                row = con.execute('SELECT * FROM art_jobs WHERE id=?', (jid,)).fetchone()
                if not row:
                    return
                current = own_memory(con, mid, owner)
                folder.mkdir(parents=True, exist_ok=True)
                scenery = folder / 'scenery.jpg'
                scenery.write_bytes(content)
                files = [scenery]
                # Existing server cover formatter applies this genuine model artwork to both sleeves.
                for kind in ('tape', 'vinyl'):
                    files.append(cover(folder, current['title'], scenery, kind))
                used = con.execute('SELECT COALESCE(SUM(bytes),0) FROM media WHERE owner=?', (owner,)).fetchone()[0]
                if used + sum(f.stat().st_size for f in files) > quota:
                    raise RuntimeError('存储空间不足，原照片与记忆已保留')
                refs = []
                for file in files:
                    ref = 'outputs/' + file.relative_to(data).as_posix()
                    refs.append(ref)
                    con.execute('INSERT INTO media VALUES(?,?,?,?,?,?)',
                                (ref, owner, mid, file.stat().st_size, 'image/jpeg', 'generated-art'))
                current.update(scene_art=refs[0], scene_art_source=source, art_status='stylized',
                               art_model=art_config()['model'], art_provider='seedream')
                # A user may switch back to photo while a job is running; preserve that choice.
                if current.get('background_mode') == 'stylized' and current.get('background_source') == source:
                    current.update(cover_tape=refs[1], cover_vinyl=refs[2])
                con.execute('UPDATE records SET payload=? WHERE id=? AND owner=?',
                            (json.dumps(current, ensure_ascii=False), mid, owner))
                con.execute("UPDATE art_jobs SET status='done',stage='手绘已生成',result=? WHERE id=?",
                            (json.dumps({'scene_art': refs[0], 'cover_tape': refs[1], 'cover_vinyl': refs[2]}), jid))
        except Exception as error:
            # Remove only the exact files in this job folder, never a recursive computed target.
            for name in ('scenery.jpg', 'cover_tape.jpg', 'cover_vinyl.jpg'):
                (folder / name).unlink(missing_ok=True)
            message = str(error) if isinstance(error, RuntimeError) else '生图服务暂时不可用，请检查凭据、模型权限或额度；原照片已保留'
            with db() as con:
                con.execute("UPDATE art_jobs SET status='failed',stage=? WHERE id=?", (message, jid))

    @app.get('/api/art/config')
    def config():
        return art_config()

    @app.post('/api/art/jobs', status_code=202)
    async def create(request: Request, background: BackgroundTasks):
        user = account(request)
        raw = await request.body()
        if len(raw) > 4000:
            raise HTTPException(413, '参数过长')
        try:
            body = json.loads(raw)
        except (ValueError, TypeError):
            raise HTTPException(400, '参数无效')
        if not isinstance(body, dict) or not isinstance(body.get('memory_id'), str):
            raise HTTPException(400, '请选择记忆')
        mid = body['memory_id']
        jid = uuid.uuid4().hex
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            memory = own_memory(con, mid, user['id'])
            source = photo_ref(con, memory, user['id'], body.get('image_index', 0))
            if body.get('consent') is not True:
                raise HTTPException(400, '请确认将这张照片发送给生图服务')
            if not art_config()['enabled']:
                raise HTTPException(503, '手绘生成服务尚未配置，当前使用原照片')
            if con.execute("SELECT 1 FROM art_jobs WHERE owner=? AND status IN ('queued','running')", (user['id'],)).fetchone():
                raise HTTPException(409, '上一张手绘仍在生成，请稍候')
            count = con.execute('SELECT COUNT(*) FROM art_jobs WHERE owner=? AND created>?', (user['id'], time.time()-86400)).fetchone()[0]
            if count >= int(os.getenv('SOUNDTRACE_IMAGE_DAILY_LIMIT', '5')):
                raise HTTPException(429, '已达到今日手绘生成次数上限')
            used = con.execute('SELECT COALESCE(SUM(bytes),0) FROM media WHERE owner=?', (user['id'],)).fetchone()[0]
            if used + 4_000_000 > quota:
                raise HTTPException(413, '可用存储空间不足，请清理后再生成')
            con.execute('INSERT INTO art_jobs VALUES(?,?,?,?,?,?,?,?)',
                        (jid, user['id'], mid, source, 'queued', '正在排队', None, time.time()))
            memory.update(scene_art_job=jid, background_mode='stylized', background_source=source)
            con.execute('UPDATE records SET payload=? WHERE id=?', (json.dumps(memory, ensure_ascii=False), mid))
        background.add_task(work, jid, user['id'], mid, source, memory)
        return {'job_id': jid}

    @app.get('/api/art/jobs/{jid}')
    def read(jid: str, request: Request):
        user = account(request)
        with db() as con:
            row = con.execute('SELECT * FROM art_jobs WHERE id=? AND owner=?', (jid, user['id'])).fetchone()
        if not row:
            raise HTTPException(404)
        return {'job_id': jid, 'status': row['status'], 'stage': row['stage'],
                'results': json.loads(row['result']) if row['status'] == 'done' else None}

    @app.post('/api/memories/{mid}/background')
    async def background_choice(mid: str, request: Request):
        user = account(request)
        raw = await request.body()
        if len(raw) > 4000:
            raise HTTPException(413, '参数过长')
        try:
            body = json.loads(raw)
        except ValueError:
            raise HTTPException(400, '参数无效')
        if not isinstance(body, dict) or body.get('mode') not in ('photo', 'stylized'):
            raise HTTPException(400, '背景选项无效')
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            memory = own_memory(con, mid, user['id'])
            source = photo_ref(con, memory, user['id'], body.get('image_index', 0))
            if body['mode'] == 'stylized' and (not memory.get('scene_art') or memory.get('scene_art_source') != source):
                raise HTTPException(409, '请先为这张照片生成手绘')
            memory.update(background_mode=body['mode'], background_source=source)
            con.execute('UPDATE records SET payload=? WHERE id=? AND owner=?', (json.dumps(memory, ensure_ascii=False), mid, user['id']))
        return memory
