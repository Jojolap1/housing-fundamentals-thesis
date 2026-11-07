"""Price, rent, yield and price-to-income statistics at city, district_l1, district_l2 and
street level, per year.

Definitions (also in docs/methodology.md):
- price/m²: median and IQR (q25, q75) of transaction price per m², local currency and EUR.
- n: number of retained transactions (liquidity).
- yoy_pct: change of the median price/m² against the same unit one year earlier.
- chg_window_pct: change of the median price/m² over the longest window with full years
  available (Paris 2022 -> 2025; Singapore 2020 -> 2025).
- rent: Paris = matched unfurnished reference rent (€/m²/month, see features/build.py);
  Singapore = matched median HDB rent per flat (SGD/month) for the same flat type.
- gross_yield = 12 × monthly rent / price, computed per transaction, then the median is taken.
  price_to_rent = 1 / gross_yield (also per transaction, then median).
- price_to_income: Paris = price of a 60 m² dwelling at the transaction's price/m², divided
  by the IRIS median annual disposable income per consumption unit (INSEE Filosofi 2021)
  (`pti_uc`), and by that income × 1.5 UC for a reference couple (`pti_hh`).
  Singapore = 4-room HDB resale price / (12 × planning-area median monthly household income
  from work, Census 2020, interpolated from income bands).
Every group with n < MIN_N_PUBLISH is flagged `publish = False`; site exports drop those.
"""
from __future__ import annotations

import zipfile

import numpy as np
import pandas as pd

from src.config import INTERIM, MIN_N_PUBLISH, PROCESSED, RAW
from src.ratios.params import PTI_REF

LEVELS = {
    "city": ["city"],
    "district_l1": ["city", "district_l1"],
    "district_l2": ["city", "district_l1", "district_l2"],
    "street": ["city", "district_l1", "street_id"],
}
WINDOW = {"Paris": (2022, 2025), "Singapore": (2020, 2025)}


# ------------------------------------------------------------------- income inputs
def paris_income() -> pd.DataFrame:
    with zipfile.ZipFile(RAW / "paris" / "filosofi_iris_2021_DISP.zip") as z:
        name = next(n for n in z.namelist() if n.endswith(".csv") and "meta" not in n.lower())
        d = pd.read_csv(z.open(name), sep=";", dtype=str)
    d = d[d["IRIS"].str.startswith("751")]
    d["income_uc"] = pd.to_numeric(d["DISP_MED21"].str.replace(",", "."), errors="coerce")
    return d[["IRIS", "income_uc"]].rename(columns={"IRIS": "iris"})


def interpolated_median(row: pd.Series, bands: list[tuple[str, float, float]]) -> float:
    """Median of a banded distribution by linear interpolation inside the median band."""
    counts = np.array([float(row[c]) for c, _, _ in bands])
    half, cum = counts.sum() / 2, 0.0
    for (c, lo, hi), n in zip(bands, counts):
        if cum + n >= half:
            if np.isinf(hi):
                return np.nan  # median inside the open-ended top band: not identifiable
            return lo + (half - cum) / n * (hi - lo)
        cum += n
    return np.nan


def singapore_income() -> pd.DataFrame:
    d = pd.read_csv(RAW / "singapore" / "census2020_hh_income_work_by_pa.csv", dtype=str)
    cols = [c for c in d.columns if c not in ("_id", "Number", "Total", "NoEmployedPerson")]

    def bounds(c: str) -> tuple[float, float]:
        if c == "Below_1_000":
            return 0, 1000
        if c == "20_000andOver":
            return 20000, np.inf
        a = c.split("_")
        lo = float(a[0] + a[1])
        hi = float(a[2] + a[3]) + 1
        return lo, hi

    bands = [(c, *bounds(c)) for c in cols]
    d["median_hh_income_work_month"] = d.apply(lambda r: interpolated_median(r, bands), axis=1)
    d["planning_area"] = d["Number"].str.upper()
    out = d[~d["planning_area"].isin(["TOTAL", "OTHERS"])][["planning_area", "median_hh_income_work_month"]]
    out.to_csv(PROCESSED / "singapore_income_by_planning_area.csv", index=False)
    return out


# ------------------------------------------------------------- per-transaction ratios
def paris_transactions() -> pd.DataFrame:
    t = pd.read_parquet(INTERIM / "features_paris.parquet")
    t["rent_m2"] = t["ref_rent_m2_exact"].fillna(t["ref_rent_m2_mix"])
    t["rent_source"] = np.where(t["ref_rent_m2_exact"].notna(), "exact_cell",
                                np.where(t["ref_rent_m2_mix"].notna(), "period_mix", "none"))
    t["gross_yield"] = 12 * t["rent_m2"] / t["price_per_m2_local"]
    t["price_to_rent"] = 1 / t["gross_yield"]
    t = t.merge(paris_income(), on="iris", how="left")
    ref = PTI_REF["Paris"]
    t["pti_uc"] = t["price_per_m2_local"] * ref["area_m2"] / t["income_uc"]
    t["pti_hh"] = t["pti_uc"] / ref["household_uc"]
    return t


