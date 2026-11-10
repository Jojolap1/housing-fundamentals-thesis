"""Explosive-root tests, price-to-rent dynamics and the verdict table.

Inputs:
  data/processed/sensitivity_<city>.csv         user-cost sensitivity grid (src/ratios/valuation.py)
  data/raw/official/*.csv                       official indices (src/ingest/official_indices.py)

Outputs (data/processed):
  explosive_<series>.csv     BSADF sequence against its 95% critical values
  explosive_summary.csv      SADF, GSADF, critical values, dated episodes, settings
  price_rent_<city>.csv      long-horizon regressions (where a rent index exists)
  ratio_history.csv          price-to-income and price-to-rent: latest value against its history
  verdict.csv                one row per city / segment

An anchor that cannot be run (missing file, series too short) is recorded as "not run" with
the reason. It is never replaced by an assumption.
"""
from __future__ import annotations

import pandas as pd

from src.config import PROCESSED, RAW
from src.ingest.official_indices import load_quarterly
from src.valuation.explosive import explosive_test
from src.valuation.price_rent import long_horizon, ratio_zscore
from src.valuation.verdict import user_cost_share, user_cost_signal, verdict, z_signal

OFF = RAW / "official"
# city -> (price index file, rent index file or None, last full year of the valuation)
SEGMENTS = {
    "paris": ("notaires_insee_paris_apartments.csv", None),
    "singapore": ("hdb_resale_price_index.csv", None),
    "singapore_private": ("ura_private_residential_price_index.csv", "ura_private_residential_rental_index.csv"),
}


def _series(name: str | None):
    if name is None:
        return None, "no long rent index identified for this market"
    p = OFF / name
    if not p.exists():
        return None, f"{name} not downloaded"
    try:
        return load_quarterly(p), ""
    except ValueError as e:
        return None, str(e)


def _explosive(label: str, s: pd.Series, summary: list) -> int | None:
    try:
        r = explosive_test(s)
    except ValueError as e:
        summary.append({"series": label, "status": f"not run: {e}"})
        return None
    r["sequence"].to_csv(PROCESSED / f"explosive_{label}.csv", index=False)
    summary.append({"series": label, "status": "run", "first": s.index[0], "last": s.index[-1], "T": r["T"],
                    "min_window": r["min_window"], "lag": r["lag"], "nrep": r["nrep"],
                    "sadf": r["sadf"], "sadf_cv95": r["cv"]["sadf"][0.95],
                    "gsadf": r["gsadf"], "gsadf_cv95": r["cv"]["gsadf"][0.95],
                    "episodes": "; ".join(f"{a} to {b}" for a, b in r["episodes"]) or "none",
                    # direction of the last episode: the statistic also rises in an accelerating fall
                    "last_episode_change_pct": (100 * (s[r["episodes"][-1][1]] / s[r["episodes"][-1][0]] - 1)
                                                if r["episodes"] else float("nan")),
                    "explosive_at_end": r["explosive_at_end"]})
    return int(r["reject_gsadf_95"] and r["explosive_at_end"])


def _annual(q: pd.Series) -> pd.Series:
    """Annual mean of a quarterly series indexed 'YYYYQn'; years with four quarters only."""
    g = q.groupby(q.index.str[:4].astype(int))
    return g.mean()[g.count() == 4]


def singapore_income() -> pd.Series:
    """Median monthly household income from work incl. employer CPF, resident employed
    households, annual (SingStat via data.gov.sg; the series already used for price-to-income)."""
    n = pd.read_csv(RAW / "singapore" / "hh_income_work_national_2000_2025.csv")
    return n.set_index(n["Dollar"].astype(int))["ResidentEmployedHouseholds_Median1"].astype(float)


def france_denominators() -> tuple[pd.Series, pd.Series]:
    """(income index, rent index) for France, quarterly, from the OECD indicators.
    Income = nominal disposable income per head, recovered as HPI / price-to-income."""
    from src.ingest.official_indices import load_oecd_france
    o = load_oecd_france()
    return (o["HPI"] / o["HPI_YDH"]).dropna(), o["RPI"].dropna()


