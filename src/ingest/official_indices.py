"""Official price and rent indices, used (a) to validate the project's own indices and
(b) as the long series for the explosive-root tests. Files go to data/raw/official.

Singapore (data.gov.sg, Singapore Open Data Licence), downloaded by this script:
  ura_private_residential_price_index.csv   d_97f8a2e995022d311c6c68cfda6d034c  (quarterly, from 1975)
  hdb_resale_price_index.csv                d_14f63e595975691e7c24a27ae4c07c79  (quarterly, 1Q2009 = 100)
  ura_private_residential_rental_index.csv  d_8e4c50283fb7052a391dfb746a05c853  (quarterly, from 2004)

Paris: the Notaires-INSEE index of existing apartments in Paris (quarterly, from 1991),
  notaires_insee_paris_apartments.csv
The series identifier is looked up by its exact title on INSEE's list of the series of the
family "Indices des prix des logements anciens" (family 105071770), then the series is read
from INSEE's SDMX service; it is kept only if the title returned with the data names Paris
and apartments. If either step fails, nothing is written: save the series by hand under
that name with two columns, `period` (e.g. 1991-Q1) and `index`.

France, OECD analytical house price indicators (quarterly): house prices, rents, and the
price-to-income and price-to-rent ratios, used to build the Paris affordability and
price-to-rent histories (oecd_house_prices_fra.csv).

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
    "ura_private_residential_rental_index.csv": {"property_type": "Non-Landed", "locality": "Whole Island"},
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


INSEE_FAMILY = "https://www.insee.fr/fr/plan-du-site/famille-bdm/105071770"
INSEE_SDMX = "https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/{idbank}"
PARIS_TITLE = ("Indice des prix des logements anciens - Paris - Appartements - "
               "Base 100 en moyenne annuelle 2015 - Série brute")


def paris_notaires(force: bool = False) -> None:
    import html

    from src.ingest.http import fetch_bytes, record
    dest = OUT / "notaires_insee_paris_apartments.csv"
    if dest.exists() and not force:
        return
    page = html.unescape(fetch_bytes(INSEE_FAMILY, retries=4).decode("utf-8", "ignore"))
    m = re.search(r'href="[^"]*?(\d{9})[^"]*"[^>]*>\s*' + re.escape(PARIS_TITLE) + r"\s*<", page)
    if not m:
        k = page.find("Paris - Appartements")
        raise RuntimeError("series title not found on the INSEE family page; context: "
                           + repr(page[max(k - 300, 0):k + 200] if k >= 0 else page[:300]))
    idbank = m.group(1)
    url = INSEE_SDMX.format(idbank=idbank)
    xml = fetch_bytes(url, retries=4).decode("utf-8", "ignore")
    title = re.search(r'TITLE_FR="([^"]*)"', xml)
    if not title or "Paris" not in title.group(1) or "Appartements" not in title.group(1):
        raise RuntimeError(f"series {idbank}: unexpected title {title.group(1) if title else None!r}")
    obs = re.findall(r'<(?:\w+:)?Obs\b[^>]*?TIME_PERIOD="(\d{4}-Q[1-4])"[^>]*?OBS_VALUE="([-0-9.]+)"', xml)
    obs += [(t, v) for v, t in re.findall(
        r'<(?:\w+:)?Obs\b[^>]*?OBS_VALUE="([-0-9.]+)"[^>]*?TIME_PERIOD="(\d{4}-Q[1-4])"', xml)]
    if len(obs) < 40:
        raise RuntimeError(f"series {idbank}: only {len(obs)} observations parsed")
    d = pd.DataFrame(sorted(set(obs)), columns=["period", "index"])
    d.to_csv(dest, index=False)
    record(dest, url, f"INSEE series {idbank}: {title.group(1)}; {len(d)} quarters")
    print(dest.name, idbank, len(d), d["period"].iloc[0], d["period"].iloc[-1])


OECD_FLOW = "DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES"
OECD_MEASURES = ["HPI", "RPI", "HPI_YDH", "HPI_RPI", "RHP"]
OECD_URLS = [  # the OECD's own service first; DBnomics (a mirror of the same dataflow) as a fallback
    "https://sdmx.oecd.org/public/rest/data/OECD.ECO.MPD,{flow},/FRA.Q.{m}.?format=csvfile",
    "https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,{flow},/FRA.Q.{m}.?format=csvfile",
]
DBNOMICS = "https://api.db.nomics.world/v22/series/OECD/{flow}/FRA.Q.{m}.IX?observations=1"


def oecd_france(force: bool = False) -> None:
    """OECD analytical house price indicators for France, quarterly: nominal house price
    index (HPI), rent price index (RPI), price-to-income (HPI_YDH), price-to-rent (HPI_RPI)
    and real house price index (RHP). Written wide to oecd_house_prices_fra.csv."""
    import io
    import json

    from src.ingest.http import fetch_bytes, record
    dest = OUT / "oecd_house_prices_fra.csv"
    if dest.exists() and not force:
        return
    wide, used = None, None
    for tpl in OECD_URLS:
        url = tpl.format(flow=OECD_FLOW, m="+".join(OECD_MEASURES))
        try:
            d = pd.read_csv(io.BytesIO(fetch_bytes(url, retries=3)))
            d = d[d["TIME_PERIOD"].astype(str).str.match(r"^\d{4}-Q[1-4]$")]
            wide = d.pivot_table(index="TIME_PERIOD", columns="MEASURE", values="OBS_VALUE", aggfunc="first")
            used = url
            break
        except Exception as e:  # noqa: BLE001 - try the next address
            print("OECD address failed:", str(e)[:200])
    if wide is None or wide.shape[0] < 40:
        cols = {}
        for m in OECD_MEASURES:
            url = DBNOMICS.format(flow=OECD_FLOW, m=m)
            doc = json.loads(fetch_bytes(url, retries=3))["series"]["docs"][0]
            cols[m] = pd.Series(pd.to_numeric(pd.Series(doc["value"]), errors="coerce").to_numpy(), index=doc["period"])
        wide, used = pd.DataFrame(cols), DBNOMICS.format(flow=OECD_FLOW, m="<measure>")
    wide = wide.reindex(columns=OECD_MEASURES).dropna(how="all")
    wide.index.name = "period"
    wide.to_csv(dest)
    record(dest, used, f"OECD analytical house price indicators, France, quarterly; {len(wide)} quarters; "
                       f"{wide.index[0]} to {wide.index[-1]}")
    print(dest.name, len(wide), wide.index[0], wide.index[-1], used[:60])


def load_oecd_france() -> pd.DataFrame:
    d = pd.read_csv(OUT / "oecd_house_prices_fra.csv")
    d["period"] = d["period"].map(to_quarter)
    return d.set_index("period").astype(float)


def main(force: bool = False) -> None:
    from src.ingest.singapore import table
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rid in TABLES.items():
        table(rid, OUT / name, force)
    for fn in (paris_notaires, oecd_france):  # each one independent of the other
        try:
            fn(force)
        except Exception as e:  # noqa: BLE001 - reported; the anchor is then "not run"
            print(f"{fn.__name__} failed: {str(e)[:300]}")


if __name__ == "__main__":
    main()
