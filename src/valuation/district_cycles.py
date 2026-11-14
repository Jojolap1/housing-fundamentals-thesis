"""Were cheaper districts already doing worse before interest rates rose?

The cross-section test (value_effect) found that Paris quartiers with low prices fell more
between 2021-22 and 2025-26. That could be an old trend and not an effect of the 2022 rise in
rates. This module rebuilds district prices over a long period from sources that go back
further than the main dataset:
- Paris: DVF+ open-data, sales of single apartments, 2014 to 2025, by quartier;
- Singapore public flats: registered resales, 1990 to date, by HDB town.
No long public transaction file was found for private homes in Singapore.

For every year t, the change in a district's quality-adjusted log price between t-1 and t is
regressed on its price level two and three years earlier (average of t-3 and t-2, so that
the level and the change share no observation). A positive slope means dearer districts
gained more (or lost less) that year. The series of slopes shows whether a relation appears
at a given date or was there all along. Districts are also grouped in three by their price
level in a fixed early window, and an index is published for each group.

Fixed before the results: district × year cells with fewer than 20 sales are dropped;
Paris groups are formed on 2014-2016, HDB groups on 2009-2011 (before the lending caps of
2013); characteristics' coefficients are estimated within district × year cells.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from src.config import PROCESSED, RAW
from src.valuation.value_effect import ols_robust, quality_adjust

MIN_CELL = 20
BASE = {"paris": (2014, 2016), "singapore": (2009, 2011)}


# ----------------------------------------------------------------------------- loaders
def paris_sales() -> tuple[pd.DataFrame, list[dict]]:
    import geopandas as gpd

    from src.clean.paris import quartiers

    use = ["datemut", "libnatmut", "vefa", "valeurfonc", "nblocapt", "nbapt1pp", "nbapt2pp", "nbapt3pp", "nbapt4pp",
           "nbapt5pp", "sbati", "sbatapt", "nblocdep", "libtypbien", "geompar_x", "geompar_y"]
    d = pd.read_csv(RAW / "dvfplus" / "dvf_plus_d75.csv", sep="|", usecols=use, dtype=str)
    log = [{"step": "0_raw", "rows": len(d)}]

    def keep(mask, step):
        nonlocal d
        d = d[mask].copy()
        log.append({"step": step, "rows": len(d)})

    keep(d["libnatmut"].eq("Vente") & d["vefa"].str.lower().ne("true"), "1_sale_of_existing_dwelling")
    keep(d["libtypbien"].eq("UN APPARTEMENT"), "2_single_apartment")
    d["price_local"] = pd.to_numeric(d["valeurfonc"], errors="coerce")
    d["floor_area_m2"] = pd.to_numeric(d["sbatapt"], errors="coerce")
    keep((d["price_local"] > 0) & d["floor_area_m2"].between(9, 400), "3_price_area_plausible")
    x, y = pd.to_numeric(d["geompar_x"], errors="coerce"), pd.to_numeric(d["geompar_y"], errors="coerce")
    crs = 4326 if x.abs().median() < 180 else 2154
    pts = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(x, y), crs=crs).to_crs(4326)
    pts = gpd.sjoin(pts, quartiers(), how="left", predicate="within").drop(columns="index_right")
    d = pd.DataFrame(pts[~pts.index.duplicated()].drop(columns="geometry"))
    keep(d["quartier_code"].notna(), f"4_located_in_a_quartier (coordinates read as EPSG:{crs})")
    d["date"] = pd.to_datetime(d["datemut"])
    d["year"] = d["date"].dt.year
    d["ppm2"] = d["price_local"] / d["floor_area_m2"]
    med = d.groupby(["arrondissement", "year"])["ppm2"].transform("median")
    keep(d["ppm2"].between(med / 3, med * 3), "5_price_per_m2_within_factor_3_of_arrondissement_year_median")
    rooms = d[[f"nbapt{k}pp" for k in range(1, 6)]].apply(pd.to_numeric, errors="coerce").to_numpy().argmax(axis=1) + 1
    out = pd.DataFrame({"unit": d["quartier_code"].astype(int).astype(str), "year": d["year"], "log_ppm2": np.log(d["ppm2"]),
                        "log_area": np.log(d["floor_area_m2"]), "rooms": rooms.astype(str),
                        "n_dependances": pd.to_numeric(d["nblocdep"], errors="coerce").fillna(0).clip(upper=3)})
    return out, log


def hdb_sales() -> tuple[pd.DataFrame, list[dict]]:
    files = sorted((RAW / "volumes").glob("hdb_resale_*.csv")) + [RAW / "singapore" / "hdb_resale_2017on.csv"]
    d = pd.concat([pd.read_csv(f, dtype=str) for f in files if f.exists()], ignore_index=True)
    log = [{"step": "0_raw", "rows": len(d)}]
    d["year"] = d["month"].str.slice(0, 4).astype(int)
    price, area = pd.to_numeric(d["resale_price"], errors="coerce"), pd.to_numeric(d["floor_area_sqm"], errors="coerce")
    lo = d["storey_range"].str.extract(r"(\d+)\D+(\d+)").astype(float)
    out = pd.DataFrame({"unit": d["town"].str.upper().str.strip(), "year": d["year"], "log_ppm2": np.log(price / area),
                        "log_area": np.log(area), "storey_mid": lo.mean(axis=1),
                        "age": d["year"] - pd.to_numeric(d["lease_commence_date"], errors="coerce"),
                        "flat_type": d["flat_type"].str.upper().str.replace("-", " ", regex=False).str.strip(),
                        "flat_model": d["flat_model"].str.upper().str.strip()})
    out = out[np.isfinite(out["log_ppm2"]) & out["age"].between(0, 99)]
    log.append({"step": "1_valid_price_area_age", "rows": len(out)})
    return out, log


SOURCES = {"paris": (paris_sales, ["log_area", "n_dependances"], ["rooms"]),
           "singapore": (hdb_sales, ["log_area", "storey_mid", "age"], ["flat_type", "flat_model"])}


# ---------------------------------------------------------------------------- analysis
def district_year(t: pd.DataFrame, numeric: list[str], categorical: list[str]) -> pd.DataFrame:
    """Mean quality-adjusted log price per district and year (cells with at least MIN_CELL sales)."""
    t = t.copy()
    t["adj"] = quality_adjust(t, numeric, categorical, ["unit", "year"])
    g = t.groupby(["unit", "year"])["adj"].agg(["mean", "count"])
    return g[g["count"] >= MIN_CELL]["mean"].unstack("year")


def yearly_slopes(p: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for y in p.columns:
        if not {y - 3, y - 2, y - 1}.issubset(p.columns):
            continue
        d = pd.DataFrame({"level": p[[y - 3, y - 2]].mean(axis=1), "change": 100 * (p[y] - p[y - 1])}).dropna()
        if len(d) < 15:
            continue
        b, se = ols_robust(d["change"].to_numpy(), d[["level"]].to_numpy())
        rows.append({"year": y, "districts": len(d), "mean_change_pct": d["change"].mean(),
                     "slope": b[1], "slope_se": se[1], "t": b[1] / se[1],
                     "change_for_10pct_dearer": b[1] * np.log(1.1)})
    return pd.DataFrame(rows)


def group_index(p: pd.DataFrame, base: tuple[int, int]) -> pd.DataFrame:
    level = p[[y for y in range(base[0], base[1] + 1) if y in p.columns]].mean(axis=1).dropna()
    lo, hi = level.quantile([1 / 3, 2 / 3])
    group = pd.Series(np.where(level <= lo, "cheapest third", np.where(level >= hi, "dearest third", "middle third")), index=level.index)
    full = p.loc[level.index].dropna(axis=0, thresh=int(0.8 * p.shape[1]))  # districts observed in most years
    m = full.groupby(group.reindex(full.index)).mean().T
    ref = base[1] + 1 if base[1] + 1 in m.index else m.index[0]
    out = (100 * np.exp(m - m.loc[ref])).rename_axis("year").reset_index().melt("year", var_name="group", value_name="index")
    n = group.reindex(full.index).value_counts()
    return out.assign(districts=out["group"].map(n), reference_year=ref)


def run() -> None:
    slopes, groups, logs = [], [], []
    for city, (loader, numeric, categorical) in SOURCES.items():
        try:
            t, log = loader()
        except FileNotFoundError as e:
            print(city, "skipped:", e)
            continue
        logs += [{"city": city, **r} for r in log]
        p = district_year(t, numeric, categorical)
        print(city, "districts", p.shape[0], "years", int(p.columns.min()), int(p.columns.max()), "sales", len(t))
        s = yearly_slopes(p).assign(city=city)
        print(s[["year", "districts", "mean_change_pct", "slope", "t"]].round(2).to_string(index=False))
        slopes.append(s)
        groups.append(group_index(p, BASE[city]).assign(city=city))
    if slopes:
        pd.concat(slopes).round(3).to_csv(PROCESSED / "district_cycle_slopes.csv", index=False)
        pd.concat(groups).round(2).to_csv(PROCESSED / "district_cycle_groups.csv", index=False)
        pd.DataFrame(logs).to_csv(PROCESSED / "district_cycle_cleaning.csv", index=False)


if __name__ == "__main__":
    run()
