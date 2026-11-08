"""Clean and harmonise URA private residential transactions and rental contracts.

Scope: the open private market of non-landed homes, i.e. propertyType Apartment or
Condominium, comparable with Paris apartments. Excluded and counted in the log:
Executive Condominiums (public-private hybrid with eligibility and resale restrictions)
and landed homes (their area is the land area). Multi-unit (bulk) transactions are
dropped because the price covers several homes.

Rules (data/processed/cleaning_log_singapore_private.csv):
 1. non-landed Apartment / Condominium only;
 2. single-unit transactions;
 3. price > 0 and 20 <= area <= 400 m²;
 4. coordinates: URA's project x/y (SVY21), else the OneMap geocode of the project;
 5. point inside an MP2019 subzone;
 6. non-market rule: price/m² within a factor 3 of the planning area × year median;
 7. 1st-99th percentile of price/m² within planning area × year.

Rentals: non-landed contracts. URA gives the area as a 10 m² band (e.g. "80-90"); the
band midpoint is used as the floor area, so rent/m² is approximate by up to ±6%.
"""
from __future__ import annotations

import glob
import json
import re

import geopandas as gpd
import numpy as np
import pandas as pd

from src.clean.common import SCHEMA, RemovalLog, add_fx, quantile_trim_by_group, within_factor_of_median
from src.config import INTERIM, PROCESSED, RAW

URA = RAW / "singapore" / "ura"
SALE_TYPE = {"1": "new sale", "2": "sub sale", "3": "resale"}


def _load(pattern: str, key: str) -> pd.DataFrame:
    rows = []
    for f in sorted(glob.glob(str(URA / pattern))):
        for p in json.load(open(f)):
            base = {k: p.get(k) for k in ("project", "street", "marketSegment", "x", "y")}
            rows += [{**base, **t} for t in p.get(key, [])]
    return pd.DataFrame(rows)


def _mmyy(s: pd.Series) -> pd.Series:
    return pd.to_datetime("20" + s.str[2:] + "-" + s.str[:2] + "-01")


def _coords(df: pd.DataFrame) -> pd.DataFrame:
    """lat/lon from URA SVY21 x/y, else from the OneMap project geocode."""
    df = df.copy()
    has = df["x"].notna()
    pts = gpd.GeoSeries(gpd.points_from_xy(df.loc[has, "x"].astype(float), df.loc[has, "y"].astype(float)), crs=3414).to_crs(4326)
    df["lat"], df["lon"] = np.nan, np.nan
    df.loc[has, "lat"], df.loc[has, "lon"] = pts.y.to_numpy(), pts.x.to_numpy()
    om = pd.read_csv(URA / "onemap_projects.csv")
    om = om[om["status"].eq("ok")][["project", "street", "lat", "lon"]].rename(columns={"lat": "lat_om", "lon": "lon_om"})
    df = df.merge(om, on=["project", "street"], how="left")
    df["coord_source"] = np.where(has.to_numpy(), "ura", np.where(df["lat_om"].notna(), "onemap", "none"))
    df["lat"] = df["lat"].fillna(df["lat_om"])
    df["lon"] = df["lon"].fillna(df["lon_om"])
    return df.drop(columns=["lat_om", "lon_om"])


def _subzones(df: pd.DataFrame) -> pd.DataFrame:
    sz = gpd.read_file(RAW / "singapore" / "mp2019_subzone.geojson")[["SUBZONE_N", "PLN_AREA_N", "geometry"]].to_crs(4326)
    ok = df["lat"].notna()
    g = gpd.GeoDataFrame(df[ok], geometry=gpd.points_from_xy(df.loc[ok, "lon"], df.loc[ok, "lat"]), crs=4326)
    g = gpd.sjoin(g, sz, how="left", predicate="within").drop(columns="index_right")
    g = g[~g.index.duplicated()]
    out = df.copy()
    out["subzone"] = g["SUBZONE_N"].reindex(out.index)
    out["planning_area"] = g["PLN_AREA_N"].reindex(out.index)
    return out


def parse_tenure(tenure: str, year: float) -> tuple[float, float]:
    """(lease length, remaining years). Freehold and leases of 900+ years -> (inf, inf)."""
    if not isinstance(tenure, str) or tenure.lower().startswith("freehold"):
        return np.inf, np.inf
    m = re.search(r"(\d+)\s*yrs? lease commencing from (\d{4})", tenure)
    if not m:
        return np.nan, np.nan
    length, start = int(m.group(1)), int(m.group(2))
    if length >= 900:
        return np.inf, np.inf
    return float(length), float(length - (year - start))


