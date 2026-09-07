#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import runtime_backend

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080
DEFAULT_ALLOWED_ORIGINS = "https://saratchai1.github.io"
DEFAULT_MAX_CONCURRENT_JOBS = 2
PDF_CONTENT_TYPES = {"application/pdf", "application/octet-stream"}
_FILENAME_RX = re.compile(r"[^A-Za-z0-9._()\- ]+")


def _allowed_origins() -> set[str]:
    raw = os.environ.get("BOQ_ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
    return {value.strip().rstrip("/") for value in raw.split(",") if value.strip()}


def _safe_filename(raw: str | None) -> str:
    name = Path(str(raw or "uploaded.pdf")).name.strip() or "uploaded.pdf"
    name = _FILENAME_RX.sub("_", name)[:180]
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class AutoBoqServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], handler_cls: type[BaseHTTPRequestHandler]):
        super().__init__(server_address, handler_cls)
        max_jobs = int(os.environ.get("BOQ_MAX_CONCURRENT_JOBS", DEFAULT_MAX_CONCURRENT_JOBS))
        self.job_slots = threading.BoundedSemaphore(max(1, max_jobs))
        self.allowed_origins = _allowed_origins()


class AutoBoqHandler(BaseHTTPRequestHandler):
    server: AutoBoqServer
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"AUTO_BOQ_HTTP {self.address_string()} {fmt % args}", flush=True)

    def _origin(self) -> str:
        return str(self.headers.get("Origin") or "").rstrip("/")

    def _origin_allowed(self) -> bool:
        origin = self._origin()
        return not origin or origin in self.server.allowed_origins

    def _send_json(self, status: int, payload: Any, *, cors: bool = True) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cors:
            origin = self._origin()
            if origin and origin in self.server.allowed_origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def _reject_origin(self) -> bool:
        if self._origin_allowed():
            return False
        self._send_json(
            HTTPStatus.FORBIDDEN,
            {"status": "error", "error": "origin_not_allowed"},
            cors=False,
        )
        return True

    def do_OPTIONS(self) -> None:  # noqa: N802
        if self.path != "/api/auto-boq":
            self._send_json(HTTPStatus.NOT_FOUND, {"status": "error", "error": "not_found"})
            return
        if self._reject_origin():
            return
        origin = self._origin()
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-File-Name")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self._send_json(HTTPStatus.NOT_FOUND, {"status": "error", "error": "not_found"})
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "status": "ok",
                "service": "blender3d-auto-boq",
                "engine": "v8.19-profile+generic-vector-v0",
                "registered_profiles": len(runtime_backend.PROFILE_REGISTRY),
                "generic_inference": "vector-sanitary-v0",
                "max_upload_bytes": runtime_backend.MAX_UPLOAD_BYTES,
                "fail_closed_unknown_profiles": True,
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/auto-boq":
            self._send_json(HTTPStatus.NOT_FOUND, {"status": "error", "error": "not_found"})
            return
        if self._reject_origin():
            return

        content_type = str(self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type not in PDF_CONTENT_TYPES:
            self._send_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                {"status": "error", "error": "content_type_must_be_application_pdf"},
            )
            return

        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            self._send_json(HTTPStatus.LENGTH_REQUIRED, {"status": "error", "error": "content_length_required"})
            return
        try:
            content_length = int(raw_length)
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"status": "error", "error": "invalid_content_length"})
            return
        if content_length <= 0:
            self._send_json(HTTPStatus.BAD_REQUEST, {"status": "error", "error": "empty_pdf_upload"})
            return
        if content_length > runtime_backend.MAX_UPLOAD_BYTES:
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {
                    "status": "error",
                    "error": "pdf_too_large",
                    "max_upload_bytes": runtime_backend.MAX_UPLOAD_BYTES,
                },
            )
            return

        if not self.server.job_slots.acquire(blocking=False):
            self._send_json(
                HTTPStatus.TOO_MANY_REQUESTS,
                {"status": "error", "error": "server_busy", "retryable": True},
            )
            return

        try:
            body = self.rfile.read(content_length)
            if len(body) != content_length:
                self._send_json(HTTPStatus.BAD_REQUEST, {"status": "error", "error": "incomplete_request_body"})
                return
            if not body.startswith(b"%PDF-"):
                self._send_json(HTTPStatus.BAD_REQUEST, {"status": "error", "error": "invalid_pdf_signature"})
                return

            filename = _safe_filename(self.headers.get("X-File-Name"))
            with tempfile.TemporaryDirectory(prefix="auto-boq-") as tmp:
                path = Path(tmp) / filename
                path.write_bytes(body)
                try:
                    result = runtime_backend.run_registered_pdf(path)
                except ValueError as exc:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"status": "error", "error": str(exc)})
                    return
                except Exception as exc:
                    self.log_error("runtime failure: %s", exc)
                    self._send_json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {"status": "error", "error": "automatic_boq_runtime_failed"},
                    )
                    return

            self._send_json(HTTPStatus.OK, result)
        finally:
            self.server.job_slots.release()


def create_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> AutoBoqServer:
    return AutoBoqServer((host, port), AutoBoqHandler)


def main() -> None:
    host = os.environ.get("HOST", DEFAULT_HOST)
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    server = create_server(host, port)
    print(
        "AUTO_BOQ_HTTP_READY",
        json.dumps(
            {
                "host": host,
                "port": server.server_port,
                "allowed_origins": sorted(server.allowed_origins),
                "max_upload_bytes": runtime_backend.MAX_UPLOAD_BYTES,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
