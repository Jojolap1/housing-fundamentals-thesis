"""Stratified (mix-adjusted) median index (Prasad & Richards 2008; Eurostat 2013, ch. 4).

Sales are split into strata that are homogeneous in price level (e.g. neighbourhood ×
number of rooms). The index is the fixed-weight geometric mean of the strata medians:

    index_t = 100 exp( sum_s w_s [log m_{s,t} - log m_{s,base}] )

Weights are fixed over time, so a change in which strata happen to sell does not move the
index. By default w_s is the stratum's share of all sales in the sample; pass `weights`
(e.g. the housing stock by stratum) to override. Only strata with at least `min_n` sales
in every period are used; `coverage` reports the share of sales they represent.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def stratified_median_index(df: pd.DataFrame, value: str, period: str, strata: list[str],
                            weights: pd.Series | None = None, min_n: int = 5) -> pd.DataFrame:
    d = df.dropna(subset=[value, period] + strata)
    g = d.groupby(strata + [period])[value].agg(["median", "size"]).reset_index()
    key = g[strata].astype(str).agg("|".join, axis=1)
    med = g.assign(_s=key).pivot(index="_s", columns=period, values="median")
    cnt = g.assign(_s=key).pivot(index="_s", columns=period, values="size").fillna(0)
    ok = (cnt >= min_n).all(axis=1)
    if not ok.any():
        raise ValueError("no stratum has min_n sales in every period; use coarser strata or periods")
    med, cnt_ok = med[ok], cnt[ok]
    w = cnt_ok.sum(axis=1) if weights is None else weights.reindex(med.index)
    if w.isna().any():
        raise ValueError("weights missing for some strata")
    w = w / w.sum()
    logm = np.log(med)
    li = (logm.sub(logm.iloc[:, 0], axis=0)).mul(w, axis=0).sum(axis=0)
    out = pd.DataFrame({"period": med.columns, "index": 100 * np.exp(li.to_numpy()),
                        "n": cnt.sum(axis=0).to_numpy().astype(int)})
    out["n_strata"] = int(ok.sum())
    out["coverage"] = float(cnt_ok.to_numpy().sum() / cnt.to_numpy().sum())
    return out
