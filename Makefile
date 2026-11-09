PY ?= python3

.PHONY: data clean features models ratios site test all

## Download every raw source into data/raw (git-ignored) and record it in data/raw/MANIFEST.csv
data:
	$(PY) -m src.ingest.fx
	$(PY) -m src.ingest.rates
	$(PY) -m src.ingest.paris
	$(PY) -m src.ingest.singapore
	$(PY) -m src.ingest.onemap
	$(PY) -m src.ingest.ura          # needs a URA access key (see README)
	$(PY) -m src.ingest.ura_geocode
	$(PY) -c "from src.ingest.ura import developer_sales; developer_sales()"

## Clean + harmonise transactions, then build features
features:
	$(PY) -m src.clean.paris
	$(PY) -m src.clean.singapore
	$(PY) -m src.clean.singapore_private
	$(PY) -m src.features.build
	$(PY) -c "from src.features.build import singapore_private_features as f; f()"
	$(PY) -m src.ratios.levels
	$(PY) -m src.ratios.liquidity

## Hedonic / ML models, validation tables, SHAP, then fundamental values and gaps
models: features
	$(PY) -m src.models.hedonic
	$(PY) -m src.ratios.valuation

## Static website data and pages (site/)
site:
	$(PY) -m src.viz.export
	$(PY) -m src.viz.pages

test:
	$(PY) -m pytest -q tests

all: data models site test