def clean_transactions() -> pd.DataFrame:
    log = RemovalLog("singapore_private")
    t = _load("transactions_batch*.json", "transaction").reset_index(drop=True)
    t["source_id"] = "ura_tx_" + t.index.astype(str)
    t = log.apply(t, t["propertyType"].isin(["Apartment", "Condominium"]), "1_non_landed_open_market",
                  "propertyType in {Apartment, Condominium} (excludes Executive Condominium and landed)", "source_id")
    t = log.apply(t, t["noOfUnits"].astype(int).eq(1), "2_single_unit", "noOfUnits == 1", "source_id")
    t["price_local"] = pd.to_numeric(t["price"], errors="coerce")
    t["floor_area_m2"] = pd.to_numeric(t["area"], errors="coerce")
    t = log.apply(t, (t["price_local"] > 0) & t["floor_area_m2"].between(20, 400), "3_price_area_plausible",
                  "price > 0 and 20 <= area <= 400 m2", "source_id")
    t = _coords(t)
    t = log.apply(t, t["lat"].notna(), "4_located", "URA x/y or OneMap project geocode", "source_id")
    t = _subzones(t)
    t = log.apply(t, t["subzone"].notna(), "5_in_subzone", "point inside an MP2019 subzone", "source_id")
    t["date"] = _mmyy(t["contractDate"])
    t["year"] = t["date"].dt.year
    t["price_per_m2_local"] = t["price_local"] / t["floor_area_m2"]
    t = log.apply(t, within_factor_of_median(t, "price_per_m2_local", ["planning_area", "year"]),
                  "6_non_market_price", "price/m2 within [median/3, median*3] of planning area x year", "source_id")
    t = log.apply(t, quantile_trim_by_group(t, "price_per_m2_local", ["planning_area", "year"]),
                  "7_ppm2_p1_p99", "price/m2 within p1-p99 of planning area x year", "source_id")
    t = add_fx(t, "SGD")
    t["price_per_m2_eur"] = t["price_eur"] / t["floor_area_m2"]
    lease = [parse_tenure(a, b) for a, b in zip(t["tenure"], t["year"])]
    t["lease_length"] = [a for a, _ in lease]
    t["lease_remaining"] = [b for _, b in lease]
    fr = t["floorRange"].str.extract(r"(\d+)-(\d+)").astype(float)
    t["storey_mid"] = fr.mean(axis=1)
    out = pd.DataFrame({
        "city": "Singapore private",
        "date": t["date"], "year": t["year"],
        "price_local": t["price_local"], "currency": "SGD",
        "price_eur": t["price_eur"], "price_usd": t["price_usd"],
        "floor_area_m2": t["floor_area_m2"],
        "price_per_m2_local": t["price_per_m2_local"], "price_per_m2_eur": t["price_per_m2_eur"],
        "rooms_or_flat_type": t["propertyType"],
        "property_type": t["propertyType"].str.lower(),
        "tenure": t["tenure"],
        # Freehold / 999-year leases have no finite remaining term: NaN here, flagged below.
        "lease_remaining_years": t["lease_remaining"].replace(np.inf, np.nan),
        "address_street": t["street"],
        "street_id": t["street"],
        "district_l1": t["planning_area"],
        "district_l2": t["subzone"],
        "lat": t["lat"], "lon": t["lon"],
        "source_id": t["source_id"],
        "project": t["project"], "market_segment": t["marketSegment"],
        "sale_type": t["typeOfSale"].map(SALE_TYPE), "storey_mid": t["storey_mid"],
        "freehold": np.isinf(t["lease_remaining"]).astype(int),
        "coord_source": t["coord_source"], "postal_district": t["district"],
        "fx_local_per_eur": t["fx_local_per_eur"], "fx_usd_per_eur": t["fx_usd_per_eur"],
    })
    assert list(out.columns[: len(SCHEMA)]) == SCHEMA
    out.to_parquet(INTERIM / "transactions_singapore_private.parquet", index=False)
    print(log.save().to_string(index=False))
    return out


def clean_rentals() -> pd.DataFrame:
    r = _load("rental_*.json", "rental").reset_index(drop=True)
    n0 = len(r)
    r = r[r["propertyType"].eq("Non-landed Properties")].copy()
    n1 = len(r)
    band = r["areaSqm"].str.extract(r"(\d+)-(\d+)").astype(float)
    r["area_mid_m2"] = band.mean(axis=1)
    r["monthly_rent"] = pd.to_numeric(r["rent"], errors="coerce")
    r = r[r["area_mid_m2"].between(20, 400) & (r["monthly_rent"] > 0)]
    r = _subzones(_coords(r))
    r = r[r["subzone"].notna()].copy()
    r["date"] = _mmyy(r["leaseDate"])
    r["year"] = r["date"].dt.year
    r["rent_m2"] = r["monthly_rent"] / r["area_mid_m2"]
    r["bedrooms"] = pd.to_numeric(r.get("noOfBedRoom"), errors="coerce")
    pd.DataFrame([{"city": "singapore_private_rent", "rows_raw": n0, "non_landed": n1, "kept": len(r)}]).to_csv(
        PROCESSED / "cleaning_log_singapore_private_rent.csv", index=False)
    r = r[["date", "year", "project", "street", "lat", "lon", "subzone", "planning_area", "area_mid_m2",
           "monthly_rent", "rent_m2", "bedrooms", "marketSegment"]]
    r.to_parquet(INTERIM / "rents_singapore_private.parquet", index=False)
    print("private rentals kept", len(r), "of", n0)
    return r


if __name__ == "__main__":
    clean_transactions()
    clean_rentals()
