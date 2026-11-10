"""Downloads with retries and a provenance manifest.

Every file written under data/raw is recorded in data/raw/MANIFEST.csv with its
source URL, retrieval time (UTC), size and SHA-256, so that each number in the
project can be traced back to a file and a URL.
"""
from __future__ import annotations

import csv
import fcntl
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from src.config import RAW

MANIFEST = RAW / "MANIFEST.csv"
UA = "housing-fundamentals-research/1.0 (academic, non-commercial)"


def fetch_bytes(url: str, retries: int = 15, timeout: int = 180) -> bytes:
    """GET a URL with curl (more robust than urllib against the frequent connection resets
    seen on some open-data portals), retrying with linear back-off."""
    last = ""
    for k in range(retries):
        p = subprocess.run(
            ["curl", "-sS", "-L", "--compressed", "--fail", "-m", str(timeout), "-A", UA, url],
            capture_output=True,
        )
        if p.returncode == 0:
            return p.stdout
        last = p.stderr.decode(errors="ignore").strip()
        if "returned error: 429" in last:  # rate limited: wait longer, then try again
            time.sleep(min(30 * (k + 1), 180))
            continue
        if "returned error: 4" in last:  # other 4xx: retrying will not help
            break
        time.sleep(min(2 * (k + 1), 20))
    raise RuntimeError(f"failed after retries: {url}: {last}")


def fetch_json(url: str, **kw):
    return json.loads(fetch_bytes(url, **kw))


def record(path: Path, url: str, note: str = "") -> None:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    with open(RAW / ".manifest.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _write_manifest(path, url, note, h.hexdigest())


def _write_manifest(path: Path, url: str, note: str, sha: str) -> None:
    rows = []
    if MANIFEST.exists():
        with open(MANIFEST, newline="") as fh:
            rows = [r for r in csv.DictReader(fh) if r["path"] != str(path.relative_to(RAW))]
    rows.append({
        "path": str(path.relative_to(RAW)),
        "url": url,
        "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bytes": path.stat().st_size,
        "sha256": sha,
        "note": note,
    })
    with open(MANIFEST, "w", newline="") as fh:
        w = csv.DictWriter(fh, ["path", "url", "retrieved_utc", "bytes", "sha256", "note"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["path"]))


def download(url: str, dest: Path, note: str = "", force: bool = False, **kw) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        return dest
    data = fetch_bytes(url, **kw)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(dest)
    record(dest, url, note)
    return dest
