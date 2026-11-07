"""Clean and harmonise Paris DVF sales into the common schema.

Rules (each step is counted in data/processed/cleaning_log_paris.csv):
 1. drop exact duplicate lines of the geo-DVF file;
 2. keep `nature_mutation == "Vente"` (drops exchanges, off-plan sales [VEFA], auctions,
    building-land sales: different price formation);
 3. keep mutations made of exactly one apartment plus, optionally, outbuildings
    (dépendances: cellars, parking). Mutations with several dwellings, commercial premises
    or land lines are dropped because their price cannot be attributed to one dwelling;
 4. price > 0 and 9 m² <= built area <= 400 m² (9 m² is the legal decency minimum,
    décret n° 2002-120; above 400 m² the few sales are atypical mansions);
 5. coordinates present and inside a Paris quartier;
 6. a) price/m² within a factor 3 of the arrondissement × year median (drops symbolic and
    other non-market prices, e.g. €1 transfers), then b) inside the 1st-99th percentile.
"""
from __future__ import annotations

import glob

import geopandas as gpd
import numpy as np
import pandas as pd

from src.clean.common import SCHEMA, RemovalLog, add_fx, quantile_trim_by_group, within_factor_of_median
from src.config import INTERIM, RAW

RAWP = RAW / "paris"


def load_dvf() -> pd.DataFrame:
    files = sorted(glob.glob(str(RAWP / "dvf_75_*.csv.gz")))
    if not files:
        raise FileNotFoundError("run `make data` first: no DVF files in data/raw/paris")
    return pd.concat([pd.read_csv(f, dtype=str) for f in files], ignore_index=True)


def quartiers() -> gpd.GeoDataFrame:
    # c_qu is the city-wide quartier number (1-80), the same key as `id_quartier` in the
    # reference-rent file. (c_quinsee numbers quartiers within each arrondissement and does
    # NOT match the rent file's code_grand_quartier.)
    q = gpd.read_file(RAWP / "quartiers.geojson")[["c_qu", "l_qu", "c_ar", "geometry"]]
    q = q.rename(columns={"c_qu": "quartier_code", "l_qu": "quartier", "c_ar": "arrondissement"})
    q["quartier_code"] = q["quartier_code"].astype(int)
    q["arrondissement"] = q["arrondissement"].astype(int)
    return q.to_crs(4326)


def iris() -> gpd.GeoDataFrame:
    g = gpd.read_file(RAWP / "contours_iris_paris.geojson")
    code = next(c for c in ("code_iris", "iris", "CODE_IRIS") if c in g.columns)
    return g[[code, "geometry"]].rename(columns={code: "iris"}).to_crs(4326)


