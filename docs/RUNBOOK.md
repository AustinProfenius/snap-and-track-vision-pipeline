# Prediction Replay & Analysis Runbook

**Purpose**: Step-by-step commands for running prediction replays and analyzing results

**Last Updated**: 2025-10-30

---

## Prerequisites

1. **Environment**: Python 3.8+, dependencies installed
2. **Database**: NEON_CONNECTION_URL set in `.env`
3. **Configs**: `configs/` directory with all YAML files
4. **Baseline**: 630-image prediction file at `nutritionverse-tests/results/gpt_5_630images_20251027_151930.json`

---

## Quick Start: Run Phase Z3 Replay

```bash
# From repo root
cd /Users/austinprofenius/snapandtrack-model-testing

# Run full 630-image replay with Z3 changes
python nutritionverse-tests/entrypoints/replay_from_predictions.py \
  --in nutritionverse-tests/results/gpt_5_630images_20251027_151930.json \
  --out runs/replay_z3_$(date +%Y%m%d_%H%M%S) \
  --config-dir configs/ \
  --schema auto

# Expected: ~13 minutes, zero vision API calls
# Output: results.jsonl, telemetry.jsonl, replay_manifest.json
```

---

## Step-by-Step: Full Workflow

### Step 1: Run Prediction Replay

**Command**:
```bash
python nutritionverse-tests/entrypoints/replay_from_predictions.py \
  --in nutritionverse-tests/results/gpt_5_630images_20251027_151930.json \
  --out runs/replay_z3_20251030_140000 \
  --config-dir configs/ \
  --schema auto
```

**Parameters**:
- `--in`: Input prediction file (JSON or JSONL)
- `--out`: Output directory for results
- `--config-dir`: Config directory (default: auto-detect)
- `--schema`: Schema version (default: auto-detect)
- `--limit`: Optional limit on predictions to process

**Output Files**:
```
runs/replay_z3_20251030_140000/
├── results.jsonl          # Alignment results (one per prediction)
├── telemetry.jsonl        # Detailed telemetry (one per food)
└── replay_manifest.json   # Run metadata
```

**Expected Duration**: 10-15 minutes for 630 predictions

**Smoke Tests**:
```bash
# Check output files exist
ls -lh runs/replay_z3_*/

# Check Stage Z usage (should be > 0)
grep "Stage Z usage" runs/replay_z3_*/*.log

# Verify no assertion failures
echo $?  # Should be 0
```

---

### Step 2: Analyze Results

**Basic Analysis**:
```bash
python analyze_batch_results.py runs/replay_z3_20251030_140000/results.jsonl
```

**Compare with Baseline**:
```bash
python analyze_batch_results.py \
  runs/replay_z3_20251030_140000/results.jsonl \
  --compare runs/replay_630_withconfigs
```

**Expected Output**:
```
================================================================================
BATCH RESULTS ANALYSIS - Phase Z2 Validation
================================================================================

Total items: 1,818
Match rate: 75.2% (1,368 matched / 450 misses)

--- Stage Z Usage ---
Total Stage Z matches: 363 (20.0%)
  - Stage Z branded fallback: 295
  - Stage Z energy-only proxy: 68

--- Comparison with Baseline ---
ΔStage Z Usage: +5.5% (264 → 363 foods)
ΔMiss Rate: -4.9% (539 → 450 misses)
```

---

### Step 3: Run Tests

**All Prediction Replay Tests**:
```bash
pytest -xvs nutritionverse-tests/tests/test_prediction_replay.py
```

**Specific Test**:
```bash
# Test form inference
pytest -xvs nutritionverse-tests/tests/test_prediction_replay.py::test_intent_cooked_bonus

# Test Z3 fallbacks
pytest -xvs nutritionverse-tests/tests/test_prediction_replay.py::test_stageZ3_fallback_coverage
```

**Expected**: 6/6 tests passing

---

## Advanced: Quick Iteration

### Test with Limited Predictions

