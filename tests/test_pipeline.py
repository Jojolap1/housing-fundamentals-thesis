"""Schema, sanity and privacy checks on the pipeline outputs.

Unit tests run anywhere. Tests on built data are skipped when the corresponding file is
absent (e.g. in CI, which only has data/processed and site/data).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.clean.common import SCHEMA, within_factor_of_median, quantile_trim_by_group
from src.clean.singapore import parse_lease, storey_mid
from src.config import INTERIM, MIN_N_PUBLISH, PROCESSED, SITE_DATA
from src.ingest.onemap import normalise
from src.ratios.levels import interpolated_median
from src.ratios.valuation import _value

CITIES = ["paris", "singapore"]


def need(p: Path):
    if not p.exists():
        pytest.skip(f"{p.name} not built")
    return p


# ------------------------------------------------------------------ unit tests
def test_parse_lease():
    assert parse_lease("61 years 04 months") == pytest.approx(61 + 4 / 12)
    assert parse_lease("70") == 70.0
    assert np.isnan(parse_lease(None))


def test_storey_mid():
    assert storey_mid("10 TO 12") == 11


def test_normalise_street():
    assert normalise("BT BATOK ST 34") == "BUKIT BATOK STREET 34"
    assert normalise("ST. GEORGE'S RD") == "SAINT GEORGE'S ROAD"


def test_interpolated_median():
    row = pd.Series({"a": 10, "b": 10})
    assert interpolated_median(row, [("a", 0, 1000), ("b", 1000, 2000)]) == pytest.approx(1000)
    assert np.isnan(interpolated_median(pd.Series({"a": 1, "b": 10}), [("a", 0, 1), ("b", 1, np.inf)]))


def test_outlier_rules():
    df = pd.DataFrame({"g": ["x"] * 101, "v": [1.0] + [100.0] * 100})
    assert not within_factor_of_median(df, "v", ["g"]).iloc[0]
    assert quantile_trim_by_group(df, "v", ["g"]).sum() >= 99


def test_user_cost_and_lease():
    p = {"tau": 0.0, "delta": 0.0, "gamma": 0.02, "g": 0.02}
    V, u = _value(np.array([100.0]), np.array([0.04]), p)
    assert u[0] == pytest.approx(0.04) and V[0] == pytest.approx(2500)
    Vt, _ = _value(np.array([100.0]), np.array([0.04]), p, T=np.array([10.0]))
    assert 0 < Vt[0] < V[0]  # a finite lease is worth less than a perpetuity
    Vn, un = _value(np.array([100.0]), np.array([0.0]), p, gamma=0.0)
    assert np.isnan(un[0]) and np.isnan(Vn[0])  # u below the floor is undefined, not clipped


# ----------------------------------------------------------- built-data tests
@pytest.mark.parametrize("city", CITIES)
def test_schema_and_ranges(city):
    t = pd.read_parquet(need(INTERIM / f"transactions_{city}.parquet"))
    assert list(t.columns[: len(SCHEMA)]) == SCHEMA
    assert t["source_id"].is_unique
    assert (t["price_local"] > 0).all() and (t["floor_area_m2"] > 0).all()
    assert t["lat"].between(-90, 90).all() and t["lon"].between(-180, 180).all()
    assert np.allclose(t["price_per_m2_local"], t["price_local"] / t["floor_area_m2"])
    assert np.allclose(t["price_per_m2_eur"], t["price_eur"] / t["floor_area_m2"])
    lo, hi = {"paris": (1_000, 60_000), "singapore": (1_000, 30_000)}[city]
    assert t["price_per_m2_local"].between(lo, hi).all()


@pytest.mark.parametrize("city", CITIES)
def test_cleaning_log_consistent(city):
    log = pd.read_csv(need(PROCESSED / f"cleaning_log_{city}.csv"))
    assert (log["rows_before"] - log["rows_removed"] == log["rows_after"]).all()
    t = pd.read_parquet(need(INTERIM / f"transactions_{city}.parquet"))
    assert log["rows_after"].iloc[-1] == len(t)


@pytest.mark.parametrize("city", CITIES)
def test_site_data_respects_n_rule(city):
    hexes = json.loads(need(SITE_DATA / f"{city}_hex.json").read_text())
    for f in hexes["features"]:
        for k, v in f["properties"].items():
            if k.startswith("n_"):
                assert v >= MIN_N_PUBLISH
    streets = json.loads(need(SITE_DATA / f"{city}_streets.json").read_text())
    assert all(r["n"] >= MIN_N_PUBLISH for r in streets)


@pytest.mark.parametrize("city", CITIES)
def test_site_data_has_no_identifiers(city):
    banned = ("id_mutation", "id_parcelle", "adresse_numero", "source_id", "postal", "block")
    for f in SITE_DATA.glob(f"{city}_*.json"):
        text = f.read_text()
        for b in banned:
            assert f'"{b}"' not in text, f"{b} found in {f.name}"


@pytest.mark.parametrize("city", CITIES)
def test_published_stats_respect_n_rule(city):
    for f in PROCESSED.glob(f"stats_{city}_street.csv"):
        s = pd.read_csv(f)
        assert (s.loc[s["publish"], "n"] >= MIN_N_PUBLISH).all()


def test_freehold_is_perpetuity():
    p = {"tau": 0.0, "delta": 0.0, "gamma": 0.02, "g": 0.02}
    V, _ = _value(np.array([100.0, 100.0]), np.array([0.04, 0.04]), p, T=np.array([np.nan, 50.0]))
    assert V[0] == pytest.approx(2500) and V[1] < V[0]


@pytest.mark.parametrize("city,first", [("singapore", 2021), ("singapore_private", 2022)])
def test_no_gap_before_rent_data(city, first):
    for lvl in ("hex", "l1", "l2"):
        fc = json.loads(need(SITE_DATA / f"{city}_{lvl}.json").read_text())
        for f in fc["features"]:
            assert not any(k.startswith("gap_") and int(k[4:]) < first for k in f["properties"])


def test_liquidity_outputs():
    p = pd.read_csv(need(PROCESSED / "liquidity_paris_city.csv"))
    assert (p["turnover_per_1000"] > 0).all() and (p["turnover_per_1000"] < 200).all()
    # year-on-year changes only between full calendar years
    assert p.loc[p["year"].isin([2021, 2022, 2026]), "divergence_pts"].isna().all()
    s = pd.read_csv(need(PROCESSED / "liquidity_singapore_city.csv"))
    assert (s["turnover_per_1000"].between(1, 100)).all()
    d = pd.read_csv(need(PROCESSED / "liquidity_singapore_private_developer.csv"))
    assert (d["unsold_launched"] >= 0).all()


def test_income_index_matches_census():
    from src.ratios.levels import singapore_income_index
    idx = singapore_income_index()
    assert idx.loc[2020] == pytest.approx(1.0) and idx.loc[2025] > idx.loc[2020]
