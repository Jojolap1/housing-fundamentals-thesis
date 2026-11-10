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
| Robust statistics | `src/ratios/robust.py` | `data/processed/robust_<city>_<level>.csv` (mean, trimmed mean, bootstrap CI, shrunk median) |
| Price indices | `src/indices/run.py` | `data/processed/index_<city>.csv`, `index_validation_<city>.csv` |
| Models | `src/models/hedonic.py` | `reports/tables/model_comparison_*.csv`, OLS coefficients, SHAP figures |
| Valuation | `src/ratios/valuation.py` | `data/processed/valuation_*`, `sensitivity_*`, `fundamental_vs_market_*` |
| Tests and verdict | `src/valuation/run.py` | `data/processed/explosive_*.csv`, `price_rent_*.csv`, `verdict.csv` |
| Site | `src/viz/export.py`, `src/viz/pages.py` | `site/` |

`make data && make indices && make models && make verdict && make site` reproduces everything. The random seed is fixed
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

## 9. What each tool can and cannot say

| Tool | Answers | Does not answer |
|---|---|---|
| Hedonic / ML model on sale prices (§6) | What does a dwelling like this sell for today? Which streets are dear or cheap **relative to comparable dwellings**? | Whether the market as a whole is too dear: a model fitted to prices reproduces any general overvaluation |
| Rent capitalisation at the user cost (§7) | Is the price consistent with current rents under stated r_f, γ and g? | Whether rents themselves are sustainable (rent is a necessity, and it is regulated in both cities); the answer changes sign inside the plausible range of r_f − g |
| Affordability ratios (§5, §8) | How many years of income, what share of income? | A "fair" level, without a history or a benchmark |
| Price-to-rent dynamics (§11) | Is the ratio far from its own history, and do prices tend to correct? | The level of fundamental value |
| Explosive-root tests (§11) | Did the series behave explosively, and when? | Why; and nothing below city level |

No single tool is treated as decisive. §12 combines them under a rule fixed in advance.

## 10. Composition and small samples

A raw average by neighbourhood moves with **which** dwellings happen to sell and, in small
cells, with a single sale: 100 sales at €1,000/m² and one at €2,000/m² give a mean of
€1,010 but a median of €1,000. Three devices deal with this.

**Cell statistics** (`src/ratios/robust.py`). For every cell and year: n, median, mean, 10%
trimmed mean, IQR, and a 95% percentile-bootstrap confidence interval of the median (1,000
resamples, fixed seed). Maps use the median.

**Thresholds.** Street and hexagon cells need n ≥ 5 and are otherwise not published at all
(DVF reuse terms). District and neighbourhood cells need n ≥ 20 for a full set of
statistics; with 5 ≤ n < 20 they are published "greyed", with the count only.

**Shrinkage.** The log median θ_i of a small cell is pulled towards the log median μ_p of
its parent (street → arrondissement or planning area; quartier or subzone → arrondissement
or planning area; these → city):

    shrunk_i = μ_p + w_i (θ_i − μ_p),   w_i = τ²_p / (τ²_p + v_i)

where v_i is the bootstrap variance of θ_i and τ²_p the dispersion of true cell medians
inside the parent, estimated by a precision-weighted method of moments. A cell with few
sales has a large v_i and moves towards its parent; a cell with many sales keeps its
value. Raw and shrunk values are both published, with the weight w_i. This is a standard
empirical-Bayes (random-effects) estimator; no specific paper is cited for it here because
the reference has not yet been checked.

**Quality-adjusted indices** (`src/indices/`), quarterly, first quarter = 100:

| Index | Method | Controls for | Weakness |
|---|---|---|---|
| Hedonic time-dummy (Hill 2013; Eurostat 2013) | log price/m² on quarter dummies and characteristics; pooled, and rolling 5-quarter windows chained on the last change | observed characteristics (size, rooms or flat type, location, building period, storey, remaining lease) | unobserved quality (condition, view, energy class) |
| Stratified median (Prasad & Richards 2008) | fixed-weight geometric mean of strata medians; strata = arrondissement × rooms (Paris), HDB town × flat type, planning area (private) | the mix of strata sold | mix changes inside a stratum |
| Repeat-sales (Bailey, Muth & Nourse 1963; Case & Shiller 1989) | price changes of dwellings sold twice; Case-Shiller weights | everything constant within a dwelling | uses only resold dwellings; needs a dwelling identifier |
| Volume | number of retained sales per quarter | – | a liquidity measure, not a price |

Dwelling identifier: in Paris, cadastral parcel + lot number. HDB and URA publish no unit
number, so the Singapore series is a **pseudo repeat-sales** index on a proxy unit (block ×
flat type × storey band × floor area; project × floor area × storey band) and is labelled
as such. Each index is compared with the official index of the market (Notaires-INSEE for
Paris apartments, HDB resale price index, URA private residential price index) on the
common quarters: correlation of quarterly changes and gap in cumulative change
(`index_validation_<city>.csv`). Differences are reported, not adjusted away.

