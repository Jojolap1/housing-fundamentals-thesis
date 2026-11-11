# Findings (build of 2026-11-10)

All figures come from `data/processed/` (`verdict.csv`, `ratio_history.csv`,
`explosive_summary.csv`, `index_validation_*.csv`). The verdict rule is the one fixed in
`docs/methodology.md` §12 before any of these results existed; it has not been adjusted.

## Verdict table

| | Paris (existing apartments) | Singapore HDB resale | Singapore private non-landed |
|---|---|---|---|
| User cost: share of the sensitivity grid with a positive gap, 2025 | 86% → **deviation** | 19% → below | 87% → **deviation** |
| Explosive root (GSADF on the official index): episode running at the end of the sample | no (2000 Q3 to 2022 Q4) | **yes** (since 2021 Q1) | **yes** (since 2021 Q1) |
| Price-to-rent, latest against its history | +27% above the 1992–2026 mean, 19% below the 2020 peak, z = 0.8 → within one s.d. | not run (no rent index) | z ≈ 0 → within one s.d. |
| Price-to-income, latest against its history | +8% above the mean, 30% below the 2020 peak, z = 0.4 → within one s.d. | +4% above the 2000–2025 mean, z = 0.5 → within one s.d. | 3% below the mean, z = −0.3 → within one s.d. |
| Anchors pointing to deviation | 1 of 4 | 1 of 3 | 2 of 4 |
| **Verdict** | **inconclusive** | **inconclusive** | **inconclusive** |

No market reaches the three agreeing anchors that "evidence of deviation" requires, and none
meets the conditions for "consistent with fundamentals".

## Two cross-checks of sale prices, 2025

Outside the verdict rule (method: `docs/methodology.md` §13; figures: `cross_checks.csv`).

| | Paris | HDB resale | Singapore private |
|---|---|---|---|
| Rent growth the price requires (risk premium 1% / 2% / 4%) | 3.0% / 4.0% / 6.0% a year | −1.2% / −0.2% / 1.8% | 2.4% / 3.4% / 5.4% |
| Growth over the last 20 years: rents; incomes | 1.4%; 2.4% (national) | no rent index; 4.7% | 4.6%; 4.7% |
| Check 1 | **implausible** | plausible | depends on the premium |
| Price ÷ what the reference household can finance (rate −1 pt / base / +1 pt) | 1.39 / 1.56 / 1.73 | 0.64 / 0.71 / 0.79 | 0.86 / 0.97 / 1.09 |
| Check 2 | **beyond capacity** | within capacity | depends on the rate |
| Read together | **fails both checks** | **passes both checks** | mixed |

Paris fails check 2 in every year from 2021 and check 1 in every year from 2023; in 2021
and 2022, with yields near zero, check 1 depended on the risk premium. HDB passes both in
every year where rents exist (2021 onward).

**Why this does not contradict the "inconclusive" verdict.** The verdict's ratios ask
whether a market is far from its own history, and Paris's history since 1992 is mostly a
high-price period, so today looks ordinary against it. The cross-checks ask whether the
level itself holds against outside yardsticks: the growth of rents and incomes, and the
lending rules. Paris prices are ordinary by the standard of the last thirty years and
demanding by those yardsticks. Both statements are true, and the thesis should state both.

**What weakens the Paris result.** Rents are regulated reference rents, below market rents,
which raises the required growth. Incomes are the 2021 neighbourhood medians, not updated,
after tax, for a median local couple, whereas actual buyers are richer and bring equity
from a previous home; all of this raises the price-to-capacity ratio. The yardsticks for
rent and income growth are national. The direction of the result survives a 10 to 15%
correction of incomes (1.56 would become about 1.4); its size does not.

## What past housing busts say

Method: `docs/methodology.md` §14; figures: `early_warning_*.csv`, `city_drawdowns.csv`.
Panel: OECD indicators for 39 countries, quarterly. A bust is a fall of real house prices of
at least 15% from a peak. Each ratio is measured as a z-score against the country's own past
only.

**Before a bust, the ratios were about two standard deviations above their past.** At the
peak, the median z-score was 2.0 for price-to-income (27 busts with enough history) and 2.1
for price-to-rent (31 busts); the median real fall that followed was 30%.

| Bust (peak) | Real fall | Price-to-income z-score at the peak |
|---|---|---|
| Ireland 2007 | −52% | 2.6 |
| Spain 2007 | −42% | 2.6 |
| Denmark 2007 | −28% | 2.8 |
| United States 2006 | −28% | 1.5 |
| Netherlands 2007 | −26% | 1.7 |
| United Kingdom 2007 | −20% | 1.9 |
| Japan 1991 | −45% | 0.9 |
| France 1991 | −17% | 0.9 |

Japan 1991 and France 1991 show the limit: both busts came with a ratio less than one
standard deviation above its past.

**Calibrated thresholds.** The threshold that best separates pre-bust quarters (the three
years before a peak) from other quarters:

| Ratio | Threshold (z-score) | Pre-bust quarters flagged | Other quarters flagged | Busts flagged before their peak | Flagged quarters that were pre-bust |
|---|---|---|---|---|---|
| Price-to-income | 1.5 | 60% | 21% | 74% | 25% |
| Price-to-rent | 1.75 | 60% | 23% | 77% | 25% |

