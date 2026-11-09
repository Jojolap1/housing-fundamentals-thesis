"""Download raw Singapore sources into data/raw/singapore (data.gov.sg, Singapore Open Data Licence).

Tabular datasets are read through the datastore API page by page; the row count is
checked against contiguous `_id` values because the API's `total` field was observed to
be unreliable (see docs/data_audit.md). GeoJSON layers go through the bulk-download API.
"""
from __future__ import annotations

import csv
import time

from src.config import RAW
from src.ingest.http import download, fetch_json, record

OUT = RAW / "singapore"
DATASTORE = "https://data.gov.sg/api/action/datastore_search?resource_id={rid}&limit={lim}&offset={off}"
BULK = "https://api-open.data.gov.sg/v1/public/api/datasets/{rid}/{action}"

TABLES = {
    "hdb_resale_2017on.csv": "d_8b84c4ee58e3cfc0ece0d773c8ca6abc",
    "hdb_rent_2021on.csv": "d_c9f57187485a850908655db0e8cfe651",
    "hdb_property_information.csv": "d_17f5382f26140b1fdae0ba2ef6239d2f",
    "census2020_hh_income_work_by_pa.csv": "d_4e150bbd35c3145ea43019212c7b46c2",
    "census2020_hh_income_work_by_pa_v2022.csv": "d_2d6793de474551149c438ba349a108fd",
    # National median monthly household income from work incl. employer CPF, 2000-2025
    # (SingStat table 17870): its 2020 value for employed households (S$9,208) matches the
    # Census 2020 band median (S$9,222), so it is the same definition.
    "hh_income_work_national_2000_2025.csv": "d_f4560da11b22b47050c75bdffb1d93e0",
}
GEO = {
    "hdb_existing_building.geojson": "d_16b157c52ed637edd6ba1232e026258d",
    "mrt_station_exit.geojson": "d_b39d3a0871985372d7e1637193335da5",
    "parks.geojson": "d_0542d48f0991541706b58059381a6eca",
    "nparks_parks_nature_reserves.geojson": "d_77d7ec97be83d44f61b85454f844382f",
    "mp2019_planning_area.geojson": "d_4765db0e87b9c86336792efe8a1f7a66",
    "mp2019_subzone.geojson": "d_8594ae9ff96d0c708bc2af633048edfb",
}


def table(rid: str, dest, force: bool = False, lim: int = 10000) -> None:
    if dest.exists() and not force:
        return
    rows, off, fields = [], 0, None
    while True:
        try:
            r = fetch_json(DATASTORE.format(rid=rid, lim=lim, off=off), timeout=180)["result"]
        except RuntimeError as e:
            if "413" in str(e) and lim > 500:  # page too large for wide tables: halve it
                lim //= 2
                continue
            raise
        recs = r["records"]
        fields = [f["id"] for f in r["fields"]]
        rows += recs
        off += len(recs)
        if not recs or off >= r["total"]:
            break
        time.sleep(1.5)  # stay well below the public rate limit
    ids = sorted(int(x["_id"]) for x in rows)
    if ids != list(range(1, len(ids) + 1)):
        raise RuntimeError(f"{rid}: _id values are not contiguous; refusing a partial download")
    with open(dest, "w", newline="") as fh:
        w = csv.DictWriter(fh, fields)
        w.writeheader()
        w.writerows(rows)
    record(dest, DATASTORE.format(rid=rid, lim=lim, off=0).split("&limit")[0], f"{len(rows)} rows, full pagination")
    print(dest.name, len(rows))


def geo(rid: str, dest, force: bool = False) -> None:
    if dest.exists() and not force:
        return
    fetch_json(BULK.format(rid=rid, action="initiate-download"))
    for _ in range(30):
        d = fetch_json(BULK.format(rid=rid, action="poll-download"))["data"]
        if d.get("url"):
            break
        time.sleep(3)
    else:
        raise RuntimeError(f"{rid}: download never became ready")
    tmp = download(d["url"], dest, force=True, timeout=600)
    # Record the stable dataset URL rather than the expiring signed link.
    record(tmp, f"https://data.gov.sg/datasets/{rid}/view", "bulk GeoJSON download")
    print(dest.name)


def main(force: bool = False) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rid in GEO.items():
        geo(rid, OUT / name, force)
    for name, rid in TABLES.items():
        table(rid, OUT / name, force)


if __name__ == "__main__":
    main()
