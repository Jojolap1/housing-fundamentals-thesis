"""Write the static HTML pages of the site (site/*.html).

Every page carries <meta name="robots" content="noindex">: the DVF reuse terms forbid
search-engine indexing, and a GitHub project site cannot rely on a root robots.txt.
"""
from __future__ import annotations

from src.config import ROOT

from src.viz.sections import cross_section, history_section, home_section, index_section, verdict_section

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
    <a href="hcmc.html"{a_hcm}>Ho Chi Minh City</a>
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
    cur = {k: "" for k in ("home", "paris", "sg", "sgp", "hcm", "meth")}
    cur[page] = ' aria-current="page"'
    return HEAD.format(title=title, desc=desc, extra=extra, body_attr=body_attr,
                       a_home=cur["home"], a_paris=cur["paris"], a_sg=cur["sg"], a_sgp=cur["sgp"], a_hcm=cur["hcm"], a_meth=cur["meth"])


INDEX = """
<h1>Are housing prices justified by fundamentals?</h1>
<p class="lede">Machine-learning and hedonic models trained on transaction prices estimate <em>market</em> value. They cannot,
by construction, say whether that market value is justified. This project anchors <em>fundamental</em> value on rents
capitalised at the user cost of housing (Poterba 1984; Himmelberg, Mayer &amp; Sinai 2005) and treats overvaluation as a
hypothesis to test, not a premise.</p>

<div class="card">
<h2 style="margin-top:0">Why not value a home the way markets value a company?</h2>
<p>Because markets do not know what a company is worth either. They know its <em>price</em>. The value of a share
is its future dividends discounted, P = D / (r − g), and the answer hangs on two numbers nobody observes: with a
gap of 4 points between the discount rate and growth, one point less raises the value by a third and one point more
lowers it by a fifth. Shiller (1981) showed that share prices move far more than later dividends justify. The
formula used here for housing, V* = R / (user cost − g), is the same one, with rent in place of the dividend, and it
is just as sensitive.</p>
<p>What a stock exchange has, and housing lacks, is a mechanism that keeps the price informative and pulls it back
when it strays:</p>
<ul>
<li><b>No identical asset.</b> One share equals another. Every dwelling is different and sells rarely, so even the
price level has to be rebuilt with quality-adjusted indices.</li>
<li><b>No continuous quote.</b> A few thousand sales per quarter, published months later, against millions of trades
a day.</li>
<li><b>No short selling.</b> Someone who finds a flat too dear cannot sell it short; they can only stay out. Prices
are then set by the most optimistic buyers (Miller 1977), and it is the number of sales that falls first.</li>
<li><b>A cash flow that is hard to see.</b> Companies publish audited accounts every quarter. The "dividend" of a
home is a rent, often regulated, or never paid at all when the owner lives in it.</li>
</ul>
<p>Housing therefore combines the valuation uncertainty of equities with a market that corrects slowly: in the panel
of 39 countries used here, a crash in house prices takes a median of 25 quarters from peak to trough. So this project
does not look for one fair price. It asks what one must believe for today's prices to be justified, whether that
belief is plausible, and it reports the answer as a range checked against independent evidence.</p>
</div>

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
<a class="card" href="hcmc.html" style="text-decoration:none;color:inherit"><b>Ho Chi Minh City (exploratory)</b><br><span class="note" style="display:block;margin-top:6px">Official administrative land values by street segment, 2026 · not transactions, not asking prices · no rents</span></a>
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
<tr><td>Ho Chi Minh City</td><td>Land price table, Resolution 87/2025/NQ-HĐND (in force 1 Jan 2026)</td><td><a href="https://congbao.hochiminhcity.gov.vn/cong-bao/van-ban/nghi-quyet/so/87-2025-nq-hdnd/ngay/26-12-2025/48983?cbid=49002">HCMC Official Gazette</a></td><td>Official legal text</td><td>2026-11-08</td></tr>
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
  <p class="meta-line" id="coverage"></p>
  <p class="note" id="gap-note" hidden>The valuation gap compares the model's predicted market price with rents capitalised at an
  assumed user cost. A positive value means prices are above what rents justify <em>under the baseline assumptions</em>;
  see the sensitivity band below. It is a model-dependent hypothesis, not investment advice.</p>
  <p class="note" id="mis-note" hidden>Relative mispricing is the median residual of the price model: positive = dearer than
  comparable dwellings elsewhere in the city, negative = cheaper. It says nothing about a bubble.</p>
  <p class="meta-line">Source: {source}. Period shown: the selected year. Cells with fewer than 5 transactions in a year are
  not published. Valuation gaps are model-dependent hypotheses, not investment advice.</p>
</div>

{verdict_section}
{cross_section}
{history_section}
{index_section}

<h2>Fundamental vs market value per m²</h2>
<div class="card">
  <div class="legend"><span><span style="color:var(--series-market)">●</span> Market: median transaction price per m²</span>
  <span><span style="color:var(--series-fund)">●</span> Fundamental: median V* per m², baseline assumptions</span>
  <span><span style="display:inline-block;width:18px;height:10px;background:var(--band-fund)"></span> Range of V* over the sensitivity grid (r<sub>f</sub> ±1 pt, risk premium 1–4%, growth 0–4%)</span></div>
  <div class="chart-wrap" id="chart"></div>
  <details><summary>Table view</summary><div id="chart-table" class="table-scroll"></div></details>
  <p class="note">{fund_note}</p>
</div>

<h2>Market tension and liquidity</h2>
<div class="card">
  <p class="note" style="margin-top:0">Rents are a constrained expense: households must be housed, so a rent-based value can
  "justify" high prices while the market is stuck. When prices are too high, sellers rarely cut them at once; sales volumes fall
  first. This section tracks that adjustment. Time on market would be the ideal measure, but it needs listing data, which are
  not open.</p>
  <div class="kpis" id="kpis"></div>
  <div class="legend"><span><span style="color:var(--series-volume)">●</span> Volume: number of sales</span>
  <span><span style="color:var(--series-market)">●</span> Price: median price per m²</span>
  <span>Both indexed to 100 in the first full year (dashed line); full calendar years only.</span></div>
  <div class="chart-wrap" id="liq-chart"></div>
  <details><summary>Table view</summary><div id="liq-table" class="table-scroll"></div></details>
  <p class="meta-line">{liq_note}</p>
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
<script src="assets/sections.js"></script>
"""

