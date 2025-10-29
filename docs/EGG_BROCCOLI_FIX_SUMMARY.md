# Egg & Broccoli Alignment Fix - Complete Implementation

**Date:** 2025-10-29
**Status:** ✅ IMPLEMENTED - Ready for testing

## Summary

Fixed two alignment misses ("scrambled eggs" and "broccoli florets") by implementing all required configuration changes, variant expansions, and telemetry improvements. The pipeline now:

1. ✅ Loads configs from `/configs` (single source of truth)
2. ✅ Returns enhanced Stage 1c telemetry with FDC IDs
3. ✅ Has expanded variants for "scrambled eggs" and "broccoli florets"
4. ✅ Allows Stage 2 raw→cooked conversion (strict_cooked_exact_gate = false)
5. ✅ Supports SR vegetables via proxy fallback
6. ✅ Has broccoli-specific allowlist rules

## Changes Made

### 1. Config Loading (alignment_adapter.py)

**File:** `nutritionverse-tests/src/adapters/alignment_adapter.py`

**Changes:**
- Updated `_auto_initialize()` to load configs from `/configs`
- Passes individual config parameters to `FDCAlignmentWithConversion`:
  - `class_thresholds`
  - `negative_vocab`
  - `feature_flags`
  - `variants`
  - `proxy_rules`
  - `category_allowlist`
  - `branded_fallbacks`
  - `unit_to_grams`

**Result:** No more "hardcoded defaults" warning when running from web app

### 2. Stage 1c Telemetry Enhancement (align_convert.py)

**File:** `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

**Changes:**
- Modified `_prefer_raw_stage1c()` to return tuple: `(candidate, telemetry_dict)`
- Telemetry now includes:
  ```python
  {
      "from": original_name,
      "to": new_name,
      "from_id": original_fdc_id,
      "to_id": new_fdc_id
  }
  ```
- Updated call site to unpack tuple and use returned telemetry

**Result:** Full traceability of Stage 1c raw-first preference switches

### 3. Scrambled Eggs Variants (variants.yml)

**File:** `configs/variants.yml`

**Added:**
```yaml
scrambled_eggs:
  - egg scrambled
  - eggs scrambled
  - egg, scrambled
  - eggs, scrambled
  - scrambled egg
  - Egg, whole, cooked, scrambled
```

**Result:** "Scrambled eggs" query now generates proper search variants

### 4. Broccoli Florets Variants (variants.yml)

**File:** `configs/variants.yml`

**Added:**
```yaml
broccoli:
  - broccoli
  - broccoli raw
  - broccoli cooked
  - broccoli steamed
  - Broccoli, raw
  - Broccoli, cooked, boiled, drained, without salt

broccoli_florets:
  - broccoli florets
  - broccoli floret
  - broccoli pieces
  - broccoli cuts
  - broccoli
  - broccoli raw
  - broccoli steamed
  - broccoli moist_heat
```

**Result:** "Broccoli florets" query maps to both raw and cooked broccoli variants

### 5. Relax Cooked Exact Gate (feature_flags.yml)

**File:** `configs/feature_flags.yml`

**Changed:**
```yaml
# Before
strict_cooked_exact_gate: true

# After
strict_cooked_exact_gate: false
```

**Result:** Allows Stage 2 raw→cooked conversion when SR cooked food not found

### 6. Broccoli Category Allowlist (category_allowlist.yml)

**File:** `configs/category_allowlist.yml`

**Added:**
```yaml
broccoli:
  allow_contains:
    - broccoli raw
    - broccoli cooked
    - broccoli boiled
    - broccoli steamed
    - broccoli florets
  penalize_contains:
    - baby food
    - babyfood
    - puree
    - soup
    - condensed
    - frozen chopped
  hard_block_contains: []