Three flagged quarters out of four were not followed by a bust within three years: a high
ratio is a necessary-looking condition far more than a sufficient one. The verdict rule
uses one standard deviation, chosen before this calibration; at that level about 35%
(price-to-income) to 51% (price-to-rent) of ordinary quarters are flagged, so the calibrated
thresholds are stricter. The rule has not been changed; no signal would change if it were,
since every current ratio is below one standard deviation.

**Housing crises only.** A real fall of 15% can come from inflation alone, with sale prices
flat. Two stricter definitions were run next to the baseline, without replacing it:

| Definition of a bust | Busts in the panel | Median real fall | Median nominal fall | Median time to the trough |
|---|---|---|---|---|
| Baseline: real fall of at least 15% | 66 | −30% | −11% | 23 quarters |
| Crash: real fall of at least 15% and nominal fall of at least 10% | 33 | −36% | −21% | 25 quarters |
| Major: real fall of at least 25% | 46 | −35% | −17% | 25 quarters |

Half of the baseline busts are not crashes in sale prices. On crashes only:

| Ratio | Threshold (z-score) | Pre-crash quarters flagged | Other quarters flagged | Crashes flagged before their peak | Flagged quarters that were pre-crash |
|---|---|---|---|---|---|
| Price-to-income (13 crashes with enough history) | 1.5 | 66% | 21% | 77% | 15% |
| Price-to-rent (16 crashes) | 2.0 | 51% | 11% | 63% | 24% |

The picture does not change: the median z-score at the peak stays close to 2 (2.0 and 2.2),
the price-to-income threshold stays at 1.5, the price-to-rent threshold rises to 2.0, and most
flagged quarters are still not followed by a crash. With 13 to 16 events these figures are
fragile. No market studied here is above any of these thresholds today.

