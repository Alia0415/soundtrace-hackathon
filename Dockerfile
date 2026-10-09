FROM node:22-bookworm-slim AS frontend
WORKDIR /build/studio
COPY studio/package.json studio/package-lock.json ./
RUN npm ci
COPY studio/src ./src
COPY studio/vite.config.js ./
RUN npm run build

FROM python:3.12-slim AS source_archive
WORKDIR /source
COPY . .
RUN python tools/package_public.py

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SOUNDTRACE_DATA_DIR=/data
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home soundtrace \
    && mkdir /data && chown soundtrace:soundtrace /data
COPY requirements-public.txt ./
RUN pip install --no-cache-dir -r requirements-public.txt
COPY soundtrace_public.py soundtrace_storage.py soundtrace_music.py soundtrace_maps.py soundtrace_art.py soundtrace_processing.py soundtrace_network.py soundtrace_uploads.py soundtrace_media.py ./
COPY webapp ./webapp
COPY --from=frontend /build/webapp/assets/studio ./webapp/assets/studio
COPY third_party/Mineradio-paused-main/public ./third_party/Mineradio-paused-main/public
COPY outputs/seeds ./outputs/seeds
COPY tools/backup_public.py ./tools/backup_public.py
COPY --from=source_archive /source/runtime/releases/soundtrace-public.zip ./public-source.zip
COPY third_party/Mineradio-paused-main/LICENSE third_party/Mineradio-paused-main/NOTICE.md ./third_party/Mineradio-paused-main/
USER soundtrace
EXPOSE 8080
CMD ["uvicorn", "soundtrace_public:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
