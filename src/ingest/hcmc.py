"""Ho Chi Minh City land price table (Resolution 87/2025/NQ-HĐND, in force 1 Jan 2026),
downloaded from the city's Official Gazette (Công báo TP.HCM), whose electronic edition
"has the value of the original". The annexes (street-segment land prices by ward) are
spread over many gazette issues; each issue's share is a separate signed PDF.

The gazette's firewall blocks bursts of requests, so requests are spaced (10-15 s) and a
blocked response triggers one 5-minute pause, then the script stops.
"""
from __future__ import annotations

import json
import re
import subprocess
import time

from src.config import RAW
from src.ingest.http import record

BASE = "https://congbao.hochiminhcity.gov.vn"
DOC = "/cong-bao/van-ban/nghi-quyet/so/87-2025-nq-hdnd/ngay/26-12-2025"
OUT = RAW / "hcmc"
UA = "Mozilla/5.0 (X11; Linux x86_64) academic-research"
BLOCKED = b"This page can't be displaye"


def _get(path: str, dest=None, pause: float = 10.0) -> bytes:
    for attempt in range(2):
        time.sleep(pause)
        p = subprocess.run(["curl", "-sS", "-L", "-m", "300", "-A", UA, BASE + path], capture_output=True)
        if p.returncode == 0 and BLOCKED not in p.stdout[:2000]:
            if dest:
                dest.write_bytes(p.stdout)
            return p.stdout
        print("blocked or failed, waiting 5 minutes:", path, flush=True)
        time.sleep(300)
    raise RuntimeError(f"gazette refused {path} twice; stopping")


def issues() -> list[str]:
    html = _get("/cong-bao/so/68-69/01-03-2026").decode("utf8", "ignore")
    out = sorted(set(re.findall(r'href="(/cong-bao/so/[0-9+-]+/\d\d-0[1-3]-2026)"', html)))
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    parts_file = OUT / "congbao_parts.json"
    parts = json.loads(parts_file.read_text()) if parts_file.exists() else {}
    if not parts:
        for path in issues():
            html = _get(path).decode("utf8", "ignore")
            for cbid in set(re.findall(r'/noi-dung/48983/(\d+)', html)):
                parts[cbid] = path
            print(path, "->", len(parts), "parts so far", flush=True)
        parts_file.write_text(json.dumps(parts, indent=1))
    for cbid, issue in sorted(parts.items(), key=lambda x: int(x[0])):
        dest = OUT / f"nq87_part_{cbid}.pdf"
        if dest.exists():
            continue
        url = f"{DOC}/tai-ve/48983?cbid={cbid}"
        _get(url, dest, pause=15.0)
        record(dest, BASE + url, f"Resolution 87/2025 annex part, gazette issue {issue}")
        print("downloaded", dest.name, dest.stat().st_size, flush=True)


if __name__ == "__main__":
    main()
