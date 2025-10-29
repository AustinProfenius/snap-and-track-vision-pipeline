#!/usr/bin/env bash
# Run first-50 batch test using canonical entrypoint
set -euo pipefail

# Get repo root
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Running first-50 batch test..."
echo "Repo root: $REPO_ROOT"
echo "NEON_CONNECTION_URL set: ${NEON_CONNECTION_URL:+YES}"
echo "PYTHONPATH: $PYTHONPATH"
echo ""

cd "$REPO_ROOT/nutritionverse-tests/entrypoints"
python3 run_first_50_by_dish_id.py 2>&1 | tee "$REPO_ROOT/runs/first_50_latest.log"

echo ""
echo "Test complete. Check runs/ directory for results."
