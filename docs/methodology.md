# Methodology

## 1. Research question and stance

ML and hedonic models fitted to transaction prices estimate **market value**: what a
dwelling with given characteristics sells for, given current market conditions. They cannot
say whether those conditions are justified. Fundamental value is anchored on **rents
capitalised at the user cost of housing** (Poterba 1984; Himmelberg, Mayer & Sinai 2005,
"HMS"). Whether prices exceed fundamentals is a **hypothesis tested** under explicit,
varied assumptions. It is never a premise.

## 2. Pipeline

| Stage | Module | Output |
|---|---|---|
| Ingest | `src/ingest/*` | `data/raw/**` + `data/raw/MANIFEST.csv` (URL, UTC time, bytes, SHA-256 of every file) |
| Clean + harmonise | `src/clean/paris.py`, `src/clean/singapore.py` | `data/interim/transactions_<city>.parquet` (common schema), `data/processed/cleaning_log_<city>.csv` |
| Features | `src/features/build.py` | distances, building period, matched rents |
| Ratios | `src/ratios/levels.py` | `data/processed/stats_<city>_<level>.csv` |
| Models | `src/models/hedonic.py` | `reports/tables/model_comparison_*.csv`, OLS coefficients, SHAP figures |
| Valuation | `src/ratios/valuation.py` | `data/processed/valuation_*`, `sensitivity_*`, `fundamental_vs_market_*` |
| Site | `src/viz/export.py`, `src/viz/pages.py` | `site/` |

`make data && make models && make site` reproduces everything. The random seed is fixed
(`src/config.py`), and package versions are written to `data/processed/package_versions.json`.

## 3. Harmonised schema

`city, date, year, price_local, currency, price_eur, price_usd, floor_area_m2,
price_per_m2_local, price_per_m2_eur, rooms_or_flat_type, property_type, tenure,
lease_remaining_years, address_street, street_id, district_l1, district_l2, lat, lon, source_id`,
plus city-specific extras (Paris: quartier name, IRIS, outbuildings, Carrez area; Singapore:
HDB town, block, flat model, storey band and mid-point, lease start year).

| | district_l1 | district_l2 | street_id |
|---|---|---|---|
| Paris | arrondissement (1–20) | quartier administratif (city-wide number 1–80, the key used by the reference rents) | INSEE commune code + FANTOIR street code |
| Singapore | URA planning area (MP2019) | URA subzone (MP2019) | HDB street name |

The HDB town, HDB's own administrative unit, is kept as `hdb_town`. Subzones are used for
`district_l2` because they nest inside planning areas, while HDB towns do not.

**FX.** The ECB euro reference rates (SGD and USD per EUR), monthly average of the
transaction month. Singapore records give only the month, so the same rule is used for
both cities. Local currency is always kept.

## 4. Cleaning rules

Every step is counted in `data/processed/cleaning_log_<city>.csv`, and the identifiers of
removed rows are kept in `data/interim/removed_rows_<city>.csv.gz` (not published).

**Paris (DVF):**
1. exact duplicate lines;
2. `nature_mutation == "Vente"` only;
3. mutations made of exactly one apartment, with or without outbuildings (dépendances);
4. price > 0 and 9 ≤ built area ≤ 400 m²;
5. point inside a Paris quartier;
6. non-market prices: price/m² more than 3× above or below the arrondissement × year median.
   This catches €1 symbolic transfers and similar, which are over 1% of some
   arrondissement-years, so a percentile trim alone misses them;
7. 1st–99th percentile of price/m² within arrondissement × year.

Floor area is `surface_reelle_bati`, which is always filled. Carrez area is filled for only
about half of the sales and is kept as a robustness variable.

**Singapore (HDB resale):**
1. price > 0, 25 ≤ area ≤ 300 m²;
2. block geocoded by OneMap;
3. inside an MP2019 subzone;
4. factor-3 non-market rule within town × flat type × year;
5. 1st–99th percentile.

