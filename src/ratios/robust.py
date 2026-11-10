"""Statistics that are robust to composition and small samples (Difficulty 3).

For every cell (city, district, neighbourhood or street) and year:
- n, median, mean, 10% trimmed mean (10% cut in each tail), q25, q75 of price per m²;
- a percentile bootstrap confidence interval of the median (N_BOOT resamples, fixed seed);
- an empirical-Bayes estimate of the median, shrunk towards the parent unit.

Shrinkage works on log medians. For child cell i in parent p:

    theta_i  = log median of the cell          v_i = bootstrap variance of theta_i
    mu_p     = log median of the parent cell
    tau2_p   = max(0, [sum_i (theta_i - mu_p)^2 / v_i - k] / sum_i 1/v_i)
               (precision-weighted method of moments over the k children of p, so that the
               many noisy small cells do not swamp the estimate of the true dispersion)
    w_i      = tau2_p / (tau2_p + v_i)
    shrunk_i = mu_p + w_i (theta_i - mu_p)

A cell with few sales has a large v_i, so it is pulled towards its parent; a cell with many
sales keeps its own value. Parents with fewer than three children use the tau2 pooled over
the city-year. Raw and shrunk values are both written.

Publication: see MIN_N_BY_LEVEL in src/config.py. Greyed rows carry the count only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.config import INTERIM, MIN_N_BY_LEVEL, MIN_N_PUBLISH, N_BOOT, PROCESSED, SEED

VALUE = "price_per_m2_local"
STAT_COLS = ["median", "mean", "trimmed_mean", "q25", "q75", "ci_lo", "ci_hi",
             "log_median_var", "shrunk_median", "shrink_weight"]
# child level -> (parent level, columns identifying the parent)
PARENT = {"street": ("district_l1", ["city", "district_l1"]),
          "district_l2": ("district_l1", ["city", "district_l1"]),
          "district_l1": ("city", ["city"])}
LEVELS = {
    "city": ["city"],
    "district_l1": ["city", "district_l1"],
    "district_l2": ["city", "district_l1", "district_l2"],
    "street": ["city", "district_l1", "street_id"],
}


def bootstrap_medians(x: np.ndarray, n_boot: int, rng: np.random.Generator) -> np.ndarray:
    """Medians of n_boot resamples of x (with replacement), drawn in memory-bounded chunks."""
    n = len(x)
    out = np.empty(n_boot)
    step = max(1, min(n_boot, 2_000_000 // max(n, 1)))
    for a in range(0, n_boot, step):
        b = min(a + step, n_boot)
        out[a:b] = np.median(x[rng.integers(0, n, size=(b - a, n))], axis=1)
    return out


def cell_stats(x, n_boot: int = N_BOOT, rng: np.random.Generator | None = None,
               trim: float = 0.10, level: float = 0.95) -> dict:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n == 0:
        return {"n": 0}
    rng = rng or np.random.default_rng(SEED)
    out = {"n": n, "median": float(np.median(x)), "mean": float(x.mean()),
           "trimmed_mean": float(stats.trim_mean(x, trim)),
           "q25": float(np.quantile(x, 0.25)), "q75": float(np.quantile(x, 0.75))}
    if n >= 2:
        bm = bootstrap_medians(x, n_boot, rng)
        a = (1 - level) / 2
        out["ci_lo"], out["ci_hi"] = (float(v) for v in np.quantile(bm, [a, 1 - a]))
        out["log_median_var"] = float(np.var(np.log(bm), ddof=1))
    return out


def table(t: pd.DataFrame, keys: list[str], value: str = VALUE, n_boot: int = N_BOOT,
          seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for k, g in t.groupby(keys, dropna=False, sort=True):
        k = k if isinstance(k, tuple) else (k,)
        rows.append({**dict(zip(keys, k)), **cell_stats(g[value].to_numpy(), n_boot, rng)})
    return pd.DataFrame(rows)


def eb_shrink(child: pd.DataFrame, parent: pd.DataFrame, parent_keys: list[str]) -> pd.DataFrame:
    """Add `shrunk_median` and `shrink_weight` to `child` (see module docstring).

    `child` needs median and log_median_var; `parent` needs parent_keys and median."""
    c = child.merge(parent[parent_keys + ["median"]].rename(columns={"median": "_pm"}),
                    on=parent_keys, how="left")
    theta, mu, v = np.log(c["median"]), np.log(c["_pm"]), c["log_median_var"]
    ok = theta.notna() & mu.notna() & v.notna()
    ok &= v > 0
    c["_q"] = ((theta - mu) ** 2 / v).where(ok)
    c["_a"] = (1 / v).where(ok)

    def tau2_by(keys: list[str]) -> pd.Series:
        g = c.groupby(keys, dropna=False)
        return ((g["_q"].transform("sum") - g["_q"].transform("count")) / g["_a"].transform("sum")).clip(lower=0)

    pooled_keys = [k for k in parent_keys if k in ("city", "year")] or parent_keys[:1]
    n_child = c.groupby(parent_keys, dropna=False)["_q"].transform("count")
    tau2 = tau2_by(parent_keys).where(n_child >= 3, tau2_by(pooled_keys))
    w = (tau2 / (tau2 + v)).where(ok)
    w = w.where(~(theta.notna() & mu.notna() & (v == 0)), 1.0)  # no sampling noise: keep the cell's value
    c["shrink_weight"] = w
    c["shrunk_median"] = np.exp(mu + w * (theta - mu))
    return c.drop(columns=["_pm", "_q", "_a"])


def apply_publication_rule(a: pd.DataFrame, level: str) -> pd.DataFrame:
    """Drop cells below MIN_N_PUBLISH; grey (count only) cells below the level's threshold."""
    a = a[a["n"] >= MIN_N_PUBLISH].copy()
    a["greyed"] = a["n"] < MIN_N_BY_LEVEL[level]
    cols = [c for c in STAT_COLS if c in a]
    a.loc[a["greyed"], cols] = np.nan
    return a


def run() -> None:
    for city in ("paris", "singapore", "singapore_private"):
        if not (INTERIM / f"ratios_input_{city}.parquet").exists():
            print(city, "skipped: ratios_input file not built")
            continue
        t = pd.read_parquet(INTERIM / f"ratios_input_{city}.parquet")
        tabs = {lvl: table(t, keys + ["year"]) for lvl, keys in LEVELS.items()}
        for lvl, (plvl, pkeys) in PARENT.items():
            tabs[lvl] = eb_shrink(tabs[lvl], tabs[plvl], pkeys + ["year"])
        for lvl, a in tabs.items():
            out = apply_publication_rule(a, lvl)
            out.to_csv(PROCESSED / f"robust_{city}_{lvl}.csv", index=False)
            print(city, lvl, len(out), "cells,", int(out["greyed"].sum()), "greyed")


if __name__ == "__main__":
    run()
