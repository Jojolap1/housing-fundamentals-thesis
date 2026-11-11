"""Transaction volumes as a second signal next to the valuation ratios.

A ratio says a market is dear; it does not say when it turns. Sales usually fall before
prices, because sellers first refuse to cut. For each market with a long count of sales this
module measures (1) what volumes did around each past price fall of at least 10%, and
(2) how often a sharp drop in volumes was not followed by such a fall.

Definitions, fixed before looking at the results:
- volume = number of sales over the last four quarters (removes seasonality);
- volume drop = that number at least 20% below its level a year earlier;
- for France there is no long public count of sales by city in the sources read; the signal is
  the INSEE household survey on the intention to buy a dwelling within a year (four-quarter
  mean of the balance of opinion), and a drop is a one-year fall of at least one standard
  deviation of its past one-year changes;
- a drop is "followed by a price fall" if a price peak that leads to a fall of at least 10%
  lies between eight quarters before and eight quarters after the first quarter of the drop.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import PROCESSED
from src.valuation.early_warning import drawdowns

DROP = -0.20
WINDOW = 8
MIN_FALL = 0.10


def annual_volume(q: pd.Series) -> pd.Series:
    """Sum over the last four quarters; quarters missing from the source stay missing."""
    full = q.reindex(pd.period_range(q.index[0], q.index[-1], freq="Q"))
    return full.rolling(4, min_periods=4).sum()


def drop_episodes(on: pd.Series) -> list[pd.Period]:
    """First quarter of each run of flagged quarters."""
    return [p for p, a, b in zip(on.index, on, on.shift(1, fill_value=False)) if a and not b]


def around_falls(price: pd.Series, level: pd.Series, change: pd.Series, on: pd.Series, relative: bool = True) -> pd.DataFrame:
    """One row per price fall of at least 10%: where the signal peaked, what it had lost by the
    price peak, and the first drop episode around the peak. `relative`: the level is a count
    (changes in %); otherwise a balance of opinion (changes in points)."""
    diff = (lambda a, b: 100 * (a / b - 1)) if relative else (lambda a, b: a - b)
    scale = 100 if relative else 1
    rows = []
    for b in drawdowns(price, MIN_FALL):
        peak = b["peak"]
        win = level[(level.index >= peak - 12) & (level.index <= peak + 4)].dropna()
        row = {"price_peak": str(peak), "price_trough": str(b["trough"]), "price_fall_pct": 100 * b["drop"]}
        if len(win) >= 8 and peak in change.index and not pd.isna(change[peak]):
            sp = win.idxmax()
            first = next((p for p in drop_episodes(on) if peak - WINDOW <= p <= peak + WINDOW), None)
            after = level[(level.index > peak) & (level.index <= peak + 12)]
            row |= {"signal_peak": str(sp), "signal_peak_lead_quarters": (peak - sp).n,
                    "signal_change_to_price_peak": diff(level[peak], win.max()),
                    "signal_change_1y_at_price_peak": scale * change[peak],
                    "signal_low_after": diff(after.min(), win.max()) if len(after) else np.nan,
                    "first_drop_quarter": str(first) if first is not None else None,
                    "drop_lead_quarters": (peak - first).n if first is not None else None}
        rows.append(row)
    return pd.DataFrame(rows)


def alarms(price: pd.Series, change: pd.Series, on: pd.Series, relative: bool = True) -> pd.DataFrame:
    peaks = [b["peak"] for b in drawdowns(price, MIN_FALL)]
    rows = []
    for p in drop_episodes(on):
        if p < price.index[0]:
            continue  # no price series yet: the drop cannot be scored
        near = [k for k in peaks if k - WINDOW <= p <= k + WINDOW]
        scored = p + WINDOW <= price.index[-1]  # the window after the drop must be observed
        rows.append({"drop_start": str(p), "signal_change_1y": (100 if relative else 1) * change[p],
                     "price_peak_nearby": str(near[0]) if near else None,
                     "followed_by_price_fall": bool(near) if scored or near else None})
    return pd.DataFrame(rows)


def _series(d: pd.DataFrame, city: str, name: str) -> pd.Series:
    g = d[(d["city"] == city) & (d["series"] == name)]
    return pd.Series(g["value"].to_numpy(dtype=float), index=pd.PeriodIndex(g["period"], freq="Q")).sort_index()


# market, price series (city in ratio_series.csv), signal (city, series in volume_series.csv), kind
SIGNALS = [("singapore", "singapore", ("singapore", "sales"), "count"),
           ("singapore_private", "singapore_private", ("singapore_private", "sales"), "count"),
           ("singapore_private", "singapore_private", ("singapore_private", "resales"), "count"),
           ("paris", "paris", ("france", "purchase_intentions"), "balance")]


def signal(raw: pd.Series, kind: str) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Level, one-year change and drop flag. Counts: four-quarter sum, change in %, drop at
    -20%. Balance of opinion: four-quarter mean, change in points, drop when the change is at
    least one standard deviation of past one-year changes below zero (expanding, 10 years)."""
    full = raw.reindex(pd.period_range(raw.index[0], raw.index[-1], freq="Q"))
    if kind == "count":
        level = full.rolling(4, min_periods=4).sum()
        change = level / level.shift(4) - 1
        return level, change, (change <= DROP).fillna(False)
    level = full.rolling(4, min_periods=4).mean()
    change = level - level.shift(4)
    sd = change.expanding(min_periods=40).std().shift(1)
    return level, change, (change <= -sd).fillna(False)


def run() -> None:
    v = pd.read_csv(PROCESSED / "volume_series.csv", dtype={"period": str})
    r = pd.read_csv(PROCESSED / "ratio_series.csv", dtype={"period": str})
    falls, als, today = [], [], []
    for market, pcity, (scity, sname), kind in SIGNALS:
        raw, price = _series(v, scity, sname), _series(r[r["period"].str.len() == 6], pcity, "price")
        if raw.empty or price.empty:
            print(market, sname, "skipped: series missing")
            continue
        level, change, on = signal(raw, kind)
        rel = kind == "count"
        head = {"market": market, "signal": sname, "unit": "%" if rel else "points"}
        f, a = around_falls(price, level, change, on, rel), alarms(price, change, on, rel)
        falls.append(f.assign(**head))
        als.append(a.assign(**head))
        scored = a.dropna(subset=["followed_by_price_fall"]) if len(a) else a
        last = change.dropna().index[-1]
        today.append({**head, "first_period": str(raw.index[0]), "last_period": str(last),
                      "change_1y_last": (100 if rel else 1) * change[last], "drop_on_last": bool(on[last]),
                      "price_falls": len(f), "price_falls_with_signal": int(f["signal_peak"].notna().sum()) if "signal_peak" in f else 0,
                      "price_falls_with_drop_nearby": int(f["first_drop_quarter"].notna().sum()) if "first_drop_quarter" in f else 0,
                      "drop_episodes_scored": len(scored),
                      "drop_episodes_followed_by_fall": int(scored["followed_by_price_fall"].sum()) if len(scored) else 0})
        print(market, sname, today[-1])
    cols = ["market", "signal", "unit"]
    for name, parts in (("volume_around_falls", falls), ("volume_drop_episodes", als)):
        d = pd.concat(parts, ignore_index=True)
        d[cols + [c for c in d.columns if c not in cols]].round(2).to_csv(PROCESSED / f"{name}.csv", index=False)
    pd.DataFrame(today).round(2).to_csv(PROCESSED / "volume_today.csv", index=False)


if __name__ == "__main__":
    run()