def clean() -> pd.DataFrame:
    log = RemovalLog("paris")
    raw = load_dvf()
    raw["_row"] = np.arange(len(raw))
    df = raw

    keep = ~df.drop(columns="_row").duplicated()
    df = log.apply(df, keep, "1_exact_duplicates", "identical line in geo-DVF", "id_mutation")

    df = log.apply(df, df["nature_mutation"].eq("Vente"), "2_nature_vente",
                   "nature_mutation == 'Vente'", "id_mutation")

    t = df["type_local"].fillna("none")
    comp = pd.DataFrame({"id": df["id_mutation"], "apt": t.eq("Appartement"),
                         "dep": t.eq("Dépendance"), "other": ~t.isin(["Appartement", "Dépendance"])})
    agg = comp.groupby("id").agg(n_apt=("apt", "sum"), n_dep=("dep", "sum"), n_other=("other", "sum"))
    ok_ids = agg.index[(agg.n_apt == 1) & (agg.n_other == 0)]
    df = log.apply(df, df["id_mutation"].isin(ok_ids), "3_single_apartment",
                   "exactly one Appartement line; other lines only Dépendance", "id_mutation")
    df = df.merge(agg[["n_dep"]], left_on="id_mutation", right_index=True)
    n_lines = len(df)
    df = df[df["type_local"].eq("Appartement")].copy()  # one line per mutation from here
    log.steps.append({"city": "paris", "step": "3b_one_line_per_sale",
                      "rule": "reshape, not a filter: outbuilding lines folded into their sale (n_dependances)",
                      "rows_before": n_lines, "rows_removed": n_lines - len(df), "rows_after": len(df)})

    df["price_local"] = pd.to_numeric(df["valeur_fonciere"], errors="coerce")
    df["floor_area_m2"] = pd.to_numeric(df["surface_reelle_bati"], errors="coerce")
    keep = (df["price_local"] > 0) & df["floor_area_m2"].between(9, 400)
    df = log.apply(df, keep, "4_price_area_plausible", "price > 0 and 9 <= area <= 400 m2", "id_mutation")

    df["lat"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["lon"] = pd.to_numeric(df["longitude"], errors="coerce")
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=4326)
    pts = gpd.sjoin(pts, quartiers(), how="left", predicate="within").drop(columns="index_right")
    pts = gpd.sjoin(pts, iris(), how="left", predicate="within").drop(columns="index_right")
    pts = pts[~pts.index.duplicated()]
    df = pd.DataFrame(pts.drop(columns="geometry"))
    df = log.apply(df, df["quartier_code"].notna(), "5_geolocated_in_paris",
                   "coordinates inside a Paris quartier administratif", "id_mutation")

    df["date"] = pd.to_datetime(df["date_mutation"])
    df["year"] = df["date"].dt.year
    df["price_per_m2_local"] = df["price_local"] / df["floor_area_m2"]
    keep = within_factor_of_median(df, "price_per_m2_local", ["arrondissement", "year"])
    df = log.apply(df, keep, "6a_non_market_price", "price/m2 within [median/3, median*3] of arrondissement x year",
                   "id_mutation")
    keep = quantile_trim_by_group(df, "price_per_m2_local", ["arrondissement", "year"])
    df = log.apply(df, keep, "6b_ppm2_p1_p99", "price/m2 within p1-p99 of arrondissement x year", "id_mutation")

    df = add_fx(df, "EUR")
    df["price_per_m2_eur"] = df["price_eur"] / df["floor_area_m2"]
    rooms = pd.to_numeric(df["nombre_pieces_principales"], errors="coerce")
    out = pd.DataFrame({
        "city": "Paris",
        "date": df["date"], "year": df["year"],
        "price_local": df["price_local"], "currency": "EUR",
        "price_eur": df["price_eur"], "price_usd": df["price_usd"],
        "floor_area_m2": df["floor_area_m2"],
        "price_per_m2_local": df["price_per_m2_local"], "price_per_m2_eur": df["price_per_m2_eur"],
        "rooms_or_flat_type": rooms,
        "property_type": "apartment",
        "tenure": "freehold (copropriété)",
        "lease_remaining_years": np.nan,
        "address_street": df["adresse_nom_voie"].str.upper(),
        "street_id": df["code_commune"] + "_" + df["adresse_code_voie"],
        "district_l1": df["arrondissement"].astype(int),
        "district_l2": df["quartier_code"].astype(int),
        "lat": df["lat"], "lon": df["lon"],
        "source_id": df["id_mutation"],
        # city-specific extras
        "quartier_name": df["quartier"], "iris": df["iris"],
        "n_dependances": df["n_dep"].astype(int),
        "carrez_m2": pd.to_numeric(df["lot1_surface_carrez"], errors="coerce"),
        "id_parcelle": df["id_parcelle"],
        "fx_usd_per_eur": df["fx_usd_per_eur"],
    })
    assert list(out.columns[: len(SCHEMA)]) == SCHEMA
    out.to_parquet(INTERIM / "transactions_paris.parquet", index=False)
    print(log.save().to_string(index=False))
    return out


if __name__ == "__main__":
    clean()
