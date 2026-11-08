"""URA Data Service: Singapore private residential transactions and rental contracts.

Needs a personal URA access key (free registration at eservice.ura.gov.sg/maps/api/).
The key is either injected by the environment's network proxy (network secret on host
eservice.ura.gov.sg, header AccessKey) or read from the URA_ACCESS_KEY environment
variable. It is never written to disk or to the manifest.

- Transactions (PMI_Resi_Transaction): past 5 years, 4 batches by postal district.
- Rental contracts (PMI_Resi_Rental): one call per quarter (refPeriod "yyqq"), past 5 years.
Locations are the project's SVY21 x/y, not the unit's.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import date

from src.config import RAW
from src.ingest.http import UA, record

BASE = "https://eservice.ura.gov.sg/uraDataService"
OUT = RAW / "singapore" / "ura"


def _get(url: str, headers: dict[str, str]) -> dict:
    cmd = ["curl", "-sS", "-L", "--compressed", "--fail", "-m", "300", "-A", UA, url]
    for k, v in headers.items():
        cmd += ["-H", f"{k}: {v}"]
    p = subprocess.run(cmd, capture_output=True, check=True)
    try:
        text = p.stdout.decode("utf-8")
    except UnicodeDecodeError:  # some project names are served in Windows-1252
        text = p.stdout.decode("cp1252")
    return json.loads(text)


def _key_header() -> dict[str, str]:
    key = os.environ.get("URA_ACCESS_KEY")
    # Without the variable, the proxy injects the network secret into this header.
    return {"AccessKey": key or "injected-by-proxy"}


def token() -> str:
    d = _get(f"{BASE}/insertNewToken/v1", _key_header())
    if d.get("Status") != "Success" or not d.get("Result"):
        raise RuntimeError(f"URA token refused: {d.get('Message')}")
    return d["Result"]


def quarters(today: date | None = None, years: int = 5) -> list[str]:
    today = today or date.today()
    q = (today.month - 1) // 3 + 1
    y = today.year
    out = []
    for _ in range(4 * years):
        out.append(f"{y % 100:02d}q{q}")
        q -= 1
        if q == 0:
            q, y = 4, y - 1
    return sorted(out)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    h = _key_header() | {"Token": token()}
    for b in (1, 2, 3, 4):
        url = f"{BASE}/invokeUraDS/v1?service=PMI_Resi_Transaction&batch={b}"
        if (OUT / f"transactions_batch{b}.json").exists():
            continue
        d = _get(url, h)
        if d.get("Status") != "Success":
            raise RuntimeError(f"transactions batch {b}: {d.get('Message')}")
        f = OUT / f"transactions_batch{b}.json"
        f.write_text(json.dumps(d["Result"]))
        record(f, url, f"{sum(len(p.get('transaction', [])) for p in d['Result'])} transactions")
    for rp in quarters():
        url = f"{BASE}/invokeUraDS/v1?service=PMI_Resi_Rental&refPeriod={rp}"
        if (OUT / f"rental_{rp}.json").exists():
            continue
        d = _get(url, h)
        if d.get("Status") != "Success":
            print("rental", rp, d.get("Message"))
            continue
        f = OUT / f"rental_{rp}.json"
        f.write_text(json.dumps(d["Result"]))
        record(f, url, f"{sum(len(p.get('rental', [])) for p in d['Result'])} rental contracts")


if __name__ == "__main__":
    main()
