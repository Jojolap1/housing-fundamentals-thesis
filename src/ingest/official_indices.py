"""Official price and rent indices, used (a) to validate the project's own indices and
(b) as the long series for the explosive-root tests. Files go to data/raw/official.

Singapore (data.gov.sg, Singapore Open Data Licence), downloaded by this script:
  ura_private_residential_price_index.csv   d_97f8a2e995022d311c6c68cfda6d034c  (quarterly, from 1975)
  hdb_resale_price_index.csv                d_14f63e595975691e7c24a27ae4c07c79  (quarterly, 1Q2009 = 100)
  ura_private_residential_rental_index.csv  d_8e4c50283fb7052a391dfb746a05c853  (quarterly, from 2004)

Paris: the Notaires-INSEE index of existing apartments in Paris (quarterly, from 1991) is
published by INSEE. Its series identifier has not been verified here, so it is NOT
downloaded automatically: save the series by hand as
  data/raw/official/notaires_insee_paris_apartments.csv
with two columns, `period` (e.g. 1991-Q1 or 1991Q1) and `index`, and record the source URL
and date in docs/data_audit.md.

`load_quarterly` reads any of these files into a Series indexed by 'YYYYQn'. It refuses a
file it cannot read unambiguously rather than guessing.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.config import RAW

OUT = RAW / "official"
TABLES = {
    "ura_private_residential_price_index.csv": "d_97f8a2e995022d311c6c68cfda6d034c",
    "hdb_resale_price_index.csv": "d_14f63e595975691e7c24a27ae4c07c79",
    "ura_private_residential_rental_index.csv": "d_8e4c50283fb7052a391dfb746a05c853",
}
# Files that hold several series: the one used by default (the project's private-market
# sample is non-landed apartments and condominiums).
DEFAULT_WHERE = {
    "ura_private_residential_price_index.csv": {"property_type": "Non-Landed"},
    "ura_private_residential_rental_index.csv": {"property_type": "Non-Landed"},
}
_Q = re.compile(r"^\s*(\d{4})\s*[-_ ]?\s*Q\s*([1-4])\s*$", re.I)
_Q_REV = re.compile(r"^\s*([1-4])\s*Q\s*[-_ ]?\s*(\d{4})\s*$", re.I)


def to_quarter(v) -> str | None:
    s = str(v)
    m = _Q.match(s)
    if m:
        return f"{m.group(1)}Q{m.group(2)}"
    m = _Q_REV.match(s)
    return f"{m.group(2)}Q{m.group(1)}" if m else None


def load_quarterly(path: Path, where: dict | None = None) -> pd.Series:
    """Quarterly index from a CSV. The period column is the one whose values all parse as
    quarters; the value column is the only remaining numeric column. If other columns
    split the file into several series (e.g. a property-type column), pass `where`
    ({column: value}) to pick one; otherwise an error lists the choices."""
    d = pd.read_csv(path, dtype=str)
    d = d.drop(columns=[c for c in d.columns if c == "_id"])
    where = DEFAULT_WHERE.get(Path(path).name) if where is None else where
    for col, val in (where or {}).items():
        if col not in d.columns or val not in set(d[col]):
            have = sorted(d[col].unique())[:12] if col in d.columns else list(d.columns)
            raise ValueError(f"{Path(path).name}: no rows with {col} = {val!r}; available: {have}")
        d = d[d[col] == val].drop(columns=col)
    pcol = [c for c in d.columns if d[c].map(to_quarter).notna().all()]
    if len(pcol) != 1:
        raise ValueError(f"{path.name}: expected one quarter column, found {pcol} among {list(d.columns)}")
    q = d[pcol[0]].map(to_quarter)
    rest = d.drop(columns=pcol)
    num = [c for c in rest.columns if pd.to_numeric(rest[c], errors="coerce").notna().mean() > 0.5]
    other = [c for c in rest.columns if c not in num]
    if len(num) != 1 or q.duplicated().any():
        choices = {c: sorted(rest[c].unique())[:12] for c in other}
        raise ValueError(f"{path.name}: cannot pick one series (numeric columns {num}; "
                         f"duplicated quarters: {bool(q.duplicated().any())}). Pass `where` using one of {choices}")
    s = pd.Series(pd.to_numeric(rest[num[0]], errors="coerce").to_numpy(), index=q.to_numpy(), name="index")
    return s.dropna().sort_index()


def main(force: bool = False) -> None:
    from src.ingest.singapore import table
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rid in TABLES.items():
        table(rid, OUT / name, force)


if __name__ == "__main__":
    main()
