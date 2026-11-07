# Singapore: status at 2026-11-07 19:43 UTC

Done
- All raw downloads (data/raw/singapore, recorded in MANIFEST.csv): HDB resale 2017+ (244,312 rows),
  HDB rent 2021+ (215,469), HDB property information (13,392 blocks), Census 2020 income by planning area
  (both data.gov.sg copies), MP2019 planning areas and subzones, LTA MRT exits, NParks parks, HDB buildings.
- OneMap geocoding: 10,020 / 10,030 blocks (99.9%); the 10 misses are on Tanglin Halt Road, a cleared estate.
  Cache: data/raw/singapore/onemap_blocks.csv. This took about an hour; keep it.
- Cleaning: 238,198 resale transactions kept (data/processed/cleaning_log_singapore.csv).
- Features and ratios: data/processed/stats_singapore_*.csv. City median S$6,493/m² in 2025,
  +49% from 2020 to 2025, gross yield about 6.2%, 4-room price-to-income 5.9 (2020 income).

To do
1. `python -m src.models.hedonic` for `singapore` and `singapore_rent`, then `rent_on_sales()`
   (stopped on request before finishing; about 30 minutes).
2. `python -m src.ratios.valuation` (Singapore part: `run_city("Singapore")`).
3. `python -m src.viz.export` and `python -m src.viz.pages`.
4. Check: the 2017-2020 valuation gaps use the rent model held at its 2021 level (flagged in the data).
