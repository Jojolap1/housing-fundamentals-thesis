"""Export pre-aggregated, privacy-safe data for the static website (site/data).

Only aggregates leave the pipeline. Any cell (hexagon, street, district) × year with fewer
than MIN_N_PUBLISH transactions is dropped. No transaction, address or parcel identifier
is written. Geometries are simplified and coordinates rounded to keep pages light.
"""
from __future__ import annotations

import json

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, mapping

from src.config import INTERIM, MIN_N_PUBLISH, PROCESSED, RAW, SITE_DATA

H3_RES = 9
METRICS = ["n", "ppm2", "ppm2_q25", "ppm2_q75", "yoy", "rent_m2", "rent_month", "yield", "pti", "gap", "mis"]


def _round_geom(geom, nd=5):
    return json.loads(json.dumps(mapping(geom)), parse_float=lambda x: round(float(x), nd))


def _agg(d: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    g = d.groupby(keys + ["year"])
    a = g.agg(n=("price_per_m2_local", "size"), ppm2=("price_per_m2_local", "median"),
              ppm2_q25=("price_per_m2_local", lambda s: s.quantile(0.25)),
              ppm2_q75=("price_per_m2_local", lambda s: s.quantile(0.75)),
              rent_m2=("rent_m2", "median"), yield_=("gross_yield", "median"),
              pti=("pti_hh", "median"), gap=("gap", "median"), mis=("mispricing_resid", "median"))
    if "rent_month" in d:
        a["rent_month"] = g["rent_month"].median()
    a = a.rename(columns={"yield_": "yield"}).reset_index().sort_values(keys + ["year"])
    prev = a.groupby(keys)["ppm2"].shift(1)
    prev_y = a.groupby(keys)["year"].shift(1)
    a["yoy"] = np.where(prev_y == a["year"] - 1, 100 * (a["ppm2"] / prev - 1), np.nan)
    return a[a["n"] >= MIN_N_PUBLISH]


def _props(a: pd.DataFrame, key: str) -> dict:
    out = {}
    for k, s in a.groupby(key):
        p = {}
        for _, r in s.iterrows():
            y = int(r["year"])
            for m in METRICS:
                if m in r and pd.notna(r[m]):
                    v = float(r[m])
                    p[f"{m}_{y}"] = round(v, 4) if m in ("yield", "gap", "mis") else round(v, 1)
        out[k] = p
    return out


def _fc(features):
    return {"type": "FeatureCollection", "features": features}


def _write(name, obj):
    (SITE_DATA / name).write_text(json.dumps(obj, separators=(",", ":"), allow_nan=False))


def export_city(city: str) -> dict:
    d = pd.read_parquet(INTERIM / f"valuation_{city}.parquet")
    years = sorted(int(y) for y in d["year"].unique())
    d["h3"] = [h3.latlng_to_cell(a, b, H3_RES) for a, b in zip(d["lat"], d["lon"])]

    # Hexagons
    hx = _agg(d, ["h3"])
    props = _props(hx, "h3")
    feats = []
    for c, p in props.items():
        ring = [(lng, lat) for lat, lng in h3.cell_to_boundary(c)]
        feats.append({"type": "Feature", "geometry": _round_geom(Polygon(ring)), "properties": p})
    _write(f"{city}_hex.json", _fc(feats))

    # Districts (l1, l2) with official geometries
    if city == "paris":
        l1 = gpd.read_file(RAW / "paris" / "arrondissements.geojson")[["c_ar", "l_ar", "geometry"]]
        l1 = l1.rename(columns={"c_ar": "key", "l_ar": "name"})
        l2 = gpd.read_file(RAW / "paris" / "quartiers.geojson")[["c_qu", "l_qu", "geometry"]]
        l2 = l2.rename(columns={"c_qu": "key", "l_qu": "name"})
        l1["key"], l2["key"] = l1["key"].astype(int), l2["key"].astype(int)
        tol = 0.0001
    else:
        l1 = gpd.read_file(RAW / "singapore" / "mp2019_planning_area.geojson")[["PLN_AREA_N", "geometry"]]
        l1 = l1.rename(columns={"PLN_AREA_N": "key"}).assign(name=lambda x: x["key"].str.title())
        l2 = gpd.read_file(RAW / "singapore" / "mp2019_subzone.geojson")[["SUBZONE_N", "geometry"]]
        l2 = l2.rename(columns={"SUBZONE_N": "key"}).assign(name=lambda x: x["key"].str.title())
        tol = 0.0002
    for lvl, gdf, col in (("l1", l1, "district_l1"), ("l2", l2, "district_l2")):
        a = _agg(d, [col])
        p = _props(a, col)
        gdf = gdf.to_crs(4326)
        gdf["geometry"] = gdf.geometry.simplify(tol, preserve_topology=True)
        feats = []
        for _, r in gdf.iterrows():
            pr = {"name": r["name"]} | p.get(r["key"], {})
            feats.append({"type": "Feature", "geometry": _round_geom(r.geometry), "properties": pr})
        _write(f"{city}_{lvl}.json", _fc(feats))

    # Streets (table only: no individual addresses, n >= 5 per street-year)
    s = _agg(d, ["street_id", "address_street", "district_l1"])
    s = s[["address_street", "district_l1", "year", "n", "ppm2", "ppm2_q25", "ppm2_q75", "yoy", "mis"]]
    s = s.rename(columns={"address_street": "street", "district_l1": "district"})
    s["district"] = s["district"].astype(str)
    _write(f"{city}_streets.json", json.loads(s.round(4).to_json(orient="records")))

    # Fundamental vs market and sensitivity
    fv = pd.read_csv(PROCESSED / f"fundamental_vs_market_{city}.csv")
    _write(f"{city}_fundamental.json", json.loads(fv.round(4).to_json(orient="records")))
    meta = {"city": city, "years": years, "n_total": int(len(d)),
            "period": [str(d["date"].min().date()), str(d["date"].max().date())],
            "min_n": MIN_N_PUBLISH}
    _write(f"{city}_meta.json", meta)
    return meta


def main() -> None:
    for c in ("paris", "singapore"):
        print(export_city(c))


if __name__ == "__main__":
    main()
