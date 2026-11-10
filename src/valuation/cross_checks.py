"""Two cross-checks of sale prices, read together.

Check 1, rent side: the growth of rents that a sale price requires. For each sold home the
user-cost equation is solved for g instead of V*:

    freehold:   g* = r_f + tau + delta + gamma - R/P
    lease, T years left:  P/R = [1 - ((1+g)/(1+i))^T] / (i - g),   i = r_f + tau + delta + gamma

(the second is the lease formula of src/ratios/valuation.py, solved numerically). g* is the
nominal growth of rents, for ever or to the end of the lease, at which today's price equals
the capitalised rent. It is compared with what rents and incomes have actually done over
the long run; incomes are the ceiling, since rents cannot outgrow them indefinitely.
Because the risk premium gamma is unknown, g* is given for gamma = 1%, 2% (baseline), 4%:

    plausible              g* at gamma = 4% is at or below long-run income growth
    implausible            g* at gamma = 1% is above long-run income growth
    depends on the premium otherwise

Check 2, income side: the price a household can finance under the lending rules, with no
reference to rents:

    P_max = share x monthly income x annuity(rate, years) / (1 - down payment)

and the sale price is set against it (P / P_max). Rules and conventions are in RULES below;
the result is also given with the rate one point lower and higher.

    within capacity        P / P_max <= 1 at the three rates
    beyond capacity        P / P_max > 1 at the three rates
    depends on the rate    otherwise

The two checks share the interest rate, so they are not fully independent; they do use
different data (rents against incomes and credit rules). They are reported next to the
verdict table and are not anchors of the verdict rule.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import INTERIM, PROCESSED, RAW
from src.ratios.params import BASE

GAMMAS = {"lo": 0.01, "base": 0.02, "hi": 0.04}

# Lending rules. France: HCSF decision D-HCSF-2021-7, binding since 1 January 2022 (effort
# rate 35% incl. insurance, 25 years); no rule on the down payment, 20% is a convention.
# Singapore (MAS): mortgage servicing ratio 30% for HDB flats, total debt servicing ratio 55%
# otherwise, loan-to-value limit 75% for a first bank loan, repayment computed at a
# medium-term rate floor of 3.5%, then 4% from 30 September 2022 (applied here from 2023).
RULES = {
    "paris": {"share": 0.35, "years": 25, "down": 0.20, "rate": "market"},
    "singapore": {"share": 0.30, "years": 25, "down": 0.25, "rate": "floor"},
    "singapore_private": {"share": 0.55, "years": 30, "down": 0.25, "rate": "floor"},
}
CITY = {"paris": "Paris", "singapore": "Singapore", "singapore_private": "Singapore private"}
SPREAD_PROXY = 0.01  # mortgage rate = 10-year yield + 1 point when no mortgage series is available
ECB_MIR = ("https://data-api.ecb.europa.eu/service/data/MIR/M.FR.B.A2C.A.R.A.2250.EUR.N"
           "?startPeriod=2015-01&format=csvdata")


# ------------------------------------------------------------------ check 1
def implied_g(yield_, i, T=None, lo=-0.5, hi=0.5, iters=80):
    """Rent growth g at which price = capitalised rent. `yield_` = R/P, `i` = r_f + tau +
    delta + gamma, `T` = remaining lease in years (NaN or None = freehold). Vectorised."""
    y = np.asarray(yield_, dtype=float)
    i = np.broadcast_to(np.asarray(i, dtype=float), y.shape)
    g_free = i - y
    if T is None:
        return g_free
    T = np.broadcast_to(np.asarray(T, dtype=float), y.shape)

    def price_to_rent(g):  # increasing in g
        d = i - g
        near = np.abs(d) < 1e-9
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            v = (1 - ((1 + g) / (1 + i)) ** T) / np.where(near, 1.0, d)
        return np.where(near, T / (1 + i), v)

    a, b = np.full(y.shape, lo), np.full(y.shape, hi)
    target = 1 / y
    for _ in range(iters):
        mid = (a + b) / 2
        up = price_to_rent(mid) < target
        a, b = np.where(up, mid, a), np.where(up, b, mid)
    g = (a + b) / 2
    g = np.where(np.isnan(T), g_free, g)
    return np.where(np.isfinite(y) & (y > 0), g, np.nan)


def cagr(s: pd.Series, years: int) -> float:
    """Compound annual growth of an annual series over its last `years` years."""
    s = s.dropna()
    if len(s) <= years:
        return float("nan")
    return float((s.iloc[-1] / s.iloc[-1 - years]) ** (1 / years) - 1)


def read_check1(g_lo: float, g_hi: float, ceiling: float) -> str:
    if any(pd.isna(v) for v in (g_lo, g_hi, ceiling)):
        return "not run"
    return "plausible" if g_hi <= ceiling else "implausible" if g_lo > ceiling else "depends on the premium"


# ------------------------------------------------------------------ check 2
def annuity(rate: float, years: int) -> float:
    """Present value of 1 paid every month for `years` years at annual `rate`."""
    m, n = rate / 12, 12 * years
    return n if abs(m) < 1e-12 else (1 - (1 + m) ** -n) / m


def price_over_capacity(pti, rate: float, share: float, years: int, down: float):
    """P / P_max from the price-to-annual-income ratio `pti` (P_max as in the docstring)."""
    return np.asarray(pti, dtype=float) * 12 * (1 - down) / (share * annuity(rate, years))


def read_check2(lo: float, base: float, hi: float) -> str:
    if any(pd.isna(v) for v in (lo, base, hi)):
        return "not run"
    v = [lo, base, hi]
    return "within capacity" if max(v) <= 1 else "beyond capacity" if min(v) > 1 else "depends on the rate"


READING = {
    ("plausible", "within capacity"): "passes both checks",
    ("implausible", "beyond capacity"): "fails both checks",
    ("implausible", "within capacity"): "financeable, but the price needs more rent growth than history shows",
    ("plausible", "beyond capacity"): "rents support the price, local incomes cannot finance it",
}


def combine(c1: str, c2: str) -> str:
    if "not run" in (c1, c2):
        return "incomplete"
    return READING.get((c1, c2), "mixed: at least one check depends on an assumption")


# ---------------------------------------------------------------------- data
def _rf(city: str) -> pd.Series:
    r = pd.read_csv(INTERIM / ("rf_paris.csv" if city == "paris" else "rf_singapore.csv"))
    return (r.groupby(r["month"].str[:4].astype(int))["rate_pct"].mean() / 100).rename("rf")


def france_mortgage_rate() -> tuple[pd.Series | None, str]:
    """Annual mean rate on new loans to households for house purchase, France (ECB MIR
    statistics). Returns (None, reason) if the series cannot be read or is not the expected one."""
    from src.ingest.http import download
    try:
        f = download(ECB_MIR, RAW / "rates" / "ecb_mir_fr_house_purchase.csv",
                     note="ECB MIR: new loans to households for house purchase, France")
        d = pd.read_csv(f)
        title = " ".join(str(d[c].iloc[0]) for c in d.columns if "TITLE" in c.upper())
        if "house purchase" not in title.lower():
            return None, f"unexpected ECB series title: {title[:120]!r}"
        s = d.groupby(d["TIME_PERIOD"].str[:4].astype(int))["OBS_VALUE"].mean() / 100
        return s, f"ECB MIR ({title[:90]})"
    except Exception as e:  # noqa: BLE001
        return None, f"ECB MIR series not available ({str(e)[:100]})"


def _benchmarks(city: str) -> dict:
    """Long-run nominal growth of rents and incomes, per year, over the last 20 years."""
    from src.ingest.official_indices import OUT, load_oecd_france, load_quarterly
    from src.valuation.run import _annual, singapore_income
    out = {"rent_growth": float("nan"), "income_growth": float("nan"), "bench_note": ""}
    try:
        if city == "paris":
            o = load_oecd_france()
            out["rent_growth"] = cagr(_annual(o["RPI"].dropna()), 20)
            out["income_growth"] = cagr(_annual((o["HPI"] / o["HPI_YDH"]).dropna()), 20)
            out["bench_note"] = "France: national rent index and disposable income per head (OECD), last 20 years"
        else:
            out["income_growth"] = cagr(singapore_income(), 20)
            out["bench_note"] = "Singapore: national median household income from work, last 20 years"
            if city == "singapore_private":
                out["rent_growth"] = cagr(_annual(load_quarterly(OUT / "ura_private_residential_rental_index.csv")), 20)
                out["bench_note"] += "; URA rental index, non-landed"
    except Exception as e:  # noqa: BLE001
        out["bench_note"] = f"benchmarks not available ({str(e)[:100]})"
    return out


def city_table(city: str, t: pd.DataFrame, rf: pd.Series, bench: dict,
               mortgage: pd.Series | None = None, mortgage_note: str = "") -> pd.DataFrame:
    """One row per year for one market. `t`: sales with year, gross_yield, pti_hh and, for
    leasehold markets, lease_remaining_years."""
    p, rule = BASE[CITY[city]], RULES[city]
    ceiling = bench["income_growth"]
    T = t["lease_remaining_years"].to_numpy(dtype=float) if city != "paris" and "lease_remaining_years" in t else None
    rows = []
    for year, s in t.groupby("year"):
        if year not in rf.index:
            continue
        idx = s.index
        g = {k: float(np.nanmedian(implied_g(s["gross_yield"].to_numpy(), rf[year] + p["tau"] + p["delta"] + gm,
                                             None if T is None else T[t.index.get_indexer(idx)])))
             if s["gross_yield"].notna().any() else float("nan") for k, gm in GAMMAS.items()}
        if rule["rate"] == "floor":
            rate, rate_note = (0.035 if year <= 2022 else 0.04), "MAS medium-term rate floor"
        elif mortgage is not None and year in mortgage.index:
            rate, rate_note = float(mortgage[year]), mortgage_note
        else:
            rate, rate_note = float(rf[year] + SPREAD_PROXY), f"10-year yield + 1 point ({mortgage_note or 'no mortgage series'})"
        pti = s["pti_hh"].median()
        cap = {k: float(price_over_capacity(pti, rate + d, rule["share"], rule["years"], rule["down"]))
               for k, d in (("lo", -0.01), ("base", 0.0), ("hi", 0.01))}
        c1, c2 = read_check1(g["lo"], g["hi"], ceiling), read_check2(cap["lo"], cap["base"], cap["hi"])
        rows.append({"city": city, "year": int(year), "n": len(s), "rf": float(rf[year]),
                     "gross_yield_median": float(s["gross_yield"].median()),
                     "g_star_gamma1": g["lo"], "g_star_gamma2": g["base"], "g_star_gamma4": g["hi"],
                     "rent_growth_20y": bench["rent_growth"], "income_growth_20y": ceiling, "check1": c1,
                     "pti_median": float(pti), "mortgage_rate": rate, "mortgage_rate_source": rate_note,
                     "price_over_capacity_rate_minus1": cap["lo"], "price_over_capacity": cap["base"],
                     "price_over_capacity_rate_plus1": cap["hi"], "check2": c2, "reading": combine(c1, c2),
                     "benchmarks": bench["bench_note"]})
    return pd.DataFrame(rows)


def run() -> pd.DataFrame:
    mortgage, note = france_mortgage_rate()
    out = []
    for city in RULES:
        f = INTERIM / f"ratios_input_{city}.parquet"
        if not f.exists():
            print(city, "skipped: ratios_input file not built")
            continue
        t = pd.read_parquet(f)
        out.append(city_table(city, t, _rf(city), _benchmarks(city), mortgage if city == "paris" else None,
                              note if city == "paris" else ""))
    res = pd.concat(out, ignore_index=True)
    res.to_csv(PROCESSED / "cross_checks.csv", index=False)
    print(res[["city", "year", "g_star_gamma2", "income_growth_20y", "check1", "price_over_capacity", "check2"]]
          .round(3).to_string(index=False))
    return res


if __name__ == "__main__":
    run()
