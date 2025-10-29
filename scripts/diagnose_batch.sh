#!/bin/bash
# Batch diagnostics for alignment results
# Usage: ./diagnose_batch.sh <batch_json_file>

BATCH_JSON="$1"
if [ -z "$BATCH_JSON" ]; then
    echo "Usage: $0 <batch_json_file>"
    exit 1
fi

echo "==========================================="
echo "  Batch Alignment Diagnostics"
echo "==========================================="
echo ""

echo "=== Stage0 Misses by Food Name ==="
jq -r '.results[].database_aligned.foods[] | select(.alignment_stage=="stage0_no_candidates") | .predicted_name' "$BATCH_JSON" | sort | uniq -c | sort -rn | head -20

echo ""
echo "=== Bad Stage2 Seeds (cooked/processed) ==="
jq -r '.results[].database_aligned.foods[] | select(.alignment_stage=="stage2_raw_convert") | [.predicted_name, .telemetry.raw_name] | @tsv' "$BATCH_JSON" \
  | egrep -i 'pancake|cracker|fast foods|ice cream|pastry|soup|puree|babyfood|cooked' || echo "✓ No bad Stage2 seeds found"

echo ""
echo "=== Stage1c Switches Missing IDs ==="
MISSING_IDS=$(jq -r '.results[].database_aligned.foods[].telemetry.stage1c_switched | select(.)' "$BATCH_JSON" \
  | jq -r 'select(.from_id==null or .to_id==null)')
if [ -z "$MISSING_IDS" ]; then
    echo "✓ All Stage1c switches have from_id and to_id"
else
    echo "✗ Found Stage1c switches with missing IDs:"
    echo "$MISSING_IDS"
fi

echo ""
echo "=== Produce → Dessert/Pastry Leakage ==="
jq -r '.results[].database_aligned.foods[] | select(.predicted_name | test("apple|berry|cherry|tomato|broccoli|mushroom"; "i")) | [.predicted_name, .matched_name] | @tsv' "$BATCH_JSON" \
  | egrep -i 'croissant|ice cream|pastry|cake|cookie|pancake|waffle' || echo "✓ No produce → dessert leakage"

echo ""
echo "=== Stage1b Dropped Despite Pool (Logic Bugs) ==="
DROPPED=$(jq -r '.results[].database_aligned.foods[].telemetry.stage1b_dropped_despite_pool | select(. == true)' "$BATCH_JSON" | wc -l | tr -d ' ')
if [ "$DROPPED" = "0" ]; then
    echo "✓ No stage1b logic bugs detected"
else
    echo "✗ Found $DROPPED cases where candidates were rejected despite non-empty pool"
fi

echo ""
echo "=== Stage Distribution ==="
jq -r '.results[].database_aligned.foods[].alignment_stage' "$BATCH_JSON" | sort | uniq -c | sort -rn

echo ""
echo "==========================================="
echo "  Diagnostics Complete"
echo "==========================================="
