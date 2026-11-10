"""Right-tailed unit-root tests for explosive behaviour: SADF, GSADF and date-stamping
(Phillips, Shi & Yu 2015).

For a window of the series y (in logs) the Dickey-Fuller regression is

    dy_t = a + b y_{t-1} + e_t          t-statistic of b = DF statistic

Under the null y is a random walk (b = 0); the alternative of interest is b > 0, a mildly
explosive root. With T observations and a minimum window of r0·T observations:

    SADF        = sup over end points of the DF statistic, window start fixed at the first obs
    BSADF(end)  = sup over start points of the DF statistic for windows ending at `end`
    GSADF       = sup over end points of BSADF(end)

An episode is dated where BSADF exceeds its 95% critical-value sequence for at least
log(T) consecutive periods. Critical values are simulated under a random walk with drift
1/T and standard normal errors, with a fixed seed.

What the test does and does not say:
- it needs no estimate of the fundamental value: it looks at the dynamics only;
- it needs a long, regular series, so it runs on city-level official indices;
- an explosive price alone can reflect explosive fundamentals; running it on a
  price-to-rent or price-to-income ratio is the stricter test;
- the lag order is fixed at 0 (no augmentation) and r0 = 0.01 + 1.8/sqrt(T); both choices
  are reported with the results and change them at the margin.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import SEED


def min_window(T: int) -> int:
    return max(int(np.floor((0.01 + 1.8 / np.sqrt(T)) * T)), 6)


def df_stat_matrix(y: np.ndarray) -> np.ndarray:
    """DF t-statistics for every window. Entry [i, j] uses regression observations i..j
    (0-based, in terms of dy), i.e. levels y[i]..y[j+1]. Entries with j < i + 2 are NaN."""
    y = np.asarray(y, dtype=float) - float(y[0])
    x, d = y[:-1], np.diff(y)
    m = len(d)
    P = lambda a: np.concatenate([[0.0], np.cumsum(a)])  # noqa: E731
    cs = {k: P(v) for k, v in {"x": x, "d": d, "xx": x * x, "xd": x * d, "dd": d * d}.items()}
    i, j = np.meshgrid(np.arange(m), np.arange(m), indexing="ij")
    win = lambda k: cs[k][j + 1] - cs[k][i]  # noqa: E731
    n = (j - i + 1).astype(float)
    sx, sd, sxx, sxd, sdd = win("x"), win("d"), win("xx"), win("xd"), win("dd")
    with np.errstate(divide="ignore", invalid="ignore"):
        den = n * sxx - sx ** 2
        b = (n * sxd - sx * sd) / den
        a = (sd - b * sx) / n
        ssr = sdd - a * sd - b * sxd
        t = b / np.sqrt(np.clip(ssr, 0, None) / (n - 2) * n / den)
    t[(n < 3) | ~np.isfinite(t)] = np.nan
    return t


def _stats_from_matrix(t: np.ndarray, w0: int) -> tuple[float, float, np.ndarray]:
    m = t.shape[0]
    n = np.arange(m)[None, :] - np.arange(m)[:, None] + 1
    tt = np.where(n >= w0, t, np.nan)
    ends = np.arange(w0 - 1, m)
    with np.errstate(all="ignore"):
        bsadf = np.nanmax(tt[:, ends], axis=0)
    return float(np.nanmax(tt[0, ends])), float(np.nanmax(bsadf)), bsadf


def critical_values(T: int, w0: int, nrep: int = 999, seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    sadf, gsadf, seq = np.empty(nrep), np.empty(nrep), np.empty((nrep, T - w0))
    for r in range(nrep):
        y = np.cumsum(1.0 / T + rng.standard_normal(T))
        sadf[r], gsadf[r], seq[r] = _stats_from_matrix(df_stat_matrix(y), w0)
    q = [0.90, 0.95, 0.99]
    return {"sadf": dict(zip(q, np.quantile(sadf, q))), "gsadf": dict(zip(q, np.quantile(gsadf, q))),
            "bsadf_95": np.quantile(seq, 0.95, axis=0)}


def episodes(flag: np.ndarray, labels: list, min_len: int) -> list[tuple]:
    out, start = [], None
    for k, f in enumerate(list(flag) + [False]):
        if f and start is None:
            start = k
        elif not f and start is not None:
            if k - start >= min_len:
                out.append((labels[start], labels[k - 1]))
            start = None
    return out


def explosive_test(series: pd.Series, nrep: int = 999, seed: int = SEED) -> dict:
    """`series`: a positive, regularly spaced series indexed by period label. Tested in logs."""
    s = series.dropna()
    y = np.log(s.to_numpy(dtype=float))
    T = len(y)
    if T < 40:
        raise ValueError(f"{T} observations: too short for a recursive explosive-root test")
    w0 = min_window(T)
    sadf, gsadf, bsadf = _stats_from_matrix(df_stat_matrix(y), w0)
    cv = critical_values(T, w0, nrep, seed)
    labels = list(s.index[w0:])
    seq = pd.DataFrame({"period": labels, "bsadf": bsadf, "cv95": cv["bsadf_95"]})
    seq["explosive"] = seq["bsadf"] > seq["cv95"]
    min_len = int(np.ceil(np.log(T)))
    eps = episodes(seq["explosive"].to_numpy(), labels, min_len)
    return {"T": T, "min_window": w0, "lag": 0, "nrep": nrep, "sadf": sadf, "gsadf": gsadf,
            "cv": cv, "reject_sadf_95": sadf > cv["sadf"][0.95], "reject_gsadf_95": gsadf > cv["gsadf"][0.95],
            "min_episode_len": min_len, "episodes": eps, "sequence": seq,
            "explosive_at_end": bool(eps) and eps[-1][1] == labels[-1]}