Exact duplicate lines are **kept and flagged** (`dup_flag`), because two flats in the same
block, month and storey band can sell at the same price.

**Geocoding.** Paris: geo-DVF coordinates, which are cadastral-parcel centroids (no
geocoder needed). Singapore: OneMap search on "block + street". A result is accepted only
if OneMap returns the same block number and the same street after HDB abbreviations are
expanded ("BT" → "BUKIT", "AVE" → "AVENUE", …). The hit rate is written to
`data/processed/geocoding_singapore.csv`.

## 5. Ratios

Computed per year at city, `district_l1`, `district_l2` and street level
(`src/ratios/levels.py`):

- **Price/m²:** median, IQR (q25–q75) and n. YoY is the change of the median against the
  same unit one year earlier. The window change is 2022 → 2025 for Paris (the only full
  years inside DVF's 5-year window) and 2020 → 2025 for Singapore.
- **Rent:**
  - Paris: unfurnished reference rent (€/m²/month) of the cell quartier × rooms (1, 2, 3, 4+) ×
    construction period × vintage. Vintages apply from 1 July to 30 June. The construction
    period comes from the nearest residential BD TOPO building within 30 m of the parcel
    point. If no building matches, the four periods are averaged, weighted by the quartier's
    dwelling mix; this is also reported as a robustness variant.
  - Singapore: median monthly rent of HDB approvals for the same flat type and year. It is
    matched at block level if that cell has n ≥ 5, then subzone, then planning area.
    `rent_source` records the level used.
- **Gross yield** = 12 × monthly rent / price, per transaction, then the median.
  **Price-to-rent** is its inverse, also per transaction, then the median.
- **Price-to-income:**
  - Paris: price of a **60 m²** dwelling at the transaction's price/m², divided by the
    annual median disposable income per consumption unit of the transaction's IRIS
    (Filosofi 2021) (`pti_uc`). It is also divided by that income × **1.5 UC**, a couple
    without children on the modified OECD scale (`pti_hh`).
  - Singapore: **4-room HDB** resale price / (12 × the planning area's median monthly
    household income from work). The median is interpolated linearly inside the income
    band from the Census 2020 band counts; it is undefined if it falls in the open
    S$20,000+ band.
- **Publication rule:** a cell (street, hexagon or district) × year is published only if
  n ≥ 5.

## 6. Models

- Target: log price/m² (sales) and log monthly rent (Singapore HDB rentals).
- Features: log floor area, rooms or flat type, flat model, construction period, building
  year and number of floors (Paris), storey mid-point and remaining lease (Singapore),
  outbuildings, log distance to the nearest metro/RER or MRT/LRT exit, log distance to the
  CBD anchor, log distance to the nearest public green space ≥ 1 ha, and time.
- **OLS:** district_l2 and year fixed effects, HC1 robust standard errors, and also
  standard errors clustered by district. Moran's I on the residuals uses 10-nearest-neighbour
  weights on a seeded random sample of 20,000 sales, with 199 permutations.
- **Random Forest** (200 trees, min leaf 5, 40% of features per split, 50% bootstrap) and
  **LightGBM** (1,500 rounds, learning rate 0.03, 63 leaves). Both see latitude/longitude
  and a numeric month index.
- **Validation:**
  - (a) spatial block CV: H3 resolution-8 cells (about 0.7 km²) are the groups, 5 folds,
    `GroupKFold`;
  - (b) time split: train on all years before the latest one, test on the latest. The
    unseen year's OLS effect is set to the last training year's.

  Errors are reported on price/m², after Duan smearing: RMSE, MAE and MAPE.
- **Interpretability:** SHAP (TreeExplainer) summary and dependence plots for LightGBM,
  compared with the OLS elasticities.

## 7. Fundamental value and valuation gap

    u   = r_f + τ + δ + γ − g
    V*  = R / u                                   Paris (freehold: perpetuity)
    V*  = R / u · [1 − ((1+g)/(1+i))^T], i = u+g  Singapore (HDB lease, T years left)
    gap = P̂ / V* − 1

- **R:**
  - Paris: annual reference rent × floor area.
  - Singapore: annual rent predicted by the HDB rent model for the sold flat's type and
    location. Rents exist only from 2021, so earlier years use the 2021 level and are
    flagged.
- **P̂:** the out-of-fold LightGBM prediction from the spatial CV, so no dwelling is valued
  by a model trained on its own sale.
- **r_f:** mean 10-year government yield of the year. France: ECB series
  IRS.M.FR.L.L40.CI.0000.EUR.N.Z. Singapore: SingStat M700071, series 15.
- **Assumptions** (baseline [sensitivity range]; sources in `src/ratios/params.py`):

  | Term | Paris | Singapore |
  |---|---|---|
  | τ, property tax | 0.25% [0.1–0.5%] | 0.10% [0–0.3%] |
  | δ, maintenance + depreciation | 1.5% [1.0–2.5%] | 1.5% [1.0–2.5%] |
  | γ, risk premium | 2% [1–4%] (HMS) | 2% [1–4%] (HMS) |
  | g, expected growth | 2% [0–4%] | 2% [0–4%] |

- **Sensitivity grid:** r_f ± 0, 0.5 and 1 percentage point; γ ∈ {1, 2, 3, 4}%;
  g ∈ {0, 1, 2, 3, 4}%. Combinations with u < 0.5% are reported as undefined, never clipped.
- **Relative mispricing** = log(actual price) − log(P̂), aggregated by street, hexagon or
  district. It measures cheap or expensive **relative to comparable dwellings**. It is
  **not** a bubble indicator.

## 8. Second pillar: market tension and liquidity

Rents are a constrained expense: households must be housed, so rents can stay high when
they are already too heavy, and a rent-capitalisation value then "justifies" high prices
while the market is stuck. When prices are too high, sellers rarely cut them at once (loss
aversion, Genesove & Mayer 2001); the adjustment shows first in volumes and time on market
(Stein 1995). Time on market needs listing data, which are not open for Paris or Singapore,
so the pillar uses open data only (`src/ratios/liquidity.py`):

| Indicator | Definition | Paris | Singapore HDB | Singapore private |
|---|---|---|---|---|
| Turnover | sales per 1,000 dwellings of the segment | every DVF sale with an apartment / apartments in the 2023 census (INSEE, IRIS); half-years annualised | every HDB resale / flats sold by HDB (property information, by block → HDB town) | not computed: no open stock series |
| Volume − price divergence | YoY % change of sales − YoY % change of median price/m², full calendar years | 2022-2025 | 2017-2025 | 2022-2025 |
| Months of supply | unsold launched units / mean monthly developer sales over 12 months | – | – | URA developer sales (served from Nov 2023 only); Executive Condominiums excluded |
| Rent-to-income | annual rent / annual income | 60 m² at the matched reference rent / (IRIS median income per UC × 1.5), Filosofi 2021 | matched flat rent / planning-area median household income from work | matched home rent / same income |
| Vacancy | vacant / all dwellings | 2023 census | – | – |

Singapore incomes: the Census 2020 planning-area medians are scaled each year by the
national median monthly household income from work of employed resident households, incl.
employer CPF (SingStat table 17870 via data.gov.sg). Its 2020 value (S$9,208) matches the
Census 2020 band median (S$9,222), so the definitions agree. 2026 uses the 2025 value.

Reading the two pillars together:

| | Prices vs fundamentals | Liquidity | Interpretation |
|---|---|---|---|
| Paris | above (baseline) | volumes −27% 2022→2024 against prices −10% | a stuck market adjusting through quantities |
| Singapore private | above (baseline) | volumes +23%, prices +25% 2022→2025; ~5 months of supply | demand-driven boom |
| Singapore HDB | below (baseline) | stable turnover | regulated market; arbitrage restricted |
