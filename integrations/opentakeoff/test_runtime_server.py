#!/usr/bin/env python3
from __future__ import annotations

import http.client
import json
import os
import threading
from pathlib import Path

import runtime_backend
import runtime_server


def request(server, method: str, path: str, *, body: bytes = b"", headers: dict[str, str] | None = None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        data = response.read()
        payload = json.loads(data.decode("utf-8")) if data else None
        return response.status, dict(response.getheaders()), payload
    finally:
        conn.close()


def main() -> None:
    old_allowed = os.environ.get("BOQ_ALLOWED_ORIGINS")
    os.environ["BOQ_ALLOWED_ORIGINS"] = "https://saratchai1.github.io"
    server = runtime_server.create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original_run = runtime_backend.run_registered_pdf
    try:
        status, headers, payload = request(server, "GET", "/health")
        assert status == 200, (status, payload)
        assert payload["status"] == "ok"
        assert payload["engine"] == "v8.19-profile-gated"
        assert payload["registered_profiles"] >= 1
        assert payload["fail_closed_unknown_profiles"] is True
        assert int(headers["Content-Length"]) > 0
        assert headers["Cache-Control"] == "no-store"

        status, headers, payload = request(
            server,
            "OPTIONS",
            "/api/auto-boq",
            headers={"Origin": "https://saratchai1.github.io"},
        )
        assert status == 204, (status, payload)
        assert headers["Access-Control-Allow-Origin"] == "https://saratchai1.github.io"
        assert "POST" in headers["Access-Control-Allow-Methods"]
        assert "X-File-Name" in headers["Access-Control-Allow-Headers"]

        status, headers, payload = request(
            server,
            "OPTIONS",
            "/api/auto-boq",
            headers={"Origin": "https://evil.example"},
        )
        assert status == 403, (status, payload)
        assert "Access-Control-Allow-Origin" not in headers
        assert payload["error"] == "origin_not_allowed"

        status, _, payload = request(
            server,
            "POST",
            "/api/auto-boq",
            body=b"not a pdf",
            headers={"Content-Type": "text/plain", "Origin": "https://saratchai1.github.io"},
        )
        assert status == 415, (status, payload)

        status, _, payload = request(
            server,
            "POST",
            "/api/auto-boq",
            body=b"not a pdf",
            headers={"Content-Type": "application/pdf", "Origin": "https://saratchai1.github.io"},
        )
        assert status == 400, (status, payload)
        assert payload["error"] == "invalid_pdf_signature"

        seen: dict[str, object] = {}

        def fake_run(path: Path):
            seen["name"] = path.name
            seen["bytes"] = path.read_bytes()
            return {
                "schema": "blender3d.auto_boq.runtime.v1",
                "runtime_status": "PUBLISHED_VALIDATED_PROFILE_BOQ",
                "rows": [{"id": "TEST", "quantity": 1, "unit": "ea"}],
                "source_policy": {"reference_used_for_generation": False},
            }

        runtime_backend.run_registered_pdf = fake_run
        fake_pdf = b"%PDF-1.7\n% runtime server test\n"
        status, headers, payload = request(
            server,
            "POST",
            "/api/auto-boq",
            body=fake_pdf,
            headers={
                "Content-Type": "application/pdf",
                "X-File-Name": "../unsafe name?.pdf",
                "Origin": "https://saratchai1.github.io",
            },
        )
        assert status == 200, (status, payload)
        assert payload["runtime_status"] == "PUBLISHED_VALIDATED_PROFILE_BOQ"
        assert payload["source_policy"]["reference_used_for_generation"] is False
        assert headers["Access-Control-Allow-Origin"] == "https://saratchai1.github.io"
        assert seen["bytes"] == fake_pdf
        assert ".." not in str(seen["name"])
        assert str(seen["name"]).endswith(".pdf")

        runtime_backend.run_registered_pdf = original_run
        with __import__("tempfile").TemporaryDirectory() as tmp:
            unknown = Path(tmp) / "unknown.pdf"
            unknown.write_bytes(b"%PDF-1.4\n% deliberately unregistered\n")
            direct = runtime_backend.run_registered_pdf(unknown)
            assert direct["runtime_status"] == "WITHHELD_UNREGISTERED_DRAWING_PROFILE"
            assert direct["rows"] == []
            assert direct["source_policy"]["reference_used_for_generation"] is False

        print("AUTO_BOQ_RUNTIME_SERVER_TEST_PASS")
    finally:
        runtime_backend.run_registered_pdf = original_run
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        if old_allowed is None:
            os.environ.pop("BOQ_ALLOWED_ORIGINS", None)
        else:
            os.environ["BOQ_ALLOWED_ORIGINS"] = old_allowed


if __name__ == "__main__":
    main()