def singapore_transactions() -> pd.DataFrame:
    t = pd.read_parquet(INTERIM / "features_singapore.parquet")
    r = pd.read_parquet(INTERIM / "features_singapore_rent.parquet")
    t["flat_type"] = t["rooms_or_flat_type"]
    # Hierarchical rent match: block -> subzone -> planning area, same flat type and year,
    # each level used only if it has at least MIN_N_PUBLISH rental approvals.
    t["rent_month"] = np.nan
    t["rent_source"] = "none"
    for level, keys in [("block", ["block", "street_name"]), ("subzone", ["subzone"]),
                        ("planning_area", ["planning_area"])]:
        g = r.groupby(keys + ["flat_type", "year"])["monthly_rent"].agg(["median", "size"])
        g = g[g["size"] >= MIN_N_PUBLISH]["median"].rename("m").reset_index()
        left = t.rename(columns={"address_street": "street_name", "district_l2": "subzone",
                                 "district_l1": "planning_area"})
        m = left.merge(g, on=keys + ["flat_type", "year"], how="left")["m"].to_numpy()
        fill = np.isnan(t["rent_month"].to_numpy()) & ~np.isnan(m)
        t.loc[fill, "rent_month"] = m[fill]
        t.loc[fill, "rent_source"] = level
    t["gross_yield"] = 12 * t["rent_month"] / t["price_local"]
    t["price_to_rent"] = 1 / t["gross_yield"]
    t["rent_m2"] = t["rent_month"] / t["floor_area_m2"]  # secondary; area is the sold flat's
    inc = singapore_income().rename(columns={"planning_area": "district_l1"})
    t = t.merge(inc, on="district_l1", how="left")
    t["pti_hh"] = np.where(t["flat_type"].eq(PTI_REF["Singapore"]["flat_type"]),
                           t["price_local"] / (12 * t["median_hh_income_work_month"]), np.nan)
    return t


# --------------------------------------------------------------------- aggregation
def _q(p):
    f = lambda s: s.quantile(p)  # noqa: E731
    f.__name__ = f"q{int(p * 100)}"
    return f


def aggregate(t: pd.DataFrame, level: str) -> pd.DataFrame:
    keys = LEVELS[level] + ["year"]
    g = t.groupby(keys, dropna=False)
    out = g.agg(
        n=("price_per_m2_local", "size"),
        ppm2_median=("price_per_m2_local", "median"),
        ppm2_q25=("price_per_m2_local", _q(0.25)),
        ppm2_q75=("price_per_m2_local", _q(0.75)),
        ppm2_eur_median=("price_per_m2_eur", "median"),
        rent_m2_median=("rent_m2", "median"),
        gross_yield_median=("gross_yield", "median"),
        price_to_rent_median=("price_to_rent", "median"),
        pti_hh_median=("pti_hh", "median"),
        n_with_rent=("gross_yield", "count"),
    ).reset_index()
    if "pti_uc" in t:
        out = out.merge(g["pti_uc"].median().rename("pti_uc_median").reset_index(), on=keys)
    if "rent_month" in t:
        out = out.merge(g["rent_month"].median().rename("rent_month_median").reset_index(), on=keys)
    unit = LEVELS[level]
    out = out.sort_values(unit + ["year"])
    prev = out.groupby(unit, dropna=False)["ppm2_median"].shift(1)
    prev_year = out.groupby(unit, dropna=False)["year"].shift(1)
    out["yoy_pct"] = np.where(prev_year == out["year"] - 1, 100 * (out["ppm2_median"] / prev - 1), np.nan)
    city = t["city"].iloc[0]
    a, b = WINDOW[city]
    w = out.pivot_table(index=unit, columns="year", values="ppm2_median", dropna=False)
    if a in w and b in w:
        chg = (100 * (w[b] / w[a] - 1)).rename(f"chg_{a}_{b}_pct").reset_index()
        out = out.merge(chg, on=unit, how="left")
    out["level"] = level
    out["publish"] = out["n"] >= MIN_N_PUBLISH
    return out


def run() -> dict[str, pd.DataFrame]:
    res = {}
    for city, fn in [("paris", paris_transactions), ("singapore", singapore_transactions)]:
        t = fn()
        t.to_parquet(INTERIM / f"ratios_input_{city}.parquet", index=False)
        for level in LEVELS:
            a = aggregate(t, level)
            # Only publishable cells (n >= MIN_N_PUBLISH) are written: data/processed is public.
            a[a["publish"]].to_csv(PROCESSED / f"stats_{city}_{level}.csv", index=False)
            res[f"{city}_{level}"] = a
        src = t["rent_source"].value_counts(normalize=True).round(4).rename("share").reset_index()
        src.to_csv(PROCESSED / f"rent_match_{city}.csv", index=False)
        print(city, "rent match:", dict(zip(src["rent_source"], src["share"])))
    return res


if __name__ == "__main__":
    run()