**Where Paris and Singapore stand** (same z-score, against each market's own past):

| Market | Ratio | Latest z-score | Threshold | Highest on record | Last time above the threshold |
|---|---|---|---|---|---|
| Paris | price-to-income | 0.4 | 1.5 | 2.1 (2011 Q3) | 2020 Q3 |
| Paris | price-to-rent | 0.8 | 1.75 | 2.1 (2005 Q3) | 2012 Q3 |
| HDB | price-to-income | 0.5 | 1.5 | 1.9 (2010) | 2011 |
| Private | price-to-income | −0.3 | 1.5 | 1.0 (2010) | never (2009–2025) |
| Private | price-to-rent | 0.3 | 1.75 | 2.1 (2018 Q2) | 2021 Q4 |

None is above its threshold today. Paris was above the price-to-income threshold in 40% of
the quarters since 2002 and at its 2020 Q3 peak (z = 1.6), before the fall of 12% that
followed: the signal was on.

**How the three markets behaved in their own downturns** (official indices, nominal):

| Market | Peak → trough | Fall | Quarters to the trough | Peak regained |
|---|---|---|---|---|
| Paris | 1992 Q1* → 1998 Q1 | −29% | 24 | 2001 Q3 |
| Paris | 2020 Q3 → 2024 Q2 | −12% | 15 | not yet |
| HDB | 1996 Q4 → 2002 Q1 | −30% | 21 | 2008 Q3 |
| HDB | 2013 Q2 → 2019 Q2 | −12% | 24 | 2021 Q3 |
| Private | 1981 Q2 → 1986 Q2 | −47% | 20 | 1991 Q2 |
| Private | 1996 Q2 → 1998 Q4 | −42% | 10 | 2007 Q4 |
| Private | 2008 Q2 → 2009 Q2 | −26% | 4 | 2010 Q2 |
| Private | 2013 Q3 → 2017 Q2 | −10% | 15 | 2019 Q3 |

*The Paris series starts in 1992 Q1, after the actual peak, so the first fall is understated.

Two patterns stand out. Falls are slow: close to four years or more to the trough in six cases
out of eight, and ten to twelve years to regain the peak after the four large ones. And Singapore's
private market has fallen much harder and faster than Paris (−42% in ten quarters from
1996, −26% in four quarters from 2008), while Paris adjusts through long, shallow declines.
Ratio z-scores exist for only three of these peaks (the income and rent series are too
short before 2010), so this record cannot test the thresholds on Singapore.

**What happened at each turning point.** The city pages chart the official index and the
ratios with these dates marked (`src/viz/events.py`). Each line states what the sources read
say happened around the date; it is a coincidence in time, not a cause estimated here.

| Market | Turning point | What the sources document | Sources |
|---|---|---|---|
| Paris | 1992 Q1 (series start) | End of the 1985–1991 boom in Île-de-France, described as a speculative bubble; real prices in Paris down nearly 46% between 1991 and 1997 | Revue Banque (2005); Grjebine, CEPII (2013) |
| Paris | 2008 Q3 | Global financial crisis; short fall, prices rising again by end 2009 | Notaires de Paris-Île-de-France, 23 Feb 2012 |
| Paris | 2011 Q3 | Euro-area sovereign debt crisis and tighter lending; capital-gains tax reform of 1 Feb 2012 | FNAIM, 3 Jan 2012; Notaires de Paris-Île-de-France, Feb 2012 |
| Paris | 2020 Q3 | Fall attributed by the notaries to the rise in mortgage rates from early 2022; the 2020–2021 part has no verified cause | Notaires du Grand Paris, 7 Sept 2023 (as reported) |
| Private | 1981 Q2 | Pension savings opened to private purchases in 1981; fall spans the 1985 recession | Stacked Homes (secondary); SG101 |
| Private | 1996 Q2 | Anti-speculation package of 14 May 1996, then the Asian financial crisis; trough 45% below the peak | BIS Papers No 64; Singapore Government, 18 Nov 1997 |
| Private | 2000 Q2 | Dot-com bust, 2001 recession, SARS | NUS IREUS study (as reported) |
| Private | 2008 Q1 | Global financial crisis; index down about a quarter | BIS Papers No 64 |
| Private | 2013 Q3 | Higher buyer's stamp duty (Jan 2013), cap on total debt service (June 2013) | Stacked Homes (secondary); PropNex (secondary) |
| Private | 2021 Q1 | Price-to-rent peak; rents then outgrew prices; no cause verified | own series |
| HDB | 1996 Q4 | Asian financial crisis, then the 2001 recession; no source specific to resale flats | BIS Papers No 64 |
| HDB | 2013 Q2 | Repayments capped at 30% of income (Jan 2013), shorter loan terms (Aug 2013) | Stacked Homes (secondary); PropNex (secondary) |

Read across markets: the large falls came with a financial or economic crisis (Paris 1991,
Singapore 1985, 1997, 2008); the milder ones with a tax or lending rule (Paris 2012,
Singapore 2013) or a rise in interest rates (Paris 2022). Several entries rest on secondary
sources and are marked as such; the Singapore measures should be re-read in the official
MAS, MND and HDB releases before the thesis is submitted.

## What can be said firmly

1. **Paris: the 2000–2020 boom has largely deflated; there is no explosive dynamic today.**
   The explosive episode dated on the Notaires-INSEE index ends in 2022. Since the 2020 peak
   the price index has lost 30% against national income per head and 19% against national
   rents; own hedonic index −10.4% from 2021 Q3 to 2026 Q2 (official: −11.3%). The only
   anchor still pointing to overvaluation is rent capitalisation, and its sign is set by
   the interest rate: the same prices were 34% *below* the user-cost value in 2021 and 64%
   above it in 2023.
2. **HDB resale: explosive price dynamics since 2021 without a deterioration of the
   ratios.** The resale index is in a dated explosive episode, yet price-to-income is 4%
   above its 2000–2025 mean and capitalised rents exceed prices over most of the grid.
   Prices rose fast, incomes and rents rose with them.
3. **Singapore private: the closest to a deviation, and still short of it.** Two anchors
   agree (user cost, explosive dynamics since 2021), but prices are 3% below their
   2000–2025 average relative to household income and the price-to-rent ratio is at its
   historical norm.
4. **Paris and HDB sit at opposite ends on outside yardsticks.** In 2025 a Paris price
   needs rents to grow 3 to 6% a year for ever, against 1.4% (rents) and 2.4% (incomes)
   over twenty years, and is about one and a half times what a median local couple can
   finance under the lending rule. An HDB resale price needs no more than 1.8% rent growth
   and is about 0.7 times the financing capacity of the median household.
5. **The methods can be trusted at the level they claim.** The quality-adjusted indices
   reproduce the official ones (Paris −10.4% against −11.3%; HDB +56% against +51%;
   private +27.3% against +26.3%), and the rebuild from a fresh download reproduces the
   published cell statistics.
6. **The rent-capitalisation anchor alone would have given a confident and unstable
   answer.** It says "overvalued" for Paris and Singapore private in 2025 and said
   "undervalued" for Paris in 2021, with the same model and the same rents. This is
   Difficulty 2 measured on the data, and it is the main reason the verdicts are
   inconclusive rather than "overvalued".

## How this compares with outside assessments

These are not inputs to the verdicts; they are listed to show where the results stand.

- **UBS Global Real Estate Bubble Index 2026** (published 22 September 2026) classifies
  Paris as low bubble risk and Singapore as moderate. Same ordering as here: Paris further
  from a deviation than Singapore private. UBS's method combines price-to-income and
  price-to-rent with credit, construction and city-to-country price indicators, which this
  project does not have.
- **Monetary Authority of Singapore, Financial Stability Review 2025**, as reported in the
  press: the pace of private residential price increases was more measured in 2025 and
  household income growth kept pace with debt. Consistent with a price-to-income ratio
  close to its average.

Both assessments were read in press releases and press coverage, not in the full reports.

## What would make a verdict conclusive

- A Paris rent and income history at city level (the ratios above use national
  denominators), and a longer transaction history (DVF+ 2014–2025).
- A rent index for the HDB market before 2021.
- Deflated (real) price indices for the explosive-root tests.
- A structural estimate of the expected growth of rents g, which the grid only spans.
