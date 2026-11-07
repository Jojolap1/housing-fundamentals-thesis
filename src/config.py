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
