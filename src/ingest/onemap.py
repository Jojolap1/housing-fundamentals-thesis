"""Geocode HDB blocks (block number + street name) with the OneMap Search API.

A match is accepted only if OneMap returns the same block number and a road name whose
first word equals the first word of the HDB street name (HDB abbreviates, e.g. "AVE" for
"AVENUE"). Results are cached in data/raw/singapore/onemap_blocks.csv, including misses,
so the geocoding hit rate can be reported.
"""
from __future__ import annotations

import csv
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.parse

import pandas as pd

from src.config import RAW
from src.ingest.http import fetch_json, record

OUT = RAW / "singapore" / "onemap_blocks.csv"
URL = ("https://www.onemap.gov.sg/api/common/elastic/search?searchVal={q}"
       "&returnGeom=Y&getAddrDetails=Y&pageNum=1")
FIELDS = ["block", "street_name", "status", "postal", "road_name", "lat", "lon", "searchval"]


# Abbreviations used in HDB street names, expanded to the OneMap spelling.
ABBREV = {
    "AVE": "AVENUE", "BT": "BUKIT", "C'WEALTH": "COMMONWEALTH", "CTRL": "CENTRAL", "CRES": "CRESCENT",
    "DR": "DRIVE", "GDNS": "GARDENS", "HTS": "HEIGHTS", "JLN": "JALAN", "KG": "KAMPONG", "LOR": "LORONG",
    "NTH": "NORTH", "PL": "PLACE", "RD": "ROAD", "ST": "STREET", "STH": "SOUTH", "TG": "TANJONG",
    "TER": "TERRACE", "UPP": "UPPER", "CL": "CLOSE", "CTR": "CENTRE", "PK": "PARK", "SQ": "SQUARE",
    "MKT": "MARKET", "BLVD": "BOULEVARD", "CT": "COURT", "HWY": "HIGHWAY", "WAY": "WAY", "CRS": "CRESCENT",
    "MT": "MOUNT", "GRN": "GREEN", "VW": "VIEW",
}


def normalise(street: str) -> str:
    toks = street.upper().replace(".", "").split()
    out = []
    for i, t in enumerate(toks):
        # "ST" is "SAINT" when it starts the name (e.g. "ST GEORGE'S RD"), "STREET" otherwise.
        out.append("SAINT" if t == "ST" and i == 0 else ABBREV.get(t, t))
    return " ".join(out)


def _match(block: str, street: str, results: list[dict]) -> dict | None:
    """Accept a result only with the same block number and the same street after
    abbreviations are expanded (exact match first, then same first word)."""
    target = normalise(street)
    same_blk = [r for r in results if r.get("BLK_NO", "").upper() == block.upper()]
    for r in same_blk:
        if normalise(r.get("ROAD_NAME", "")) == target:
            return r
    for r in same_blk:
        if normalise(r.get("ROAD_NAME", "")).split()[:1] == target.split()[:1]:
            return r
    return None


WORKERS = 4  # each request takes ~1 s, so 4 workers stay under OneMap's 250 calls/minute


def _query(key: tuple[str, str]) -> dict:
    blk, st = key
    t0 = time.time()
    try:
        res = fetch_json(URL.format(q=urllib.parse.quote(f"{blk} {st}")), timeout=60).get("results", [])
    except Exception:  # keep going; the miss is recorded
        res = []
    m = _match(blk, st, res)
    row = {"block": blk, "street_name": st}
    if m:
        row.update(status="ok", postal=m.get("POSTAL"), road_name=m.get("ROAD_NAME"),
                   lat=m.get("LATITUDE"), lon=m.get("LONGITUDE"), searchval=m.get("SEARCHVAL"))
    else:
        row.update(status="no_match" if res else "no_result")
    time.sleep(max(0.0, 1.0 - (time.time() - t0)))  # at most 1 request per second per worker
    return row


def main() -> None:
    sg = RAW / "singapore"
    srcs = [sg / "hdb_resale_2017on.csv", sg / "hdb_rent_2021on.csv"]
    keys = pd.concat([pd.read_csv(f, usecols=["block", "street_name"], dtype=str)
                      for f in srcs if f.exists()]).drop_duplicates()
    done = set()
    if OUT.exists():
        done = set(map(tuple, pd.read_csv(OUT, dtype=str)[["block", "street_name"]].values))
    todo = [k for k in map(tuple, keys.values) if k not in done]
    print(f"{len(keys)} unique blocks, {len(todo)} to query")
    new = not OUT.exists()
    with open(OUT, "a", newline="") as fh, ThreadPoolExecutor(max_workers=WORKERS) as pool:
        w = csv.DictWriter(fh, FIELDS)
        if new:
            w.writeheader()
        for i, row in enumerate(pool.map(_query, todo)):
            w.writerow(row)
            if i % 200 == 0:
                fh.flush()
                print(i, flush=True)
    record(OUT, URL.split("?")[0], "OneMap search, one query per unique HDB block + street")


if __name__ == "__main__":
    main()
