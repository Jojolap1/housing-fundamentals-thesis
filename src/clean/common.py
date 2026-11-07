"""Shared pieces of the cleaning stage: harmonised schema, FX conversion, removal log."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.config import INTERIM, PROCESSED, RAW

# Harmonised transaction schema (one tidy table per city).
SCHEMA = [
    "city", "date", "year", "price_local", "currency", "price_eur", "price_usd", "floor_area_m2",
    "price_per_m2_local", "price_per_m2_eur", "rooms_or_flat_type", "property_type", "tenure",
    "lease_remaining_years", "address_street", "street_id", "district_l1", "district_l2",
    "lat", "lon", "source_id",
]


def fx_monthly() -> pd.DataFrame:
    """Monthly average ECB reference rates: columns month (Period[M]), SGD, USD (units per EUR)."""
    fx = pd.read_csv(RAW / "fx" / "ecb_eurofxref_sgd_usd.csv", usecols=["CURRENCY", "TIME_PERIOD", "OBS_VALUE"])
    fx["month"] = pd.PeriodIndex(fx["TIME_PERIOD"], freq="M")
    return fx.pivot_table(index="month", columns="CURRENCY", values="OBS_VALUE", aggfunc="mean").reset_index()


def add_fx(df: pd.DataFrame, currency: str) -> pd.DataFrame:
    """Add EUR and USD prices using the monthly average ECB rate of the transaction month."""
    fx = fx_monthly()
    df = df.copy()
    df["month"] = df["date"].dt.to_period("M")
    df = df.merge(fx, on="month", how="left")
    if df["USD"].isna().any():
        missing = sorted(df.loc[df["USD"].isna(), "month"].astype(str).unique())
        raise ValueError(f"no ECB rate for months {missing}")
    if currency == "EUR":
        df["price_eur"] = df["price_local"]
    else:
        df["price_eur"] = df["price_local"] / df[currency]
    df["price_usd"] = df["price_eur"] * df["USD"]
    df["fx_local_per_eur"] = 1.0 if currency == "EUR" else df[currency]
    df["fx_usd_per_eur"] = df["USD"]
    return df.drop(columns=[c for c in ("SGD", "USD", "month") if c in df.columns])


@dataclass
class RemovalLog:
    """Counts every filtering step and keeps the identifiers of removed rows."""
    city: str
    steps: list[dict] = field(default_factory=list)
    removed: list[pd.DataFrame] = field(default_factory=list)

    def apply(self, df: pd.DataFrame, keep: pd.Series, step: str, rule: str, id_col: str) -> pd.DataFrame:
        keep = keep.fillna(False).astype(bool)
        gone = df.loc[~keep, [id_col]].copy()
        gone["step"] = step
        self.removed.append(gone.rename(columns={id_col: "source_id"}))
        self.steps.append({"city": self.city, "step": step, "rule": rule, "rows_before": len(df),
                           "rows_removed": int((~keep).sum()), "rows_after": int(keep.sum())})
        return df.loc[keep].copy()

    def save(self) -> pd.DataFrame:
        summary = pd.DataFrame(self.steps)
        summary.to_csv(PROCESSED / f"cleaning_log_{self.city}.csv", index=False)
        if self.removed:
            pd.concat(self.removed).to_csv(INTERIM / f"removed_rows_{self.city}.csv.gz", index=False)
        return summary


def quantile_trim_by_group(df: pd.DataFrame, value: str, groups: list[str], lo: float = 0.01, hi: float = 0.99) -> pd.Series:
    """True where `value` lies within the [lo, hi] quantiles of its group."""
    g = df.groupby(groups)[value]
    return df[value].between(g.transform(lambda s: s.quantile(lo)), g.transform(lambda s: s.quantile(hi)))


def within_factor_of_median(df: pd.DataFrame, value: str, groups: list[str], factor: float = 3.0) -> pd.Series:
    """True where `value` lies within [median / factor, median × factor] of its group.

    Removes non-market prices (symbolic €1 transfers, life-annuity sales, partial shares)
    that can exceed 1% of a group, so a percentile trim alone would not catch them."""
    med = df.groupby(groups)[value].transform("median")
    return df[value].between(med / factor, med * factor)
