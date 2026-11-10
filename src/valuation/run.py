"""Explosive-root tests, price-to-rent dynamics and the verdict table.

Inputs:
  data/processed/sensitivity_<city>.csv         user-cost sensitivity grid (src/ratios/valuation.py)
  data/raw/official/*.csv                       official indices (src/ingest/official_indices.py)

Outputs (data/processed):
  explosive_<series>.csv     BSADF sequence against its 95% critical values
  explosive_summary.csv      SADF, GSADF, critical values, dated episodes, settings
  price_rent_<city>.csv      long-horizon regressions (where a rent index exists)
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
                    "explosive_at_end": r["explosive_at_end"]})
    return int(r["reject_gsadf_95"] and r["explosive_at_end"])


def run() -> pd.DataFrame:
    summary, rows = [], []
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
            z = ratio_zscore(price, rent)
            sig["price_rent"] = z_signal(z["z_last"])
            try:
                long_horizon(price, rent).to_csv(PROCESSED / f"price_rent_{city}.csv", index=False)
            except ValueError as e:
                notes.append(f"price_rent regression: {e}")
            both = pd.concat([price.rename("p"), rent.rename("r")], axis=1).dropna()
            _explosive(f"{city}_price_to_rent", both["p"] / both["r"], summary)
        sig["affordability"] = None
        notes.append("affordability: no price-to-income history to compare the current level with")
        rows.append({"city": city, "valuation_year": year, "user_cost_share_gap_positive": share,
                     **{f"signal_{k}": v for k, v in sig.items()}, **verdict(sig), "notes": " | ".join(notes)})
    out = pd.DataFrame(rows)
    out.to_csv(PROCESSED / "verdict.csv", index=False)
    pd.DataFrame(summary).to_csv(PROCESSED / "explosive_summary.csv", index=False)
    print(out[["city", "valuation_year", "user_cost_share_gap_positive", "verdict", "anchors_not_run"]].to_string(index=False))
    return out


if __name__ == "__main__":
    run()
