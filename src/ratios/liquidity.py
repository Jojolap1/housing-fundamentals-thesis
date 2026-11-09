"""Second pillar: market tension and liquidity.

Rents are a constrained expense (households must be housed), so a rent-capitalisation
value can "justify" high prices while the market is stuck: sellers do not cut prices
(loss aversion, Genesove & Mayer 2001) and the adjustment shows first in volumes and
time on market (Stein 1995). Time on market needs listing data, which are not open for
Paris or Singapore; the indicators below use open data only.

- turnover_per_1000: sales of the segment per 1,000 dwellings of the same segment in the
  stock. Paris: every DVF sale (nature "Vente") containing at least one apartment, over the
  apartments of the 2023 census (INSEE, by IRIS). Singapore HDB: resale transactions over
  the flats sold by HDB (HDB property information, *_sold columns), by HDB town.
- volume_change_pct, price_change_pct and divergence_pts = volume change − price change
  (percentage points), year on year, full calendar years only. Strongly negative values
  mean that volumes fall much faster than prices: a market that clears through quantity,
  not price.
- vacancy_pct (Paris only): vacant dwellings / all dwellings, 2023 census.
"""
from __future__ import annotations

import glob

import geopandas as gpd
import numpy as np
import pandas as pd

from src.config import INTERIM, PROCESSED, RAW

FULL_YEARS = {"paris": range(2022, 2026), "singapore": range(2017, 2026)}


# ------------------------------------------------------------------------- Paris
def paris_stock() -> pd.DataFrame:
    d = pd.read_csv(INTERIM / "insee_logement_iris_2023_paris_full.csv", dtype={"Code géographique": str})
    out = pd.DataFrame({
        "iris": d["Code géographique"],
        "dwellings": pd.to_numeric(d["Logements (princ)"], errors="coerce"),
        "vacant": pd.to_numeric(d["Logements vacants (princ)"], errors="coerce"),
        "apartments": pd.to_numeric(d["Appartements (princ)"], errors="coerce"),
    })
    out["arrondissement"] = out["iris"].str[3:5].astype(int)
    iris = gpd.read_file(RAW / "paris" / "contours_iris_paris.geojson")
    code = next(c for c in ("code_iris", "iris", "CODE_IRIS") if c in iris.columns)
    q = gpd.read_file(RAW / "paris" / "quartiers.geojson")[["c_qu", "geometry"]].to_crs(2154)
    pts = iris[[code, "geometry"]].to_crs(2154)
    pts["geometry"] = pts.geometry.representative_point()
    j = gpd.sjoin(pts, q, predicate="within")[[code, "c_qu"]].rename(columns={code: "iris", "c_qu": "quartier"})
    return out.merge(j, on="iris", how="left")


def paris_sales() -> pd.DataFrame:
    """All DVF sales containing at least one apartment, one row per mutation."""
    d = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(str(RAW / "paris" / "dvf_75_*.csv.gz")))])
    d = d.drop_duplicates()
    d = d[d["nature_mutation"].eq("Vente") & d["type_local"].eq("Appartement")]
    m = d.groupby("id_mutation").agg(date=("date_mutation", "first"), commune=("code_commune", "first"),
                                     lat=("latitude", "first"), lon=("longitude", "first")).reset_index()
    m["year"] = m["date"].str[:4].astype(int)
    m["arrondissement"] = m["commune"].str[-2:].astype(int)
    q = gpd.read_file(RAW / "paris" / "quartiers.geojson")[["c_qu", "geometry"]].to_crs(4326)
    g = gpd.GeoDataFrame(m, geometry=gpd.points_from_xy(pd.to_numeric(m["lon"]), pd.to_numeric(m["lat"])), crs=4326)
    g = gpd.sjoin(g, q, how="left", predicate="within")
    m["quartier"] = g.loc[~g.index.duplicated(), "c_qu"].reindex(m.index)
    return m


# --------------------------------------------------------------------- Singapore
def hdb_stock() -> pd.DataFrame:
    """Flats sold by HDB per town. The town of each block's contract code is inferred from
    the resale file (same block and street), not from a hand-written table."""
    info = pd.read_csv(RAW / "singapore" / "hdb_property_information.csv", dtype=str)
    sold = [c for c in info.columns if c.endswith("_sold")]
    info["flats_sold"] = info[sold].apply(pd.to_numeric, errors="coerce").sum(axis=1)
    rs = pd.read_csv(RAW / "singapore" / "hdb_resale_2017on.csv", usecols=["town", "block", "street_name"], dtype=str)
    m = info.merge(rs.drop_duplicates(), left_on=["blk_no", "street"], right_on=["block", "street_name"], how="left")
    code_town = m.dropna(subset=["town"]).groupby("bldg_contract_town")["town"].agg(lambda s: s.mode().iloc[0])
    info["town"] = info["bldg_contract_town"].map(code_town)
    pd.DataFrame({"contract_code": code_town.index, "town": code_town.values}).to_csv(
        PROCESSED / "hdb_contract_town_codes_inferred.csv", index=False)
    unmapped = info.loc[info["town"].isna() & (info["flats_sold"] > 0), "flats_sold"].sum()
    print("HDB flats sold in blocks whose town code could not be inferred:", int(unmapped))
    return info.groupby("town")["flats_sold"].sum().rename("stock").reset_index()


