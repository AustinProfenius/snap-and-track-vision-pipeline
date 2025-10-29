#!/usr/bin/env bash
# Search for stage1c_switched events in telemetry
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Searching for stage1c_switched events in telemetry..."
echo ""

count=$(grep -r '"stage1c_switched"' runs/*/telemetry.jsonl 2>/dev/null | wc -l | tr -d ' ')

if [ "$count" -gt 0 ]; then
    echo "Found $count stage1c_switched events:"
    echo ""
    grep -r '"stage1c_switched"' runs/*/telemetry.jsonl 2>/dev/null | head -10
    if [ "$count" -gt 10 ]; then
        echo ""
        echo "... and $(($count - 10)) more"
    fi
else
    echo "No stage1c_switched events found in runs/*/telemetry.jsonl"
fi
