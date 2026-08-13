from __future__ import annotations

import json
import mimetypes
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from typing import Any
from urllib.parse import unquote

from .engine import execute_action, scan_images


@dataclass
class Job:
    id: str
    action: str
    status: str = "queued"
    logs: list[str] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def log(self, message: str) -> None:
        self.logs.append(message)
        self.updated_at = time.time()


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, action: str) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], action=action)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def snapshot(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return _job_payload(job)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)
            return [_job_payload(job) for job in jobs]


JOBS = JobStore()


def serve_ui(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> None:
    server = ThreadingHTTPServer((host, port), TihuluHandler)
    url = f"http://{host}:{server.server_port}"
    print(f"Tihulu UI running at {url}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping Tihulu UI.")
    finally:
        server.server_close()


class TihuluHandler(BaseHTTPRequestHandler):
    server_version = "TihuluUI/0.1"

    def do_GET(self) -> None:
        path = unquote(self.path.split("?", 1)[0])
        if path in {"/", "/index.html"}:
            self._send_resource("index.html")
            return
        if path in {"/style.css", "/app.js"}:
            self._send_resource(path.removeprefix("/"))
            return
        if path == "/api/jobs":
            self._send_json({"jobs": JOBS.list()})
            return
        if path.startswith("/api/jobs/"):
            job_id = path.rsplit("/", 1)[-1]
            payload = JOBS.snapshot(job_id)
            if payload is None:
                self._send_json({"error": "Job not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(payload)
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = unquote(self.path.split("?", 1)[0])
        try:
            payload = self._read_json()
        except ValueError as error:
            self._send_json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return

        if path == "/api/scan":
            self._handle_scan(payload)
            return
        if path == "/api/run":
            self._handle_run(payload)
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _handle_scan(self, payload: dict[str, Any]) -> None:
        self._send_json(scan_images(payload))

    def _handle_run(self, payload: dict[str, Any]) -> None:
        action = str(payload.get("action", "run"))
        job = JOBS.create(action=action)
        thread = threading.Thread(target=_run_job, args=(job, payload), daemon=True)
        thread.start()
        self._send_json({"job_id": job.id, "job": _job_payload(job)}, status=HTTPStatus.ACCEPTED)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("Invalid JSON payload") from error
        if not isinstance(payload, dict):
            raise ValueError("JSON payload must be an object")
        return payload

    def _send_resource(self, name: str) -> None:
        content = resources.files("tihulu_star_trail.web").joinpath(name).read_bytes()
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _run_job(job: Job, payload: dict[str, Any]) -> None:
    job.status = "running"
    job.log("Job started")
    try:
        result = execute_action(payload, progress=job.log)
    except Exception as error:
        job.status = "failed"
        job.error = str(error)
        job.log(f"Failed: {error}")
    else:
        job.status = "completed"
        job.result = result
        job.log("Job completed")
    finally:
        job.updated_at = time.time()


def _job_payload(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "action": job.action,
        "status": job.status,
        "logs": list(job.logs[-250:]),
        "result": job.result,
        "error": job.error,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def _optional_max_side(value: int) -> int | None:
    return None if value <= 0 else value