```bash
# Test with first 10 predictions only
python nutritionverse-tests/entrypoints/replay_from_predictions.py \
  --in nutritionverse-tests/results/gpt_5_630images_20251027_151930.json \
  --out /tmp/replay_quick_test \
  --limit 10 \
  --schema auto

# Should complete in < 30 seconds
```

### Check Config Loading

```bash
# Verify configs loaded
grep "\[CFG\]" runs/replay_z3_*/replay_log.txt

# Expected output:
# [CFG] fallbacks_loaded=116  (107 baseline + 9 Z3 additions)
# [CFG] allow_stageZ_for_partial_pools=True
# [CFG] db_available=True
```

### Extract Top Misses

```bash
# Get top 20 missing foods
python -c "
import json
from collections import Counter

data = []
with open('runs/replay_z3_20251030_140000/telemetry.jsonl') as f:
    for line in f:
        if line.strip():
            data.append(json.loads(line))

misses = [d for d in data if d.get('alignment_stage') == 'stage0_no_candidates']
food_names = Counter(d.get('food_name', '') for d in misses)

print('Top 20 Missing Foods:')
for name, count in food_names.most_common(20):
    print(f'  {count:3d}x  {name}')
"
```

---

## Troubleshooting

### Issue: Stage Z usage == 0

**Symptoms**:
```
❌ ERROR: Stage Z usage == 0 on replay with 630 predictions
Config/flags likely not wired correctly.
```

**Fix**:
1. Check configs loaded:
   ```bash
   grep "fallbacks_loaded" runs/replay_z3_*/replay_log.txt
   ```
2. Verify feature flags:
   ```bash
   cat configs/feature_flags.yml | grep allow_stageZ
   ```
3. Check database connection:
   ```bash
   echo $NEON_CONNECTION_URL
   ```

---

### Issue: High miss rate (>30%)

**Symptoms**: Miss rate higher than expected

**Debug**:
```bash
# Extract unique misses
python -c "
import json
from collections import Counter

data = []
with open('runs/replay_z3_*/telemetry.jsonl') as f:
    for line in f:
        data.append(json.loads(line.strip()))

misses = [d for d in data if d.get('alignment_stage') == 'stage0_no_candidates']
foods = Counter(d.get('food_name') for d in misses)

print(f'Total misses: {len(misses)}')
print(f'Unique foods: {len(foods)}')
print('\nTop 10:')
for name, count in foods.most_common(10):
    print(f'  {count:3d}x  {name}')
"
```

**Next Steps**:
- Add missing foods to `stageZ_branded_fallbacks.yml` (Phase Z4)
- Check if Foundation/SR entries exist but not matching
- Review negative vocabulary (foods intentionally ignored)

---

### Issue: Assertion failures in tests

**Symptoms**: Test fails with assertion error

**Debug**:
```bash
# Run test with verbose output
pytest -xvs nutritionverse-tests/tests/test_prediction_replay.py::test_stageZ3_fallback_coverage

# Check telemetry
cat /tmp/<test_output>/telemetry.jsonl | grep stageZ
```

---

## File Locations

| File | Path |
|------|------|
| Replay entrypoint | `nutritionverse-tests/entrypoints/replay_from_predictions.py` |
| Analyzer | `analyze_batch_results.py` |
| Tests | `nutritionverse-tests/tests/test_prediction_replay.py` |
| Configs | `configs/` |
| Stage Z fallbacks | `configs/stageZ_branded_fallbacks.yml` |
| Feature flags | `configs/feature_flags.yml` |
| Baseline prediction file | `nutritionverse-tests/results/gpt_5_630images_20251027_151930.json` |
| Run outputs | `runs/replay_z3_*/` |

---

## See Also

- `docs/PHASE_Z3_PLAN.md` - Phase Z3 goals and scope
- `docs/EVAL_BASELINES.md` - Baseline definitions
- `docs/CHANGELOG.md` - Change history
- `CONTINUE_HERE.md` - Latest run pointer
