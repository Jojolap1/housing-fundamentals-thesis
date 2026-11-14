"""Unit tests on synthetic data for the robust statistics, the price indices, the
explosive-root tests and the verdict rule. They need no downloaded data."""
import numpy as np
import pandas as pd
import pytest

from src.indices.hedonic import rolling_time_dummy_index, time_dummy_index
from src.indices.repeat_sales import make_pairs, repeat_sales_index
from src.indices.stratified import stratified_median_index
from src.ratios.robust import apply_publication_rule, cell_stats, eb_shrink, table
from src.valuation.explosive import (critical_values, df_stat_matrix, episodes, explosive_test,
                                     min_window)
from src.valuation.price_rent import long_horizon, ratio_zscore
from src.valuation.verdict import user_cost_share, user_cost_signal, verdict, z_signal

TRUE = np.array([0.0, 0.02, 0.05, 0.03, 0.08, 0.12, 0.10, 0.15])  # true log index, 8 periods


def synthetic_sales(n=24000, seed=1):
    """Two areas with a 2:1 price gap. The share of the expensive area rises over time, so
    the raw median overstates price growth; the true index is TRUE."""
    rng = np.random.default_rng(seed)
    t = rng.integers(0, len(TRUE), n)
    area = (rng.random(n) < 0.2 + 0.08 * t).astype(int)
    size = rng.uniform(20, 100, n)
    logp = np.log(5000) + TRUE[t] + np.log(2) * area - 0.2 * np.log(size / 50) + rng.normal(0, 0.15, n)
    unit = rng.integers(0, n // 4, n)  # about four sales per dwelling
    return pd.DataFrame({"period": t, "area": area, "log_size": np.log(size), "logp": logp,
                         "p": np.exp(logp), "unit": unit})


# ------------------------------------------------------------ robust statistics
def test_cell_stats_outlier_and_ci():
    x = np.r_[np.full(100, 1000.0), 2000.0]  # the brief's example: 100 sales at 1,000, one at 2,000
    s = cell_stats(x, n_boot=500, rng=np.random.default_rng(0))
    assert s["n"] == 101 and s["median"] == 1000 and s["trimmed_mean"] == 1000
    assert s["mean"] == pytest.approx(1009.9, abs=0.1)
    assert s["ci_lo"] <= s["median"] <= s["ci_hi"]


def test_bootstrap_ci_covers_true_median():
    rng = np.random.default_rng(3)
    hits = 0
    for _ in range(200):
        s = cell_stats(rng.lognormal(0, 0.5, 60), n_boot=300, rng=rng)
        hits += s["ci_lo"] <= 1.0 <= s["ci_hi"]
    assert 0.88 <= hits / 200 <= 0.995


def test_shrinkage_pulls_small_cells_more():
    rng = np.random.default_rng(5)
    rows = []
    for street in range(40):
        n = 6 if street % 2 else 300
        rows += [{"city": "X", "district_l1": 1, "street_id": street, "year": 2025,
                  "price_per_m2_local": v} for v in rng.lognormal(np.log(10000) + rng.normal(0, 0.05), 0.3, n)]
    t = pd.DataFrame(rows)
    child = table(t, ["city", "district_l1", "street_id", "year"], n_boot=200)
    parent = table(t, ["city", "district_l1", "year"], n_boot=200)
    out = eb_shrink(child, parent, ["city", "district_l1", "year"])
    small, big = out[out["n"] == 6], out[out["n"] == 300]
    assert small["shrink_weight"].mean() < big["shrink_weight"].mean()
    assert out["shrink_weight"].between(0, 1).all()
    pm = parent["median"].iloc[0]
    assert (np.abs(out["shrunk_median"] - pm) <= np.abs(out["median"] - pm) + 1e-9).all()


def test_publication_rule_greys_small_districts():
    a = pd.DataFrame({"n": [3, 12, 50], "median": [1.0, 2.0, 3.0], "mean": [1.0, 2.0, 3.0]})
    out = apply_publication_rule(a, "district_l2")
    assert list(out["n"]) == [12, 50] and list(out["greyed"]) == [True, False]
    assert np.isnan(out["median"].iloc[0]) and out["median"].iloc[1] == 3.0
    assert not apply_publication_rule(a, "street")["greyed"].any()


# ------------------------------------------------------------------- indices
def test_raw_median_is_biased_but_indices_are_not():
    d = synthetic_sales()
    raw = np.log(d.groupby("period")["p"].median())
    assert (raw.iloc[-1] - raw.iloc[0]) - TRUE[-1] > 0.10  # composition bias
    hed = time_dummy_index(d, "logp", "period", numeric=["log_size"], categorical=["area"])
    assert np.allclose(np.log(hed["index"] / 100), TRUE, atol=0.02)
    assert (hed["n"] > 0).all() and hed["index"].iloc[0] == pytest.approx(100)
    roll = rolling_time_dummy_index(d, "logp", "period", ["log_size"], ["area"], window=4)
    assert np.allclose(np.log(roll["index"] / 100), TRUE, atol=0.03)
    strat = stratified_median_index(d, "p", "period", ["area"])
    assert np.allclose(np.log(strat["index"] / 100), TRUE, atol=0.03)
    assert strat["coverage"].iloc[0] == pytest.approx(1.0)


@pytest.mark.parametrize("weighted", [False, True])
def test_repeat_sales_recovers_index(weighted):
    rng = np.random.default_rng(2)
    n_units = 6000
    quality = rng.normal(0, 0.5, n_units)  # unobserved, constant per dwelling: differenced out
    rows = []
    for u in range(n_units):
        for t in sorted(rng.choice(len(TRUE), size=2, replace=False)):
            rows.append({"unit": u, "period": int(t), "logp": TRUE[t] + quality[u] + rng.normal(0, 0.05)})
    pairs = make_pairs(pd.DataFrame(rows), ["unit"], "period", "logp")
    assert len(pairs) == n_units and (pairs["p1"] > pairs["p0"]).all()
    rs = repeat_sales_index(pairs, list(range(len(TRUE))), weighted=weighted)
    assert np.allclose(np.log(rs["index"] / 100), TRUE, atol=0.01)


def test_repeat_sales_unobserved_period_is_nan():
    pairs = pd.DataFrame({"p0": [0, 0], "p1": [2, 2], "dlog": [0.1, 0.12]})
    rs = repeat_sales_index(pairs, [0, 1, 2], weighted=False)
    assert np.isnan(rs["index"].iloc[1]) and rs["index"].iloc[2] == pytest.approx(100 * np.exp(0.11))


def test_stratified_refuses_empty_strata():
    d = pd.DataFrame({"p": [1.0, 2.0], "period": [0, 1], "s": ["a", "b"]})
    with pytest.raises(ValueError):
        stratified_median_index(d, "p", "period", ["s"], min_n=1)


# ------------------------------------------------------ explosive-root tests
def test_df_matrix_matches_direct_regression():
    rng = np.random.default_rng(7)
    y = np.cumsum(rng.standard_normal(60)) + 50
    t = df_stat_matrix(y)
    for i, j in [(0, 58), (5, 30), (20, 45)]:
        x, d = y[i:j + 1], np.diff(y)[i:j + 1]
        X = np.column_stack([np.ones(len(x)), x])
        b, res = np.linalg.lstsq(X, d, rcond=None)[:2]
        s2 = res[0] / (len(d) - 2)
        se = np.sqrt(s2 * np.linalg.inv(X.T @ X)[1, 1])
        assert t[i, j] == pytest.approx(b[1] / se, rel=1e-6)


def test_gsadf_detects_bubble_and_not_random_walk():
    rng = np.random.default_rng(11)
    T = 120
    rw = np.cumsum(rng.normal(0, 0.01, T)) + np.log(100)
    idx = [f"q{k}" for k in range(T)]
    calm = explosive_test(pd.Series(np.exp(rw), index=idx), nrep=199)
    assert not calm["reject_gsadf_95"] and calm["episodes"] == []
    bub = rw.copy()
    for k in range(70, 100):  # explosive root 1.04 for 30 periods, then collapse
        bub[k] = bub[69] + (bub[k - 1] - bub[69]) * 1.04 + 0.01 + rng.normal(0, 0.01)
    bub[100:] = bub[69] + np.cumsum(rng.normal(0, 0.01, T - 100))
    res = explosive_test(pd.Series(np.exp(bub), index=idx), nrep=199)
    assert res["reject_gsadf_95"] and res["episodes"]
    start, end = (int(p[1:]) for p in res["episodes"][0])
    assert 70 <= start <= 95 and end <= 102 and not res["explosive_at_end"]
    assert res["min_window"] == min_window(T) and len(res["sequence"]) == T - res["min_window"]


def test_critical_values_are_reproducible_and_ordered():
    a, b = critical_values(60, min_window(60), nrep=99), critical_values(60, min_window(60), nrep=99)
    assert a["gsadf"] == b["gsadf"] and a["gsadf"][0.95] > a["sadf"][0.95]
    assert a["gsadf"][0.90] < a["gsadf"][0.95] < a["gsadf"][0.99]


def test_episodes_minimum_length():
    f = np.array([1, 1, 0, 1, 1, 1, 1, 0, 1], dtype=bool)
    assert episodes(f, list("abcdefghi"), 3) == [("d", "g")]
    assert episodes(f, list("abcdefghi"), 1)[-1] == ("i", "i")


def test_explosive_test_refuses_short_series():
    with pytest.raises(ValueError):
        explosive_test(pd.Series(np.arange(1, 21.0)))


# ---------------------------------------------------- price-to-rent, verdict
def test_long_horizon_finds_error_correction():
    rng = np.random.default_rng(4)
    T = 240
    r = np.cumsum(rng.normal(0.005, 0.01, T))
    gap = np.zeros(T)  # log price-to-rent ratio, mean-reverting
    for t in range(1, T):
        gap[t] = 0.9 * gap[t - 1] + rng.normal(0, 0.03)
    idx = pd.RangeIndex(T)
    res = long_horizon(pd.Series(np.exp(r + gap), idx), pd.Series(np.exp(r), idx), k=12)
    assert res.loc[0, "coef_rent_price_ratio"] > 0 and res.loc[0, "t"] > 2  # prices correct
    z = ratio_zscore(pd.Series(np.exp(r + gap), idx), pd.Series(np.exp(r), idx))
    assert z["n"] == T and abs(z["z_last"]) < 5


def test_verdict_rule():
    assert verdict({"user_cost": 1, "price_rent": 1, "explosive": 1, "affordability": None})["verdict"] \
        == "evidence of deviation"
    # three anchors but all rent-based or not enough: inconclusive
    assert verdict({"user_cost": 1, "price_rent": 1, "explosive": 0})["verdict"] == "inconclusive"
    assert verdict({"user_cost": 1, "price_rent": None, "explosive": None})["verdict"] == "inconclusive"
    assert verdict({"user_cost": -1, "explosive": 0})["verdict"] == "consistent with fundamentals"
    assert verdict({"user_cost": 0, "explosive": 0})["verdict"] == "inconclusive"
    assert verdict({"user_cost": -1})["verdict"] == "inconclusive"
    v = verdict({"user_cost": 1, "explosive": None})
    assert v["anchors_not_run"] == "explosive" and v["anchors_pointing_to_deviation"] == "user_cost"


def test_user_cost_share_and_signals():
    sens = pd.DataFrame({"year": [2025] * 5 + [2024], "gap_median": [0.3, 0.1, -0.2, np.nan, 0.4, -1.0]})
    assert user_cost_share(sens, 2025) == pytest.approx(0.75)
    assert user_cost_signal(0.75) == 0 and user_cost_signal(0.9) == 1 and user_cost_signal(0.1) == -1
    assert user_cost_signal(float("nan")) is None
    assert z_signal(1.5) == 1 and z_signal(-1.5) == -1 and z_signal(0.2) == 0 and z_signal(None) is None


def test_official_index_loader(tmp_path):
    from src.ingest.official_indices import load_quarterly, to_quarter
    assert to_quarter("1Q2009") == to_quarter("2009 Q1") == to_quarter("2009-Q1") == "2009Q1"
    pd.DataFrame({"_id": [1, 2], "quarter": ["1975-Q2", "1975-Q1"], "index": ["9.1", "8.9"]}).to_csv(
        tmp_path / "a.csv", index=False)
    assert load_quarterly(tmp_path / "a.csv").to_dict() == {"1975Q1": 8.9, "1975Q2": 9.1}
    pd.DataFrame({"quarter": ["1975-Q1"] * 2, "type": ["Landed", "Non-Landed"], "index": [1, 2]}).to_csv(
        tmp_path / "b.csv", index=False)
    with pytest.raises(ValueError):  # two series in one file: refuse to guess
        load_quarterly(tmp_path / "b.csv")
    assert load_quarterly(tmp_path / "b.csv", {"type": "Landed"}).iloc[0] == 1
    with pytest.raises(ValueError, match="available"):  # a filter value that is not in the file
        load_quarterly(tmp_path / "b.csv", {"type": "Strata"})


def test_index_build_and_validation_on_schema_like_data():
    from src.indices.run import CONFIG, build, validate
    rng = np.random.default_rng(0)
    n = 20000
    dates = pd.to_datetime("2021-07-01") + pd.to_timedelta(rng.integers(0, 5 * 365, n), unit="D")
    q = ((dates.year - 2021) * 4 + dates.quarter).to_numpy()
    t = pd.DataFrame({"date": dates, "district_l1": rng.integers(1, 21, n),
                      "rooms_or_flat_type": rng.integers(1, 6, n).astype(float),
                      "floor_area_m2": rng.uniform(15, 120, n), "n_dependances": rng.integers(0, 3, n),
                      "id_parcelle": rng.integers(0, 6000, n).astype(str),
                      "lot1_numero": rng.integers(0, 3, n).astype(str)})
    t["district_l2"] = t["district_l1"] * 4 + rng.integers(0, 4, n)
    t["price_per_m2_local"] = np.exp(np.log(10000) - 0.004 * q + 0.02 * t["district_l1"] + rng.normal(0, 0.1, n))
    idx, meta = build(t, CONFIG["paris"])
    assert len(idx) == 20 and idx["volume"].iloc[0] == 100 and meta["repeat_sales_kind"] == "repeat-sales"
    true_last = 100 * np.exp(-0.004 * 19)
    for c in ("hedonic", "hedonic_rolling", "stratified", "repeat_sales"):
        assert idx[c].iloc[-1] == pytest.approx(true_last, abs=1.5), c
    official = pd.Series(100 * np.exp(-0.004 * np.arange(20)), index=idx["period"])
    v = validate(idx, official)
    assert set(v["index"]) == {"hedonic", "hedonic_rolling", "stratified", "repeat_sales"}
    assert v["gap_pts"].abs().max() < 1.5
    # without the lot number there is no dwelling identifier: no repeat-sales index, and it says why
    idx2, meta2 = build(t.drop(columns="lot1_numero"), CONFIG["paris"])
    assert idx2["repeat_sales"].isna().all() and "lot1_numero" in meta2["repeat_sales_error"]


# ------------------------------------------------------------ two cross-checks
def test_implied_g_inverts_the_valuation_formula():
    from src.ratios.params import BASE
    from src.ratios.valuation import _value
    from src.valuation.cross_checks import implied_g
    p, rf, g_true = BASE["Singapore"], 0.03, 0.025
    R = np.array([30000.0, 30000.0, 30000.0])
    T = np.array([60.0, 95.0, np.nan])  # two leases and a freehold
    V, _ = _value(R, rf, p, T, g=g_true)
    i = rf + p["tau"] + p["delta"] + p["gamma"]
    assert np.allclose(implied_g(R / V, i, T), g_true, atol=1e-6)
    assert np.allclose(implied_g(R / V, i)[2], g_true, atol=1e-9)  # freehold: closed form
    # a dearer home needs more rent growth; a shorter lease needs more growth for the same price
    assert implied_g(0.02, i, 60.0) > implied_g(0.03, i, 60.0)
    assert implied_g(0.03, i, 40.0) > implied_g(0.03, i, 90.0)
    assert np.isnan(implied_g(np.nan, i, 60.0))


def test_borrowing_capacity_and_readings():
    from src.valuation.cross_checks import (annuity, cagr, combine, price_over_capacity, read_check1,
                                            read_check2)
    assert annuity(0.0, 25) == 300 and annuity(0.04, 25) == pytest.approx(189.45, abs=0.01)
    # income 16,000 a month, 55% at 4% over 25 years: loan of about 1.667 million (MAS worked example in the press)
    assert 0.55 * 16000 * annuity(0.04, 25) == pytest.approx(1.667e6, rel=0.002)
    pmax = 0.55 * 16000 * annuity(0.04, 25) / 0.75
    assert price_over_capacity(pmax / (12 * 16000), 0.04, 0.55, 25, 0.25) == pytest.approx(1.0)
    assert cagr(pd.Series([100.0, 110.0, 121.0]), 2) == pytest.approx(0.10)
    assert read_check1(0.01, 0.02, 0.03) == "plausible" and read_check1(0.04, 0.07, 0.03) == "implausible"
    assert read_check1(0.02, 0.05, 0.03) == "depends on the premium" and read_check1(np.nan, 0.05, 0.03) == "not run"
    assert read_check2(0.7, 0.8, 0.9) == "within capacity" and read_check2(1.1, 1.2, 1.3) == "beyond capacity"
    assert read_check2(0.9, 1.0, 1.1) == "depends on the rate"
    assert combine("implausible", "beyond capacity") == "fails both checks"
    assert combine("plausible", "not run") == "incomplete" and combine("depends on the premium", "within capacity").startswith("mixed")


def test_cross_check_table_on_schema_like_data():
    from src.valuation.cross_checks import city_table
    t = pd.DataFrame({"year": [2024] * 3 + [2025] * 3, "gross_yield": [0.03, 0.031, 0.029] * 2,
                      "pti_hh": [13.0, 14.0, 15.0] * 2})
    rf = pd.Series({2024: 0.03, 2025: 0.033})
    bench = {"rent_growth": 0.012, "income_growth": 0.02, "bench_note": "x"}
    out = city_table("paris", t, rf, bench, pd.Series({2024: 0.037, 2025: 0.032}), "ECB")
    r = out.set_index("year").loc[2025]
    assert r["g_star_gamma2"] == pytest.approx(0.033 + 0.0025 + 0.015 + 0.02 - 0.03)
    assert r["check1"] == "implausible" and r["check2"] == "beyond capacity" and r["reading"] == "fails both checks"
    assert r["mortgage_rate"] == 0.032 and len(out) == 2


# --------------------------------------------------------- early-warning record
def test_drawdowns_and_labels():
    from src.valuation.early_warning import drawdowns, label_quarters
    s = pd.Series([100, 110, 120, 100, 96, 108, 121, 130, 125, 104], index=list("abcdefghij"), dtype=float)
    d = drawdowns(s, 0.15)
    assert [(e["peak"], e["trough"], e["recovered"]) for e in d] == [("c", "e", "g"), ("h", "j", None)]
    assert d[0]["drop"] == pytest.approx(-0.2) and d[1]["drop"] == pytest.approx(-0.2)
    assert drawdowns(s, 0.25) == []
    lab = label_quarters(10, d, horizon=1)
    assert list(lab) == [0, 1, 1, -1, -1, 0, 1, 1, -1, -1]


def test_expanding_z_uses_the_past_only():
    from src.valuation.early_warning import expanding_z
    x = pd.Series(np.r_[np.full(40, 100.0) * np.exp(np.random.default_rng(0).normal(0, 0.02, 40)), 150.0, 150.0])
    z = expanding_z(x, 40)
    assert z.iloc[:39].isna().all() and z.iloc[40] > 3  # a jump is unusual against the past...
    assert z.iloc[41] < z.iloc[40]                      # ...and less so once it is part of the past


def test_signal_evaluation_finds_an_informative_threshold():
    from src.valuation.early_warning import best_threshold, evaluate
    rng = np.random.default_rng(1)
    panel = {}
    for c in range(12):
        n = 160
        ratio = 100 * np.exp(rng.normal(0, 0.03, n))
        price = 100 * np.exp(np.cumsum(rng.normal(0.004, 0.004, n)))
        if c < 8:  # a boom in the ratio, then a 25% bust
            ratio[100:121] *= np.linspace(1.0, 1.5, 21)
            price[121:137] = price[120] * np.linspace(0.98, 0.75, 16)
            price[137:] = price[136] * np.exp(np.cumsum(rng.normal(0.004, 0.004, n - 137)))
            ratio[121:] = ratio[121:] * np.r_[np.linspace(1.5, 1.0, 16), np.ones(n - 137)]
        idx = [f"{1980 + k // 4}Q{k % 4 + 1}" for k in range(n)]
        panel[f"C{c}"] = pd.DataFrame({"RHP": price, "HPI_YDH": ratio}, index=idx)
    table, busts = evaluate(panel, "HPI_YDH")
    assert len(busts) == 8 and (busts["real_drop_pct"] < -15).all()
    best = table.set_index("threshold_z").loc[best_threshold(table)]
    assert best["hit_minus_false_alarm"] > 0.3 and best["busts_flagged_share"] == 1.0
    assert table["hit_rate"].is_monotonic_decreasing and table["false_alarm_rate"].is_monotonic_decreasing


def test_bust_definitions_separate_crashes_from_inflation_erosion():
    from src.valuation.early_warning import country_busts, evaluate, label_quarters, qualifies
    n = 120
    idx = [f"{1970 + k // 4}Q{k % 4 + 1}" for k in range(n)]
    cpi = np.r_[np.ones(40), np.exp(0.03 * np.arange(1, 21)), np.full(60, np.exp(0.6))]  # inflation burst, quarters 40-59
    nominal = np.r_[np.linspace(100, 140, 40), np.full(20, 140.0), np.linspace(140, 300, 30),
                    np.linspace(298, 225, 10), np.linspace(228, 330, 20)]            # a nominal crash, quarters 90-99
    d = pd.DataFrame({"HPI": nominal, "RHP": nominal / cpi, "HPI_YDH": 100.0}, index=idx)
    b = country_busts(d)
    assert len(b) == 2
    assert b[0]["nominal_drop"] == pytest.approx(0.0) and not qualifies(b[0], "crash")   # erosion by inflation
    assert b[1]["nominal_drop"] < -0.2 and qualifies(b[1], "crash") and qualifies(b[1], "major")
    lab = label_quarters(n, [b[1]], excluded=[b[0]])
    assert (lab[b[0]["i_peak"] - 5:b[0]["i_trough"] + 1] == -1).all() and lab[b[1]["i_peak"]] == 1
    d["HPI_YDH"] = 100 * np.exp(np.random.default_rng(0).normal(0, 0.02, n))
    _, crash = evaluate({"X": d}, "HPI_YDH", "crash")
    _, every = evaluate({"X": d}, "HPI_YDH", "all")
    assert len(crash) == 1 and len(every) == 2 and crash["nominal_drop_pct"].iloc[0] < -20


def test_volume_drop_precedes_price_fall():
    from src.valuation import volumes as V
    idx = pd.period_range("2000Q1", periods=60, freq="Q")
    price = pd.Series(np.r_[np.linspace(100, 200, 30), np.linspace(198, 150, 12), np.linspace(152, 190, 18)], index=idx)
    q = pd.Series(np.r_[np.full(26, 1000.0), np.full(14, 600.0), np.full(20, 1000.0)], index=idx)
    level, change, on = V.signal(q, "count")
    assert pd.isna(level.iloc[2]) and level.iloc[3] == 4000
    eps = V.drop_episodes(on)
    assert len(eps) == 1 and eps[0] < idx[29]
    a = V.around_falls(price, level, change, on)
    assert len(a) == 1 and a.loc[0, "signal_peak_lead_quarters"] > 0 and a.loc[0, "drop_lead_quarters"] > 0
    assert V.alarms(price, change, on)["followed_by_price_fall"].tolist() == [True]
    # a balance of opinion: flagged only once ten years of one-year changes exist
    bal = pd.Series(np.r_[np.sin(np.arange(52) / 3) * 2 - 70, np.full(8, -90.0)], index=idx)
    _, ch, flag = V.signal(bal, "balance")
    assert not flag.iloc[:44].any() and flag.iloc[-6:].any()


def _value_panel(effect: float, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for u in range(60):
        level, ratio = rng.normal(9, 0.3), rng.normal(0, 0.15)  # log price level and log price-to-rent deviation
        growth = 0.05 + effect * ratio
        for when, base in (("2021-09-15", 0.0), ("2025-09-15", growth)):
            n = 80
            area = rng.uniform(20, 120, n)
            lp = level + ratio + base - 0.1 * np.log(area) + rng.normal(0, 0.2, n)
            rows.append(pd.DataFrame({"district_l2": f"u{u}", "date": when, "floor_area_m2": area,
                                      "price_per_m2_local": np.exp(lp), "rooms_or_flat_type": "2",
                                      "price_to_rent": np.exp(lp - level + 3)}))
    t = pd.concat(rows, ignore_index=True)
    t["date"] = pd.to_datetime(t["date"]) + pd.to_timedelta(np.random.default_rng(seed).integers(0, 60, len(t)), unit="D")
    return t


def test_value_effect_detects_and_does_not_invent():
    from src.indices.run import prepare
    from src.valuation import value_effect as VE
    for effect, expect_negative in ((-0.5, True), (0.0, False)):
        t = prepare(_value_panel(effect))
        d, w = VE.district_table(t, ["log_area"], ["rooms_or_flat_type"], np.random.default_rng(1))
        r = VE.test(d, np.random.default_rng(1))
        assert r["districts"] == 60 and w["formation_start"] == "2021-09"
        if expect_negative:
            assert r["slope"] < -25 and r["slope_p"] < 0.01 and r["dear_minus_cheap_third_pct"] < 0
        else:  # split sample: noise in starting prices must not create a relation
            assert abs(r["slope"] / r["slope_se"]) < 2.5


def test_district_cycles_slope_appears_only_when_built_in():
    from src.valuation import district_cycles as DC
    rng = np.random.default_rng(5)
    rows = []
    level = {u: rng.normal(9, 0.3) for u in range(40)}
    cum = {u: 0.0 for u in range(40)}
    for year in range(2010, 2021):
        for u in range(40):
            cum[u] += 0.03 + (0.10 * (level[u] - 9) if year == 2019 else 0.0)
            area = rng.uniform(20, 100, 40)
            rows.append(pd.DataFrame({"unit": str(u), "year": year, "log_area": np.log(area), "rooms": "2",
                                      "log_ppm2": level[u] + cum[u] - 0.1 * np.log(area) + rng.normal(0, 0.1, 40)}))
    p = DC.district_year(pd.concat(rows, ignore_index=True), ["log_area"], ["rooms"])
    s = DC.yearly_slopes(p).set_index("year")
    assert p.shape == (40, 11) and s.index.min() == 2013
    assert s.loc[2019, "t"] > 4 and (s.drop(2019)["t"].abs() < 3).all()
    g = DC.group_index(p, (2010, 2012))
    assert set(g["group"]) == {"cheapest third", "middle third", "dearest third"} and (g[g["year"] == 2013]["index"].round(6) == 100).all()