# ---------------------------------------------------------------------- measures
def _changes(t: pd.DataFrame, keys: list[str], years) -> pd.DataFrame:
    t = t[t["year"].isin(years)].sort_values(keys + ["year"]).copy()
    g = t.groupby(keys)
    for c, src in (("volume_change_pct", "sales"), ("price_change_pct", "ppm2_median")):
        prev = g[src].shift(1)
        t[c] = np.where(g["year"].shift(1) == t["year"] - 1, 100 * (t[src] / prev - 1), np.nan)
    t["divergence_pts"] = t["volume_change_pct"] - t["price_change_pct"]
    return t


def paris(level: str) -> pd.DataFrame:
    stock = paris_stock()
    sales = paris_sales()
    prices = pd.read_parquet(INTERIM / "transactions_paris.parquet")
    key = {"city": None, "arrondissement": "arrondissement", "quartier": "quartier"}[level]
    if key is None:
        stock["k"], sales["k"], prices["k"] = 1, 1, 1
        key = "k"
    else:
        prices[key] = prices["district_l1"] if key == "arrondissement" else prices["district_l2"]
    st = stock.groupby(key)[["apartments", "dwellings", "vacant"]].sum()
    v = sales.groupby([key, "year"]).size().rename("sales")
    p = prices.groupby([key, "year"])["price_per_m2_local"].median().rename("ppm2_median")
    t = pd.concat([v, p], axis=1).reset_index().merge(st.reset_index(), on=key, how="left")
    # 2021 and 2026 are half-years in DVF: turnover is annualised (x2), changes use full years only.
    half = t["year"].isin([2021, 2026])
    t["turnover_per_1000"] = 1000 * t["sales"] * np.where(half, 2, 1) / t["apartments"]
    t["vacancy_pct"] = 100 * t["vacant"] / t["dwellings"]
    t = t.merge(_changes(t, [key], FULL_YEARS["paris"])[[key, "year", "volume_change_pct", "price_change_pct",
                                                           "divergence_pts"]], on=[key, "year"], how="left")
    return t.rename(columns={"k": "city"}) if key == "k" else t


def singapore() -> pd.DataFrame:
    stock = hdb_stock()
    t = pd.read_parquet(INTERIM / "transactions_singapore.parquet")
    # Volume: every resale in the source file (liquidity); price: the cleaned sample.
    raw = pd.read_csv(RAW / "singapore" / "hdb_resale_2017on.csv", usecols=["month", "town"], dtype=str)
    raw["year"] = raw["month"].str[:4].astype(int)
    vol = raw.groupby(["town", "year"]).size().rename("sales")
    pr = t.groupby(["hdb_town", "year"])["price_per_m2_local"].median().rename("ppm2_median")
    pr.index = pr.index.set_names(["town", "year"])
    v = pd.concat([vol, pr], axis=1).reset_index().merge(stock, on="town", how="left")
    # 2026 runs to November: annualise turnover by the number of months observed.
    months = t[t["year"] == 2026]["date"].dt.month.nunique() or 12
    v["turnover_per_1000"] = 1000 * v["sales"] * np.where(v["year"] == 2026, 12 / months, 1) / v["stock"]
    ch = _changes(v, ["town"], FULL_YEARS["singapore"])
    return v.merge(ch[["town", "year", "volume_change_pct", "price_change_pct", "divergence_pts"]],
                   on=["town", "year"], how="left")


def main() -> None:
    for level in ("city", "arrondissement", "quartier"):
        paris(level).round(3).to_csv(PROCESSED / f"liquidity_paris_{level}.csv", index=False)
    sg = singapore()
    sg.round(3).to_csv(PROCESSED / "liquidity_singapore_town.csv", index=False)
    tot = sg.groupby("year").agg(sales=("sales", "sum"), stock=("stock", "sum"))
    tot["turnover_per_1000"] = 1000 * tot["sales"] / tot["stock"]
    tot.round(3).to_csv(PROCESSED / "liquidity_singapore_city.csv")
    singapore_private_volume().round(3).to_csv(PROCESSED / "liquidity_singapore_private_city.csv", index=False)
    ura_developer_stock().round(2).to_csv(PROCESSED / "liquidity_singapore_private_developer.csv", index=False)
    rent_burden().to_csv(PROCESSED / "rent_burden_pct.csv")
    print(pd.read_csv(PROCESSED / "liquidity_paris_city.csv").round(2).to_string(index=False))
    print(tot.round(1).to_string())



