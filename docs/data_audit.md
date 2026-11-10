# Data source audit (Step 0)

Retrieval date for every figure below: **2026-11-07** (UTC). Counts were computed from the files at the
URLs given, downloaded on that date. Raw downloads are not committed; Step 1 turns each probe into a
download script under `src/ingest/` so every count can be reproduced.

## 1. Is there one source covering all cities at transaction/address level?

**No.** No single source covers Paris, Singapore, London, New York and Ho Chi Minh City with
transaction-level prices at address or street level.

| Candidate | What it actually is | Why it is rejected as primary data |
|---|---|---|
| Numbeo | Crowdsourced survey of user-entered prices | Not transactions; unknown sample, no address level |
| Global Property Guide | Asking prices and yields compiled from agents/listings | Aggregated, listing-based, small samples per city |
| Savills / CBRE / Knight Frank | Proprietary research indices, prime-segment focus | Aggregated, not redistributable, methodology not reproducible |
| BIS Residential Property Price database / OECD house prices | Official, but national or metro indices | No dwelling/street granularity |

This conclusion rests on knowing how each candidate is built, not on an exhaustive proof that nothing else
exists. If you know of a candidate I have not listed, I will audit it the same way.

**Decision:** use each city's official register and harmonise them into one common schema (Step 1).

## 2. Audit table, Tier 1

