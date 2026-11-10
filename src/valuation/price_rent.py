"""Long-run price-to-rent dynamics (Gallin 2008; present-value logic of Campbell & Shiller 1988).

If prices and rents share a long-run relation, a high price-to-rent ratio must be followed
by slower price growth, faster rent growth, or both. Long-horizon regressions, horizon k:

    p_{t+k} - p_t = a_p + b_p (r_t - p_t) + e        r_{t+k} - r_t = a_r + b_r (r_t - p_t) + e

with p, r the logs of the price and rent indices. b_p > 0 means prices correct towards
rents. Standard errors are Newey-West with k-1 lags because the k-period changes overlap.
Gallin shows that these regressions are biased in small samples and uses a bootstrap for
inference; the Newey-West t-values reported here are therefore indicative only.

`ratio_zscore` gives the position of the latest log price-to-rent ratio in its own history.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _ols_nw(y: np.ndarray, x: np.ndarray, lags: int) -> tuple[np.ndarray, np.ndarray]:
    X = np.column_stack([np.ones(len(y)), x])
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    u = (y - X @ beta)[:, None] * X
    S = u.T @ u
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = u[L:].T @ u[:-L]
        S += w * (G + G.T)
    return beta, np.sqrt(np.diag(xtx_inv @ S @ xtx_inv))


def long_horizon(price: pd.Series, rent: pd.Series, k: int = 16) -> pd.DataFrame:
    """`price`, `rent`: positive index series on the same regular (quarterly) index."""
    d = pd.concat([np.log(price).rename("p"), np.log(rent).rename("r")], axis=1).dropna()
    if len(d) < 3 * k:
        raise ValueError(f"{len(d)} observations for horizon {k}: too short")
    rp = (d["r"] - d["p"]).to_numpy()[:-k]
    rows = []
    for name in ("p", "r"):
        dy = (d[name].shift(-k) - d[name]).to_numpy()[:-k]
        beta, se = _ols_nw(dy, rp, k - 1)
        rows.append({"dependent": f"{k}-period change in log {'price' if name == 'p' else 'rent'}",
                     "coef_rent_price_ratio": beta[1], "se_newey_west": se[1], "t": beta[1] / se[1], "n": len(dy)})
    return pd.DataFrame(rows)


def ratio_zscore(price: pd.Series, rent: pd.Series) -> dict:
    d = pd.concat([price.rename("p"), rent.rename("r")], axis=1).dropna()
    lr = np.log(d["p"] / d["r"])
    return {"n": len(lr), "last_period": lr.index[-1], "z_last": float((lr.iloc[-1] - lr.mean()) / lr.std(ddof=1))}
