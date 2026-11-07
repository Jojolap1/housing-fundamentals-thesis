"""Fundamental value V* and the valuation gap, with a sensitivity grid.

    u   = r_f + tau + delta + gamma - g                       (user cost of housing)
    V*  = R / u                                               (Paris: freehold, perpetuity)
    V*  = R / u × [1 - ((1+g)/(1+i))^T],  i = u + g           (Singapore: HDB lease with T years left)
    gap = P_hat / V* - 1

R is the annual rent of the dwelling:
- Paris: matched unfurnished reference rent (€/m²/month) × 12 × floor area;
- Singapore: out-of-fold prediction of the HDB rent model (SGD/month) × 12, for the sold
  flat's type and location.
P_hat is the out-of-fold LightGBM prediction of the price (market value), so a dwelling is
never valued by a model that saw its own price.

The gap is a HYPOTHESIS TEST: a positive gap means prices exceed what rents capitalised
at the assumed user cost justify. It depends on the assumed parameters, which is why the
grid is published. It is not investment advice.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from src.config import INTERIM, MIN_N_PUBLISH, PROCESSED, RAW
from src.ratios.levels import LEVELS
from src.ratios.params import BASE, GRID, MIN_USER_COST


def rf_by_year(city: str) -> pd.Series:
    f = INTERIM / ("rf_paris.csv" if city == "Paris" else "rf_singapore.csv")
    r = pd.read_csv(f)
    r["year"] = r["month"].str[:4].astype(int)
    return (r.groupby("year")["rate_pct"].mean() / 100).rename("rf")


def _value(R, rf, p, T=None, rf_shift=0.0, gamma=None, g=None):
    gamma = p["gamma"] if gamma is None else gamma
    g = p["g"] if g is None else g
    u = rf + rf_shift + p["tau"] + p["delta"] + gamma - g
    u = np.where(u >= MIN_USER_COST, u, np.nan)
    V = R / u
    if T is not None:
        i = u + g
        V = V * (1 - ((1 + g) / (1 + i)) ** T)
    return V, u


def inputs(city: str) -> pd.DataFrame:
    if city == "Paris":
        d = pd.read_parquet(INTERIM / "oof_paris.parquet")
        d["R"] = 12 * d["rent_m2"] * d["floor_area_m2"]
        d["T"] = np.nan
    else:
        d = pd.read_parquet(INTERIM / "oof_singapore.parquet")
        rent = pd.read_parquet(INTERIM / "rent_model_on_sales_singapore.parquet")
        d = d.merge(rent, on="source_id", how="left")
        d["R"] = 12 * d["pred_rent_month"]
        d["T"] = d["lease_remaining_years"]
    d["P"] = d["price_local"]
    d["P_hat"] = np.exp(d["oof_log_LightGBM"]) * d["floor_area_m2"]
    d = d.merge(rf_by_year(city), left_on="year", right_index=True, how="left")
    return d


def run_city(city: str) -> pd.DataFrame:
    d = inputs(city)
    p = BASE[city]
    T = d["T"].to_numpy() if city == "Singapore" else None
    V, u = _value(d["R"].to_numpy(), d["rf"].to_numpy(), p, T)
    d["user_cost"], d["V_star"] = u, V
    d["V_star_m2"] = V / d["floor_area_m2"]
    d["gap"] = d["P_hat"] / V - 1
    d["gap_actual_price"] = d["P"] / V - 1
    d["mispricing_resid"] = np.log(d["P"]) - np.log(d["P_hat"])  # >0: dearer than comparables
    tag = city.lower()
    d.to_parquet(INTERIM / f"valuation_{tag}.parquet", index=False)

    for level, keys in LEVELS.items():
        g = d.groupby(keys + ["year"], dropna=False)
        a = g.agg(n=("gap", "size"), n_gap=("gap", "count"), gap_median=("gap", "median"),
                  gap_q25=("gap", lambda s: s.quantile(0.25)), gap_q75=("gap", lambda s: s.quantile(0.75)),
                  mispricing_median=("mispricing_resid", "median"),
                  vstar_m2_median=("V_star_m2", "median")).reset_index()
        a["publish"] = a["n_gap"] >= MIN_N_PUBLISH
        a[a["publish"]].to_csv(PROCESSED / f"valuation_{tag}_{level}.csv", index=False)

    # Sensitivity grid at city × year level.
    rows = []
    for rs, gm, gg in itertools.product(GRID["rf_shift"], GRID["gamma"], GRID["g"]):
        Vg, ug = _value(d["R"].to_numpy(), d["rf"].to_numpy(), p, T, rs, gm, gg)
        tmp = pd.DataFrame({"year": d["year"], "gap": d["P_hat"].to_numpy() / Vg - 1,
                            "vm2": Vg / d["floor_area_m2"].to_numpy(), "u": ug})
        for y, s in tmp.groupby("year"):
            ok = s["gap"].notna()
            rows.append({"city": city, "year": y, "rf_shift": rs, "gamma": gm, "g": gg,
                         "user_cost_median": s["u"].median(), "share_defined": ok.mean(),
                         "gap_median": s.loc[ok, "gap"].median(), "vstar_m2_median": s.loc[ok, "vm2"].median()})
    grid = pd.DataFrame(rows)
    grid.to_csv(PROCESSED / f"sensitivity_{tag}.csv", index=False)

    market = d.groupby("year").agg(price_m2_median=("price_per_m2_local", "median"),
                                   pred_price_m2_median=("P_hat", lambda s: (s / d.loc[s.index, "floor_area_m2"]).median()),
                                   rf=("rf", "first"), n=("P", "size"))
    base = d.groupby("year").agg(vstar_m2_base=("V_star_m2", "median"), gap_base=("gap", "median"))
    band = grid.groupby("year").agg(vstar_m2_lo=("vstar_m2_median", "min"), vstar_m2_hi=("vstar_m2_median", "max"),
                                    gap_lo=("gap_median", "min"), gap_hi=("gap_median", "max"))
    fv = market.join(base).join(band).reset_index()
    fv.insert(0, "city", city)
    fv.to_csv(PROCESSED / f"fundamental_vs_market_{tag}.csv", index=False)
    print(fv.round(3).to_string(index=False))
    return fv


def run() -> None:
    for city in ("Paris", "Singapore"):
        run_city(city)


if __name__ == "__main__":
    run()
