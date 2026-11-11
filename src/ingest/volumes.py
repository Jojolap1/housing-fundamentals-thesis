"""Long series of the number of housing transactions, for the volume signal.

- HDB resale flats: every registered resale since 1990 (data.gov.sg collection 189, five
  files); only the count per quarter is kept. Before March 2012 the month is the approval
  date of the resale, from March 2012 the registration date.
- Private homes, Singapore: URA quarterly count of new sales, sub-sales and resales
  (data.gov.sg), from 1999 Q4. Sub-sales and resales come from caveats before 2015 Q1 and
  from stamp duty records since, so the two periods are not strictly comparable.
- France: INSEE series of the number of sales of existing dwellings over twelve months.

The transaction files stay in data/raw; data/processed/volume_series.csv holds counts only."""
from __future__ import annotations

import re

import pandas as pd

from src.config import PROCESSED, RAW
from src.ingest.http import fetch_bytes, fetch_json, record
from src.ingest.singapore import table

OUT = RAW / "volumes"
HDB_COLLECTION = "https://api-production.data.gov.sg/v2/public/api/collections/189/metadata"
HDB_KNOWN = ["d_ebc5ab87086db484f88045b47411ebc5", "d_43f493c6c50d54243cc1eab0df142d6a",
             "d_8b84c4ee58e3cfc0ece0d773c8ca6abc"]
URA_TRANSACTIONS = "d_7c69c943d5f0d89d6a9a773d2b51f337"
INSEE_SDMX = "https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/{idbank}"
INSEE_CANDIDATE = "000857201"


def hdb_counts(force: bool = False) -> pd.Series:
    import json
    try:
        ids = sorted(set(re.findall(r"d_[0-9a-f]{32}", json.dumps(fetch_json(HDB_COLLECTION, retries=4)))))
    except Exception as e:  # the collection listing is a convenience; the known files still load
        print("collection listing failed:", e)
        ids = []
    ids = sorted(set(ids) | set(HDB_KNOWN))
    counts = []
    for rid in ids:
        dest = OUT / f"hdb_resale_{rid}.csv"
        table(rid, dest, force)
        d = pd.read_csv(dest, usecols=["month"], dtype=str)
        q = pd.PeriodIndex(d["month"].str.slice(0, 7), freq="M").asfreq("Q")
        counts.append(pd.Series(1, index=q).groupby(level=0).sum())
        print(rid, len(d), d["month"].min(), d["month"].max())
    s = pd.concat(counts).groupby(level=0).sum().sort_index()
    full = pd.period_range(s.index[0], s.index[-1], freq="Q")
    missing = [str(p) for p in full if p not in s.index]
    if missing:
        print("quarters without any file:", missing[:6], "..." if len(missing) > 6 else "")
    return s


def ura_counts(force: bool = False) -> pd.DataFrame:
    dest = OUT / "ura_private_transactions_quarterly.csv"
    table(URA_TRANSACTIONS, dest, force)
    d = pd.read_csv(dest)
    print(dest.name, list(d.columns), len(d))
    for c in d.columns:
        if d[c].dtype == object and d[c].nunique() < 12:
            print(" ", c, d[c].value_counts().to_dict())
    print(d.head(8).to_string())
    return d


def insee_probe() -> pd.Series | None:
    xml = fetch_bytes(INSEE_SDMX.format(idbank=INSEE_CANDIDATE), retries=4).decode("utf-8", "ignore")
    title = re.search(r'TITLE_FR="([^"]*)"', xml)
    obs = re.findall(r'TIME_PERIOD="(\d{4}-(?:Q[1-4]|\d{2}))"[^>]*?OBS_VALUE="([-0-9.]+)"', xml)
    obs += [(t, v) for v, t in re.findall(r'OBS_VALUE="([-0-9.]+)"[^>]*?TIME_PERIOD="(\d{4}-(?:Q[1-4]|\d{2}))"', xml)]
    obs = sorted(set(obs))
    print("INSEE", INSEE_CANDIDATE, "title:", title.group(1) if title else None, "| obs:", len(obs), obs[:2], obs[-2:])
    if not title or "transactions" not in title.group(1).lower() or len(obs) < 40:
        return None
    (OUT / "insee_transactions.csv").write_text("period,value\n" + "\n".join(f"{t},{v}" for t, v in obs) + "\n")
    record(OUT / "insee_transactions.csv", INSEE_SDMX.format(idbank=INSEE_CANDIDATE), f"INSEE {INSEE_CANDIDATE}: {title.group(1)}")
    return pd.Series({t: float(v) for t, v in obs})


def main(force: bool = False) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    out = []
    for name, f in (("hdb", hdb_counts), ("ura", ura_counts), ("insee", insee_probe)):
        try:
            r = f(force) if name != "insee" else f()
        except Exception as e:
            print(name, "FAILED:", repr(e)[:400])
            continue
        if name == "hdb":
            out.append(pd.DataFrame({"city": "singapore", "series": "resale_registrations", "period": [str(p) for p in r.index], "value": r.to_numpy()}))
    if out:
        pd.concat(out).to_csv(PROCESSED / "volume_series.csv", index=False)


if __name__ == "__main__":
    main()
