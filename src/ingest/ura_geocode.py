"""Geocode URA projects that come without coordinates (mostly new launches) with OneMap.

Query = project name + street; a result is accepted only if its road name matches the URA
street (after normalisation) and its building name contains the project's first word.
Cache: data/raw/singapore/ura/onemap_projects.csv (misses included, for the hit rate).
"""
import csv
import glob
import json
import time
import urllib.parse

import pandas as pd

from src.config import RAW
from src.ingest.http import fetch_json, record
from src.ingest.onemap import URL, normalise

OUT = RAW / "singapore" / "ura" / "onemap_projects.csv"


def missing_projects() -> pd.DataFrame:
    rows = []
    for f in sorted(glob.glob(str(RAW / "singapore" / "ura" / "*.json"))):
        key = "transaction" if "transactions" in f else "rental"
        for p in json.load(open(f)):
            rows.append({"project": p.get("project"), "street": p.get("street"), "has_xy": p.get("x") is not None})
    d = pd.DataFrame(rows)
    ok = set(d.loc[d["has_xy"], "project"])
    return d[~d["project"].isin(ok)][["project", "street"]].drop_duplicates()


def main() -> None:
    todo = missing_projects()
    rows = []
    for _, r in todo.iterrows():
        q = urllib.parse.quote(f"{r.project} {r.street}")
        try:
            res = fetch_json(URL.format(q=q), timeout=60).get("results", [])
        except Exception:
            res = []
        hit = None
        for x in res:
            if normalise(x.get("ROAD_NAME", "")) == normalise(r.street) and \
               r.project.split()[0].upper() in (x.get("BUILDING", "") + " " + x.get("SEARCHVAL", "")).upper():
                hit = x
                break
        rows.append({"project": r.project, "street": r.street, "status": "ok" if hit else "no_match",
                     "lat": hit and hit["LATITUDE"], "lon": hit and hit["LONGITUDE"],
                     "searchval": hit and hit["SEARCHVAL"]})
        time.sleep(0.3)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    record(OUT, URL.split("?")[0], "OneMap search for URA projects without coordinates")
    print(pd.DataFrame(rows)["status"].value_counts().to_dict())


if __name__ == "__main__":
    main()
