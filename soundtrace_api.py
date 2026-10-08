"""Minimal HTTP/job boundary for the SoundTrace audio pipeline."""
from __future__ import annotations
import argparse, json, queue, shutil, threading, time, uuid
from dataclasses import asdict, dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse
from soundtrace_mvp import ROOT, make_demo_inputs, run
JOB_OUTPUTS = ROOT / "outputs" / "jobs"

@dataclass
class Job:
    id: str
    status: str = "queued"
    target: str = "birds"
    duration: float = 42
    created_at: float = field(default_factory=time.time)
    result: dict[str, Any] | None = None
    error: str | None = None

class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
    def create(self, target: str, duration: float) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], target=target, duration=duration)
        with self._lock: self._jobs[job.id] = job
        return job
    def get(self, job_id: str) -> Job | None:
        with self._lock: return self._jobs.get(job_id)

class DemoWorker:
    """Single worker avoids collisions in the MVP pipeline's shared output folder."""
    def __init__(self, store: JobStore) -> None:
        self.store = store
        self.pending: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._loop, daemon=True, name="soundtrace-worker").start()
    def submit(self, job: Job) -> None: self.pending.put(job.id)
    def _loop(self) -> None:
        while True:
            job_id = self.pending.get()
            job = self.store.get(job_id)
            if job is None:
                self.pending.task_done()
                continue
            job.status = "processing"
            try:
                environment, hum = make_demo_inputs()
                result = run(environment, hum, job.target, job.duration)
                destination = JOB_OUTPUTS / job.id
                destination.mkdir(parents=True, exist_ok=True)
                copied: dict[str, str] = {}
                for name, relative in result["outputs"].items():
                    source = ROOT / relative
                    target = destination / source.name
                    shutil.copy2(source, target)
                    copied[name] = str(target.relative_to(ROOT)).replace("\\", "/")
                result["outputs"] = copied
                job.result, job.status = result, "succeeded"
            except Exception as exc:
                job.error, job.status = f"{type(exc).__name__}: {exc}", "failed"
            finally: self.pending.task_done()

STORE = JobStore()
WORKER = DemoWorker(STORE)

class Handler(BaseHTTPRequestHandler):
    server_version = "SoundTrace/0.1"
    def _json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._json(HTTPStatus.OK, {"status": "ok", "service": "soundtrace"})
        elif path.startswith("/v1/jobs/"):
            job = STORE.get(path.rsplit("/", 1)[-1])
            self._json(HTTPStatus.OK, asdict(job)) if job else self._json(HTTPStatus.NOT_FOUND, {"error": "job_not_found"})
        else: self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
    def do_POST(self) -> None:
        if urlparse(self.path).path != "/v1/demo-jobs":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(size) or b"{}")
            duration = float(body.get("duration", 42))
            target = str(body.get("target", "birds")).strip()[:120] or "birds"
            if not 30 <= duration <= 60: raise ValueError("duration must be between 30 and 60 seconds")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request", "detail": str(exc)})
            return
        job = STORE.create(target, duration)
        WORKER.submit(job)
        self._json(HTTPStatus.ACCEPTED, asdict(job))
    def log_message(self, format: str, *args: Any) -> None:
        print(f"[api] {self.address_string()} {format % args}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SoundTrace MVP API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"SoundTrace API listening on http://{args.host}:{args.port}")
    server.serve_forever()

if __name__ == "__main__": main()
