"""Project-wide paths and constants."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
TABLES = REPORTS / "tables"
SITE_DATA = ROOT / "site" / "data"

SEED = 20261107

# Publication rule: a cell (street-year, hexagon-year, ...) is published only if it
# contains at least this many transactions.
MIN_N_PUBLISH = 5

for _p in (RAW, INTERIM, PROCESSED, FIGURES, TABLES, SITE_DATA):
    _p.mkdir(parents=True, exist_ok=True)

# Minimum sample by level for a full set of statistics. Street cells below the street
# threshold are never published. District cells between MIN_N_PUBLISH and their own
# threshold are published "greyed": the count only, no price statistic.
MIN_N_BY_LEVEL = {"city": 20, "district_l1": 20, "district_l2": 20, "street": 5}

# Bootstrap resamples for the confidence interval of a median.
N_BOOT = 1000
