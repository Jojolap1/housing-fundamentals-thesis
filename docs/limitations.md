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
- **Singapore private housing (URA) is not included yet.** It needs a personal access key.
  Results for Singapore are for public housing only, and public housing is a regulated
  market: eligibility rules, CPF financing and grants all shape HDB prices.

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
- Moran's I is computed on a 20,000-sale sample with k = 10 neighbours.
- Distances are straight-line, not walking distances. The CBD anchor is a single point.

## Data access
- The OSM Overpass API and Geofabrik were unreachable from the build environment, so
  stations and parks come from official sources instead (IDFM, Ville de Paris, LTA,
  NParks). This is an improvement in provenance, but OSM-based features are not
  reproduced.
