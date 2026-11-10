# Limitations

These are stated plainly because they bound what the results can say.

## Rents
- **Paris rents are regulatory reference values, not contracts.** They are set by
  prefectoral order from observed rents (OLAP). The "reference" is roughly a median, and
  the legal ceiling is +20% above it. A gap computed with them compares prices with
  regulated-market rents. Observed market rents (and especially furnished lets) can be
  higher, which would lower the measured gap.
- **The rented and the owned stocks differ.** Reference rents describe the private rental
  stock, while DVF describes the dwellings that were sold. Matching on quartier × rooms ×
  construction period reduces, but does not remove, the composition difference.
- **Construction period** is not in DVF. It comes from the nearest residential BD TOPO
  building within 30 m of the parcel centroid (matched for about 86% of sales). A wrong
  building match puts a sale in the wrong rent cell. The period-mix rent is the robustness
  check.
- **Singapore rents are HDB approvals to rent out whole flats**, with the declared rent and
  no floor area. They cover 2021 onwards only: for 2017–2020 the rent model is held at its
  2021 level, so gaps for those years are weaker evidence. Room rentals are excluded.

## Prices
- **DVF covers only the last five years** (legal rule), currently July 2021 – June 2026, so
  there is no Paris history before the 2022 rate shock, and 2021 and 2026 are half-years.
- DVF has no floor level, condition, view or energy class. Hedonic residuals therefore mix
  unobserved quality with genuine mispricing.
- The DVF price covers the whole mutation, including outbuildings (parking, cellar);
  outbuildings are a model feature.
- HDB resale prices are recorded by month only. Storey is a 3-floor band.
- Exact duplicate HDB lines are kept: they cannot be told apart from distinct sales.
- **Singapore private housing (URA)** covers non-landed apartments and condominiums only, from
  November 2021 (URA serves the last 5 years). Rental areas are 10 m² bands, so rent/m² is
  approximate. Transaction locations are the project's, not the unit's.
- **URA terms of use not yet verified**: publication of aggregates derived from the URA API
  depends on them.
- HDB public housing is a regulated market: eligibility rules, CPF financing and grants all
  shape HDB prices.

## Income
- Paris: median disposable income **per consumption unit**, by IRIS, for **2021** only.
  The household version assumes a 1.5-UC couple.
- Singapore: household income **from work** only, in bands, from the **2020** Census, by
  planning area. Households with no employed member (13% of the total) are excluded, and
  several small planning areas are pooled into "Others" and get no value.
- The two price-to-income definitions are **not strictly comparable across cities**.

## Fundamental value
- Only r_f is measured. τ, δ, γ and g are assumptions. The sensitivity grid shows how far
  the conclusion moves with them, and it moves a lot, as it does in HMS (2005). A gap is
  evidence *conditional* on those assumptions.
- The user-cost model is a steady-state arbitrage condition. It ignores credit
  constraints, transaction costs, taxes on rental income, and (for Paris) rent regulation
  itself, which caps R.
- For HDB, the finite lease is handled by discounting over the remaining lease. Policy
  around lease expiry (e.g. VERS/SERS redevelopment) is not modelled.

## Models and spatial statistics
- Spatial block CV uses H3 resolution-8 cells. Larger blocks would be stricter.
- OLS residuals remain spatially autocorrelated: Moran's I = 0.06 for Paris, 0.25 for Singapore
  sales, 0.04 for Singapore rents. The tree models, which see coordinates, capture more of this.
- The HDB rent model has no floor area or storey (not in the source): its MAPE is about 15%,
  against 5-7% for HDB prices.
- HDB demand is restricted (eligibility, 5-year minimum occupation before renting out, grants,
  CPF rules), so the arbitrage behind rent capitalisation is constrained. A negative HDB gap is
  not evidence that flats are available below their value to any buyer.
- Moran's I is computed on a 20,000-sale sample with k = 10 neighbours.
- Distances are straight-line, not walking distances. The CBD anchor is a single point.

## Data access
- The OSM Overpass API and Geofabrik were unreachable from the build environment, so
  stations and parks come from official sources instead (IDFM, Ville de Paris, LTA,
  NParks). This is an improvement in provenance, but OSM-based features are not
  reproduced.

## Second pillar (tension and liquidity)
- Time on market and sale-to-list discounts, the most direct measures of a stuck market,
  need listing data that are not open; turnover and volume-price divergence are proxies.
- Paris turnover uses the 2023 census stock for all years; DVF 2021 and 2026 are half-years
  (annualised for turnover, excluded from year-on-year changes).
- HDB stock: 16,236 flats (1.5%) are in blocks whose HDB town could not be inferred from the
  resale file and are left out of the denominators.
- URA serves developer sales for about the last three years only (from November 2023).
- Paris incomes are held at their 2021 level (Filosofi), so the Paris rent-to-income trend
  is overstated by income growth since 2021.

## Robust statistics, indices and tests (added 2026-11-10)
- **Status.** These modules are tested on synthetic data only (`tests/test_indices_valuation.py`).
  Their outputs on the real data have not been produced yet, so nothing here has been
  compared with an official index so far.
- **Verdicts are inconclusive for now.** `verdict.csv` currently rests on the user-cost
  anchor alone (share of sensitivity-grid cells with a positive gap in 2025: Paris 86%,
  Singapore private 87%, HDB 19%). One anchor cannot give a verdict under the rule.
- **Bootstrap intervals** treat the sales of a cell as independent draws; sales in the same
  building or project are not, so intervals are somewhat too narrow. For very small cells
  the bootstrap distribution of a median is coarse.
- **Shrinkage** assumes the cells of a parent are exchangeable. A street that truly differs
  from its arrondissement and has few sales is pulled towards it: the shrunk map is smoother
  than reality, which is why raw values stay published.
- **Hedonic indices** hold observed characteristics constant, not condition, view or energy
  class. The pooled version fixes the characteristic prices over the whole period.
- **Repeat-sales.** Paris: at most five years of DVF, so few dwellings sell twice and those
  that do (short holding periods) are not representative. Singapore: no unit identifier, so
  only a pseudo repeat-sales index on a proxy unit, where two different flats can be paired.
- **Explosive-root tests** use nominal official indices, a fixed lag order of 0 and simulated
  critical values; they date explosive episodes at city level and say nothing about streets
  or about the level of fundamental value. No long rent series has been found for Paris, so
  the price-to-rent version runs for Singapore private housing only.
- **Paris window.** DVF+ open-data is listed as covering 2014 to 2025 (see the data audit,
  §10). Until that is tested, all Paris results rest on July 2021 to June 2026.
- **HDB history before 2017** is not ingested, so the HDB index starts in 2017.
