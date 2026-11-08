"""User-cost parameters for the fundamental value V* = annual rent / user cost.

    user cost u = r_f + tau + delta + gamma - g          (Poterba 1984; Himmelberg, Mayer & Sinai 2005)

r_f comes from data (src/ingest/rates.py): the mean 10-year government yield over the
analysis year. Every other term is an ASSUMPTION, not a measurement. Each has a baseline
taken from the literature or from the tax rules, and a range that the sensitivity grid
covers. They are kept here, in one place, so they can be challenged and changed.

tau   property tax as % of market value
      Paris: taxe foncière is levied on cadastral rental values (1970 base), not on market
      value; its effective rate on Paris market values is low. Baseline 0.25%, range 0.1-0.5%.
      Singapore: owner-occupier property tax on HDB annual values is progressive and small
      relative to resale prices. Baseline 0.10%, range 0.0-0.3%.
      Singapore private homes: owner-occupier rates are progressive on the annual value (about
      the annual rent) and non-owner-occupier rates are 12-36% of it, i.e. roughly 0.1-1% of
      market value at a 3% gross yield. Baseline 0.40%, range 0.1-1.0%.
delta maintenance + depreciation, % of value. HMS (2005) use 2.5% (structure-heavy US
      housing). Land is a large share of value in both cities, so the baseline is lower:
      1.5%, range 1.0-2.5%. Singapore HDB adds lease decay, which is handled through the
      remaining-lease term in the models rather than through delta.
gamma risk premium of owning over a risk-free bond. HMS (2005): 2%. Range 1-4%.
g     expected long-run nominal growth of rents/prices. Baseline 2% (Paris: the ECB
      inflation target; Singapore: same value for comparability). Range 0-4%.
"""

BASE = {
    "Paris":     {"tau": 0.0025, "delta": 0.015, "gamma": 0.02, "g": 0.02},
    "Singapore": {"tau": 0.0010, "delta": 0.015, "gamma": 0.02, "g": 0.02},
    "Singapore private": {"tau": 0.0040, "delta": 0.015, "gamma": 0.02, "g": 0.02},
}

# Sensitivity grid (the user asked for r_f, risk premium and growth). r_f is shifted
# around its observed value; the other two take absolute values.
GRID = {
    "rf_shift": [-0.01, -0.005, 0.0, 0.005, 0.01],
    "gamma": [0.01, 0.02, 0.03, 0.04],
    "g": [0.0, 0.01, 0.02, 0.03, 0.04],
}

# User cost must stay strictly positive; combinations below this floor are reported as
# "undefined" (V* explodes as u -> 0), never silently clipped.
MIN_USER_COST = 0.005

# Price-to-income reference dwellings.
PTI_REF = {
    "Paris": {"area_m2": 60, "household_uc": 1.5},  # couple without children = 1.5 UC (modified OECD scale)
    "Singapore": {"flat_type": "4 ROOM"},
}
