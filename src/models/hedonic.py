"""Hedonic models of log price/m² (and log monthly rent for Singapore HDB).

Models: OLS with district fixed effects (HC1 robust SEs), Random Forest, LightGBM.
Validation:
- spatial block CV: H3 resolution-8 cells (~0.7 km²) are the blocks, assigned to 5 folds
  with GroupKFold, so test dwellings never share a cell with training dwellings;
- time split: train on all years before the latest one, test on the latest year. Year
  effects cannot be estimated for an unseen year, so the OLS uses the last training
  year's effect (a random-walk nowcast) and the tree models see a numeric month index.
Errors are reported on price/m² (not logs), after Duan smearing of the log predictions.
Out-of-fold predictions from the spatial CV are kept: they feed the relative-mispricing
residuals and the valuation gap, so no dwelling is valued by a model that saw it.
"""
from __future__ import annotations

import json
import platform
from importlib.metadata import version

import h3
import lightgbm as lgb
import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GroupKFold

from src.config import INTERIM, PROCESSED, SEED, TABLES

SPEC = {
    "paris": {
        "file": "ratios_input_paris.parquet", "target": "price_per_m2_local", "fe": "district_l2",
        "num": ["log_area", "log_dist_rail", "log_dist_cbd", "log_dist_park", "has_dependance",
                "building_floors", "build_year"],
        "cat": ["rooms_capped", "epoque"],
    },
    "singapore": {
        "file": "ratios_input_singapore.parquet", "target": "price_per_m2_local", "fe": "district_l2",
        "num": ["log_area", "log_dist_rail", "log_dist_cbd", "log_dist_park", "storey_mid",
                "lease_remaining_years", "block_max_floor"],
        "cat": ["rooms_or_flat_type", "flat_model"],
    },
    "singapore_rent": {
        "file": "features_singapore_rent.parquet", "target": "monthly_rent", "fe": "subzone",
        "num": ["log_dist_rail", "log_dist_cbd", "log_dist_park"],
        "cat": ["flat_type"],
    },
}


def prepare(name: str) -> pd.DataFrame:
    s = SPEC[name]
    d = pd.read_parquet(INTERIM / s["file"])
    if "floor_area_m2" in d:
        d["log_area"] = np.log(d["floor_area_m2"])
    for v in ("rail", "cbd", "park"):
        d[f"log_dist_{v}"] = np.log1p(d[f"dist_{v}_m"])
    d["y"] = np.log(d[s["target"]])
    d["t_month"] = (d["date"].dt.year - d["date"].dt.year.min()) * 12 + d["date"].dt.month
    d["cell8"] = [h3.latlng_to_cell(a, b, 8) for a, b in zip(d["lat"], d["lon"])]
    d = d.dropna(subset=["y", "lat", "lon"]).reset_index(drop=True)
    return d


def _design(d: pd.DataFrame, s: dict, cols: list[str] | None, year_map: dict | None = None):
    X = d[s["num"]].astype(float).copy()
    # missing numeric values: indicator + median-free zero fill (documented, not silent)
    for c in s["num"]:
        if X[c].isna().any():
            X[c + "_missing"] = X[c].isna().astype(float)
            X[c] = X[c].fillna(0.0)
    yr = d["year"].map(year_map) if year_map else d["year"]
    dummies = pd.get_dummies(
        pd.concat([d[s["cat"]].astype(str), d[[s["fe"]]].astype(str), yr.astype(str).rename("yr")], axis=1),
        drop_first=False, dtype=float)
    X = pd.concat([X, dummies], axis=1)
    if cols is None:
        # drop one level per categorical block to avoid perfect collinearity with the constant
        drop = [next(c for c in dummies.columns if c.startswith(p + "_")) for p in s["cat"] + [s["fe"], "yr"]]
        X = X.drop(columns=drop)
        cols = list(X.columns)
    X = X.reindex(columns=cols, fill_value=0.0)
    return sm.add_constant(X, has_constant="add"), cols


def _tree_X(d: pd.DataFrame, s: dict) -> pd.DataFrame:
    X = d[s["num"] + ["t_month", "lat", "lon"]].astype(float).copy()
    for c in s["cat"] + [s["fe"]]:
        X[c] = d[c].astype("category")
    return X


def _smear(y_tr, p_tr):
    return float(np.mean(np.exp(y_tr - p_tr)))


