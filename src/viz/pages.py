"""Write the static HTML pages of the site (site/*.html).

Every page carries <meta name="robots" content="noindex">: the DVF reuse terms forbid
search-engine indexing, and a GitHub project site cannot rely on a root robots.txt.
"""
from __future__ import annotations

from src.config import ROOT

SITE = ROOT / "site"
MAPLIBRE = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl"

HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="assets/style.css">
{extra}
</head>
<body{body_attr}>
<header class="top"><div class="wrap">
  <a class="brand" href="index.html">Housing fundamentals</a>
  <nav>
    <a href="index.html"{a_home}>Overview</a>
    <a href="paris.html"{a_paris}>Paris</a>
    <a href="singapore.html"{a_sg}>Singapore (HDB)</a>
    <a href="singapore_private.html"{a_sgp}>Singapore (private)</a>
    <a href="methodology.html"{a_meth}>Method &amp; limits</a>
  </nav>
</div></header>
<main class="wrap">
"""

FOOT = """</main>
<footer><div class="wrap">
Code and processed aggregates: see the project repository. Data: DGFiP / Etalab (DVF), Ville de Paris (ODbL),
INSEE, IGN, Île-de-France Mobilités, HDB / URA / LTA / NParks / SingStat via data.gov.sg (Singapore Open Data
Licence), ECB. Map tiles © OpenStreetMap contributors © CARTO. Derived databases from ODbL sources are released
under ODbL. Nothing here is investment advice.
</div></footer>
</body>
</html>
"""


def head(title, desc, page, extra="", body_attr=""):
    cur = {k: "" for k in ("home", "paris", "sg", "sgp", "meth")}
    cur[page] = ' aria-current="page"'
    return HEAD.format(title=title, desc=desc, extra=extra, body_attr=body_attr,
                       a_home=cur["home"], a_paris=cur["paris"], a_sg=cur["sg"], a_sgp=cur["sgp"], a_meth=cur["meth"])


INDEX = """
<h1>Are housing prices justified by fundamentals?</h1>
<p class="lede">Machine-learning and hedonic models trained on transaction prices estimate <em>market</em> value. They cannot,
by construction, say whether that market value is justified. This project anchors <em>fundamental</em> value on rents
capitalised at the user cost of housing (Poterba 1984; Himmelberg, Mayer &amp; Sinai 2005) and treats overvaluation as a
hypothesis to test, not a premise.</p>

<div class="card">
<h2 style="margin-top:0">Method in five lines</h2>
<ol>
<li>Official transaction registers are cleaned and harmonised into one schema per city (every removed row is logged).</li>
<li>Hedonic OLS (district fixed effects), Random Forest and LightGBM predict price per m²; they are validated with spatial block cross-validation and a time split.</li>
<li>Annual rent R comes from regulatory reference rents (Paris) or HDB rental approvals (Singapore).</li>
<li>Fundamental value V* = R / (r<sub>f</sub> + property tax + maintenance + risk premium − expected growth); for 99-year HDB leases, R is discounted over the remaining lease only.</li>
<li>Valuation gap = predicted price / V* − 1, reported with a sensitivity grid over r<sub>f</sub>, the risk premium and growth.</li>
</ol>
</div>

<div class="grid2">
<a class="card" href="paris.html" style="text-decoration:none;color:inherit"><b>Paris</b><br><span class="note" style="display:block;margin-top:6px">DVF apartment sales, Jul 2021 – Jun 2026 · reference rents 2021–2025 · INSEE Filosofi 2021</span></a>
<a class="card" href="singapore.html" style="text-decoration:none;color:inherit"><b>Singapore (HDB)</b><br><span class="note" style="display:block;margin-top:6px">Public resale flats, Jan 2017 – latest month · HDB rental approvals from 2021 · Census 2020 income</span></a>
<a class="card" href="singapore_private.html" style="text-decoration:none;color:inherit"><b>Singapore (private)</b><br><span class="note" style="display:block;margin-top:6px">Private apartments and condominiums, Nov 2021 – latest month · URA rental contracts · the open market</span></a>
</div>

