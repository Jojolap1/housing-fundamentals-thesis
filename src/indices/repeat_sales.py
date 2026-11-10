"""Repeat-sales price index (Bailey, Muth & Nourse 1963; Case & Shiller 1989).

For a dwelling sold in periods s < t:   log P_t - log P_s = d_t - d_s + e
Stacking all pairs gives a regression on period dummies (-1 at the first sale, +1 at the
second); index_t = 100 exp(d_t), base = first period.

- `weighted=False`: BMN, ordinary least squares.
- `weighted=True`: Case-Shiller three steps. The squared BMN residuals are regressed on a
  constant and the time between the two sales, and the pairs are re-weighted by the inverse
  of the fitted standard deviation, because price noise grows with the holding period.

The method uses only dwellings sold at least twice (a selected sample) and assumes the
dwelling did not change between the two sales. When the source has no dwelling identifier
the unit can only be a proxy (e.g. block × flat type × storey band): the result is then a
"pseudo repeat-sales" index and must be labelled as such.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse


def make_pairs(df: pd.DataFrame, unit: list[str], period: str, log_price: str) -> pd.DataFrame:
    """Consecutive sales of the same unit in different periods. Several sales of a unit in
    the same period are averaged first."""
    d = df.dropna(subset=unit + [period, log_price])
    d = d.groupby(unit + [period], sort=True)[log_price].mean().reset_index()
    g = d.groupby(unit, sort=False)
    out = pd.DataFrame({"p0": g[period].shift(1), "p1": d[period],
                        "dlog": d[log_price] - g[log_price].shift(1)})
    return out.dropna(subset=["p0"]).reset_index(drop=True)


def repeat_sales_index(pairs: pd.DataFrame, periods: list, weighted: bool = True) -> pd.DataFrame:
    """`pairs` has p0, p1 (period labels) and dlog. `periods` is the full ordered list."""
    pos = {p: i for i, p in enumerate(periods)}
    i0, i1 = pairs["p0"].map(pos).to_numpy(), pairs["p1"].map(pos).to_numpy()
    n, k = len(pairs), len(periods) - 1
    rows = np.arange(n)
    r = np.concatenate([rows[i1 > 0], rows[i0 > 0]])
    c = np.concatenate([i1[i1 > 0] - 1, i0[i0 > 0] - 1])
    v = np.concatenate([np.ones((i1 > 0).sum()), -np.ones((i0 > 0).sum())])
    X = sparse.csr_matrix((v, (r, c)), shape=(n, k))
    y = pairs["dlog"].to_numpy(dtype=float)

    def solve(Xw, yw):
        return np.linalg.lstsq((Xw.T @ Xw).toarray(), Xw.T @ yw, rcond=None)[0]

    beta = solve(X, y)
    if weighted and n > k + 2:
        e2 = (y - X @ beta) ** 2
        gap = (i1 - i0).astype(float)
        A = np.column_stack([np.ones(n), gap])
        fit = A @ np.linalg.lstsq(A, e2, rcond=None)[0]
        fit = np.clip(fit, np.quantile(e2, 0.05) if np.quantile(e2, 0.05) > 0 else 1e-8, None)
        wgt = 1 / np.sqrt(fit)
        beta = solve(sparse.diags(wgt) @ X, wgt * y)
    touched = np.zeros(len(periods), dtype=int)
    np.add.at(touched, i0, 1)
    np.add.at(touched, i1, 1)
    li = np.concatenate([[0.0], beta])
    li[touched == 0] = np.nan  # a period no pair touches is not identified
    return pd.DataFrame({"period": periods, "index": 100 * np.exp(li), "n_pair_ends": touched})
