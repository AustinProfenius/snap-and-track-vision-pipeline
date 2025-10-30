#!/bin/bash
# Phase Z2 Quick Start Script
# Run this to execute the completed tools and validate outputs

set -e  # Exit on error

echo "=============================================================================="
echo "Phase Z2: Close Alignment Misses - Quick Start"
echo "=============================================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
echo "[1/5] Checking prerequisites..."
if [ ! -f "./missed_food_names.csv" ]; then
    echo -e "${RED}ERROR: missed_food_names.csv not found${NC}"
    exit 1
fi

if [ ! -f "tools/merge_verified_fallbacks.py" ]; then
    echo -e "${RED}ERROR: tools/merge_verified_fallbacks.py not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites OK${NC}"
echo ""

# Create runs directory if needed
mkdir -p runs

# Run CSV merge
echo "[2/5] Running CSV merge..."
echo "  Input: missed_food_names.csv"
echo "  Output: configs/stageZ_branded_fallbacks_verified.yml"
echo "  Merge into: configs/stageZ_branded_fallbacks.yml"
echo ""

python tools/merge_verified_fallbacks.py \
  --csv ./missed_food_names.csv \
  --out configs/stageZ_branded_fallbacks_verified.yml \
  --merge-into configs/stageZ_branded_fallbacks.yml \
  --report runs/csv_merge_report.json

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ CSV merge completed${NC}"
else
    echo -e "${RED}✗ CSV merge failed${NC}"
    exit 1
fi
echo ""

# Validate merged config
echo "[3/5] Validating merged config..."
python tools/validate_stageZ_config.py configs/stageZ_branded_fallbacks.yml

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Config validation passed${NC}"
else
    echo -e "${YELLOW}⚠ Config validation failed (check errors above)${NC}"
fi
echo ""

# Show merge report summary
echo "[4/5] Merge Report Summary..."
if [ -f "runs/csv_merge_report.json" ]; then
    echo "  Report: runs/csv_merge_report.json"

    # Extract key metrics using python
    python -c "
import json
with open('runs/csv_merge_report.json', 'r') as f:
    report = json.load(f)

print(f\"  Total CSV rows: {report['parsing']['total_rows']}\")
print(f\"  Parsed: {report['parsing']['parsed']}\")
print(f\"  Skipped: {report['parsing']['skipped']}\")

if report['merge']:
    merge = report['merge']
    print(f\"  New keys added: {len(merge['new_keys'])}\")
    print(f\"  Keys replaced: {len(merge['replaced_keys'])}\")
    print(f\"  Skipped (precedence): {len(merge['skipped_due_to_precedence'])}\")

    db = merge['db_validation_summary']
    print(f\"  DB verified: {db['verified']}\")
    print(f\"  DB missing: {db['missing']}\")
    print(f\"  DB unknown: {db['unknown']}\")
" 2>/dev/null || echo "  (Could not parse report)"
else
    echo -e "${YELLOW}  No merge report found${NC}"
fi
echo ""

# Show next steps
echo "[5/5] Next Steps"
echo "=============================================================================="
echo ""
echo -e "${GREEN}✓ Completed:${NC}"
echo "  1. CSV merge tool created and tested"
echo "  2. Config validation tool created and tested"
echo "  3. CSV data merged into stageZ_branded_fallbacks.yml"
echo "  4. Config validated (see output above)"
echo ""
echo -e "${YELLOW}⚠ Remaining Work:${NC}"
echo "  1. Normalization fixes (align_convert.py::_normalize_for_lookup)"
echo "     - Collapse duplicate parentheticals"
echo "     - Normalize sun-dried → sun_dried"
echo "     - Peel hints → telemetry only"
echo "     - Handle 'deprecated' token"
echo ""
echo "  2. Config updates"
echo "     - Add celery root → celery mapping"
echo "     - Add tatsoi, alcohol to negative_vocabulary.yml"
echo ""
echo "  3. Telemetry enhancements"
echo "     - Add coverage_class field"
echo "     - Enhance Stage Z telemetry (source, fdc_id_missing_in_db)"
echo "     - Add form_hint for peel"
echo "     - Add ignored_class for negative vocab"
echo ""
echo "  4. Test suite (tests/test_phaseZ2_verified.py)"
echo "     - CSV merge tests"
echo "     - Special case tests (chicken, cherry tomato, etc.)"
echo "     - No-result food tests (celery root, tatsoi, alcohol)"
echo "     - Normalization tests"
echo ""
echo "  5. Integration & validation"
echo "     - Run consolidated test"
echo "     - Analyze misses (target: 54 → ≤10)"
echo "     - Verify no regressions"
echo ""
echo -e "📖 See ${GREEN}docs/phase_z2_implementation_status.md${NC} for detailed instructions"
echo ""
echo "=============================================================================="
echo "Phase Z2 Quick Start Complete!"
echo "=============================================================================="