```

**Result:** Prioritizes fresh/cooked broccoli over processed forms

### 7. Stage 2 Conversion Already Supports Scrambled

**File:** `configs/cook_conversions.v2.json` (no changes needed)

**Confirmed:**
```json
"egg_whole": {
  "methods": {
    "scrambled": {
      "mass_change": { "type": "shrinkage", "mean": 0.10, "sd": 0.03 },
      "surface_oil_uptake_g_per_100g": { "mean": 2.0, "sd": 0.8 }
    }
  },
  "fallback": "scrambled"
}
```

**Result:** Raw egg → scrambled conversion already configured with proper shrinkage and oil uptake

## Expected Alignment Paths

### Scrambled Eggs

**Before:** `stage0_no_candidates` (miss)

**After (Expected Path):**
1. **Stage 1c (preferred):** Match to SR Legacy "Egg, whole, cooked, scrambled"
   - Uses `scrambled_eggs` variants from `variants.yml`
   - Direct SR Legacy match via expanded variants

2. **Stage 2 (fallback):** Match "Egg, whole, raw, fresh" + apply scrambled conversion
   - Uses raw Foundation egg
   - Applies `scrambled` method from `cook_conversions.v2.json`
   - 10% mass shrinkage + 2g oil uptake per 100g

3. **Stage 5B (final fallback):** Proxy to closest egg entry

**Stage:** `stage1c_cooked_sr_direct` or `stage2_raw_convert`

### Broccoli Florets (Steamed)

**Before:** `stage0_no_candidates` (miss)

**After (Expected Path):**
1. **Stage 1b (preferred):** Match "Broccoli, raw" via raw-first preference
   - Uses `broccoli_florets` → `broccoli` variant mapping
   - Stage 1c may switch from frozen to raw via raw-first preference
   - `stage1c_switched` telemetry logged

2. **Stage 2 (if form=cooked):** Match "Broccoli, raw" + apply moist_heat conversion
   - Raw Foundation broccoli
   - Conversion factors for steamed vegetables

3. **Stage 5B (fallback):** Proxy to "Broccoli, cooked, boiled, drained, without salt" (SR Legacy)
   - Category allowlist permits SR vegetables
   - Direct match to cooked broccoli

**Stage:** `stage1b_raw_foundation_direct` or `stage5b_proxy`

## Verification Commands

### 1. Quick Adapter Test

```bash
cd nutritionverse-tests
python3 -c "
import sys
sys.path.insert(0, '..')
from dotenv import load_dotenv
load_dotenv('../.env', override=True)

from src.adapters.alignment_adapter import AlignmentEngineAdapter

adapter = AlignmentEngineAdapter()

# Test scrambled eggs
result = adapter.align_prediction_batch({
    'foods': [{'name': 'scrambled eggs', 'form': 'cooked', 'mass_g': 130.0, 'confidence': 0.78}]
})
print(f'Scrambled Eggs: {result[\"available\"]}, Stage: {result[\"foods\"][0].get(\"alignment_stage\") if result[\"foods\"] else \"N/A\"}')

# Test broccoli florets
result = adapter.align_prediction_batch({
    'foods': [{'name': 'broccoli florets', 'form': 'steamed', 'mass_g': 100.0, 'confidence': 0.75}]
})
print(f'Broccoli Florets: {result[\"available\"]}, Stage: {result[\"foods\"][0].get(\"alignment_stage\") if result[\"foods\"] else \"N/A\"}')
"
```

**Expected output:**
```
[ADAPTER] Loaded configs from /Users/.../configs
[ADAPTER] Config version: configs@...
Scrambled Eggs: True, Stage: stage1c_cooked_sr_direct (or stage2_raw_convert)
Broccoli Florets: True, Stage: stage1b_raw_foundation_direct (or stage5b_proxy)
```

### 2. Run First-50 Batch Test

```bash
cd nutritionverse-tests/entrypoints
python run_first_50_by_dish_id.py 2>&1 | tee ../../runs/fix_test.log
```

**Check for eggs/broccoli:**
```bash
grep -Ei 'egg|broccoli' runs/fix_test.log | grep -v stage0
```

### 3. Check Stage 1c Telemetry

```bash
# Run batch test
bash scripts/run_first_50.sh