<h2>Data sources</h2>
<div class="card table-scroll"><table>
<thead><tr><th>City</th><th>Data</th><th>Source</th><th>Licence</th><th>Retrieved</th></tr></thead>
<tbody>
<tr><td>Paris</td><td>Transactions (DVF géolocalisées)</td><td><a href="https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres-geolocalisees">data.gouv.fr</a></td><td>Licence Ouverte 2.0 + DGFiP terms</td><td>2026-11-07</td></tr>
<tr><td>Paris</td><td>Reference rents (encadrement des loyers)</td><td><a href="https://opendata.paris.fr/explore/dataset/logement-encadrement-des-loyers/">opendata.paris.fr</a></td><td>ODbL</td><td>2026-11-07</td></tr>
<tr><td>Paris</td><td>Income by IRIS (Filosofi 2021)</td><td><a href="https://www.insee.fr/fr/statistiques/8229323">insee.fr</a></td><td>Licence Ouverte 2.0</td><td>2026-11-07</td></tr>
<tr><td>Paris</td><td>Buildings (BD TOPO), IRIS contours</td><td><a href="https://geoservices.ign.fr/">IGN (data.geopf.fr)</a></td><td>Licence Ouverte 2.0</td><td>2026-11-07</td></tr>
<tr><td>Paris</td><td>Stations</td><td><a href="https://data.iledefrance-mobilites.fr/explore/dataset/emplacement-des-gares-idf/">Île-de-France Mobilités</a></td><td>Licence Ouverte</td><td>2026-11-07</td></tr>
<tr><td>Paris</td><td>Green spaces, arrondissements, quartiers</td><td><a href="https://opendata.paris.fr/">opendata.paris.fr</a></td><td>ODbL</td><td>2026-11-07</td></tr>
<tr><td>Singapore</td><td>HDB resale prices</td><td><a href="https://data.gov.sg/datasets/d_8b84c4ee58e3cfc0ece0d773c8ca6abc/view">data.gov.sg</a></td><td>Singapore Open Data Licence</td><td>2026-11-07</td></tr>
<tr><td>Singapore</td><td>HDB renting out of flats</td><td><a href="https://data.gov.sg/datasets/d_c9f57187485a850908655db0e8cfe651/view">data.gov.sg</a></td><td>Singapore Open Data Licence</td><td>2026-11-07</td></tr>
<tr><td>Singapore</td><td>Census 2020 household income by planning area</td><td><a href="https://data.gov.sg/datasets/d_4e150bbd35c3145ea43019212c7b46c2/view">data.gov.sg</a></td><td>Singapore Open Data Licence</td><td>2026-11-07</td></tr>
<tr><td>Singapore</td><td>Planning areas, subzones (MP2019), MRT exits, parks</td><td><a href="https://data.gov.sg/">data.gov.sg (URA, LTA, NParks)</a></td><td>Singapore Open Data Licence</td><td>2026-11-07</td></tr>
<tr><td>Singapore</td><td>Private transactions and rental contracts</td><td><a href="https://eservice.ura.gov.sg/maps/api/">URA Data Service</a></td><td>URA terms of use (access key)</td><td>2026-11-07</td></tr>
<tr><td>Singapore</td><td>Block geocoding</td><td><a href="https://www.onemap.gov.sg/apidocs/">OneMap (SLA)</a></td><td>OneMap terms of use</td><td>2026-11-07</td></tr>
<tr><td>Both</td><td>FX (ECB reference rates), 10-year government yields</td><td><a href="https://data.ecb.europa.eu/">ECB</a>, <a href="https://tablebuilder.singstat.gov.sg/table/TS/M700071">SingStat M700071</a></td><td>Reuse with attribution</td><td>2026-11-07</td></tr>
</tbody></table></div>
<p class="note">Valuation gaps are model-dependent hypotheses, not investment advice. Street-level and hexagon statistics are published only for cells with at least five transactions in the year; no individual transaction or address is shown.</p>
"""

CITY = """
<h1>{name}</h1>
<p class="lede">{lede}</p>
<p class="meta-line">Period: <span id="period">…</span> · retained transactions: <span id="ntotal">…</span> · source: {source}</p>

