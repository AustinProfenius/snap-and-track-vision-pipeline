#!/bin/bash
# Compare multiple APIs on the same dataset slice

set -e

# Configuration
START=${1:-0}
END=${2:-50}
TASK=${3:-itemized}
RPS=0.5
MAX_COST=20.00

echo "==================================="
echo "Multi-API Comparison"
echo "==================================="
echo "Range: $START to $END"
echo "Task: $TASK"
echo "RPS: $RPS"
echo "Max cost per API: \$$MAX_COST"
echo ""

# Run OpenAI
echo "[1/3] Running OpenAI GPT-4o-mini..."
python -m src.core.runner \
  --api openai \
  --task "$TASK" \
  --start "$START" \
  --end "$END" \
  --rps "$RPS" \
  --max-cost "$MAX_COST" \
  --resume

echo ""
echo "[2/3] Running Claude 3.5 Sonnet..."
python -m src.core.runner \
  --api claude \
  --task "$TASK" \
  --start "$START" \
  --end "$END" \
  --rps 0.2 \
  --max-cost "$MAX_COST" \
  --resume

echo ""
echo "[3/3] Running Gemini 1.5 Flash..."
python -m src.core.runner \
  --api gemini \
  --task "$TASK" \
  --start "$START" \
  --end "$END" \
  --rps 1.0 \
  --max-cost "$MAX_COST" \
  --resume

echo ""
echo "==================================="
echo "All runs complete!"
echo "View results in Streamlit:"
echo "  streamlit run src/ui/app.py"
echo "==================================="
