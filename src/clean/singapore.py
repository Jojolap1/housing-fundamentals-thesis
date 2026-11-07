"""Clean and harmonise Singapore HDB resale transactions and HDB rental approvals.

Resale rules (counted in data/processed/cleaning_log_singapore.csv):
 1. price > 0 and 25 m² <= floor area <= 300 m² (smallest HDB type, 1-room, is ~31 m²);
 2. block geocoded by OneMap (see src/ingest/onemap.py for the acceptance rule);
 3. point inside a URA Master Plan 2019 subzone;
 4. a) price/m² within a factor 3 of the town × flat type × year median, then
    b) inside the 1st-99th percentile.
Exact duplicate lines (same month, block, storey band, area and price) cannot be told
apart from distinct sales, so they are kept and flagged (`dup_flag`).

Geography: district_l1 = URA planning area, district_l2 = URA subzone (a nested
hierarchy). The HDB town, which is HDB's own administrative unit, is kept as `hdb_town`.
"""
from __future__ import annotations

import re

import geopandas as gpd
import numpy as np
import pandas as pd

from src.clean.common import SCHEMA, RemovalLog, add_fx, quantile_trim_by_group, within_factor_of_median
from src.config import INTERIM, PROCESSED, RAW

RAWS = RAW / "singapore"


def parse_lease(s: str) -> float:
    """'61 years 04 months' -> 61.33; '70' -> 70.0."""
    if pd.isna(s):
        return np.nan
    y = re.search(r"(\d+)\s*year", str(s))
    m = re.search(r"(\d+)\s*month", str(s))
    if y:
        return int(y.group(1)) + (int(m.group(1)) / 12 if m else 0)
    try:
        return float(s)
    except ValueError:
        return np.nan


def storey_mid(s: str) -> float:
    a, b = str(s).split(" TO ")
    return (int(a) + int(b)) / 2


def blocks() -> gpd.GeoDataFrame:
    g = pd.read_csv(RAWS / "onemap_blocks.csv", dtype=str)
    g = g[g["status"].eq("ok")].copy()
    g["lat"] = g["lat"].astype(float)
    g["lon"] = g["lon"].astype(float)
    gdf = gpd.GeoDataFrame(g, geometry=gpd.points_from_xy(g["lon"], g["lat"]), crs=4326)
    sz = gpd.read_file(RAWS / "mp2019_subzone.geojson")[["SUBZONE_N", "PLN_AREA_N", "REGION_N", "geometry"]]
    gdf = gpd.sjoin(gdf, sz.to_crs(4326), how="left", predicate="within").drop(columns="index_right")
    gdf = gdf[~gdf.index.duplicated()]
    return gdf.rename(columns={"SUBZONE_N": "subzone", "PLN_AREA_N": "planning_area", "REGION_N": "region"})


def geocode_report() -> dict:
    g = pd.read_csv(RAWS / "onemap_blocks.csv", dtype=str)
    rep = {"blocks_queried": len(g), "geocoded": int(g["status"].eq("ok").sum())}
    rep["hit_rate"] = round(rep["geocoded"] / rep["blocks_queried"], 4)
    pd.DataFrame([rep]).to_csv(PROCESSED / "geocoding_singapore.csv", index=False)
    return rep