def _metrics(y_true_log, p_log, smear):
    yt, yp = np.exp(y_true_log), np.exp(p_log) * smear
    e = yp - yt
    return {"RMSE": float(np.sqrt(np.mean(e ** 2))), "MAE": float(np.mean(np.abs(e))),
            "MAPE_pct": float(100 * np.mean(np.abs(e) / yt)), "n_test": int(len(yt))}


def fit_predict(model: str, tr: pd.DataFrame, te: pd.DataFrame, s: dict, year_map=None):
    if model == "OLS":
        Xtr, cols = _design(tr, s, None)
        Xte, _ = _design(te, s, cols, year_map)
        res = sm.OLS(tr["y"].to_numpy(), Xtr).fit(cov_type="HC1")
        return res.predict(Xtr), res.predict(Xte), res
    Xtr, Xte = _tree_X(tr, s), _tree_X(te, s)
    if model == "RandomForest":
        Xtr2 = pd.get_dummies(Xtr, dtype=float)
        Xte2 = pd.get_dummies(Xte, dtype=float).reindex(columns=Xtr2.columns, fill_value=0.0)
        m = RandomForestRegressor(n_estimators=200, min_samples_leaf=5, max_features=0.4, max_samples=0.5,
                                  n_jobs=-1, random_state=SEED)
        m.fit(Xtr2.fillna(-1), tr["y"])
        return m.predict(Xtr2.fillna(-1)), m.predict(Xte2.fillna(-1)), m
    m = lgb.LGBMRegressor(n_estimators=1500, learning_rate=0.03, num_leaves=63, min_child_samples=20,
                          subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=SEED, verbose=-1)
    for c in Xte.select_dtypes("category"):
        Xte[c] = pd.Categorical(Xte[c], categories=Xtr[c].cat.categories)
    m.fit(Xtr, tr["y"])
    return m.predict(Xtr), m.predict(Xte), m


MODELS = ["OLS", "RandomForest", "LightGBM"]


