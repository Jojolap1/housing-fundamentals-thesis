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
- **Coverage.** Built for Paris, Singapore HDB and Singapore private from a fresh download
  of the sources on 2026-11-10 (see `data/processed/build_report.txt`).
- **Verdicts stay inconclusive in all three markets, with every anchor now run** (except
  price-to-rent for HDB). The anchors disagree, which is a result and not a gap: see
  `docs/findings.md`. The rule was not changed after seeing the results.
- **Paris ratios use national denominators.** No city-level rent or income history is open,
  so the Paris price index is set against the national rent index and national disposable
  income per head (OECD). Paris rents and incomes have not moved exactly like the national
  ones, so the level of these ratios is indicative; their history starts in 1992, inside a
  period of high prices, which raises the mean they are compared with.
- **Singapore price-to-income is annual and national** (26 observations, 2000 to 2025):
  median household income from work of resident employed households, not the income of
  buyers of each segment.
- **Agreement with official indices.** Paris, 2021 Q3 to 2026 Q2: hedonic −10.4%,
  stratified −11.0%, Notaires-INSEE −11.3%; correlation of quarterly changes 0.94 to 0.95.
  HDB, 2017 Q1 to 2026 Q3: hedonic +56%, stratified +48%, HDB resale price index +51%;
  correlation 0.94 to 0.98. Singapore private, 2021 Q4 to 2026 Q3: hedonic +27.3%,
  stratified +24.3%, URA non-landed index +26.3%. The gaps are reported, not corrected.
- **The private-market index tracks the level, not the quarters.** Its quarterly changes
  correlate weakly with URA's (0.39 hedonic, 0.80 stratified): each quarter's sales depend
  on which projects are launched. A first specification without sale type, market segment
  and lease gave +16% against +26% for URA; those controls were missing, not optional, and
  were added. This is the one case where the specification was changed after a comparison
  with the official index.
- **The Paris repeat-sales index is not usable** (+10.8% against −11.3% for the official
  index, 4,249 pairs). Within a five-year window, dwellings sold twice are mostly short
  holds, often resold after works, so the "same dwelling" assumption fails; the lot number
  of a DVF line may also not identify the same apartment in both deeds. It is published as
  a documented failure of the method on this sample, not as a price measure.
- **The pseudo repeat-sales indices understate the official ones** (HDB +42% against +51%,
  private +19% against +26%): pairs match a block or project, a storey band and a floor
  area, not a dwelling, and the lease is shorter at the second sale.
- **Bootstrap intervals** treat the sales of a cell as independent draws; sales in the same
  building or project are not, so intervals are somewhat too narrow. For cells of five to
  ten sales the bootstrap distribution of a median is coarse, and so is the shrinkage weight
  that depends on it.
- **Shrinkage** assumes the cells of a parent are exchangeable. A street that truly differs
  from its arrondissement and has few sales is pulled towards it: the shrunk map is smoother
  than reality, which is why raw values stay published.
- **Hedonic indices** hold observed characteristics constant, not condition, view or energy
  class. The pooled version fixes the characteristic prices over the whole period.
- **Explosive-root tests** use nominal official indices, a fixed lag order of 0 and simulated
  critical values. They date explosive episodes at city level and say nothing about streets
  or the level of fundamental value. On a nominal index a long period of steady growth is
  dated as one long episode (Paris: 2000 Q3 to 2022 Q4), so the dates are indications, not
  turning points. The statistic also rises when a series falls at an accelerating pace, so
  the direction of each episode must be read from the series itself; this matters for the
  price-to-rent ratio.
- **Paris window.** DVF+ open-data is listed as covering 2014 to 2025, but its files sit in
  a shared folder that needs a manual download (data audit, §10). Until that is done, all
  Paris results rest on July 2021 to June 2026.
- **HDB history before 2017** is not ingested, so the HDB index starts in 2017.
- **Dates of the inputs differ.** Robust statistics, indices and tests come from the
  download of 2026-11-10; model, valuation and site outputs from that of 2026-11-07. For
  Paris and HDB the cell statistics common to both are identical up to rounding. For the
  private market they differ slightly: URA serves a rolling five-year window, so the oldest
  weeks have dropped out and recent sales have been added (100,890 sales kept against
  101,104).

## Two cross-checks (added 2026-11-10)
- **They share the interest rate.** When rates rise, both checks deteriorate together, so
  two failures are less than two independent pieces of evidence.
- **Check 1 inherits the rent data.** Paris reference rents are regulated and below market
  rents, which raises the required growth; HDB and private rents are medians matched by
  location and type, not the rent of the sold home. Rents are gross: vacancy and charges
  are not deducted, which lowers the required growth.
- **Check 1's yardstick is national and backward-looking**: twenty years of national rent
  and income growth, not a forecast and not the city's own.
- **Check 2 describes a median local household, not buyers.** Paris: neighbourhood median
  disposable income of 2021 (after tax, not updated) for a couple; the lending rule applies
  to income before tax, and buyers are richer than residents and often bring equity.
  Singapore: income from work includes employer CPF contributions, which overstates the
  income lenders count; CPF savings and housing grants, which finance much of an HDB
  purchase, are ignored, which understates capacity.
- **The down payment for Paris (20%) is a convention**; the rule sets none. At 10% the
  price-to-capacity ratio rises by an eighth.
- **Lending parameters** were read in secondary sources and remain to be checked in the
  HCSF and MAS texts.

## Calibration on past busts (added 2026-11-11)
- **Few events:** 27 to 31 busts with enough history, so the thresholds are imprecise; they
  were chosen and evaluated on the same sample (no out-of-sample test).
- **Countries, not cities:** the calibration is national; Paris and Singapore are cities,
  and Singapore is not in the OECD panel.
- **A z-score measures how unusual a ratio is against its own past, not its right level.**
  A market that has been dear for twenty years looks ordinary (Paris), and a bust can come
  with a ratio that was not unusual (Japan 1991, France 1991).
- **Ratios only.** Credit growth, construction and lending standards, which the literature
  on housing busts gives at least as much weight, are not in the data.
- **The thresholds depend on the definitions** (15% real fall, 12-quarter horizon, ten years
  of history); these were set once and not tuned.
- **City downturns are in nominal terms**, and the Paris series starts after the 1991 peak.
