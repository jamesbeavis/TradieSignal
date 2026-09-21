#!/usr/bin/env bash
# Tradiesignal :: weekly production run
# Usage: ./run_weekly.sh [days]
# Produces reports/Tradiesignal_Hunter_Report.pdf and the web/site pages.
set -euo pipefail
DAYS="${1:-120}"
export PYTHONPATH=src

echo "==> 1/5  collecting NSW ePlanning data (${DAYS} days, 5 councils, 3 services)"
python3 src/collect_eplanning.py --days "$DAYS" --out data/raw

echo "==> 2/5  normalising, validating and scoring"
python3 src/normalise_and_score.py

echo "==> 3/5  building report slices"
python3 src/report_data.py

echo "==> 4/5  rendering report (print + web)"
python3 src/build_report.py

echo "==> 5/5  rendering site pages and PDF"
python3 src/build_landing.py
# External data mode: the deployed dashboard fetches its rows, so a weekly
# refresh replaces one JSON file instead of a 1.2 MB HTML document.
python3 src/build_dashboard.py --data-url /data/dashboard.json --data-file site/dashboard-data.json
node src/export_pdf.cjs

echo
echo "done. outputs:"
ls -la reports/*.pdf site/*.html data/projects.csv
