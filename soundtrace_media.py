"""Bounded media conversion and credential-free provider downloads."""
import ipaddress
import os
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

FORMATS = {'.wav':'wav', '.mp3':'mp3', '.m4a':'mov', '.mp4':'mov', '.mov':'mov',
           '.webm':'matroska', '.mkv':'matroska', '.ogg':'ogg', '.flac':'flac'}


def ffmpeg():
    program = os.getenv('SOUNDTRACE_FFMPEG') or shutil.which('ffmpeg')
    if not program:
        raise RuntimeError('服务器尚未安装音视频转换组件，请部署包含 FFmpeg 的版本')
    return program


def convert(content, suffix='.wav', mp3=False):
    fmt = FORMATS.get(suffix.lower())
    if not fmt or not content or len(content) > 60_000_000:
        raise RuntimeError('请选择不超过 60 MB 的音频或视频文件')
    with tempfile.TemporaryDirectory(prefix='soundtrace-media-') as tmp:
        source, target = Path(tmp)/('input'+suffix.lower()), Path(tmp)/('audio.mp3' if mp3 else 'audio.wav')
        source.write_bytes(content)
        command = [ffmpeg(), '-nostdin', '-y', '-v', 'error', '-protocol_whitelist', 'file,pipe',
                   '-f', fmt, '-i', str(source), '-map', '0:a:0', '-vn', '-t', '301',
                   '-threads', '1', '-ac', '2', '-ar', '44100']
        command += ['-c:a', 'libmp3lame', '-b:a', '160k'] if mp3 else ['-c:a', 'pcm_s16le']
        try:
            result = subprocess.run(command+[str(target)], capture_output=True, timeout=90)
        except subprocess.TimeoutExpired:
            raise RuntimeError('音频提取超时，请截取较短的片段后重试')
        if result.returncode or not target.exists():
            raise RuntimeError('无法提取声音；请确认文件未损坏且视频包含音轨')
        return target.read_bytes()


async def download_public(client, url, limit=60_000_000):
    target = urlsplit(url)
    if target.scheme != 'https' or not target.hostname or target.username or target.password or target.port not in (None,443):
        raise RuntimeError('音频服务返回了无效下载地址')
    import asyncio
    addresses = await asyncio.to_thread(socket.getaddrinfo, target.hostname, 443)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise RuntimeError('音频服务下载地址无法验证')
    content = bytearray()
    # The client must have no default Authorization header or auth handler.
    async with client.stream('GET', url) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            content.extend(chunk)
            if len(content) > limit:
                raise RuntimeError('音频服务返回的文件过大')
    return bytes(content)