CITIES = {
    "paris": dict(
        name="Paris", page="paris", l1="Arrondissement", l2="Quartier", cur="€", example="RUE DE RIVOLI",
        rent_label="Reference rent per m²",
        source="DGFiP DVF géolocalisées (apartment sales), Ville de Paris reference rents, INSEE Filosofi 2021",
        lede="Single-apartment sales recorded by the tax administration, July 2021 – June 2026. Rents are the city's "
             "regulatory reference rents (unfurnished, by quartier, rooms and construction period): they are not "
             "observed contracts, and the rented stock differs from the stock that is sold.",
        liq_note="Volume: every DVF sale containing an apartment (DGFiP). Stock: apartments in the 2023 census (INSEE). "
                 "Rent-to-income uses Filosofi 2021 incomes, held at their 2021 level.",
        fund_note="Paris reference rents are regulatory values set from observed rents; the gap therefore measures prices "
                  "against regulated-market rents. 2021 covers July–December and 2026 January–June.",
    ),
    "singapore": dict(
        name="Singapore (HDB)", page="sg", l1="Planning area", l2="Subzone", cur="S$", example="ANG MO KIO AVE 10",
        rent_label="Monthly rent per flat",
        source="HDB resale flat prices and HDB rental approvals (data.gov.sg), Census of Population 2020",
        lede="Resale transactions of public (HDB) flats on 99-year leases, January 2017 onward. Rents are HDB approvals to "
             "rent out whole flats. Fundamental value discounts rent over the remaining lease, not in perpetuity.",
        liq_note="Volume: every HDB resale (data.gov.sg). Stock: flats sold by HDB, by block (HDB property information). "
                 "Incomes: Census 2020 by planning area, scaled each year by the national median household income from work.",
        fund_note="HDB rents are published from January 2021, so fundamental values and gaps start in 2021. A negative gap does not mean HDB flats are a bargain anyone can take: only eligible "
                  "households (mainly citizens) may buy, owners must live in the flat for 5 years before renting it "
                  "out, and grants and CPF rules shape demand, so rent capitalisation is constrained. The open "
                  "private market is on the Singapore (private) page.",
    ),
    "singapore_private": dict(
        name="Singapore (private)", page="sgp", l1="Planning area", l2="Subzone", cur="S$", example="ANSON ROAD",
        rent_label="Monthly rent per home",
        source="URA private residential transactions and rental contracts (URA Data Service), Census of Population 2020",
        lede="Sales of private apartments and condominiums (the open market: no eligibility rules, buy-to-let allowed), "
             "November 2021 onward, and the rental contracts stamped with IRAS. This is the Singapore market most "
             "comparable with Paris.",
        liq_note="Volume: every single-unit apartment and condominium sale (URA). Months of supply: unsold launched units / "
                 "average monthly developer sales over 12 months (URA developer sales; served from Nov 2023 only). No open "
                 "series of the private stock, so no turnover rate.",
        fund_note="Rent is predicted for each sold home from URA rental contracts (area recorded in 10 m² bands). "
                  "Leasehold homes are valued over their remaining lease; freehold and 999-year homes in perpetuity. "
                  "URA rental contracts start in 2022, so fundamental values and gaps start in 2022.",
    ),
}