def evaluate(name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    s = SPEC[name]
    d = prepare(name)
    rows = []
    oof = pd.DataFrame(index=d.index)
    folds = GroupKFold(n_splits=5).split(d, groups=d["cell8"])
    for k, (i_tr, i_te) in enumerate(folds):
        tr, te = d.iloc[i_tr], d.iloc[i_te]
        for m in MODELS:
            p_tr, p_te, _ = fit_predict(m, tr, te, s)
            sm_ = _smear(tr["y"].to_numpy(), np.asarray(p_tr))
            oof.loc[te.index, m] = np.asarray(p_te) + np.log(sm_)
            rows.append({"dataset": name, "validation": "spatial_block_cv", "fold": k, "model": m,
                         **_metrics(te["y"].to_numpy(), np.asarray(p_te), sm_)})
    last = int(d["year"].max())
    tr, te = d[d["year"] < last], d[d["year"] == last]
    ymap = {y: y for y in tr["year"].unique()} | {last: last - 1}
    for m in MODELS:
        p_tr, p_te, _ = fit_predict(m, tr, te, s, ymap)
        sm_ = _smear(tr["y"].to_numpy(), np.asarray(p_tr))
        rows.append({"dataset": name, "validation": f"time_split_test_{last}", "fold": 0, "model": m,
                     **_metrics(te["y"].to_numpy(), np.asarray(p_te), sm_)})
    res = pd.DataFrame(rows)
    summary = (res.groupby(["dataset", "validation", "model"])[["RMSE", "MAE", "MAPE_pct", "n_test"]]
               .agg({"RMSE": "mean", "MAE": "mean", "MAPE_pct": "mean", "n_test": "sum"}).reset_index())
    summary.to_csv(TABLES / f"model_comparison_{name}.csv", index=False)
    summary.to_csv(PROCESSED / f"model_comparison_{name}.csv", index=False)
    d = d.join(oof.add_prefix("oof_log_"))
    d.to_parquet(INTERIM / f"oof_{name}.parquet", index=False)
    print(summary.to_string(index=False))
    return summary, d


def ols_full(name: str) -> pd.DataFrame:
    """Full-sample OLS: coefficients (HC1 and cluster-robust by district) and Moran's I."""
    from esda.moran import Moran
    from libpysal.weights import KNN

    s = SPEC[name]
    d = prepare(name)
    X, cols = _design(d, s, None)
    res = sm.OLS(d["y"].to_numpy(), X).fit(cov_type="HC1")
    resc = sm.OLS(d["y"].to_numpy(), X).fit(cov_type="cluster", cov_kwds={"groups": d[s["fe"]].astype("category").cat.codes})
    keep = [c for c in cols if not any(c.startswith(p + "_") for p in (s["fe"], "yr"))] + ["const"]
    coef = pd.DataFrame({"coef": res.params, "se_hc1": res.bse, "p_hc1": res.pvalues,
                         "se_cluster_district": resc.bse}).loc[lambda x: x.index.isin(keep)]
    coef["r2"], coef["n"] = res.rsquared, int(res.nobs)
    rng = np.random.default_rng(SEED)
    idx = rng.choice(len(d), size=min(20000, len(d)), replace=False)
    pts = np.c_[d["lon"].to_numpy()[idx], d["lat"].to_numpy()[idx]]
    w = KNN.from_array(pts, k=10)
    w.transform = "r"
    mi = Moran(np.asarray(res.resid)[idx], w, permutations=199)
    coef["morans_I_resid"], coef["morans_p_sim"] = mi.I, mi.p_sim
    coef.to_csv(TABLES / f"ols_coefficients_{name}.csv")
    coef.to_csv(PROCESSED / f"ols_coefficients_{name}.csv")
    print(name, "R2", round(res.rsquared, 3), "Moran I", round(mi.I, 3), "p", mi.p_sim)
    return coef


def shap_outputs(name: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import shap

    from src.config import FIGURES

    s = SPEC[name]
    d = prepare(name)
    _, _, m = fit_predict("LightGBM", d, d.iloc[:10], s)
    X = _tree_X(d, s)
    Xs = X.sample(n=min(5000, len(X)), random_state=SEED)
    sv = shap.TreeExplainer(m).shap_values(Xs)
    plt.figure()
    shap.summary_plot(sv, Xs, show=False, max_display=15)
    plt.tight_layout()
    plt.savefig(FIGURES / f"shap_summary_{name}.png", dpi=150)
    plt.close("all")
    for f in [c for c in ("log_dist_rail", "log_dist_cbd", "storey_mid", "lease_remaining_years", "build_year") if c in Xs]:
        shap.dependence_plot(f, sv, Xs, show=False, interaction_index=None)
        plt.tight_layout()
        plt.savefig(FIGURES / f"shap_dependence_{name}_{f}.png", dpi=150)
        plt.close("all")
    imp = pd.Series(np.abs(sv).mean(0), index=Xs.columns).sort_values(ascending=False)
    imp.rename("mean_abs_shap").to_csv(TABLES / f"shap_importance_{name}.csv")


def rent_on_sales() -> pd.DataFrame:
    """Predict the monthly HDB rent of each SOLD flat with the rent model (LightGBM fitted on
    all rental approvals). Sales are not in the rent training data, so this is out of sample."""
    s = SPEC["singapore_rent"]
    rent = prepare("singapore_rent")
    sales = prepare("singapore")
    sales["flat_type"] = sales["rooms_or_flat_type"]
    sales["subzone"] = sales["district_l2"]
    # Time index on the rent data's own origin, so both share the same month numbering.
    origin = rent["date"].dt.year.min()
    for d in (rent, sales):
        d["t_month"] = (d["date"].dt.year - origin) * 12 + d["date"].dt.month
    _, _, m = fit_predict("LightGBM", rent, rent.iloc[:10], s)
    smear = _smear(rent["y"].to_numpy(), m.predict(_tree_X(rent, s)))
    Xs = _tree_X(sales, s)
    Xr = _tree_X(rent, s)
    for c in Xs.select_dtypes("category"):
        Xs[c] = pd.Categorical(Xs[c].astype(str), categories=Xr[c].cat.categories)
    out = pd.DataFrame({"source_id": sales["source_id"],
                        "pred_rent_month": np.exp(m.predict(Xs)) * smear})
    # Rent data start in 2021: sales before 2021 get the model's 2021 level (flagged).
    out["rent_extrapolated_before_2021"] = (sales["year"] < origin).to_numpy()
    out.to_parquet(INTERIM / "rent_model_on_sales_singapore.parquet", index=False)
    return out


def versions() -> None:
    pk = ["pandas", "numpy", "geopandas", "statsmodels", "scikit-learn", "lightgbm", "shap", "h3", "esda", "libpysal"]
    info = {"python": platform.python_version(), "seed": SEED} | {p: version(p) for p in pk}
    (PROCESSED / "package_versions.json").write_text(json.dumps(info, indent=2))


def main() -> None:
    versions()
    for name in SPEC:
        evaluate(name)
        ols_full(name)
        shap_outputs(name)
    rent_on_sales()


if __name__ == "__main__":
    main()