## 11. Dynamics: price-to-rent and explosive roots

**Price-to-rent** (`src/valuation/price_rent.py`). Following Gallin (2008), and the
present-value logic of Campbell & Shiller (1988), k-quarter changes in log prices and log
rents are regressed on the lagged log rent-price ratio (k = 16). A positive coefficient in
the price equation means prices correct towards rents. Newey-West standard errors with k−1
lags are reported; Gallin shows that such regressions are biased in small samples and
uses a bootstrap, so the t-values are indicative. The z-score of the latest log
price-to-rent ratio in its own history is also reported.

**Explosive roots** (`src/valuation/explosive.py`). SADF and GSADF statistics and the
backward sup ADF (BSADF) date-stamping of Phillips, Shi & Yu (2015), applied to housing as
in Pavlidis et al. (2016). Settings: series in logs; Dickey-Fuller regression with a
constant and no lagged differences; minimum window 0.01 + 1.8/√T of the sample; critical
values from 999 simulated random walks with drift 1/T and a fixed seed; an episode needs
BSADF above its 95% critical value for at least log(T) quarters.

- *Advantage:* no level of fundamental value is needed, so the test does not inherit the
  weaknesses of the rent anchor.
- *Limits:* it needs a long, regular series, so it runs on city-level official indices
  (Notaires-INSEE from 1991, URA from 1975, HDB resale price index), never on streets; an
  explosive price can reflect explosive fundamentals, so the test is also run on the
  price-to-rent ratio where a rent index exists (Singapore private, from 2004); indices are
  nominal; results depend at the margin on the minimum window and the lag order.

## 12. Verdict rule

Fixed before the results (`src/valuation/verdict.py`). Each anchor gives +1 (prices above
fundamentals), 0, −1 or "not run":

| Anchor | Rent-based | +1 when |
|---|---|---|
| User cost | yes | the gap is positive in at least 80% of the defined sensitivity-grid cells of the latest full year (−1 when in at most 20%) |
| Price-to-rent | yes | the latest log ratio is more than one standard deviation above its historical mean (URA price and rental indices for private housing; Paris price index over the national rent index) |
| Explosive root | no | GSADF rejects at 5% and a dated episode includes the latest quarter |
| Affordability | no | the latest log price-to-income ratio is more than one standard deviation above its historical mean (official price index over national median household income from work for Singapore, annual from 2000; over national disposable income per head for Paris, quarterly from 1992) |

- **Evidence of deviation:** at least three anchors at +1, one of them not rent-based.
- **Consistent with fundamentals:** at least two anchors run, none at +1, user cost at −1.
- **Inconclusive:** everything else.

The thresholds (80%, one standard deviation) are conventions. `verdict.csv` lists, for
each market, the signals, the anchors that agree and those that could not be run, with the
reason. Liquidity (§8) is reported next to the verdict; it is not an anchor.

## 13. Two cross-checks of sale prices

Reported next to the verdict and outside its rule (`src/valuation/cross_checks.py`,
`data/processed/cross_checks.csv`). The verdict's ratios compare each market with its own
past; these two checks compare it with outside yardsticks.

**Check 1, rent side: the rent growth a price requires.** The user-cost equation is solved
for g instead of V*:

    freehold:             g* = r_f + τ + δ + γ − R/P
    lease, T years left:  P/R = [1 − ((1+g)/(1+i))^T] / (i − g),   i = r_f + τ + δ + γ

g* is the nominal growth of rents at which the sale price equals the capitalised rent. It
removes the need to choose g, the most circular input of §7. It is computed for each sale
and the median is reported for γ = 1%, 2% and 4%. Yardstick: the growth of incomes over the
last 20 years, since rents cannot outgrow incomes indefinitely (rent growth is shown too).
*Plausible* if g* at γ = 4% is at or below income growth; *implausible* if g* at γ = 1% is
above it; otherwise *depends on the premium*.

**Check 2, income side: the price a household can finance.** No rent enters:

    P_max = share × monthly income × annuity(rate, years) / (1 − down payment)

| Market | Share of income | Years | Down payment | Rate | Income |
|---|---|---|---|---|---|
| Paris | 35% (HCSF decision D-HCSF-2021-7, binding since 2022) | 25 | 20% (convention: the rule sets none) | average rate on new home loans in France (ECB MIR statistics) | couple (1.5 consumption units) at the median disposable income of the IRIS, Filosofi 2021; 60 m² |
| HDB | 30% (mortgage servicing ratio) | 25 | 25% (loan-to-value limit 75%) | MAS medium-term rate floor: 3.5%, then 4% from 2023 | median household income from work of the planning area; 4-room flat |
| Private | 55% (total debt servicing ratio) | 30 | 25% | same floor | median household income from work of the planning area |

The result is P / P_max, also with the rate one point lower and higher: *within capacity*
(at or below 1 at the three rates), *beyond capacity* (above 1 at the three rates),
otherwise *depends on the rate*. The lending parameters were read in parliamentary answers
and press explanations of the rules, not yet in the regulators' own texts.

