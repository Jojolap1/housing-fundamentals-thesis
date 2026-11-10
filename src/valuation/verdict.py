"""Verdict per city / segment, from a rule fixed before looking at the results.

Each anchor gives a signal: +1 (points to prices above fundamentals), 0 (does not),
-1 (points to prices below), or None (could not be run; the reason is recorded).

Anchors and their conventions (thresholds are conventions, stated so they can be challenged):
- user_cost   (rent-based): share of the defined sensitivity-grid cells with a positive
                valuation gap in the latest full year. >= 0.8 -> +1; <= 0.2 -> -1; else 0.
- price_rent  (rent-based): z-score of the latest log price-to-rent ratio in its own
                history. > +1 -> +1; < -1 -> -1; else 0.
- explosive   (not rent-based): GSADF rejects at 5% and a dated episode includes the last
                observation -> +1; else 0.
- affordability (not rent-based): z-score of the latest price-to-income ratio in its own
                history, same thresholds. Not run without a history.

Rule:
- "evidence of deviation": at least three anchors at +1, one of them not rent-based;
- "consistent with fundamentals": at least two anchors could be run, none is at +1, and the
  user-cost anchor is at -1 (the sign of the gap is stable over most of the grid);
- "inconclusive": everything else.
"""
from __future__ import annotations

import pandas as pd

RENT_BASED = {"user_cost", "price_rent"}
UC_HI, UC_LO, Z = 0.8, 0.2, 1.0


def user_cost_share(sens: pd.DataFrame, year: int) -> float:
    """Share of grid cells (rf_shift × gamma × g) with a defined, positive median gap."""
    s = sens[(sens["year"] == year) & sens["gap_median"].notna()]
    return float((s["gap_median"] > 0).mean()) if len(s) else float("nan")


def user_cost_signal(share: float) -> int | None:
    if share != share:
        return None
    return 1 if share >= UC_HI else -1 if share <= UC_LO else 0


def z_signal(z: float | None) -> int | None:
    if z is None or z != z:
        return None
    return 1 if z > Z else -1 if z < -Z else 0


def verdict(signals: dict[str, int | None]) -> dict:
    run = {k: v for k, v in signals.items() if v is not None}
    up = sorted(k for k, v in run.items() if v == 1)
    if len(up) >= 3 and any(k not in RENT_BASED for k in up):
        label = "evidence of deviation"
    elif len(run) >= 2 and not up and run.get("user_cost") == -1:
        label = "consistent with fundamentals"
    else:
        label = "inconclusive"
    return {"verdict": label, "anchors_pointing_to_deviation": ", ".join(up) or "none",
            "anchors_run": ", ".join(sorted(run)) or "none",
            "anchors_not_run": ", ".join(sorted(k for k, v in signals.items() if v is None)) or "none"}
