#!/usr/bin/env bash
# Rebuild the public-data part of the pipeline on a machine with open internet access
# (GitHub Actions runner). Raw and transaction-level files stay on the runner; only
# aggregates in data/processed and the download manifest are committed by the workflow.
# Every step is attempted, including after a failure; its exit status and, on failure, the end of its output are
# written to data/processed/build_report.txt.
set -u
REPORT=data/processed/build_report.txt
mkdir -p logs
{ echo "build started $(date -u +%Y-%m-%dT%H:%M:%SZ)"; python --version; } > "$REPORT"

step() {  # step <name> <command...>
  local name="$1"; shift
  local log="logs/${name}.log" t0=$SECONDS
  if "$@" > "$log" 2>&1; then
    echo "OK    ${name} ($((SECONDS - t0))s)" >> "$REPORT"
  else
    echo "FAIL  ${name} ($((SECONDS - t0))s)" >> "$REPORT"
    tail -n 12 "$log" | cut -c1-400 | sed 's/^/        /' >> "$REPORT"
  fi
}

step ingest_fx        python -m src.ingest.fx
step ingest_rates     python -m src.ingest.rates
step ingest_paris     python -m src.ingest.paris
step ingest_singapore python -m src.ingest.singapore
step ingest_onemap    python -m src.ingest.onemap
step ingest_official  python -m src.ingest.official_indices
step ingest_volumes   python -m src.ingest.volumes
echo "URA access key provided to the build: $([ -n "${URA_ACCESS_KEY:-}" ] && echo yes || echo no)" >> "$REPORT"
if [ -n "${URA_ACCESS_KEY:-}" ]; then
  step ingest_ura         python -m src.ingest.ura
  step ingest_ura_geocode python -m src.ingest.ura_geocode
  step ingest_ura_dev     python -c "from src.ingest.ura import developer_sales; developer_sales()"
else
  echo "SKIP  ura (no URA_ACCESS_KEY secret): Singapore private market not rebuilt" >> "$REPORT"
fi

step clean_paris      python -m src.clean.paris
step clean_singapore  python -m src.clean.singapore
if [ -n "${URA_ACCESS_KEY:-}" ]; then
  step clean_private    python -m src.clean.singapore_private
fi
step features_paris     python -c "from src.features.build import paris_features as f; f()"
step features_singapore python -c "from src.features.build import singapore_features as f; f()"
if [ -n "${URA_ACCESS_KEY:-}" ]; then
  step features_private python -c "from src.features.build import singapore_private_features as f; f()"
fi
step levels           python -m src.ratios.levels
step robust           python -m src.ratios.robust
step indices          python -m src.indices.run
step verdict          python -m src.valuation.run
step cross_checks     python -m src.valuation.cross_checks
step early_warning    python -m src.valuation.early_warning
step volumes          python -m src.valuation.volumes
step tests            python -m pytest -q tests

# Probes for two open questions of the data audit (results are only printed, nothing is used).
{ echo "--- probe: files of DVF+ open-data on data.gouv.fr";
  python - <<'PY'
from src.ingest.http import fetch_json
try:
    d = fetch_json("https://www.data.gouv.fr/api/1/datasets/dvf-open-data/", retries=3)
    print("licence:", d.get("license"), "| temporal:", d.get("temporal_coverage"))
    for r in d.get("resources", []):
        print(" ", r.get("title"), "|", r.get("format"), "|", r.get("filesize"), "|", r.get("url"))
except Exception as e:
    print("probe failed:", e)
PY
} >> "$REPORT" 2>&1

{ echo "--- index metadata"; cat data/processed/index_meta_*.json 2>/dev/null | tr -d '\n' | cut -c1-3000; echo;
  echo "--- official index series"; tail -n 4 logs/ingest_official.log | cut -c1-600; } >> "$REPORT"

{ echo "--- volumes"; tail -n 14 logs/ingest_volumes.log 2>/dev/null | cut -c1-500; tail -n 8 logs/volumes.log 2>/dev/null | cut -c1-900; } >> "$REPORT"

{ echo "--- raw files"; find data/raw -type f -not -name '*.pdf' -printf '%s %P\n' | sort -k2 | head -80;
  echo "--- official index headers"; for f in data/raw/official/*.csv; do [ -f "$f" ] && { echo "$f"; head -n 3 "$f" | cut -c1-300; cut -d, -f2 "$f" | sort | uniq -c | head -8; }; done;
  echo "build finished $(date -u +%Y-%m-%dT%H:%M:%SZ)"; } >> "$REPORT"
exit 0
