"""Hedonic time-dummy price index (Hill 2013; Eurostat 2013, ch. 5).

    log(price per m²)_i = a + sum_t d_t D_it + x_i'b + e_i        index_t = 100 exp(d_t - d_base)

The period dummies D absorb the pure price change once the characteristics x (size, rooms,
location, age, floor, lease...) are held constant. Two variants:
- pooled: one regression over the whole sample (coefficients b fixed over time);
- rolling: regressions on overlapping windows of `window` periods, chained on the change
  between the last two periods of each window, so b can drift and past values are not
  revised when a period is added.

The design matrix is sparse and the normal equations are solved directly, so samples of
several hundred thousand sales stay cheap.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse


def _design(df: pd.DataFrame, period: str, numeric: list[str], categorical: list[str],
            periods: list) -> tuple[sparse.csr_matrix, list[str]]:
    n = len(df)
    blocks, names = [sparse.csr_matrix(np.ones((n, 1)))], ["const"]
    if numeric:
        blocks.append(sparse.csr_matrix(df[numeric].to_numpy(dtype=float)))
        names += list(numeric)
    for c, levels in [(period, periods)] + [(c, None) for c in categorical]:
        col = df[c].astype("object").where(df[c].notna(), "NA")
        cat = pd.Categorical(col, categories=levels if levels is not None else sorted(set(col), key=str))
        codes = cat.codes
        k = len(cat.categories)
        keep = codes > 0  # first category is the reference
        m = sparse.csr_matrix((np.ones(keep.sum()), (np.flatnonzero(keep), codes[keep] - 1)), shape=(n, k - 1))
        blocks.append(m)
        names += [f"{c}={v}" for v in cat.categories[1:]]
    return sparse.hstack(blocks, format="csr"), names


def _fit(X: sparse.csr_matrix, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    xtx = (X.T @ X).toarray()
    xty = X.T @ y
    beta = np.linalg.lstsq(xtx, xty, rcond=None)[0]
    resid = y - X @ beta
    s2 = float(resid @ resid) / max(len(y) - X.shape[1], 1)
    se = np.sqrt(np.clip(np.diag(np.linalg.pinv(xtx)) * s2, 0, None))
    return beta, se


def time_dummy_index(df: pd.DataFrame, y: str, period: str, numeric: list[str] | None = None,
                     categorical: list[str] | None = None) -> pd.DataFrame:
    """Pooled time-dummy index, base = first period = 100. `y` is a log price column.
    Returns period, index, se_log (classical standard error of d_t) and n."""
    numeric, categorical = list(numeric or []), list(categorical or [])
    d = df.dropna(subset=[y, period] + numeric)
    periods = sorted(d[period].unique())
    X, names = _design(d, period, numeric, categorical, periods)
    beta, se = _fit(X, d[y].to_numpy(dtype=float))
    pos = {nm: i for i, nm in enumerate(names)}
    rows = [{"period": periods[0], "log_index": 0.0, "se_log": 0.0}]
    rows += [{"period": p, "log_index": beta[pos[f"{period}={p}"]], "se_log": se[pos[f"{period}={p}"]]}
             for p in periods[1:]]
    out = pd.DataFrame(rows)
    out["index"] = 100 * np.exp(out["log_index"])
    out["n"] = out["period"].map(d.groupby(period).size()).to_numpy()
    return out[["period", "index", "se_log", "n"]]


def rolling_time_dummy_index(df: pd.DataFrame, y: str, period: str, numeric: list[str] | None = None,
                             categorical: list[str] | None = None, window: int = 5) -> pd.DataFrame:
    """Rolling time-dummy index: the first window gives its `window` periods; each later
    window contributes only the change between its last two periods."""
    periods = sorted(df.dropna(subset=[y, period])[period].unique())
    if len(periods) <= window:
        return time_dummy_index(df, y, period, numeric, categorical)
    log_idx = {}
    for k in range(window, len(periods) + 1):
        w = periods[k - window:k]
        r = time_dummy_index(df[df[period].isin(w)], y, period, numeric, categorical)
        li = np.log(r["index"].to_numpy() / 100)
        if k == window:
            log_idx.update(dict(zip(w, li)))
        else:
            log_idx[w[-1]] = log_idx[w[-2]] + (li[-1] - li[-2])
    out = pd.DataFrame({"period": periods})
    out["index"] = 100 * np.exp(out["period"].map(log_idx))
    out["n"] = out["period"].map(df.groupby(period).size()).to_numpy()
    return out