| City | Source | URL | Licence | Period available | Granularity | Key fields | n rows (verified) | Known biases / caveats |
|---|---|---|---|---|---|---|---|---|
| Paris | DGFiP **DVF**, geolocated version (Etalab "DVF géolocalisées") | https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres-geolocalisees (raw DGFiP: https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres) | Licence Ouverte 2.0 **plus DGFiP CGU** (see §4) | **2021-07-01 → 2026-06-30 only** (rolling 5-year window required by law, art. L112 A LPF; older years are withdrawn) | Address (number + street) and cadastral parcel; lat/lon = **parcel centroid**, not the building entrance | date, nature_mutation, valeur_fonciere, address, code_voie, parcel, Carrez area per lot (lots 1–5), surface_reelle_bati, nombre_pieces, type_local, lat, lon | Département 75: **428,067 rows** (lot/local lines), **211,236 mutations**. Sales (`Vente`) of exactly one apartment, with or without outbuildings (dépendances) only: **151,181** (2021 H2: 16,710 · 2022: 35,355 · 2023: 28,390 · 2024: 25,643 · 2025: 30,522 · 2026 H1: 14,561) | Price is for the whole mutation (multi-lot sales must be dropped). No construction year, no floor level, no furnished flag. `surface_reelle_bati` ≠ Carrez area (Carrez is filled for only 56.2% of lot 1). Price may include parking or cellar. Excludes Alsace-Moselle (irrelevant here). Lat present for 99.99% of retained sales. 3,725 distinct streets |
| Paris | Ville de Paris, **reference rents** ("Logement – Encadrement des loyers") | https://opendata.paris.fr/explore/dataset/logement-encadrement-des-loyers/ | **ODbL** | Vintages **2019–2025** (each vintage applies from 1 July). Dataset last modified 2025-06-17, so the 2026 vintage is **not yet published here** | 80 administrative quartiers (14 rent zones) × rooms (1, 2, 3, 4+) × construction period (4 classes) × furnished/unfurnished | annee, id_quartier, nom_quartier, piece, epoque, meuble_txt, ref / min / max (€/m²/month, excluding charges), geo_shape | **17,920 rows** = 7 vintages × 2,560 cells | These are **regulatory reference values** (ref = estimated median, max = ref + 20%, min = ref − 30%), derived from OLAP observed rents and set by prefectoral order. They are **not contracts**. They cover the regulated private rental stock, a different composition from the owner-occupied stock in DVF. Matching a sale to a cell needs the construction period, **which DVF does not contain** (see §5) |
| Paris | INSEE **Filosofi 2021, IRIS level** (disposable and declared income) | https://www.insee.fr/fr/statistiques/8229323 (files `BASE_TD_FILO_IRIS_2021_DISP_CSV.zip`, `…_DEC_CSV.zip`) | Licence Ouverte 2.0 (INSEE reuse terms) | **2021** (latest IRIS vintage published; released 2024-07-31) | IRIS | median, quartiles and deciles of income, poverty rate | France: 16,026 IRIS. Paris: **992 IRIS, 864 with a published median** (the rest are suppressed for confidentiality) | Medians are **per consumption unit (UC)**, not per household. A household-income price-to-income ratio therefore needs a stated conversion (e.g. × mean UC per household from a census table) or a per-UC definition. Single year (2021) against prices from 2021–2026. Excludes the PEPA bonus (INSEE note). INSEE advises against analysing changes for areas under 1,000 households |
| Singapore | HDB **resale flat prices** (registration date, Jan 2017 onwards) | https://data.gov.sg/datasets/d_8b84c4ee58e3cfc0ece0d773c8ca6abc (collection 189 also has 1990–1999, 2000–Feb 2012, Mar 2012–2014 and 2015–2016 files) | Singapore Open Data Licence v1.0 | **2017-01 → 2026-11** (monthly; refreshed 2026-11-08 SGT) | **Block + street** (no unit number); month only | month, town, flat_type, block, street_name, storey_range (3-floor bands), floor_area_sqm, flat_model, lease_commence_date, remaining_lease, resale_price | **244,312 rows** (IDs 1…244,312, contiguous). Per year: 2017: 20,509 … 2025: 25,084, 2026 (to Nov): 22,246. 26 towns, 580 streets, 9,770 blocks. Older files: 369,651 (2000–Feb 2012), 52,203 (Mar 2012–2014), 37,153 (2015–2016) | Public housing on 99-year leases: prices reflect a decaying lease, so remaining lease is essential. Resale market only (no BTO new-flat prices, which are subsidised). Month resolution only. 318 exact duplicate rows (same block, month, storey band, area and price): these cannot be told apart from genuinely distinct sales, so they are kept and flagged. **Caveat:** the API's `total` field reported 143,396 on one call and 244,312 on another; I rely on full pagination plus the ID check |
| Singapore | HDB **"Renting Out of Flats from Jan 2021"** | https://data.gov.sg/datasets/d_c9f57187485a850908655db0e8cfe651 | Singapore Open Data Licence v1.0 | **2021-01 → 2026-10** | Block + street; month | rent_approval_date, town, block, street_name, flat_type, monthly_rent | **215,469 rows** (contiguous IDs). Per year: 2021: 38,882 · 2022: 33,612 · 2023: 36,855 · 2024: 36,508 · 2025: 39,099 · 2026 (to Oct): 30,513. 9,739 blocks, 9,479 of which also appear in the resale data | These are **HDB approvals to rent out a whole flat**, with the declared rent, not market contracts observed by a third party. **No floor area**: rent/m² needs an explicit, documented flat-type × block area mapping from the resale file (not a silent imputation). Whole-flat lets only (room rentals excluded) |
| Singapore | URA Data Service: **private residential transactions** (`PMI_Resi_Transaction`) and **rental contracts** (`PMI_Resi_Rental`) | https://eservice.ura.gov.sg/maps/api/ | URA Data Service terms, to be read when the key is issued | **Past 5 years only** (URA advises dropping records older than 5 years) | Project + street; x/y (SVY21) of the **project**, not the unit; floor range in 5-floor bands. Rentals: area in **10 m² bins**, bedrooms | Sales: contractDate, area, price, propertyType, tenure, floorRange, typeOfSale (new/sub/resale), district, noOfUnits. Rentals: leaseDate, areaSqm (bin), rent, noOfBedRoom | **Not verified.** Needs a free personal AccessKey (registration) and a daily token. I have no key, so I cannot count rows yet | Rentals are contracts submitted to IRAS for stamp duty (good), but area is binned. Location is at project level. Batches are split by postal district |
| Singapore | **Census of Population 2020**: "Resident Households by Planning Area of Residence and Monthly Household Income from Work" | https://data.gov.sg/datasets/d_4e150bbd35c3145ea43019212c7b46c2 (an earlier copy: https://data.gov.sg/datasets/d_2d6793de474551149c438ba349a108fd) | Singapore Open Data Licence v1.0 | **2020** (single cross-section) | Planning area: **30 named areas + "Others" + Total** (smaller areas are pooled into "Others") | Household counts in 18 income bands, plus "no employed person" | 32 rows; total 1,372,559 resident households | **Income from work only**: it excludes the 182,445 households with no employed person and all non-work income. **Banded**: a median by planning area must be interpolated from the bands, and the method will be stated. The two data.gov.sg copies differ slightly in the band counts (e.g. "Below 1,000": 26,987 vs 27,007) with the same total; I will check which one matches the SingStat release before using it. HDB towns and URA planning areas are not identical units |