HCMC = """
<h1>Ho Chi Minh City <span style="font-weight:400;color:var(--text-secondary)">(exploratory)</span></h1>
<div class="note" style="border-left:3px solid var(--series-fund);margin:10px 0 14px">
<b>Administrative land values, not market prices.</b> These are the land prices set by the city for taxes, fees and
compensation (Resolution 87/2025/NQ-HĐND of the HCMC People's Council, in force since 1 January 2026). They are neither
transaction prices nor asking prices, they cover land only, and they have historically been well below market values.
Vietnam publishes no transaction register and no rents, so the rent-capitalisation test run for Paris and Singapore
cannot be run here.</div>
<p class="meta-line"><span id="n-seg">…</span> priced street segments in <span id="n-units">…</span> wards, communes and
special zone (the new city after the July 2025 merger with Bình Dương and Bà Rịa–Vũng Tàu). Values: residential land,
million VND per m². Source: HCMC Official Gazette, issues 62+63 to 84+85 of 1 March 2026, extracted from the signed
PDFs; 2.4% of entries were unreadable and are excluded.</p>

<h2>By ward or commune</h2>
<div class="card">
  <div class="controls"><label>Search<input type="search" id="w-search" placeholder="e.g. Bến Thành"></label>
  <span class="meta-line" id="w-count"></span></div>
  <div class="table-scroll"><table>
    <thead id="w-head"><tr><th data-k="ward">Ward / commune</th><th data-k="type">Type</th><th class="num" data-k="segments">Segments</th>
    <th class="num" data-k="median">Median</th><th class="num">IQR</th><th class="num" data-k="max">Max</th>
    <th class="num" data-k="median_commercial">Median, commercial land</th></tr></thead>
    <tbody id="w-body"></tbody></table></div>
  <p class="meta-line">Million VND per m² of residential land (last column: commercial and service land). Click a column title to sort.</p>
</div>

<h2>By street</h2>
<div class="card">
  <div class="controls"><label>Search street or ward<input type="search" id="s-search" placeholder="e.g. Nguyễn Huệ"></label>
  <span class="meta-line" id="s-count"></span></div>
  <div class="table-scroll"><table>
    <thead id="s-head"><tr><th data-k="street">Street</th><th data-k="ward">Ward / commune</th><th class="num" data-k="segments">Segments</th>
    <th class="num" data-k="min">Min</th><th class="num" data-k="max">Max</th></tr></thead>
    <tbody id="s-body"></tbody></table></div>
  <p class="meta-line">A street crossing several wards appears once per ward. Some Vietnamese diacritics may be imperfect
  where the source PDF encodes them inconsistently.</p>
</div>
<script src="assets/hcmc.js"></script>
"""


def methodology() -> str:
    """Methodology and limitations pages, rendered from docs/*.md."""
    import markdown

    docs = ROOT / "docs"
    body = "".join(
        markdown.markdown((docs / f).read_text(), extensions=["tables", "fenced_code"])
        for f in ("findings.md", "methodology.md", "limitations.md"))
    return ('<div class="card doc">' + body + "</div>")


def main() -> None:
    (SITE / "index.html").write_text(
        head("Housing fundamentals", "Do rents justify housing prices in Paris and Singapore?", "home")
        + INDEX.replace("<h2>Data sources</h2>", home_section() + "\n<h2>Data sources</h2>", 1) + FOOT)
    (SITE / "methodology.html").write_text(
        head("Method and limits", "How prices, rents and fundamental values are computed, and what limits them.", "meth")
        + methodology() + FOOT)
    (SITE / "hcmc.html").write_text(
        head("Ho Chi Minh City land values", "Official administrative land values by street segment in Ho Chi Minh City, 2026.", "hcm")
        + HCMC + FOOT)
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
        (SITE / f"{key}.html").write_text(
            html + CITY.format(maplibre=MAPLIBRE, index_section=index_section(key),
                               verdict_section=verdict_section(key),
                               cross_section=cross_section(key),
                               history_section=history_section(key), **c) + FOOT)


if __name__ == "__main__":
    main()
