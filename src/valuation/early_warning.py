"""What did valuation ratios look like before past housing busts, and where are Paris and
Singapore against that record?

1. Panel: OECD analytical house price indicators, all countries, quarterly: real house
   prices, price-to-income and price-to-rent (the dataflow already used for France).
2. Busts: a fall of real house prices of at least 15% from a peak, before the peak is
   regained (`drawdowns`). Two narrower definitions are evaluated next to it (DEFINITIONS):
   "crash", where nominal prices fell by at least 10% as well, which leaves out the erosion
   of real prices by inflation; and "major", a real fall of at least 25%.
3. Signal: for each country and quarter, the z-score of the log ratio against its own past
   only (expanding window, at least 10 years). Using only data known at the time avoids
   judging the past with hindsight.
4. Evaluation (signalling approach): a quarter is "pre-bust" if a bust peak falls within the
   next 12 quarters; quarters inside a bust are left out. For each threshold: share of
   pre-bust quarters flagged (hit rate), share of other quarters flagged (false-alarm rate),
   share of busts flagged at least once before their peak, and share of flagged quarters
   that were pre-bust (precision). The threshold retained maximises hit rate minus
   false-alarm rate.
5. Today: the same z-score for Paris and Singapore, set against the calibrated threshold.
6. City record: every fall of at least 10% of the three official indices (nominal), with
   its depth and length, the time to regain the peak, and the ratios at the peak.

Limits: few busts; countries, not cities, in the calibration; Singapore is not in the OECD
panel; a threshold calibrated on z-scores says how unusual a ratio is, not what it should be.
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd

from src.config import PROCESSED, RAW

OUT = RAW / "official"
PANEL_URL = ("https://sdmx.oecd.org/public/rest/data/OECD.ECO.MPD,DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES,/"
             ".Q.RHP+HPI+HPI_YDH+HPI_RPI.?format=csvfile")
RATIOS = {"HPI_YDH": "price_to_income", "HPI_RPI": "price_to_rent"}
BUST_DROP, CITY_DROP, HORIZON, MIN_OBS = 0.15, 0.10, 12, 40
THRESHOLDS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]


def drawdowns(s: pd.Series, min_drop: float) -> list[dict]:
    """Falls of at least `min_drop` from a peak, before the peak is regained. `s`: positive
    series in time order. Each episode: peak, trough, recovered (label or None), drop (< 0),
    and positions i_peak, i_trough."""
    v, idx = s.to_numpy(dtype=float), list(s.index)
    out, ip, it = [], 0, 0
    for k in range(1, len(v)):
        if v[k] >= v[ip]:
            if v[it] / v[ip] - 1 <= -min_drop:
                out.append({"peak": idx[ip], "trough": idx[it], "recovered": idx[k], "drop": v[it] / v[ip] - 1,
                            "i_peak": ip, "i_trough": it})
            ip = it = k
        elif v[k] < v[it]:
            it = k
    if v[it] / v[ip] - 1 <= -min_drop:
        out.append({"peak": idx[ip], "trough": idx[it], "recovered": None, "drop": v[it] / v[ip] - 1,
                    "i_peak": ip, "i_trough": it})
    return out


def expanding_z(x: pd.Series, min_obs: int = MIN_OBS) -> pd.Series:
    """z-score of log(x) against its own past (expanding mean and standard deviation)."""
    lx = np.log(x.astype(float))
    e = lx.expanding(min_periods=min_obs)
    return (lx - e.mean()) / e.std(ddof=1)


def label_quarters(n: int, busts: list[dict], horizon: int = HORIZON, excluded: list[dict] | None = None) -> np.ndarray:
    """1 = pre-bust (a peak within the next `horizon` quarters, peak included), 0 = other,
    -1 = left out: inside a bust (after the peak, up to the trough), or around an `excluded`
    bust (one that does not meet the definition under study: neither a hit nor a false alarm)."""
    lab = np.zeros(n, dtype=int)
    for b in busts:
        lab[max(b["i_peak"] - horizon, 0):b["i_peak"] + 1] = 1
    for b in busts:
        lab[b["i_peak"] + 1:b["i_trough"] + 1] = -1
    for b in excluded or []:
        lab[max(b["i_peak"] - horizon, 0):b["i_trough"] + 1] = -1
    return lab


# Definitions of a bust. All start from a fall of real prices of at least 15%.
#   all      every such fall (includes the erosion of real prices by inflation, common before 1990)
#   crash    housing crises proper: nominal prices also fell by at least 10% between peak and trough
#   major    real fall of at least 25%
DEFINITIONS = {"all": "real fall of at least 15%",
               "crash": "real fall of at least 15% and nominal fall of at least 10%",
               "major": "real fall of at least 25%"}
NOMINAL_DROP, MAJOR_DROP = 0.10, 0.25


def qualifies(b: dict, definition: str) -> bool:
    if definition == "crash":
        return b.get("nominal_drop", np.nan) <= -NOMINAL_DROP
    if definition == "major":
        return b["drop"] <= -MAJOR_DROP
    return True


def country_busts(d: pd.DataFrame) -> list[dict]:
    """Busts of one country on real prices, with the fall of nominal prices over the same
    peak-to-trough window (largest fall from the nominal value at the real peak)."""
    busts = drawdowns(d["RHP"], BUST_DROP)
    for b in busts:
        if "HPI" in d and d["HPI"].notna().any():
            w = d["HPI"].iloc[b["i_peak"]:b["i_trough"] + 1].dropna()
            b["nominal_drop"] = float(w.min() / w.iloc[0] - 1) if len(w) else np.nan
        else:
            b["nominal_drop"] = np.nan
    return busts


def evaluate(panel: dict[str, pd.DataFrame], ratio: str, definition: str = "all") -> tuple[pd.DataFrame, pd.DataFrame]:
    """`panel`: country -> DataFrame (quarters in order) with RHP, the ratio and, for the
    "crash" definition, HPI. Returns (threshold table, table of the busts that meet
    `definition`, with the z-score at and before each peak)."""
    zs, labs, bust_rows = [], [], []
    for c, d in panel.items():
        d = d.dropna(subset=["RHP"])
        if ratio not in d or d[ratio].notna().sum() < MIN_OBS + 8:
            continue
        z = expanding_z(d[ratio]).to_numpy()
        every = country_busts(d)
        busts = [b for b in every if qualifies(b, definition)]
        lab = label_quarters(len(d), busts, excluded=[b for b in every if not qualifies(b, definition)])
        zs.append(z)
        labs.append(lab)
        for b in busts:
            w = z[max(b["i_peak"] - HORIZON, 0):b["i_peak"] + 1]
            bust_rows.append({"country": c, "peak": b["peak"], "trough": b["trough"], "real_drop_pct": 100 * b["drop"],
                              "nominal_drop_pct": 100 * b["nominal_drop"],
                              "quarters_to_trough": b["i_trough"] - b["i_peak"],
                              "z_at_peak": z[b["i_peak"]], "z_max_before_peak": np.nanmax(w) if np.isfinite(w).any() else np.nan})
    if not zs:
        raise RuntimeError(f"no country has enough {ratio} history: panel of {len(panel)} areas")
    z, lab = np.concatenate(zs), np.concatenate(labs)
    ok = np.isfinite(z) & (lab >= 0)
    busts = pd.DataFrame(bust_rows)
    scored = busts.dropna(subset=["z_max_before_peak"]) if len(busts) else busts
    rows = []
    for th in THRESHOLDS:
        flag = z > th
        pre, other = ok & (lab == 1), ok & (lab == 0)
        hit = flag[pre].mean() if pre.any() else np.nan
        fa = flag[other].mean() if other.any() else np.nan
        rows.append({"definition": definition, "ratio": RATIOS.get(ratio, ratio), "threshold_z": th, "hit_rate": hit,
                     "false_alarm_rate": fa, "hit_minus_false_alarm": hit - fa,
                     "busts_flagged_share": float((scored["z_max_before_peak"] > th).mean()) if len(scored) else np.nan,
                     "precision": flag[pre].sum() / max(flag[ok].sum(), 1),
                     "n_pre_bust_quarters": int(pre.sum()), "n_other_quarters": int(other.sum()), "n_busts": len(scored)})
    if len(busts):
        busts.insert(1, "ratio", RATIOS.get(ratio, ratio))
        busts.insert(0, "definition", definition)
    return pd.DataFrame(rows), busts


def best_threshold(table: pd.DataFrame) -> float:
    return float(table.loc[table["hit_minus_false_alarm"].idxmax(), "threshold_z"])


# ------------------------------------------------------------------------ data
def load_panel(force: bool = False) -> dict[str, pd.DataFrame]:
    from src.ingest.http import fetch_bytes, record
    from src.ingest.official_indices import to_quarter
    dest = OUT / "oecd_house_prices_panel.csv"
    if force or not dest.exists():
        d = pd.read_csv(io.BytesIO(fetch_bytes(PANEL_URL, retries=4)))
        d = d[d["TIME_PERIOD"].astype(str).str.match(r"^\d{4}-Q[1-4]$")][["REF_AREA", "MEASURE", "TIME_PERIOD", "OBS_VALUE"]]
        OUT.mkdir(parents=True, exist_ok=True)
        d.to_csv(dest, index=False)
        record(dest, PANEL_URL, f"OECD analytical house price indicators, all areas, quarterly; {d['REF_AREA'].nunique()} areas")
    d = pd.read_csv(dest)
    d = d[d["REF_AREA"].str.fullmatch(r"[A-Z]{3}")]  # ISO country codes only: drops aggregates (OECD, EA...)
    d["period"] = d["TIME_PERIOD"].map(to_quarter)
    w = d.pivot_table(index=["REF_AREA", "period"], columns="MEASURE", values="OBS_VALUE", aggfunc="first")
    return {c: g.droplevel(0).sort_index() for c, g in w.groupby(level=0)}


def city_series() -> dict[str, dict]:
    """Official price index of each market and the ratio series available for it."""
    from src.ingest.official_indices import load_quarterly
    from src.valuation.run import _annual, france_denominators, singapore_income
    out = {}
    try:
        paris = load_quarterly(OUT / "notaires_insee_paris_apartments.csv")
        inc, rent = france_denominators()
        out["paris"] = {"price": paris, "price_to_income": (paris / inc).dropna(), "price_to_rent": (paris / rent).dropna()}
    except Exception as e:  # noqa: BLE001
        print("paris series not available:", e)
    try:
        sg_inc = singapore_income()
        hdb = load_quarterly(OUT / "hdb_resale_price_index.csv")
        out["singapore"] = {"price": hdb, "price_to_income": (_annual(hdb) / sg_inc).dropna()}
        ura = load_quarterly(OUT / "ura_private_residential_price_index.csv")
        urr = load_quarterly(OUT / "ura_private_residential_rental_index.csv")
        out["singapore_private"] = {"price": ura, "price_to_income": (_annual(ura) / sg_inc).dropna(),
                                    "price_to_rent": (ura / urr).dropna()}
    except Exception as e:  # noqa: BLE001
        print("singapore series not available:", e)
    return out


def _z_for(series: pd.Series) -> pd.Series:
    annual = not str(series.index[0]).endswith(("Q1", "Q2", "Q3", "Q4"))
    return expanding_z(series, 10 if annual else MIN_OBS)


def _z_at(z: pd.Series, period: str) -> float:
    key = int(period[:4]) if not str(z.index[0]).endswith(("Q1", "Q2", "Q3", "Q4")) else period
    return float(z.get(key, np.nan))


def run() -> None:
    panel = load_panel()
    tables, busts, best = [], [], {}
    for definition in DEFINITIONS:
        for ratio in RATIOS:
            t, b = evaluate(panel, ratio, definition)
            tables.append(t)
            busts.append(b)
            best[(definition, RATIOS[ratio])] = best_threshold(t)
    thresholds = pd.concat(tables, ignore_index=True)
    thresholds["retained"] = thresholds.apply(lambda r: r["threshold_z"] == best[(r["definition"], r["ratio"])], axis=1)
    thresholds.to_csv(PROCESSED / "early_warning_thresholds.csv", index=False)
    pd.concat(busts, ignore_index=True).to_csv(PROCESSED / "early_warning_busts.csv", index=False)

    cities = city_series()
    today, record_rows = [], []
    for city, s in cities.items():
        zs = {k: _z_for(v) for k, v in s.items() if k != "price"}
        for k, z in zs.items():
            zz = z.dropna()
            if zz.empty:
                continue
            th = best[("all", k)]
            above = zz[zz > th]
            today.append({"city": city, "ratio": k, "last_period": zz.index[-1], "z_last": float(zz.iloc[-1]),
                          "threshold_z": th, "above_threshold": bool(zz.iloc[-1] > th),
                          "threshold_z_crash": best[("crash", k)], "threshold_z_major": best[("major", k)],
                          "z_max": float(zz.max()), "period_of_z_max": zz.idxmax(),
                          "last_period_above": above.index[-1] if len(above) else None,
                          "share_of_periods_above": float((zz > th).mean()), "n": len(zz)})
        for b in drawdowns(s["price"], CITY_DROP):
            row = {"city": city, "peak": b["peak"], "trough": b["trough"], "nominal_drop_pct": 100 * b["drop"],
                   "quarters_to_trough": b["i_trough"] - b["i_peak"], "recovered": b["recovered"],
                   "quarters_peak_to_recovery": (list(s["price"].index).index(b["recovered"]) - b["i_peak"])
                   if b["recovered"] is not None else np.nan}
            for k, z in zs.items():
                row[f"z_{k}_at_peak"] = _z_at(z, b["peak"])
            record_rows.append(row)
    # the series themselves (indices and ratios of indices: aggregates, no transaction data), for the charts
    series = [pd.DataFrame({"city": city, "series": k, "period": [str(p) for p in v.index], "value": v.to_numpy()})
              for city, s in cities.items() for k, v in s.items()]
    if series:
        pd.concat(series, ignore_index=True).round(6).to_csv(PROCESSED / "ratio_series.csv", index=False)
    pd.DataFrame(today).to_csv(PROCESSED / "early_warning_today.csv", index=False)
    pd.DataFrame(record_rows).to_csv(PROCESSED / "city_drawdowns.csv", index=False)
    pd.set_option("display.width", 250)
    print(thresholds.round(3).to_string(index=False))
    print(pd.DataFrame(today).round(2).to_string(index=False))
    print(pd.DataFrame(record_rows).round(2).to_string(index=False))


if __name__ == "__main__":
    run()
