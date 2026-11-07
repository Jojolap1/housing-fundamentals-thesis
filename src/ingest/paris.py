"""Download raw Paris sources into data/raw/paris.

Sources (see docs/data_audit.md for licences and caveats):
- DVF géolocalisées (Etalab / DGFiP), national yearly files filtered to département 75
- Ville de Paris reference rents (encadrement des loyers)
- Ville de Paris arrondissements, quartiers administratifs, green spaces
- INSEE Filosofi 2021 IRIS
- IGN contours IRIS and BD TOPO buildings (WFS, data.geopf.fr)
- Île-de-France Mobilités rail/metro/tram stations
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import subprocess
import time
import urllib.parse

from src.config import RAW
from src.ingest.http import UA, download, fetch_json, record

OUT = RAW / "paris"
DATAGOUV = "https://www.data.gouv.fr/api/1/datasets/"
GEODVF_DATASET = "demandes-de-valeurs-foncieres-geolocalisees"
PARIS_OD = "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
IDFM = "https://data.iledefrance-mobilites.fr/api/explore/v2.1/catalog/datasets/"
WFS = "https://data.geopf.fr/wfs/ows"
FILOSOFI = "https://www.insee.fr/fr/statistiques/fichier/8229323/BASE_TD_FILO_IRIS_2021_{}_CSV.zip"
# Bounding box of Paris (lat_min, lon_min, lat_max, lon_max), EPSG:4326; features are clipped later.
PARIS_BBOX = (48.8155, 2.2241, 48.9022, 2.4699)


def dvf_resources() -> list[dict]:
    """Yearly geo-DVF files as listed by the data.gouv.fr API (URLs change at each release)."""
    meta = fetch_json(DATAGOUV + GEODVF_DATASET + "/")
    out = []
    for r in meta["resources"]:
        t = r["title"]
        if t.startswith("DVF 20") and r["url"].endswith(".csv.gz"):
            label = t.replace("DVF ", "").replace(" (2nd semestre)", "-s2").replace(" (1er semestre)", "-s1")
            out.append({"label": label, "url": r["url"]})
    return out


def dvf(force: bool = False) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for res in dvf_resources():
        dest = OUT / f"dvf_75_{res['label']}.csv.gz"
        if dest.exists() and not force:
            continue
        for attempt in range(8):
            try:
                n = _stream_filter_dept(res["url"], dest, "75")
                break
            except Exception as e:  # mid-stream resets: restart the file
                print("retry", res["label"], e)
                time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"could not download {res['url']}")
        record(dest, res["url"], f"national file filtered to code_departement == 75 ({n} rows)")
        print(dest.name, n)


def _stream_filter_dept(url: str, dest, dept: str) -> int:
    """Stream a national gzip CSV through curl and keep only one departement."""
    tmp = dest.with_suffix(".part")
    n = 0
    proc = subprocess.Popen(["curl", "-sS", "-L", "--fail", "-m", "1800", "-A", UA, url],
                            stdout=subprocess.PIPE)
    with gzip.open(tmp, "wt", newline="") as fo:
        text = io.TextIOWrapper(gzip.GzipFile(fileobj=proc.stdout), encoding="utf-8", newline="")
        reader = csv.reader(text)
        header = next(reader)
        i = header.index("code_departement")
        w = csv.writer(fo)
        w.writerow(header)
        for row in reader:
            if row[i] == dept:
                w.writerow(row)
                n += 1
    if proc.wait() != 0:
        raise RuntimeError(f"curl exited with {proc.returncode}")
    tmp.replace(dest)
    return n


def opendata_paris(force: bool = False) -> None:
    exports = {
        "loyers_reference.csv": PARIS_OD + "logement-encadrement-des-loyers/exports/csv?delimiter=%3B"
        "&select=annee,id_zone,id_quartier,nom_quartier,piece,epoque,meuble_txt,ref,max,min,code_grand_quartier",
        "arrondissements.geojson": PARIS_OD + "arrondissements/exports/geojson",
        "quartiers.geojson": PARIS_OD + "quartier_paris/exports/geojson",
        "espaces_verts.geojson": PARIS_OD + "espaces_verts/exports/geojson",
    }
    for name, url in exports.items():
        download(url, OUT / name, note="Ville de Paris open data, ODbL", force=force, timeout=300)


def stations(force: bool = False) -> None:
    download(IDFM + "emplacement-des-gares-idf/exports/geojson", OUT / "gares_idf.geojson",
             note="Ile-de-France Mobilites, Licence Ouverte", force=force, timeout=300)


def filosofi(force: bool = False) -> None:
    for kind in ("DISP", "DEC"):
        download(FILOSOFI.format(kind), OUT / f"filosofi_iris_2021_{kind}.zip",
                 note="INSEE Filosofi 2021 IRIS", force=force)


def _wfs_pages(typename: str, dest, props: list[str] | None = None, cql: str | None = None,
               bbox: tuple | None = None, page: int = 5000, force: bool = False) -> None:
    if dest.exists() and not force:
        return
    feats, start = [], 0
    base = {
        "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature", "TYPENAMES": typename,
        "OUTPUTFORMAT": "application/json", "SRSNAME": "EPSG:4326", "COUNT": str(page),
        "SORTBY": "cleabs" if "BDTOPO" in typename else "",
    }
    if props:
        base["PROPERTYNAME"] = ",".join(props)
    if cql:
        base["CQL_FILTER"] = cql
    elif bbox:
        base["BBOX"] = ",".join(map(str, bbox)) + ",urn:ogc:def:crs:EPSG::4326"
    base = {k: v for k, v in base.items() if v}
    while True:
        q = dict(base, STARTINDEX=str(start))
        url = WFS + "?" + urllib.parse.urlencode(q)
        d = fetch_json(url, timeout=300)
        got = d.get("features", [])
        feats += got
        start += len(got)
        if len(got) < page:
            break
    dest.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    record(dest, WFS + "?" + urllib.parse.urlencode(base), f"WFS {typename}, {len(feats)} features")
    print(dest.name, len(feats))


def ign(force: bool = False) -> None:
    _wfs_pages("STATISTICALUNITS.IRIS:contours_iris", OUT / "contours_iris_paris.geojson",
               cql="code_insee LIKE '751%'", force=force)
    _wfs_pages(
        "BDTOPO_V3:batiment", OUT / "bdtopo_batiment_paris.geojson",
        props=["cleabs", "usage_1", "usage_2", "date_d_apparition", "nombre_de_logements",
               "nombre_d_etages", "hauteur", "geometrie"],
        bbox=PARIS_BBOX, force=force,
    )


def main(force: bool = False) -> None:
    opendata_paris(force)
    stations(force)
    filosofi(force)
    ign(force)
    dvf(force)


if __name__ == "__main__":
    main()
