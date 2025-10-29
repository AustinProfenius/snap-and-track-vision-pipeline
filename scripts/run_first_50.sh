#!/usr/bin/env bash
# Run first-50 batch test using canonical entrypoint
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Running first-50 batch test..."
cd nutritionverse-tests/entrypoints
python run_first_50_by_dish_id.py 2>&1 | tee ../../runs/first_50_latest.log

echo ""
echo "Test complete. Check runs/ directory for results."
