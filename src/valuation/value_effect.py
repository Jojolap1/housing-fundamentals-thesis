"""Does a district that is dear relative to its rents see lower price growth afterwards?

The time-series tests in this project have a handful of episodes to learn from. Inside a city
there are tens to hundreds of districts observed over the same years, which allows a test in
the cross-section, in the spirit of the value effect in equities: sort districts on a
valuation ratio measured at the start, then look at what prices did next.

Design, written before the results were seen:
- unit: the finest district level (`district_l2`: quartier in Paris, subzone in Singapore);
- formation window: the first twelve months for which sales can be matched to a rent;
  end window: the last twelve complete months;
- signal: log of the district's median price-to-rent ratio in the formation window;
- outcome: change in the district's quality-adjusted log price per m² between the two
  windows. Quality adjustment: characteristics' coefficients are estimated within
  district × quarter cells, and their contribution is removed from each sale;
- split sample: sales of the formation window are divided at random into two halves; the
  signal uses one half and the starting price level uses the other. Otherwise noise in the
  starting prices would enter the signal with a plus sign and the outcome with a minus
  sign, and create a negative relation where none exists;
- districts need at least 30 sales in the formation window and 20 in the end window;
- statistics: slope of the outcome on the signal (OLS, heteroskedasticity-robust standard
  error), Spearman rank correlation, and the gap in price growth between the dearest third
  and the cheapest third of districts (bootstrap interval over districts). The same slope
  is also reported controlling for the starting price level, to separate "dear relative
  to rents" from "expensive".
A value effect means a negative slope. No threshold is tuned; whatever comes out is reported.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.config import N_BOOT, PROCESSED, SEED
from src.indices.run import prepare
from src.ratios import levels

UNIT = "district_l2"
MIN_FORMATION, MIN_END = 30, 20
# characteristics only: nothing that locates the dwelling
CONTROLS = {
    "paris": (["log_area", "n_dependances"], ["rooms_or_flat_type", "epoque"]),
    "singapore": (["log_area", "storey_mid", "lease_remaining_years"], ["rooms_or_flat_type", "flat_model"]),
    "singapore_private": (["log_area", "storey_mid", "freehold", "lease_term"], ["rooms_or_flat_type", "sale_type"]),
}
LOADERS = {"paris": levels.paris_transactions, "singapore": levels.singapore_transactions,
           "singapore_private": levels.singapore_private_transactions}


def quality_adjust(t: pd.DataFrame, numeric: list[str], categorical: list[str], cell: list[str]) -> pd.Series:
    """log price per m² minus the contribution of the characteristics, whose coefficients are
    estimated on deviations from the district × quarter mean."""
    numeric = [c for c in numeric if c in t and t[c].notna().mean() >= 0.95]
    categorical = [c for c in categorical if c in t and t[c].notna().mean() >= 0.5]
    X = pd.concat([t[numeric].astype(float)] + [pd.get_dummies(t[c].astype(str), prefix=c, drop_first=True, dtype=float)
                                               for c in categorical], axis=1)
    ok = X.notna().all(axis=1) & t["log_ppm2"].notna()
    g = [t.loc[ok, c] for c in cell]
    Xd = X[ok] - X[ok].groupby(g).transform("mean")
    yd = t.loc[ok, "log_ppm2"] - t.loc[ok, "log_ppm2"].groupby(g).transform("mean")
    beta = np.linalg.lstsq(Xd.to_numpy(), yd.to_numpy(), rcond=None)[0]
    adj = pd.Series(np.nan, index=t.index)
    adj[ok] = t.loc[ok, "log_ppm2"] - X[ok].to_numpy() @ beta
    return adj


def ols_robust(y: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Coefficients and HC1 standard errors; X without the constant."""
    Z = np.column_stack([np.ones(len(y)), X])
    b = np.linalg.lstsq(Z, y, rcond=None)[0]
    e = y - Z @ b
    bread = np.linalg.inv(Z.T @ Z)
    V = bread @ (Z.T * e**2) @ Z @ bread * len(y) / (len(y) - Z.shape[1])
    return b, np.sqrt(np.diag(V))


def tercile_gap(signal: np.ndarray, change: np.ndarray) -> float:
    lo, hi = np.quantile(signal, [1 / 3, 2 / 3])
    return float(change[signal >= hi].mean() - change[signal <= lo].mean())


