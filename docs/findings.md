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
