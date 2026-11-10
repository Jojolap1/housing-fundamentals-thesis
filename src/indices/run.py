"""Quality-adjusted price indices and a transaction-volume index, per city and quarter.

Three price indices are built from the same cleaned sales so they can be compared:
hedonic time-dummy (pooled and rolling), stratified median, and repeat-sales. They are then
set against the official index of the market (when its file has been downloaded, see
src/ingest/official_indices.py) as a validation check. Differences are reported, not tuned.

Outputs (data/processed):
  index_<city>.csv             period, hedonic, hedonic_rolling, stratified, repeat_sales,
                               volume, n, [official]; all indices = 100 in the first period
  index_meta_<city>.json       columns actually used, strata coverage, number of pairs
  index_validation_<city>.csv  comparison with the official index on the common quarters
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.config import INTERIM, PROCESSED, RAW
from src.indices.hedonic import rolling_time_dummy_index, time_dummy_index
from src.indices.repeat_sales import make_pairs, repeat_sales_index
from src.indices.stratified import stratified_median_index

# Columns are used only if present in the city's file; index_meta records what was used.
CONFIG = {
    "paris": {
        "numeric": ["log_area", "n_dependances"],
        "categorical": ["district_l2", "rooms_or_flat_type", "epoque"],
        "strata": ["district_l1", "rooms_cap"],
        "unit": ["id_parcelle", "lot1_numero"], "unit_is_dwelling": True,
        "official": "notaires_insee_paris_apartments.csv",
    },
    "singapore": {
        "numeric": ["log_area", "storey_mid", "lease_remaining_years"],
        "categorical": ["hdb_town", "rooms_or_flat_type", "flat_model"],
        "strata": ["hdb_town", "rooms_or_flat_type"],
        # HDB publishes block and storey band, not the unit: a proxy, not a dwelling.
        "unit": ["block", "address_street", "rooms_or_flat_type", "storey_range", "floor_area_m2"],
        "unit_is_dwelling": False,
        "official": "hdb_resale_price_index.csv",
    },
    "singapore_private": {
        # lease_term: remaining lease in years, 0 for freehold (the freehold dummy carries the level)
        "numeric": ["log_area", "storey_mid", "freehold", "lease_term"],
        "categorical": ["district_l1", "rooms_or_flat_type", "sale_type", "market_segment"],
        "strata": ["market_segment", "sale_type"],
        # URA publishes the project and a floor band, not the unit: a proxy as well.
        "unit": ["project", "floor_area_m2", "storey_mid"], "unit_is_dwelling": False,
        "official": "ura_private_residential_price_index.csv",
    },
}


def prepare(t: pd.DataFrame) -> pd.DataFrame:
    t = t.copy()
    t["period"] = pd.PeriodIndex(pd.to_datetime(t["date"]), freq="Q").astype(str)
    t["log_ppm2"] = np.log(t["price_per_m2_local"])
    t["log_area"] = np.log(t["floor_area_m2"])
    if "freehold" in t and "lease_remaining_years" in t:
        t["lease_term"] = t["lease_remaining_years"].where(t["freehold"] != 1, 0.0)
    rooms = pd.to_numeric(t["rooms_or_flat_type"], errors="coerce")
    t["rooms_cap"] = rooms.clip(upper=4) if rooms.notna().any() else t["rooms_or_flat_type"]
    return t


def _usable(t: pd.DataFrame, cols: list[str], min_share: float = 0.5) -> list[str]:
    return [c for c in cols if c in t and t[c].notna().mean() >= min_share]


def build(t: pd.DataFrame, cfg: dict, min_n: int = 5) -> tuple[pd.DataFrame, dict]:
    """All indices for one city from its cleaned sales (harmonised schema + extras)."""
    t = prepare(t)
    periods = sorted(t["period"].unique())
    # numeric controls with missing values would drop sales: keep those filled for >= 95%
    numeric = [c for c in _usable(t, cfg["numeric"], 0.95)]
    categorical = _usable(t, cfg["categorical"])
    strata = _usable(t, cfg["strata"], 0.95)
    meta = {"periods": [periods[0], periods[-1]], "n_sales": int(len(t)),
            "hedonic_numeric": numeric, "hedonic_categorical": categorical, "strata": strata}
    out = pd.DataFrame({"period": periods})
    out["n"] = out["period"].map(t.groupby("period").size()).to_numpy()
    out["volume"] = 100 * out["n"] / out["n"].iloc[0]
    hed = time_dummy_index(t, "log_ppm2", "period", numeric, categorical)
    out["hedonic"] = out["period"].map(hed.set_index("period")["index"])
    roll = rolling_time_dummy_index(t, "log_ppm2", "period", numeric, categorical, window=5)
    out["hedonic_rolling"] = out["period"].map(roll.set_index("period")["index"])
    try:
        st = stratified_median_index(t, "price_per_m2_local", "period", strata, min_n=min_n)
        out["stratified"] = out["period"].map(st.set_index("period")["index"])
        meta["strata_used"], meta["strata_coverage"] = int(st["n_strata"].iloc[0]), round(float(st["coverage"].iloc[0]), 4)
    except ValueError as e:
        out["stratified"] = np.nan
        meta["stratified_error"] = str(e)
    unit = [c for c in cfg["unit"] if c in t and t[c].notna().any()]
    if unit == cfg["unit"]:
        pairs = make_pairs(t, unit, "period", "log_ppm2")
        meta["repeat_pairs"] = int(len(pairs))
        meta["repeat_sales_kind"] = "repeat-sales" if cfg["unit_is_dwelling"] else "pseudo repeat-sales (proxy unit)"
        if len(pairs) >= 10 * len(periods):
            rs = repeat_sales_index(pairs, periods, weighted=True)
            out["repeat_sales"] = rs["index"].to_numpy()
        else:
            out["repeat_sales"] = np.nan
            meta["repeat_sales_error"] = "fewer than 10 pairs per period"
    else:
        out["repeat_sales"] = np.nan
        meta["repeat_sales_error"] = f"unit columns missing: {sorted(set(cfg['unit']) - set(unit))}"
    return out, meta


def validate(idx: pd.DataFrame, official: pd.Series) -> pd.DataFrame:
    """Compare each index with the official one on the quarters they share: correlation of
    quarterly log changes, and the gap in cumulative log change over the common window."""
    d = idx.drop(columns="official", errors="ignore").set_index("period").join(official.rename("official"), how="inner")
    rows = []
    for c in ("hedonic", "hedonic_rolling", "stratified", "repeat_sales"):
        s = d[[c, "official"]].dropna()
        if len(s) < 4:
            continue
        dl = np.log(s).diff().dropna()
        cum = np.log(s.iloc[-1] / s.iloc[0])
        rows.append({"index": c, "quarters": len(s), "first": s.index[0], "last": s.index[-1],
                     "corr_quarterly_changes": float(dl[c].corr(dl["official"])),
                     "cum_change_pct": float(100 * (np.exp(cum[c]) - 1)),
                     "official_cum_change_pct": float(100 * (np.exp(cum["official"]) - 1)),
                     "gap_pts": float(100 * (np.exp(cum[c]) - np.exp(cum["official"])))})
    return pd.DataFrame(rows)


def run() -> None:
    from src.ingest.official_indices import load_quarterly
    for city, cfg in CONFIG.items():
        if not (INTERIM / f"ratios_input_{city}.parquet").exists():
            print(city, "skipped: ratios_input file not built")
            continue
        t = pd.read_parquet(INTERIM / f"ratios_input_{city}.parquet")
        idx, meta = build(t, cfg)
        off = RAW / "official" / cfg["official"]
        o = None
        if off.exists():
            try:
                o = load_quarterly(off)
            except ValueError as e:
                meta["official"] = f"not compared: {e}"
        if o is not None:
            idx["official"] = idx["period"].map(o)
            base = idx["official"].dropna()
            if len(base):
                idx["official"] = 100 * idx["official"] / base.iloc[0]
            validate(idx, o).to_csv(PROCESSED / f"index_validation_{city}.csv", index=False)
        elif "official" not in meta:
            meta["official"] = f"not compared: {off.name} not downloaded"
        idx.to_csv(PROCESSED / f"index_{city}.csv", index=False)
        (PROCESSED / f"index_meta_{city}.json").write_text(json.dumps(meta, indent=1, default=str))
        print(city, meta)


if __name__ == "__main__":
    run()
