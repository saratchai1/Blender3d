#!/usr/bin/env python3
"""Fetch the byte-identical public Family 4 plan used as the real takeoff benchmark."""
from __future__ import annotations
import argparse
import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path

EXPECTED_SHA256 = "f6db0f85e12113b31a545a5e881a75173938e011908ba1a4491016f77b302175"
EXPECTED_SIZE = 13_058_241
DEFAULT_SOURCES = [
    "https://www.kongkhak.go.th/web/bab/family4.pdf",
]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def valid(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size != EXPECTED_SIZE:
        return False
    with path.open("rb") as f:
        if f.read(5) != b"%PDF-":
            return False
    return digest(path) == EXPECTED_SHA256


def fetch(url: str, dest: Path) -> None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 Blender3d-OpenTakeoff-POC/1.0",
            "Accept": "application/pdf,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as response, dest.open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--url", action="append", default=[])
    args = ap.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if valid(output):
        print(f"FAMILY4_SAMPLE_OK cached {output} sha256={EXPECTED_SHA256}")
        return

    sources = []
    if os.environ.get("FAMILY4_URL"):
        sources.append(os.environ["FAMILY4_URL"])
    sources.extend(args.url)
    sources.extend(DEFAULT_SOURCES)
    errors = []
    for url in dict.fromkeys(sources):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(prefix="family4-", suffix=".pdf", dir=output.parent, delete=False) as tmp:
                tmp_path = Path(tmp.name)
            fetch(url, tmp_path)
            size = tmp_path.stat().st_size
            sha = digest(tmp_path)
            if size != EXPECTED_SIZE or sha != EXPECTED_SHA256:
                raise RuntimeError(f"unexpected bytes size={size} sha256={sha}")
            with tmp_path.open("rb") as f:
                if f.read(5) != b"%PDF-":
                    raise RuntimeError("download is not a PDF")
            tmp_path.replace(output)
            print(f"FAMILY4_SAMPLE_OK {url} -> {output} sha256={sha}")
            return
        except Exception as exc:
            errors.append(f"{url}: {exc}")
            if tmp_path:
                tmp_path.unlink(missing_ok=True)
    raise SystemExit("Could not fetch the verified Family 4 benchmark PDF. " + " | ".join(errors))


if __name__ == "__main__":
    main()
