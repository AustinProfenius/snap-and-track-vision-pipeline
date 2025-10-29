#!/bin/bash
# Wrapper script to run tests with correct Python paths and environment setup
# Usage: ./run_tests.sh [test_name]

set -e  # Exit on error

# Get script directory (repo root)
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "  Snap & Track Test Runner"
echo "=========================================="
echo "Repo root: $REPO_ROOT"
echo ""

# Setup Python path
export PYTHONPATH="$REPO_ROOT/nutritionverse-tests:$REPO_ROOT/pipeline:$PYTHONPATH"
echo "PYTHONPATH set: $PYTHONPATH"

# Load .env file
if [ -f "$REPO_ROOT/.env" ]; then
    export $(cat "$REPO_ROOT/.env" | grep -v '^#' | xargs)
    echo ".env loaded from: $REPO_ROOT/.env"
else
    echo "WARNING: .env file not found at $REPO_ROOT/.env"
fi

# Check NEON_CONNECTION_URL
if [ -z "$NEON_CONNECTION_URL" ]; then
    echo "ERROR: NEON_CONNECTION_URL not set"
    exit 1
fi
echo "✓ NEON_CONNECTION_URL loaded"

# Enable pipeline mode (fail-fast on config errors)
export PIPELINE_MODE=true
echo "✓ PIPELINE_MODE=true"
echo ""

# Run requested test
TEST_NAME="${1:-unit}"

case "$TEST_NAME" in
    "unit"|"pytest")
        echo "Running unit tests..."
        cd "$REPO_ROOT/tests"
        python3 -m pytest test_produce_alignment.py -v
        ;;

    "diagnostic"|"diag")
        echo "Running diagnostic test..."
        cd "$REPO_ROOT/tests"
        python3 test_db_connection.py
        ;;

    "50batch"|"batch50"|"first50")
        echo "Running first 50 dishes batch test..."
        cd "$REPO_ROOT"

        # Check if run script exists
        if [ ! -f "scripts/run_first_50.sh" ]; then
            echo "ERROR: run_first_50.sh not found"
            echo "Expected: $REPO_ROOT/scripts/run_first_50.sh"
            exit 1
        fi

        bash scripts/run_first_50.sh
        ;;

    "quick"|"validation")
        echo "Running quick validation test (apple, eggs, broccoli, cherry tomatoes, mushrooms, green beans)..."
        cd "$REPO_ROOT"
        python3 << 'EOF'
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "nutritionverse-tests"))
sys.path.insert(0, str(Path.cwd() / "pipeline"))

from dotenv import load_dotenv
load_dotenv(Path.cwd() / ".env", override=True)

from src.adapters.alignment_adapter import AlignmentEngineAdapter

adapter = AlignmentEngineAdapter()

test_items = [
    ("apple", "raw"),
    ("cherry tomatoes", "raw"),
    ("mushrooms", "raw"),
    ("green beans", "raw"),
    ("scrambled eggs", "cooked"),
    ("broccoli florets", "raw"),
]

print("\n===== P0+P1 Quick Validation =====\n")
for name, form in test_items:
    pred = {"foods": [{"name": name, "form": form, "mass_g": 100.0, "confidence": 0.8}]}
    res = adapter.align_prediction_batch(pred)

    if res["available"] and res["foods"]:
        f = res["foods"][0]
        stage = f.get("alignment_stage", "unknown")
        match = f.get("fdc_name", "NO_MATCH")[:50]
        status = "✓" if stage != "stage0_no_candidates" else "✗"

        # Check for dessert leakage
        if "croissant" in match.lower() or "ice cream" in match.lower():
            status = "⚠️ LEAKAGE"

        print(f"{status} {name:20s} {stage:30s} {match}")
    else:
        error = res.get("error", "Unknown error")
        print(f"✗ {name:20s} ERROR: {error}")

print("\n===== Config Version =====")
print(f"Config: {adapter.config_version}")
EOF
        ;;

    "help"|"--help"|"-h")
        echo "Usage: ./run_tests.sh [test_name]"
        echo ""
        echo "Available tests:"
        echo "  unit, pytest      - Run unit tests (test_produce_alignment.py)"
        echo "  diagnostic, diag  - Run diagnostic connection test"
        echo "  50batch, batch50  - Run first 50 dishes batch test"
        echo "  quick, validation - Run quick validation (6 key foods)"
        echo "  help              - Show this help"
        echo ""
        echo "Environment:"
        echo "  NEON_CONNECTION_URL must be set in .env"
        echo "  PIPELINE_MODE=true (set automatically)"
        ;;

    *)
        echo "ERROR: Unknown test: $TEST_NAME"
        echo "Run './run_tests.sh help' for usage"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "  Test Complete"
echo "=========================================="