def _ratio_anchor(label: str, num: pd.Series, den: pd.Series, ratios: list, summary: list,
                  explosive: bool = True) -> float | None:
    """z-score of the latest log ratio in its own history; records the series; optionally
    runs the explosive-root test on the ratio (reported, not an anchor by itself)."""
    d = pd.concat([num.rename("p"), den.rename("r")], axis=1).dropna()
    if len(d) < 20:
        return None
    z = ratio_zscore(d["p"], d["r"])
    ratio = d["p"] / d["r"]
    ratios.append({"series": label, "first": d.index[0], "last": d.index[-1], "n": z["n"], "z_last": z["z_last"],
                   "last_vs_mean_pct": 100 * (ratio.iloc[-1] / ratio.mean() - 1),
                   "last_vs_max_pct": 100 * (ratio.iloc[-1] / ratio.max() - 1),
                   "period_of_max": ratio.idxmax()})
    if explosive:
        _explosive(label, ratio, summary)
    return z["z_last"]


def run() -> pd.DataFrame:
    summary, rows, ratios = [], [], []
    try:
        fr_income, fr_rent = france_denominators()
        fr_why = ""
    except Exception as e:  # noqa: BLE001
        fr_income = fr_rent = None
        fr_why = f"OECD indicators for France not available ({str(e)[:120]})"
    try:
        sg_income = singapore_income()
    except Exception as e:  # noqa: BLE001
        sg_income = None
        print("Singapore income series not available:", e)
    for city, (pfile, rfile) in SEGMENTS.items():
        notes, sig = [], {}
        sens = pd.read_csv(PROCESSED / f"sensitivity_{city}.csv")
        # latest full calendar year: the last year but one if the last year is still running
        years = sorted(sens["year"].unique())
        year = years[-2] if len(years) > 1 else years[-1]
        share = user_cost_share(sens, year)
        sig["user_cost"] = user_cost_signal(share)
        price, why = _series(pfile)
        if price is None:
            sig["explosive"] = None
            notes.append(f"explosive: {why}")
        else:
            sig["explosive"] = _explosive(f"{city}_price", price, summary)
        rent, why = _series(rfile)
        if price is None or rent is None:
            sig["price_rent"] = None
            notes.append(f"price_rent: {why or 'price index missing'}")
        else:
            sig["price_rent"] = z_signal(_ratio_anchor(f"{city}_price_to_rent", price, rent, ratios, summary))
            try:
                long_horizon(price, rent).to_csv(PROCESSED / f"price_rent_{city}.csv", index=False)
            except ValueError as e:
                notes.append(f"price_rent regression: {e}")
        # Paris: no city-level rent or income history is open, so the denominators are the
        # national rent index and national disposable income per head (OECD).
        if city == "paris" and price is not None:
            if fr_rent is None:
                notes.append(f"price_rent: {fr_why}")
            else:
                z = _ratio_anchor("paris_price_to_national_rent", price, fr_rent, ratios, summary)
                sig["price_rent"] = z_signal(z)
                notes = [n for n in notes if not n.startswith("price_rent:")]
                notes.append("price_rent: Paris price index over the national rent index (OECD)")
        # Affordability: price index over an income series, latest value against its history.
        z, how = None, ""
        if price is None:
            how = "price index missing"
        elif city == "paris":
            if fr_income is None:
                how = fr_why
            else:
                z = _ratio_anchor("paris_price_to_national_income", price, fr_income, ratios, summary)
                how = "Paris price index over national disposable income per head (OECD)"
        elif sg_income is None:
            how = "national household income series missing"
        else:
            z = _ratio_anchor(f"{city}_price_to_income", _annual(price), sg_income, ratios, summary, explosive=False)
            how = "annual price index over national median household income from work"
        sig["affordability"] = z_signal(z)
        notes.append(f"affordability: {how}" if z is not None else f"affordability not run: {how or 'series too short'}")
        rows.append({"city": city, "valuation_year": year, "user_cost_share_gap_positive": share,
                     **{f"signal_{k}": v for k, v in sig.items()}, **verdict(sig), "notes": " | ".join(notes)})
    out = pd.DataFrame(rows)
    out.to_csv(PROCESSED / "verdict.csv", index=False)
    pd.DataFrame(summary).to_csv(PROCESSED / "explosive_summary.csv", index=False)
    pd.DataFrame(ratios).to_csv(PROCESSED / "ratio_history.csv", index=False)
    print(out[["city", "valuation_year", "user_cost_share_gap_positive", "verdict", "anchors_not_run"]].to_string(index=False))
    return out


if __name__ == "__main__":
    run()