def district_table(t: pd.DataFrame, numeric: list[str], categorical: list[str], rng: np.random.Generator) -> tuple[pd.DataFrame, dict]:
    t = t[t[UNIT].notna()].copy()
    t["date"] = pd.to_datetime(t["date"])
    t["adj"] = quality_adjust(t, numeric, categorical, [UNIT, "period"])
    start = t.loc[t["price_to_rent"].notna(), "date"].min().to_period("M")
    last = t["date"].max().to_period("M") - 1  # the running month is incomplete
    month = t["date"].dt.to_period("M")
    form = t[(month >= start) & (month < start + 12)].copy()
    end = t[(month > last - 12) & (month <= last)]
    form["half"] = rng.integers(0, 2, len(form))
    a, b = form[form["half"] == 0], form[form["half"] == 1]
    d = pd.DataFrame({
        "n_formation": form.groupby(UNIT).size(), "n_end": end.groupby(UNIT).size(),
        "price_to_rent": a.groupby(UNIT)["price_to_rent"].median(),
        "n_rent": a.groupby(UNIT)["price_to_rent"].count(),
        "adj_start": b.groupby(UNIT)["adj"].mean(), "adj_start_signal_half": a.groupby(UNIT)["adj"].mean(),
        "adj_end": end.groupby(UNIT)["adj"].mean(),
        "ppm2_start": form.groupby(UNIT)["price_per_m2_local"].median(), "ppm2_end": end.groupby(UNIT)["price_per_m2_local"].median(),
    })
    d = d[(d["n_formation"] >= MIN_FORMATION) & (d["n_end"] >= MIN_END) & (d["n_rent"] >= 5)].dropna()
    d["log_price_to_rent"] = np.log(d["price_to_rent"])
    d["change_pct"] = 100 * (d["adj_end"] - d["adj_start"])
    d["raw_change_pct"] = 100 * (d["ppm2_end"] / d["ppm2_start"] - 1)
    windows = {"formation_start": str(start), "formation_end": str(start + 11), "end_start": str(last - 11), "end_end": str(last)}
    return d.reset_index(), windows


def test(d: pd.DataFrame, rng: np.random.Generator) -> dict:
    s, y = d["log_price_to_rent"].to_numpy(), d["change_pct"].to_numpy()
    b, se = ols_robust(y, s[:, None])
    b2, se2 = ols_robust(y, np.column_stack([s, d["adj_start_signal_half"].to_numpy()]))
    rho, p_rho = stats.spearmanr(s, y)
    idx = [rng.integers(0, len(d), len(d)) for _ in range(N_BOOT)]
    gaps = np.array([tercile_gap(s[i], y[i]) for i in idx])
    dof = len(d) - 2
    return {"districts": len(d), "mean_change_pct": y.mean(), "sd_change_pct": y.std(ddof=1), "sd_signal": s.std(ddof=1),
            "slope": b[1], "slope_se": se[1], "slope_p": 2 * stats.t.sf(abs(b[1] / se[1]), dof),
            "change_for_10pct_dearer": b[1] * np.log(1.1), "r2": 1 - ((y - b[0] - b[1] * s) ** 2).sum() / ((y - y.mean()) ** 2).sum(),
            "slope_with_price_level": b2[1], "slope_with_price_level_se": se2[1],
            "slope_with_price_level_p": 2 * stats.t.sf(abs(b2[1] / se2[1]), dof - 1),
            "spearman": rho, "spearman_p": p_rho,
            "dear_minus_cheap_third_pct": tercile_gap(s, y), "gap_ci_low": np.quantile(gaps, 0.025), "gap_ci_high": np.quantile(gaps, 0.975),
            "raw_slope": ols_robust(d["raw_change_pct"].to_numpy(), s[:, None])[0][1]}


def run() -> None:
    rows, tables = [], []
    for city, loader in LOADERS.items():
        rng = np.random.default_rng(SEED)
        try:
            t = prepare(loader())
        except FileNotFoundError as e:
            print(city, "skipped:", e)
            continue
        d, windows = district_table(t, *CONTROLS[city], rng)
        if len(d) < 15:
            print(city, "skipped: only", len(d), "districts pass the thresholds")
            continue
        r = {"city": city, **windows, **test(d, rng)}
        rows.append(r)
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
        tables.append(d.assign(city=city)[["city", UNIT, "n_formation", "n_end", "price_to_rent", "change_pct", "raw_change_pct"]])
    if rows:
        pd.DataFrame(rows).round(4).to_csv(PROCESSED / "value_effect_summary.csv", index=False)
        pd.concat(tables).round(3).to_csv(PROCESSED / "value_effect_districts.csv", index=False)


if __name__ == "__main__":
    run()