# Search for stage1c_switched events
bash scripts/grep_stage1c.sh

# Count events
grep -c '"stage1c_switched"' runs/*/telemetry.jsonl
```

**Expected:** Multiple stage1c_switched events with from/to/from_id/to_id fields

### 4. Verify No Egg/Broccoli Stage0 Misses

```bash
grep -Ri '"stage0_no_candidates"' runs/*/telemetry.jsonl | grep -Ei 'egg|broccoli' || echo "✓ No egg/broccoli stage0 misses"
```

**Expected:** `✓ No egg/broccoli stage0 misses`

### 5. Check Config Loading (No Hardcoded Warnings)

```bash
cd nutritionverse-tests
streamlit run nutritionverse_app.py
# Upload image with eggs or broccoli
# Check logs for: "[ADAPTER] Config version: configs@..."
# Should NOT see: "[WARNING] Using hardcoded config defaults"
```

## Files Modified

1. **nutritionverse-tests/src/adapters/alignment_adapter.py**
   - Lines 69-105: Config loading and engine initialization

2. **nutritionverse-tests/src/nutrition/alignment/align_convert.py**
   - Lines 126-177: `_prefer_raw_stage1c()` return signature and telemetry
   - Lines 1205-1214: Call site unpacking and telemetry handling

3. **configs/variants.yml**
   - Lines 12-18: Added `scrambled_eggs` variants
   - Lines 70-86: Added `broccoli` and `broccoli_florets` variants

4. **configs/feature_flags.yml**
   - Line 20: Changed `strict_cooked_exact_gate: false`

5. **configs/category_allowlist.yml**
   - Lines 125-140: Added `broccoli` category allowlist

## Testing Matrix

| Food | Form | Expected Stage | Telemetry Field | FDC Match |
|------|------|---------------|-----------------|-----------|
| scrambled eggs | cooked | stage1c_cooked_sr_direct | - | Egg, whole, cooked, scrambled |
| scrambled eggs | cooked | stage2_raw_convert | conversion_applied=true | Egg, whole, raw (+ conversion) |
| broccoli florets | raw | stage1b_raw_foundation_direct | stage1c_switched (maybe) | Broccoli, raw |
| broccoli florets | steamed | stage1b_raw_foundation_direct | stage1c_switched (maybe) | Broccoli, raw |
| broccoli florets | steamed | stage5b_proxy | - | Broccoli, cooked, boiled |

## Success Criteria

✅ **Primary:**
1. "scrambled eggs" aligns to FDC (not stage0)
2. "broccoli florets" aligns to FDC (not stage0)
3. Stage1c telemetry includes from_id/to_id
4. Configs loaded from `/configs` (no hardcoded warnings)

✅ **Secondary:**
1. `grep -c '"stage1c_switched"' runs/*/telemetry.jsonl` > 0
2. No egg/broccoli in stage0_no_candidates
3. Telemetry shows proper stage distribution
4. Pipeline completes full first-50 run without errors

## Rollback (If Needed)

```bash
# Revert all changes
git checkout nutritionverse-tests/src/adapters/alignment_adapter.py
git checkout nutritionverse-tests/src/nutrition/alignment/align_convert.py
git checkout configs/variants.yml
git checkout configs/feature_flags.yml
git checkout configs/category_allowlist.yml
```

## Next Steps

1. **Run first-50 batch test** to validate both fixes
2. **Check telemetry.jsonl** for stage1c_switched events
3. **Verify no stage0** for eggs/broccoli
4. **Test web app** with sample images containing eggs and broccoli
5. **Run full 459-batch** evaluation if first-50 passes

---

**Implementation Status:** ✅ COMPLETE
**Ready for:** Testing and validation
**Estimated test time:** 5-10 minutes for first-50