def clean_resale() -> pd.DataFrame:
    log = RemovalLog("singapore")
    df = pd.read_csv(RAWS / "hdb_resale_2017on.csv", dtype=str)
    df["source_id"] = "hdb_resale_" + df["_id"]
    df["dup_flag"] = df.drop(columns=["_id", "source_id"]).duplicated(keep=False)
    df["price_local"] = pd.to_numeric(df["resale_price"], errors="coerce")
    df["floor_area_m2"] = pd.to_numeric(df["floor_area_sqm"], errors="coerce")
    keep = (df["price_local"] > 0) & df["floor_area_m2"].between(25, 300)
    df = log.apply(df, keep, "1_price_area_plausible", "price > 0 and 25 <= area <= 300 m2", "source_id")

    b = blocks()
    df = df.merge(b[["block", "street_name", "lat", "lon", "postal", "subzone", "planning_area", "region"]],
                  on=["block", "street_name"], how="left")
    df = log.apply(df, df["lat"].notna(), "2_geocoded", "block + street matched by OneMap", "source_id")
    df = log.apply(df, df["subzone"].notna(), "3_in_subzone", "point inside an MP2019 subzone", "source_id")

    df["date"] = pd.to_datetime(df["month"] + "-01")
    df["year"] = df["date"].dt.year
    df["price_per_m2_local"] = df["price_local"] / df["floor_area_m2"]
    keep = within_factor_of_median(df, "price_per_m2_local", ["town", "flat_type", "year"])
    df = log.apply(df, keep, "4a_non_market_price", "price/m2 within [median/3, median*3] of town x flat type x year",
                   "source_id")
    keep = quantile_trim_by_group(df, "price_per_m2_local", ["town", "flat_type", "year"])
    df = log.apply(df, keep, "4b_ppm2_p1_p99", "price/m2 within p1-p99 of town x flat type x year", "source_id")

    df = add_fx(df, "SGD")
    df["price_per_m2_eur"] = df["price_eur"] / df["floor_area_m2"]
    lease_start = pd.to_numeric(df["lease_commence_date"], errors="coerce")
    lease = df["remaining_lease"].map(parse_lease)
    # Before the field existed, remaining lease = 99 - (transaction year - lease start).
    lease = lease.fillna(99 - (df["year"] + (df["date"].dt.month - 1) / 12 - lease_start))
    out = pd.DataFrame({
        "city": "Singapore",
        "date": df["date"], "year": df["year"],
        "price_local": df["price_local"], "currency": "SGD",
        "price_eur": df["price_eur"], "price_usd": df["price_usd"],
        "floor_area_m2": df["floor_area_m2"],
        "price_per_m2_local": df["price_per_m2_local"], "price_per_m2_eur": df["price_per_m2_eur"],
        "rooms_or_flat_type": df["flat_type"],
        "property_type": "HDB flat",
        "tenure": "99-year HDB lease",
        "lease_remaining_years": lease,
        "address_street": df["street_name"],
        "street_id": df["street_name"],
        "district_l1": df["planning_area"],
        "district_l2": df["subzone"],
        "lat": df["lat"], "lon": df["lon"],
        "source_id": df["source_id"],
        "hdb_town": df["town"], "block": df["block"], "flat_model": df["flat_model"],
        "storey_mid": df["storey_range"].map(storey_mid), "storey_range": df["storey_range"],
        "lease_commence_year": lease_start, "region": df["region"], "dup_flag": df["dup_flag"],
        "fx_local_per_eur": df["fx_local_per_eur"], "fx_usd_per_eur": df["fx_usd_per_eur"],
    })
    assert list(out.columns[: len(SCHEMA)]) == SCHEMA
    out.to_parquet(INTERIM / "transactions_singapore.parquet", index=False)
    print(log.save().to_string(index=False))
    return out


def clean_rent() -> pd.DataFrame:
    """HDB rental approvals with block geography. No floor area in the source."""
    r = pd.read_csv(RAWS / "hdb_rent_2021on.csv", dtype=str)
    r["monthly_rent"] = pd.to_numeric(r["monthly_rent"], errors="coerce")
    r["date"] = pd.to_datetime(r["rent_approval_date"] + "-01")
    r["year"] = r["date"].dt.year
    # Harmonise flat type labels with the resale file ("4-ROOM" -> "4 ROOM").
    r["flat_type"] = r["flat_type"].str.replace("-", " ", regex=False)
    b = blocks()
    r = r.merge(b[["block", "street_name", "lat", "lon", "subzone", "planning_area"]],
                on=["block", "street_name"], how="left")
    n0 = len(r)
    r = r[(r["monthly_rent"] > 0) & r["subzone"].notna()].copy()
    pd.DataFrame([{"city": "singapore_rent", "step": "geocoded_positive_rent", "rows_before": n0,
                   "rows_removed": n0 - len(r), "rows_after": len(r)}]).to_csv(
        PROCESSED / "cleaning_log_singapore_rent.csv", index=False)
    r = r.rename(columns={"town": "hdb_town"})
    r[["date", "year", "hdb_town", "block", "street_name", "flat_type", "monthly_rent", "lat", "lon",
       "subzone", "planning_area", "_id"]].to_parquet(INTERIM / "rents_singapore.parquet", index=False)
    return r


if __name__ == "__main__":
    print(geocode_report())
    clean_resale()
    clean_rent()