### Supporting sources (verified reachable)

| Purpose | Source | URL | Licence | Status |
|---|---|---|---|---|
| FX | ECB euro foreign exchange reference rates (SGD, USD per EUR, daily) | https://data-api.ecb.europa.eu/service/data/EXR/D.SGD+USD.EUR.SP00.A | ECB statistics reuse with attribution | OK (e.g. SGD/EUR 1.4274 on 2026-10-28) |
| Geocoding, Paris | BAN geocoder | https://api-adresse.data.gouv.fr/search/ (same engine at https://data.geopf.fr/geocodage/search) | Licence Ouverte 2.0 | OK. Barely needed: DVF is already 99.99% geolocated |
| Geocoding, Singapore | OneMap Search API | https://www.onemap.gov.sg/api/common/elastic/search | OneMap terms of use | OK: answered without a token, but the response asks for an account and API token. I will register and respect the rate limits. Hit rate measured in Step 1 |
| Paris geometries | Quartiers administratifs / arrondissements (Ville de Paris); IRIS contours (IGN) | opendata.paris.fr; data.geopf.fr | ODbL; Licence Ouverte | To confirm in Step 1 |
| POIs (metro/MRT, parks, CBD) | OpenStreetMap via osmnx/Overpass, or Geofabrik extracts | overpass-api.de; download.geofabrik.de | ODbL | **Not verified**: both hosts reset the connection repeatedly from this environment today |

### Observed-rent alternative for Paris (not yet downloaded)

The Observatoires Locaux des Loyers (OLL/OLAP) publish **observed** rents
(https://www.data.gouv.fr/datasets/resultats-nationaux-des-observatoires-locaux-des-loyers, Licence Ouverte,
files hosted on observatoires-des-loyers.org). The national files are at agglomeration / central-city level,
so they are too coarse for quartier maps. They are a useful check on how close the regulatory reference
rents are to observed market rents.

## 3. Tier 2 and Tier 3: not audited yet

As instructed, these wait until Tier 1 is finished. Candidates noted for later: London (HM Land Registry
Price Paid + EPC floor area), New York (NYC DOF Rolling Sales + PLUTO). Ho Chi Minh City has no public
transaction register, so only asking-price listings, aggregated to district/ward and labelled "asking prices,
not transactions", subject to each site's terms and robots.txt.

## 4. Terms that constrain the project

1. **DVF CGU (DGFiP)**:
   (a) reuse must never aim at, or result in, re-identifying individuals;
   (b) the information **must not be indexed by search engines**: the CGU asks reusers to block it
   (robots.txt or similar);
   (c) GDPR applies (a retention period must be defined; the source itself keeps a 5-year window).
   *Consequences:*
   - only aggregates are published, with n ≥ 5 per street-year;
   - no transaction-level rows on the site, the Kaggle dataset or in git;
   - the site carries `<meta name="robots" content="noindex">` on every page. A project Pages site cannot
     rely on a root robots.txt it does not control, so the meta tag is needed.