<div class="card">
  <div class="controls">
    <label>Geography<select id="layer">
      <option value="hex">Hexagons (H3 res. 9, street scale)</option>
      <option value="l1">{l1}</option>
      <option value="l2">{l2}</option>
    </select></label>
    <label>Indicator<select id="metric">
      <option value="ppm2">Price per m²</option>
      <option value="rent">{rent_label}</option>
      <option value="yield">Gross rental yield</option>
      <option value="pti">Price-to-income</option>
      <option value="gap">Valuation gap (model)</option>
      <option value="mis">Relative mispricing</option>
    </select></label>
    <label>Year<select id="year"></select></label>
  </div>
  <div id="map-title" style="font-weight:600;margin-bottom:6px"></div>
  <div id="map" style="position:relative"></div>
  <div class="legend" id="legend"></div>
  <p class="note" id="gap-note" hidden>The valuation gap compares the model's predicted market price with rents capitalised at an
  assumed user cost. A positive value means prices are above what rents justify <em>under the baseline assumptions</em>;
  see the sensitivity band below. It is a model-dependent hypothesis, not investment advice.</p>
  <p class="note" id="mis-note" hidden>Relative mispricing is the median residual of the price model: positive = dearer than
  comparable dwellings elsewhere in the city, negative = cheaper. It says nothing about a bubble.</p>
  <p class="meta-line">Source: {source}. Period shown: the selected year. Cells with fewer than 5 transactions in a year are
  not published. Valuation gaps are model-dependent hypotheses, not investment advice.</p>
</div>

<h2>Fundamental vs market value per m²</h2>
<div class="card">
  <div class="legend"><span><span style="color:var(--series-market)">●</span> Market: median transaction price per m²</span>
  <span><span style="color:var(--series-fund)">●</span> Fundamental: median V* per m², baseline assumptions</span>
  <span><span style="display:inline-block;width:18px;height:10px;background:var(--band-fund)"></span> Range of V* over the sensitivity grid (r<sub>f</sub> ±1 pt, risk premium 1–4%, growth 0–4%)</span></div>
  <div class="chart-wrap" id="chart"></div>
  <details><summary>Table view</summary><div id="chart-table" class="table-scroll"></div></details>
  <p class="note">{fund_note}</p>
</div>

<h2>Streets</h2>
<div class="card">
  <div class="controls">
    <label>Year<select id="t-year"></select></label>
    <label>Search street<input type="search" id="t-search" placeholder="e.g. {example}"></label>
    <span class="meta-line" id="t-count"></span>
  </div>
  <div class="table-scroll"><table>
    <thead id="t-head"><tr><th>Street</th><th>{l1}</th><th class="num" data-k="n">n</th><th class="num" data-k="ppm2">Median {cur}/m²</th>
    <th class="num">IQR</th><th class="num" data-k="yoy">YoY</th><th class="num" data-k="mis">Rel. mispricing</th></tr></thead>
    <tbody id="t-body"></tbody>
  </table></div>
  <p class="meta-line">Only street-years with at least 5 transactions are listed. Relative mispricing = cheap/expensive versus
  comparable dwellings, not a bubble indicator.</p>
