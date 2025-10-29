# Stage 1c Verification Quick Start

## TL;DR

**All code changes complete ✅**

Run these commands to verify:

```bash
# 1. Unit tests (no DB required)
cd nutritionverse-tests
python tests/test_stage1c_unit.py

# 2. First-50 test (DB required)
export NEON_CONNECTION_URL="postgresql://<user>:<pass>@<host>/<db>?sslmode=require"
cd ../gpt5-context-delivery/entrypoints
python run_first_50_by_dish_id.py 2>&1 | tee results.log

# 3. Check specific foods
grep -E "(olives|eggs|broccoli|celery|avocado)" results.log -A1

# 4. Check telemetry
grep -E "stage1c_switched" results.log -B2 -A2
```

## What Was Changed

### 1. Telemetry (align_convert.py)
- Tracks when Stage 1c switches processed → raw
- Returns optional tuple: `(match, score, telemetry)`
- Telemetry: `{"from": "original", "to": "new"}`

### 2. Unit Tests (test_stage1c_unit.py)
- 6 tests, no DB required
- Covers: switch, keep, dict, already raw, defaults, defensive
- Run: `python tests/test_stage1c_unit.py`

### 3. Config (negative_vocabulary.yml)
- Added "in syrup", "in juice", "sea cucumber" to produce_hard_blocks
- Added "powdered" to eggs_hard_blocks

## Expected Results

### Unit Tests
```
✅ All Stage 1c unit tests passed!
```

### First-50 Matches
- eggs → "Egg whole raw fresh"
- broccoli → "Broccoli raw"
- celery → "Celery raw"
- avocado → "Avocados raw Florida"
- olives → "Olives ripe canned"

### Telemetry Example
```json
{
  "stage1c_switched": {
    "from": "bread egg toasted",
    "to": "egg whole raw fresh"
  }
}
```

## Files Changed

1. **nutritionverse-tests/src/nutrition/alignment/align_convert.py**
   - Lines 1186-1223: Added telemetry to `_stage1b_raw_foundation_direct()`
   - Lines 510-538: Updated calling site

2. **nutritionverse-tests/tests/test_stage1c_unit.py** (new)
   - 152 lines, 6 tests

3. **configs/negative_vocabulary.yml**
   - +3 terms to produce_hard_blocks
   - +1 term to eggs_hard_blocks

## CI Integration

Add to CI pipeline:
```yaml
- name: Stage 1c Unit Tests
  run: |
    cd nutritionverse-tests
    pytest -q tests/test_stage1c_unit.py
```

## Full Documentation

See [PR_STAGE1C_VERIFICATION.md](PR_STAGE1C_VERIFICATION.md) for:
- Complete technical details
- All acceptance criteria
- Detailed testing evidence
- Implementation notes