The two checks share the interest rate, so they are not fully independent, but they rest on
different data: rents on one side, incomes and credit rules on the other.

## 14. Calibrating the ratios on past busts

`src/valuation/early_warning.py`. The one-standard-deviation convention of §12 is arbitrary;
this step measures what the ratios looked like before past busts.

- **Panel:** OECD analytical house price indicators, all countries, quarterly (real house
  prices, price-to-income, price-to-rent).
- **Bust:** a fall of real house prices of at least 15% from a peak, before the peak is regained.
- **Signal:** z-score of the log ratio against the country's own past only (expanding
  window, at least ten years), so that a quarter is never judged with later data.
- **Evaluation:** a quarter is pre-bust if a bust peak falls within the next 12 quarters;
  quarters inside a bust are left out. For each threshold: share of pre-bust quarters
  flagged, share of other quarters flagged, share of busts flagged before their peak, share
  of flagged quarters that were pre-bust. The retained threshold maximises the first minus
  the second.
- **Application:** the same z-score for Paris and Singapore, and the list of every fall of
  at least 10% of the three official indices with the ratios at the peak.

The calibrated thresholds are reported next to the verdict; the verdict rule is unchanged.

The price-to-income and price-to-rent ratios follow common practice in institutional
monitoring: the OECD publishes both ratios by country and reads them against their long-term
average, and the UBS Global Real Estate Bubble Index combines price-to-income and
price-to-rent with credit, construction and city-to-country price indicators. Only the two
valuation ratios are reproduced here; credit and construction indicators are not.

## References

Checked on 2026-11-10 (authors, year, journal, volume and pages; DOI where given).

- Bailey, M. J., Muth, R. F., Nourse, H. O. (1963). A regression method for real estate price index construction. *Journal of the American Statistical Association* 58(304), 933–942. doi:10.1080/01621459.1963.10480679
- Campbell, J. Y., Shiller, R. J. (1988). The dividend-price ratio and expectations of future dividends and discount factors. *Review of Financial Studies* 1(3), 195–228. doi:10.1093/rfs/1.3.195
- Case, K. E., Shiller, R. J. (1989). The efficiency of the market for single-family homes. *American Economic Review* 79(1), 125–137. (No DOI found; NBER Working Paper 2506.)
- Eurostat, ILO, IMF, OECD, UNECE, World Bank (2013). *Handbook on Residential Property Prices Indices (RPPIs)*. Luxembourg: Publications Office of the European Union. ISBN 978-92-79-25984-5. doi:10.2785/34007
- Gallin, J. (2008). The long-run relationship between house prices and rents. *Real Estate Economics* 36(4), 635–658. doi:10.1111/j.1540-6229.2008.00225.x
- Genesove, D., Mayer, C. (2001). Loss aversion and seller behavior: evidence from the housing market. *Quarterly Journal of Economics* 116(4), 1233–1260. (DOI not confirmed.)
- Glaeser, E. L., Gottlieb, J. D., Gyourko, J. (2013). Can cheap credit explain the housing boom? In E. L. Glaeser and T. Sinai (eds.), *Housing and the Financial Crisis*, University of Chicago Press, 301–359. (Book chapter; NBER Working Paper 16230.)
- Hill, R. J. (2013). Hedonic price indexes for residential housing: a survey, evaluation and taxonomy. *Journal of Economic Surveys* 27(5), 879–914. (DOI not confirmed.)
- Himmelberg, C., Mayer, C., Sinai, T. (2005). Assessing high house prices: bubbles, fundamentals and misperceptions. *Journal of Economic Perspectives* 19(4), 67–92. doi:10.1257/089533005775196769
- Pavlidis, E., Yusupova, A., Paya, I., Peel, D., Martínez-García, E., Mack, A., Grossman, V. (2016). Episodes of exuberance in housing markets: in search of the smoking gun. *Journal of Real Estate Finance and Economics* 53(4), 419–449. doi:10.1007/s11146-015-9531-2
- Phillips, P. C. B., Shi, S., Yu, J. (2015). Testing for multiple bubbles: historical episodes of exuberance and collapse in the S&P 500. *International Economic Review* 56(4), 1043–1078. doi:10.1111/iere.12132
- Poterba, J. M. (1984). Tax subsidies to owner-occupied housing: an asset-market approach. *Quarterly Journal of Economics* 99(4), 729–752. doi:10.2307/1883123
- Prasad, N., Richards, A. (2008). Improving median housing price indexes through stratification. *Journal of Real Estate Research* 30(1), 45–72. doi:10.1080/10835547.2008.12091213
- Stein, J. C. (1995). Prices and trading volume in the housing market: a model with down-payment effects. *Quarterly Journal of Economics* 110(2), 379–406. (DOI not confirmed.)

Methods used without a checked reference, to be completed before submission: empirical-Bayes
shrinkage, spatial block cross-validation, SHAP values, Moran's I, Duan smearing, Newey-West
standard errors.