</div>
<script src="{maplibre}.js"></script>
<script src="assets/app.js"></script>
"""

CITIES = {
    "paris": dict(
        name="Paris", page="paris", l1="Arrondissement", l2="Quartier", cur="€", example="RUE DE RIVOLI",
        rent_label="Reference rent per m²",
        source="DGFiP DVF géolocalisées (apartment sales), Ville de Paris reference rents, INSEE Filosofi 2021",
        lede="Single-apartment sales recorded by the tax administration, July 2021 – June 2026. Rents are the city's "
             "regulatory reference rents (unfurnished, by quartier, rooms and construction period): they are not "
             "observed contracts, and the rented stock differs from the stock that is sold.",
        fund_note="Paris reference rents are regulatory values set from observed rents; the gap therefore measures prices "
                  "against regulated-market rents. 2021 covers July–December and 2026 January–June.",
    ),
    "singapore": dict(
        name="Singapore (HDB)", page="sg", l1="Planning area", l2="Subzone", cur="S$", example="ANG MO KIO AVE 10",
        rent_label="Monthly rent per flat",
        source="HDB resale flat prices and HDB rental approvals (data.gov.sg), Census of Population 2020",
        lede="Resale transactions of public (HDB) flats on 99-year leases, January 2017 onward. Rents are HDB approvals to "
             "rent out whole flats. Fundamental value discounts rent over the remaining lease, not in perpetuity.",
        fund_note="HDB rents are available from 2021; earlier years use the rent model's 2021 level and should be read "
                  "with care. A negative gap does not mean HDB flats are a bargain anyone can take: only eligible "
                  "households (mainly citizens) may buy, owners must live in the flat for 5 years before renting it "
                  "out, and grants and CPF rules shape demand, so rent capitalisation is constrained. Private "
                  "condominiums (URA) are not included yet.",
    ),
    "singapore_private": dict(
        name="Singapore (private)", page="sgp", l1="Planning area", l2="Subzone", cur="S$", example="ANSON ROAD",
        rent_label="Monthly rent per home",
        source="URA private residential transactions and rental contracts (URA Data Service), Census of Population 2020",
        lede="Sales of private apartments and condominiums (the open market: no eligibility rules, buy-to-let allowed), "
             "November 2021 onward, and the rental contracts stamped with IRAS. This is the Singapore market most "
             "comparable with Paris.",
        fund_note="Rent is predicted for each sold home from URA rental contracts (area recorded in 10 m² bands). "
                  "Leasehold homes are valued over their remaining lease; freehold and 999-year homes in perpetuity. "
                  "2021 covers November and December only.",
    ),
}


def methodology() -> str:
    """Methodology and limitations pages, rendered from docs/*.md."""
    import markdown

    docs = ROOT / "docs"
    body = "".join(
        markdown.markdown((docs / f).read_text(), extensions=["tables", "fenced_code"])
        for f in ("methodology.md", "limitations.md"))
    return ('<div class="card doc">' + body + "</div>")


def main() -> None:
    (SITE / "index.html").write_text(
        head("Housing fundamentals", "Do rents justify housing prices in Paris and Singapore?", "home") + INDEX + FOOT)
    (SITE / "methodology.html").write_text(
        head("Method and limits", "How prices, rents and fundamental values are computed, and what limits them.", "meth")
        + methodology() + FOOT)
    for key, c in CITIES.items():
        if not (SITE / "data" / f"{key}_meta.json").exists():
            (SITE / f"{key}.html").write_text(
                head(f"{c['name']} housing", f"{c['name']}: in preparation.", c["page"])
                + f"<h1>{c['name']}</h1><p class=\"lede\">In preparation: the data are downloaded and cleaned; "
                  "models and valuation are being finalised.</p>" + FOOT)
            continue
        extra = f'<link rel="stylesheet" href="{MAPLIBRE}.css">'
        html = head(f"{c['name']} housing", f"Prices, rents, yields and valuation gaps in {c['name']}.", c["page"],
                    extra, f' data-city="{key}"')
        (SITE / f"{key}.html").write_text(html + CITY.format(maplibre=MAPLIBRE, **c) + FOOT)


if __name__ == "__main__":
    main()