def ura_developer_stock() -> pd.DataFrame:
    """Private new-launch market (URA developer sales), monthly:
    - sold_in_month: units sold by developers in the month;
    - unsold_launched: launched to date − sold to date (unsold units already on the market);
    - unsold_total: units in the projects − sold to date (including units not yet launched);
    - months_of_supply: unsold_launched / mean monthly sales over the last 12 months (developer
      sales are lumpy, driven by launches, so a short window is too noisy).
    The URA service returns data for about the last 3 years only (empty before Nov 2023).
    Executive Condominiums are reported separately by URA's propertyType and kept apart."""
    import json as _json

    rows = []
    for f in sorted(glob.glob(str(RAW / "singapore" / "ura" / "developer_sales" / "dev_sales_*.json"))):
        ym = f.split("_")[-1][:6]
        for p in _json.load(open(f)):
            for s in p.get("developerSales", []):
                rows.append({"month": f"{ym[:4]}-{ym[4:]}", "segment": p.get("marketSegment"),
                             "ptype": p.get("propertyType"), "project": p.get("project"),
                             "launched": s.get("launchedToDate"), "sold_to_date": s.get("soldToDate"),
                             "units": s.get("unitsAvail"), "sold_in_month": s.get("soldInMonth")})
    d = pd.DataFrame(rows)
    for c in ("launched", "sold_to_date", "units", "sold_in_month"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["is_ec"] = d["ptype"].astype(str).str.contains("Exec", case=False)  # URA label: "Exec Condo"
    d = d[~d["is_ec"]]
    m = d.groupby("month").agg(projects=("project", "nunique"), sold_in_month=("sold_in_month", "sum"),
                               launched=("launched", "sum"), sold_to_date=("sold_to_date", "sum"),
                               units=("units", "sum")).reset_index()
    m["unsold_launched"] = m["launched"] - m["sold_to_date"]
    m["unsold_total"] = m["units"] - m["sold_to_date"]
    m = m[m["projects"] > 0].reset_index(drop=True)
    m["sales_12m_avg"] = m["sold_in_month"].rolling(12).mean()
    m["months_of_supply"] = m["unsold_launched"] / m["sales_12m_avg"]
    return m


def rent_burden() -> pd.DataFrame:
    """Rent-to-income ratio (taux d'effort), median by year.
    Paris: reference rent of a 60 m² dwelling at the matched €/m² rent, × 12, over the IRIS
    median disposable income per consumption unit × 1.5 UC (couple, Filosofi 2021).
    Singapore HDB and private: monthly rent of the sold home (matched rent) over the
    planning-area median monthly household income from work (Census 2020).
    Incomes are fixed at their single available year, so rising ratios also reflect income
    growth that is not observed."""
    out = []
    p = pd.read_parquet(INTERIM / "ratios_input_paris.parquet")
    p["rent_to_income"] = 12 * 60 * p["rent_m2"] / (1.5 * p["income_uc"])
    out.append(p.groupby("year")["rent_to_income"].median().rename("Paris"))
    h = pd.read_parquet(INTERIM / "ratios_input_singapore.parquet")
    h["rent_to_income"] = h["rent_month"] / h["median_hh_income_work_month"]
    out.append(h.groupby("year")["rent_to_income"].median().rename("Singapore HDB"))
    s = pd.read_parquet(INTERIM / "ratios_input_singapore_private.parquet")
    s["rent_to_income"] = s["rent_month"] / s["median_hh_income_work_month"]
    out.append(s.groupby("year")["rent_to_income"].median().rename("Singapore private"))
    return (100 * pd.concat(out, axis=1)).round(1)


def singapore_private_volume() -> pd.DataFrame:
    """Yearly volume of private non-landed sales (all URA Apartment/Condominium transactions,
    single units) and the median price/m² of the cleaned sample. No stock series is open, so
    no turnover rate for the private market."""
    from src.clean.singapore_private import _load

    raw = _load("transactions_batch*.json", "transaction")
    raw = raw[raw["propertyType"].isin(["Apartment", "Condominium"]) & raw["noOfUnits"].astype(int).eq(1)]
    raw["year"] = ("20" + raw["contractDate"].str[2:]).astype(int)
    vol = raw.groupby("year").size().rename("sales")
    t = pd.read_parquet(INTERIM / "transactions_singapore_private.parquet")
    pr = t.groupby("year")["price_per_m2_local"].median().rename("ppm2_median")
    v = pd.concat([vol, pr], axis=1).reset_index()
    v["k"] = 1
    ch = _changes(v, ["k"], range(2022, 2026))
    return v.merge(ch[["year", "volume_change_pct", "price_change_pct", "divergence_pts"]], on="year", how="left").drop(columns="k")


if __name__ == "__main__":
    main()