2. **ODbL (Paris rents, OSM)**: share-alike. A published database derived from them (the Kaggle
   dataset, the site's GeoJSON) must also be released under ODbL with attribution. **The Kaggle dataset's
   licence therefore has to be ODbL.**
3. **Singapore Open Data Licence v1.0**: free reuse with attribution, no endorsement implied.
4. **URA**: to be read when the access key is issued.

## 5. Coverage under the n ≥ 5 publication rule (measured)

| City | Level | Units with ≥ 1 sale (unit-years) | Units meeting n ≥ 5 | Share of sales in units meeting n ≥ 5 |
|---|---|---|---|---|
| Paris (single-apartment sales) | street (commune + code_voie) × year | 18,378 | 8,561 | **86%** |
| Singapore HDB resale | street × year | 5,486 | 5,027 | **99.5%** |
| Singapore HDB resale | block × year | 77,008 | 14,672 | 44.5% |
| Singapore HDB rent | block × year | 51,461 | 17,758 | 62.8% |

Street level works for both cities. For Singapore blocks, H3 hexagons (resolution 9) will probably publish
more data than blocks while still respecting n ≥ 5.

## 6. Issues that change the design (need your decision)

1. **Paris time window is only 2021 H2 to 2026 H1.** "5-year change" can only be computed between the
   2021 H2 and 2026 H1 half-years, which is less than 5 full years. A longer history would need DVF+
   (Cerema; **corrected in §10: DVF+ open-data is listed as open, 2014 to 2025, to be tested**), or archived pre-2021 DVF copies, which the 5-year rule makes legally
   doubtful to republish. I propose: YoY changes plus a "2022 → 2025" change, labelled honestly.
2. **DVF has no construction period, yet the reference rents depend on it.** Options:
   - (a) add building construction year from the BDNB (CSTB, open licence) or the IGN BD TOPO building
     layer, joined by parcel;
   - (b) use the quartier × rooms rent averaged across construction periods, weighted by the local
     building-age mix, and state this;
   - (c) run both and use (b) as a robustness check.

   I recommend (c).
3. **Singapore rent has no floor area.** Proposed rent/m² = monthly rent ÷ median floor area of the same
   flat_type in the same block (from resale), falling back to town × flat_type, with each fallback logged.
   The alternative is to work in per-flat terms (price-to-rent per flat type), which needs no area at all.
   I recommend the per-flat ratio as the primary measure and rent/m² as secondary.
4. **Income definitions differ by city**: per-UC disposable income (Paris, 2021) vs household income from
   work, banded (Singapore, 2020). Cross-city price-to-income comparisons must be presented as
   "not strictly comparable".
5. **Singapore private market (URA)** needs your access key: register at https://eservice.ura.gov.sg/maps/api/
   (the "Sign Up for an Access Key" section). When you have it, I will ask you to save it through the
   environment's secure secret form, never in chat or in the repo.
6. **OSM hosts** were unreachable today. I will retry in Step 1 and report back. No substitute will be used
   without asking you.

## 7. Addendum (Step 1): sources added during the build, verified 2026-11-07

| Purpose | Source | URL | Licence | Verified content |
|---|---|---|---|---|
| Paris building construction date, floors, dwellings | IGN BD TOPO v3, layer `batiment` (WFS) | https://data.geopf.fr/wfs/ows (`BDTOPO_V3:batiment`) | Licence Ouverte 2.0 | 239,300 buildings in the Paris bounding box; `date_d_apparition`, `nombre_d_etages`, `nombre_de_logements` |
| Paris IRIS contours | IGN `STATISTICALUNITS.IRIS:contours_iris` (WFS) | https://data.geopf.fr/wfs/ows | Licence Ouverte 2.0 | 992 Paris IRIS (matches Filosofi) |
| Paris stations | Île-de-France Mobilités, "Gares et stations du réseau ferré d'Île-de-France" | https://data.iledefrance-mobilites.fr/explore/dataset/emplacement-des-gares-idf/ | Licence Ouverte | 1,287 station × line points (metro, RER, train, tram) |
| Paris green spaces | Ville de Paris, "Espaces verts et assimilés" | https://opendata.paris.fr/explore/dataset/espaces_verts/ | ODbL | 2,535 polygons |
| Paris arrondissements / quartiers | Ville de Paris | https://opendata.paris.fr/explore/dataset/arrondissements/ · .../quartier_paris/ | ODbL | 20 / 80 polygons |
| Singapore geometries | URA MP2019 planning areas and subzones | https://data.gov.sg/datasets/d_4765db0e87b9c86336792efe8a1f7a66 · d_8594ae9ff96d0c708bc2af633048edfb | Singapore Open Data Licence | 55 planning areas / 332 subzones |
| Singapore MRT/LRT | LTA MRT station exits | https://data.gov.sg/datasets/d_b39d3a0871985372d7e1637193335da5 | Singapore Open Data Licence | 613 exits |
| Singapore parks | NParks parks and nature reserves | https://data.gov.sg/datasets/d_77d7ec97be83d44f61b85454f844382f | Singapore Open Data Licence | 462 polygons |
| Singapore block attributes | HDB Property Information | https://data.gov.sg/datasets/d_17f5382f26140b1fdae0ba2ef6239d2f | Singapore Open Data Licence | 13,392 blocks (max floor, completion year) |
| Risk-free rate, France | ECB long-term interest rate, 10-year government bond | https://data-api.ecb.europa.eu/service/data/IRS/M.FR.L.L40.CI.0000.EUR.N.Z | ECB statistics reuse | monthly, e.g. 4.44% in 2026-09 |
| Risk-free rate, Singapore | SingStat M700071, "Government Securities - 10-Year Bond Yield" | https://tablebuilder.singstat.gov.sg/table/TS/M700071 | SingStat terms of use | monthly, 1998-06 to 2026-09 (2.47% in 2026-09) |

**OpenStreetMap:** Overpass (two endpoints) and Geofabrik kept dropping connections from the
build environment. The official sources above replace OSM for stations and parks; no OSM
data are used.

**Corrections found during the build:**
- **Join key for the Paris reference rents.** The rent file's `code_grand_quartier` uses the
  city-wide quartier number (Gaillon = 7510205), while the quartier geometry's `c_quinsee`
  numbers quartiers within each arrondissement (Gaillon = 7510201). The two files are
  joined on the city-wide number 1–80 (`id_quartier` = `c_qu`).
- **Non-market prices in DVF.** Over 1% of some arrondissement-years are symbolic or
  non-market prices (e.g. €1). These are removed by a factor-3-of-median rule before the
  percentile trim (5,729 sales).
- **Singapore datastore API.** The `total` field is unreliable and wide tables return
  "413 Payload Too Large" for 10,000-row pages. Downloads use full pagination, an adaptive
  page size and a check that `_id` values are contiguous.

## 8. Addendum: URA private market, verified 2026-11-07 with the user's access key

| Source | URL | Licence | Period | Granularity | n rows | Caveats |
|---|---|---|---|---|---|---|
| URA private residential transactions (`PMI_Resi_Transaction`, 4 batches) | https://eservice.ura.gov.sg/maps/api/ | URA Data Service terms: **not yet read** (the terms page could not be reached from the build environment) | 2021-11 to 2026-11 (rolling 5 years) | Project + street; project x/y (SVY21), missing for 22.7% of records (mostly new launches; 109 of 120 such projects geocoded with OneMap) | 132,192 transactions (103,850 Apartment/Condominium; 15,928 Executive Condominium; 12,414 landed) | Location is the project's, not the unit's; floor in 5-storey bands; some project names served in Windows-1252 |
| URA private rental contracts (`PMI_Resi_Rental`, per quarter) | same | same | 2022 Q1 to 2026 Q3 (2026 Q4 not yet published) | Project + street; area in 10 m² bands; bedrooms | 430,973 contracts (397,046 non-landed) | Contracts stamped with IRAS (observed market rents) |

Scope used: non-landed Apartment and Condominium, single-unit sales (open market). Executive
Condominiums (eligibility and resale restrictions) and landed homes (land area) are excluded.

## 9. Ho Chi Minh City (Tier 3, exploratory), audited 2026-11-08

Vietnam has no public register of property transaction prices.

| Candidate | What it is | Access verified | Usable? |
|---|---|---|---|
| batdongsan.com.vn, nhatot.com (listings) | Asking prices of listings, address/project level | Both serve a Cloudflare bot challenge to automated clients, even for robots.txt | **No.** Collecting them would mean circumventing an active anti-bot measure |
| chotot.com | General classifieds (real estate is on nhatot.com) | robots.txt reachable; `Content-Signal: ai-train=no`; price-filter URLs disallowed | No for housing (listings are on nhatot.com) |
| HCMC land price table, Resolution 87/2025/NQ-HĐND (in force 1 Jan 2026) | Official administrative land prices (VND/m²) per street segment, Annexes II-IV | Official text announced on hdnd.hochiminhcity.gov.vn; the annexes found online are third-party PDF copies, not yet the signed original | **Reliable but not market prices**: administrative values used for taxes and fees, land only, historically far below market |
| Ministry of Construction quarterly housing bulletins | City-level average apartment prices (e.g. about VND 89 million/m² in Q2 2025) | moc.gov.vn press releases | Aggregate only: no district or street detail |
| GSO (General Statistics Office) | National statistics; no open district-level house price series found | Not verified | Not at the needed granularity |
| Kaggle "House Pricing HCM" and similar | Third-party compilations of scraped listings, provenance not stated | Not downloaded | **No**: unknown provenance and licence |
| CBRE, Savills, Numbeo | Aggregated or crowdsourced | n/a | Excluded by design |

**Conclusion:** no reliable, legally accessible dataset gives HCMC dwelling prices or rents at
street or ward level. The only official street-level source is the administrative land
price table, which measures regulated land values, not market prices or rents, so a
rent-capitalisation test cannot be run for HCMC with public data.

**Update 2026-11-08: Official Gazette.** The signed annexes are published in the HCMC Official
Gazette (congbao.hochiminhcity.gov.vn), split over the issues of 1 January to 15 March 2026.
One part was downloaded (issue 68+69, 94 pages, wards incl. Phước Long): the tables are
machine-readable (street, segment from/to, residential, commercial and non-commercial land
prices in thousand VND/m²), with some mis-encoded Vietnamese diacritics. The gazette's
firewall blocks automated requests, even spaced 10-15 s apart, so the remaining parts are
downloaded by hand (`docs/hcmc_download_list.md`). OSM is unreachable from the build
environment and HCMC wards were redrawn in July 2025, so no ward or street geometry is
available yet.

**Update 2026-11-08: complete table.** All gazette issues carrying the annexes of Resolution
87/2025 (issues 62+63 to 84+85 of 1 March 2026; 12 PDFs, downloaded by hand) were extracted
by `src/clean/hcmc.py`: **10,812 priced street segments in all 168 wards, communes and the
Côn Đảo special zone** of the new Ho Chi Minh City. Numbering is complete in every unit;
247 of 10,307 numbered entries (2.4%) are unreadable (mostly under the signature stamp) and
excluded. Checks against published figures: the maximum residential value is VND 687.2
million/m² (Đồng Khởi, Nguyễn Huệ, Lê Lợi) and the zone-3 maximum VND 149.48 million/m²
(Thùy Vân), both as announced. These remain administrative land values, not market prices.

## 10. Addendum: review of 2026-11-10

Checked on official pages on 2026-11-10. The public sources were then downloaded again on a
GitHub runner the same day (`data/raw/MANIFEST.csv`, `data/processed/build_report.txt`): the
Paris and HDB files have the same sizes as on 2026-11-07 and reproduce the published cell
statistics up to rounding. data.gov.sg rate-limits unauthenticated requests (HTTP 429): the
download waits and retries, and takes about 15 minutes.

| Topic | Finding | Status |
|---|---|---|
| **DVF+ open-data** (Cerema / DGALN) | Listed on data.gouv.fr under Licence Ouverte 2.0, temporal coverage "2014 à 2025", updated twice a year (https://www.data.gouv.fr/datasets/dvf-open-data). §6.1 above called DVF+ "not open data"; that describes DV3F, the enriched restricted base, not DVF+ open-data | The data.gouv.fr API confirms the licence (`lov2`) and the coverage 2014-01-01 to 2025-12-31, but the two resources point to a shared folder (cerema.app.box.com/v/dvfplus-opendata), not to files: **manual download needed**. Still to check: the content for département 75 and how the DGFiP reuse terms apply outside the 5-year window |
| Notaires-INSEE, existing apartments, Paris | Quarterly hedonic index, series published from 1991 Q1 (INSEE Méthodes n°132, 2019) | **Downloaded 2026-11-10:** INSEE series 010567012 ("Paris - Appartements - Base 100 en moyenne annuelle 2015 - Série brute"), 138 quarters, 1992 Q1 to 2026 Q2, from INSEE's SDMX service |
| URA private residential property price index | data.gov.sg `d_97f8a2e995022d311c6c68cfda6d034c`, quarterly from 1975 Q1, stratified hedonic regression | **Downloaded 2026-11-10:** 621 rows (three property types × 207 quarters, to 2026 Q3); the non-landed series is used |
| HDB resale price index (1Q2009 = 100) | data.gov.sg `d_14f63e595975691e7c24a27ae4c07c79`, quarterly | **Downloaded 2026-11-10:** 147 quarters, 1990 Q1 to 2026 Q3 |
| URA private residential rental index | data.gov.sg `d_8e4c50283fb7052a391dfb746a05c853`, quarterly from 2004 Q1, private homes only | **Downloaded 2026-11-10:** 525 rows by property type and locality; non-landed, whole island is used (2004 Q1 to 2026 Q3) |
| Long rent series for Paris | None identified | Open: without one, no Paris price-to-rent test |
| HDB resale before 2017 | Collection 189 on data.gov.sg goes back to January 1990 (approval date before March 2012, registration date after) | Not ingested: dataset identifiers and schemas of the older files to confirm |
| Census 2020 income table | `d_2d6793de474551149c438ba349a108fd` is adapted from SingStat table CT/17779; the copy `d_4e150bbd…` notes an update for Additional MediSave contributions, the likely source of the small band differences noted in §2 | To confirm on SingStat |
| INSEE Filosofi | 2021 is the last vintage of the original scheme; "Filosofi 2" starts with the 2023 vintage (local indicators published May 2026, restricted release); no 2022 vintage | IRIS-level availability for 2023 not verified |
| URA Data Service terms | Still not read on an official page | Blocks publication of URA-derived aggregates |
| One source for all cities | None. BIS residential property price statistics are indices by country, not transactions | Conclusion of §1 stands |
| Tier 2 | HM Land Registry Price Paid Data (from 1995, Open Government Licence v3.0, attribution required, third-party rights in address fields excluded); NYC Department of Finance rolling sales (last 12 months) and annualised sales (from 2003) | Sources exist; not started |
