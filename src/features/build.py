"""Location and building features, plus the rent matched to each sale.

Distances are Euclidean, in metres, in a projected CRS (Lambert-93 for Paris, SVY21 for
Singapore). Definitions:
- dist_rail_m: nearest metro/RER station (Paris, IDFM) or MRT/LRT station exit (Singapore, LTA);
- dist_cbd_m: distance to the business-district anchor, taken from the station data
  itself (Paris: "Opéra" metro station, centre of the Quartier Central des Affaires;
  Singapore: centroid of the "RAFFLES PLACE MRT STATION" exits);
- dist_park_m: nearest public green space of at least 1 ha (Paris: Ville de Paris
  "espaces verts", Singapore: NParks parks and nature reserves).

Paris only: construction period of the building, from the nearest residential BD TOPO
building (within 30 m of the DVF parcel point), mapped to the four reference-rent periods.
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from src.config import INTERIM, PROCESSED, RAW

L93, SVY21 = 2154, 3414
RENT_EPOQUES = ["Avant 1946", "1946-1970", "1971-1990", "Apres 1990"]


def _nearest_dist(points: gpd.GeoDataFrame, targets: gpd.GeoDataFrame) -> np.ndarray:
    j = gpd.sjoin_nearest(points[["geometry"]], targets[["geometry"]], how="left", distance_col="d")
    return j[~j.index.duplicated()]["d"].reindex(points.index).to_numpy()


def epoque(year: pd.Series) -> pd.Series:
    bins = [-np.inf, 1945, 1970, 1990, np.inf]
    return pd.cut(year, bins=bins, labels=RENT_EPOQUES).astype("object")


# --------------------------------------------------------------------------- Paris
def paris_buildings() -> gpd.GeoDataFrame:
    b = gpd.read_file(RAW / "paris" / "bdtopo_batiment_paris.geojson")
    res = b["usage_1"].eq("Résidentiel") | b["usage_2"].eq("Résidentiel")
    b = b[res].copy()
    b["build_year"] = pd.to_numeric(b["date_d_apparition"].astype(str).str[:4], errors="coerce")
    b.loc[b["build_year"] < 1600, "build_year"] = np.nan
    return b.to_crs(L93)


def paris_features() -> pd.DataFrame:
    t = pd.read_parquet(INTERIM / "transactions_paris.parquet")
    pts = gpd.GeoDataFrame(t, geometry=gpd.points_from_xy(t["lon"], t["lat"]), crs=4326).to_crs(L93)

    st = gpd.read_file(RAW / "paris" / "gares_idf.geojson").to_crs(L93)
    rail = st[st["mode"].isin(["METRO", "RER"])]
    pts["dist_rail_m"] = _nearest_dist(pts, rail)
    opera = st[(st["nom_gares"] == "Opéra") & (st["mode"] == "METRO")].geometry.union_all().centroid
    pts["dist_cbd_m"] = pts.geometry.distance(opera)

    ev = gpd.read_file(RAW / "paris" / "espaces_verts.geojson").to_crs(L93)
    ev = ev[ev.geometry.notna() & (ev.geometry.area >= 10_000)]
    pts["dist_park_m"] = _nearest_dist(pts, ev)

    b = paris_buildings()
    j = gpd.sjoin_nearest(pts[["geometry"]], b[["build_year", "nombre_d_etages", "nombre_de_logements", "geometry"]],
                          how="left", max_distance=30, distance_col="dist_building_m")
    j = j[~j.index.duplicated()]
    pts["build_year"] = j["build_year"]
    pts["building_floors"] = j["nombre_d_etages"]
    pts["building_dwellings"] = j["nombre_de_logements"]
    pts["epoque"] = epoque(pts["build_year"])

    out = pd.DataFrame(pts.drop(columns="geometry"))
    out["rooms_capped"] = out["rooms_or_flat_type"].clip(upper=4)
    out["has_dependance"] = (out["n_dependances"] > 0).astype(int)
    # Reference rents apply from 1 July of their vintage year to 30 June of the next.
    out["rent_vintage"] = np.where(out["date"].dt.month >= 7, out["year"], out["year"] - 1)
    out = _match_paris_rent(out, b)
    out.to_parquet(INTERIM / "features_paris.parquet", index=False)
    cov = {
        "n": len(out),
        "share_with_build_year": round(out["build_year"].notna().mean(), 4),
        "share_with_rent_exact": round(out["ref_rent_m2_exact"].notna().mean(), 4),
        "share_with_rent_mix": round(out["ref_rent_m2_mix"].notna().mean(), 4),
    }
    pd.DataFrame([cov]).to_csv(PROCESSED / "feature_coverage_paris.csv", index=False)
    print(cov)
    return out


def _match_paris_rent(t: pd.DataFrame, b: gpd.GeoDataFrame) -> pd.DataFrame:
    """Two matched reference rents (unfurnished, €/m²/month):
    - ref_rent_m2_exact: cell quartier × rooms × building period × vintage;
    - ref_rent_m2_mix: same cell averaged over the four periods, weighted by the dwelling
      share of each period in the quartier's residential buildings (robustness check that
      does not depend on the building match).
    """
    r = pd.read_csv(RAW / "paris" / "loyers_reference.csv", sep=";")
    r = r[r["meuble_txt"].eq("non meublé")]
    r = r.rename(columns={"annee": "rent_vintage", "id_quartier": "district_l2", "piece": "rooms_capped"})
    exact = r[["rent_vintage", "district_l2", "rooms_capped", "epoque", "ref"]].rename(columns={"ref": "ref_rent_m2_exact"})
    t = t.merge(exact, on=["rent_vintage", "district_l2", "rooms_capped", "epoque"], how="left")

    q = gpd.read_file(RAW / "paris" / "quartiers.geojson")[["c_qu", "geometry"]].to_crs(L93)
    bq = gpd.sjoin(b.assign(geometry=b.geometry.representative_point()), q, predicate="within")
    bq["epoque"] = epoque(bq["build_year"])
    bq["w"] = pd.to_numeric(bq["nombre_de_logements"], errors="coerce").fillna(0)
    mix = bq.dropna(subset=["epoque"]).groupby(["c_qu", "epoque"])["w"].sum()
    mix = (mix / mix.groupby(level=0).transform("sum")).rename("share").reset_index()
    mix = mix.rename(columns={"c_qu": "district_l2"})
    mix["district_l2"] = mix["district_l2"].astype(int)
    mix.to_csv(PROCESSED / "paris_building_period_mix.csv", index=False)
    rm = r.merge(mix, on=["district_l2", "epoque"], how="left").fillna({"share": 0})
    rm = (rm.assign(x=rm["ref"] * rm["share"]).groupby(["rent_vintage", "district_l2", "rooms_capped"])
          .agg(x=("x", "sum"), s=("share", "sum")))
    rm["ref_rent_m2_mix"] = rm["x"] / rm["s"]
    t = t.merge(rm[["ref_rent_m2_mix"]].reset_index(), on=["rent_vintage", "district_l2", "rooms_capped"], how="left")
    return t


# ------------------------------------------------------------------------ Singapore
def _sg_layers():
    ex = gpd.read_file(RAW / "singapore" / "mrt_station_exit.geojson").to_crs(SVY21)
    cbd = ex[ex["STATION_NA"].eq("RAFFLES PLACE MRT STATION")].geometry.union_all().centroid
    parks = gpd.read_file(RAW / "singapore" / "nparks_parks_nature_reserves.geojson").to_crs(SVY21)
    parks = parks[parks.geometry.area >= 10_000]
    return ex, cbd, parks


def _sg_geo(df: pd.DataFrame) -> pd.DataFrame:
    ex, cbd, parks = _sg_layers()
    keys = df[["block", "street_name", "lat", "lon"]].drop_duplicates(["block", "street_name"]).reset_index(drop=True)
    g = gpd.GeoDataFrame(keys, geometry=gpd.points_from_xy(keys["lon"], keys["lat"]), crs=4326).to_crs(SVY21)
    keys["dist_rail_m"] = _nearest_dist(g, ex)
    keys["dist_cbd_m"] = g.geometry.distance(cbd).to_numpy()
    keys["dist_park_m"] = _nearest_dist(g, parks)
    return df.merge(keys.drop(columns=["lat", "lon"]), on=["block", "street_name"], how="left")


def singapore_features() -> tuple[pd.DataFrame, pd.DataFrame]:
    t = pd.read_parquet(INTERIM / "transactions_singapore.parquet")
    t["street_name"] = t["address_street"]
    t = _sg_geo(t)
    info = pd.read_csv(RAW / "singapore" / "hdb_property_information.csv", dtype=str)
    info = info.rename(columns={"blk_no": "block", "street": "street_name"})
    info["block_max_floor"] = pd.to_numeric(info.get("max_floor_lvl"), errors="coerce")
    t = t.merge(info[["block", "street_name", "block_max_floor"]].drop_duplicates(["block", "street_name"]),
                on=["block", "street_name"], how="left")
    t.drop(columns="street_name").to_parquet(INTERIM / "features_singapore.parquet", index=False)

    r = pd.read_parquet(INTERIM / "rents_singapore.parquet")
    r = _sg_geo(r)
    r.to_parquet(INTERIM / "features_singapore_rent.parquet", index=False)
    print("singapore features", len(t), "rents", len(r))
    return t, r


if __name__ == "__main__":
    singapore_features()
    paris_features()


def singapore_private_features() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Distances for URA private sales and rentals, keyed on project location."""
    ex, cbd, parks = _sg_layers()

    def geo(df: pd.DataFrame) -> pd.DataFrame:
        keys = df[["lat", "lon"]].drop_duplicates().reset_index(drop=True)
        g = gpd.GeoDataFrame(keys, geometry=gpd.points_from_xy(keys["lon"], keys["lat"]), crs=4326).to_crs(SVY21)
        keys["dist_rail_m"] = _nearest_dist(g, ex)
        keys["dist_cbd_m"] = g.geometry.distance(cbd).to_numpy()
        keys["dist_park_m"] = _nearest_dist(g, parks)
        return df.merge(keys, on=["lat", "lon"], how="left")

    t = geo(pd.read_parquet(INTERIM / "transactions_singapore_private.parquet"))
    t.to_parquet(INTERIM / "features_singapore_private.parquet", index=False)
    r = geo(pd.read_parquet(INTERIM / "rents_singapore_private.parquet"))
    r.to_parquet(INTERIM / "features_singapore_private_rent.parquet", index=False)
    print("singapore private features", len(t), "rents", len(r))
    return t, r
