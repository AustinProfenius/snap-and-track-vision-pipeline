# P0 + P1 Implementation Status

## ✅ COMPLETED (P0 - Safety Rails)

### 1. Config Load Contract & Assertions
**File:** `nutritionverse-tests/src/adapters/alignment_adapter.py`

**Changes:**
- Added config file assertions in `_auto_initialize()`:
  - Checks for: variants.yml, category_allowlist.yml, negative_vocabulary.yml, feature_flags.yml, unit_to_grams.yml
  - **Pipeline mode** (PIPELINE_MODE=true): Raises FileNotFoundError (fail-fast)
  - **Web app mode**: Returns graceful error `{"available": false, "error": "config_load_failed: <details>"}`

- Config version stamping:
  - Stores `config_version` and `config_fingerprint` in adapter
  - Stamps into telemetry header: `{"config_version": ..., "config_fingerprint": ...}`

**Status:** ✅ Complete

---

### 2. Stage2 Seed Guardrail
**File:** `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

**Changes:**
- Added `_validate_stage2_seed()` method (lines 1348-1380):
  - Validates source == "foundation"
  - Validates form == "raw"
  - Blocks processed/cooked name tokens: cooked, fast foods, pancake, cracker, ice cream, pastry, soup, puree, babyfood, frozen, canned, fried, baked, roasted, grilled
  - Returns (is_valid, reason) tuple

- Integrated into `_stage2_raw_convert()` (lines 1455-1468):
  - Validates seed before `convert_from_raw()`
  - Logs rejection with ALIGN_VERBOSE
  - Attaches `_stage2_seed_guardrail` telemetry to candidate
  - Returns None if validation fails

**Status:** ✅ Complete

---

## ✅ COMPLETED (P1 - Produce Gaps)

### 3. Produce Variants Added
**File:** `configs/variants.yml`

**Added:**
```yaml
# Cherry/grape tomatoes
cherry_tomatoes: [cherry tomatoes, cherry tomato, tomatoes cherry, tomato cherry, Tomatoes, cherry, raw]
grape_tomatoes: [grape tomatoes, grape tomato, tomatoes grape, tomato grape, Tomatoes, grape, raw]

# Mushrooms
mushrooms: [mushrooms, mushroom, button mushrooms, white mushrooms, brown mushrooms, cremini, cremini mushrooms, baby bella, Mushrooms, white, raw]

# Green beans
green_beans: [green beans, string beans, snap beans, haricot vert, green bean, Beans, snap, green, raw, Beans, snap, green, cooked, boiled, drained, without salt]
```

**Status:** ✅ Complete

---

### 4. Category Allowlist Enhanced
**File:** `configs/category_allowlist.yml`

**Added:**
```yaml
tomatoes_cherry:
  allow_contains: [cherry, tomato raw, tomatoes cherry]
  penalize_contains: [soup, sauce, paste]

mushrooms:
  allow_contains: [mushroom raw, mushrooms white, button, cremini]
  penalize_contains: [soup, cream of, canned]

green_beans:
  allow_contains: [beans snap, green beans raw, green beans cooked]
  penalize_contains: [canned, soup, baby food]
```

**Status:** ✅ Complete

---

## ⏳ REMAINING TASKS

### 5. Stage1b Transparency Telemetry
**File:** `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

**Required:**
- Add telemetry in `_stage1b_raw_foundation_direct()`:
  ```python
  telemetry_stage1b = {
      "candidate_pool_size": len(raw_foundation),
      "best_candidate_name": best_match.name if best_match else None,
      "best_candidate_id": best_match.fdc_id if best_match else None,
      "best_score": best_score,
      "threshold": threshold,
  }
  # Sentinel: pool exists but all rejected
  if len(raw_foundation) > 0 and not best_match:
      telemetry_stage1b["stage1b_dropped_despite_pool"] = True
  ```

**Status:** ⏳ TODO

---

### 6. Class-Conditional Penalties for Produce
**File:** `nutritionverse-tests/src/nutrition/alignment/align_convert.py` (Stage1b scoring)

**Required:**
- Add produce penalty logic after jaccard/energy scoring:
  ```python
  if class_intent in ["produce", "leafy_or_crucifer"]:
      dessert_tokens = ["croissant", "ice cream", "cake", "cookie", "pastry", "muffin"]
      starchy_processed = ["cracker", "pancake", "bread", "toast"]

      entry_check = entry.name.lower()
      for token in dessert_tokens + starchy_processed:
          if token in entry_check:
              score -= 0.35  # Strong penalty (apple→croissant killer)
  ```

**Status:** ⏳ TODO

---

### 7. Stage1c Telemetry ID Verification
**Status:** ✅ Already implemented in previous session (lines 126-177 of align_convert.py)
- Need unit test to verify from_id/to_id are populated

---

### 8. Unit Tests
**File:** `nutritionverse-tests/tests/test_produce_alignment.py` (NEW)

**Required tests:**
- `test_produce_alignment()`: cherry tomatoes, grape tomatoes, mushrooms, green beans, broccoli florets not stage0
- `test_produce_no_dessert_leakage()`: apple/strawberry don't match croissant/ice cream
- `test_stage1c_telemetry_ids()`: stage1c switches have non-null from_id/to_id
- `test_stage2_seed_guardrail()`: Stage2 conversions pass guardrail

**Status:** ⏳ TODO

---

### 9. Batch Diagnostics Script
**File:** `scripts/diagnose_batch.sh` (NEW)

**Required:**
```bash
#!/bin/bash
# Usage: ./diagnose_batch.sh <batch_json_file>
jq -r '.results[].database_aligned.foods[] | select(.alignment_stage=="stage0_no_candidates") | .predicted_name' "$1" | sort | uniq -c
jq -r '.results[].database_aligned.foods[] | select(.alignment_stage=="stage2_raw_convert") | [.predicted_name, .telemetry.raw_name] | @tsv' "$1" | egrep -i 'pancake|cracker|fast foods'
jq -r '.results[].database_aligned.foods[].telemetry.stage1c_switched | select(.)' "$1" | jq -r 'select(.from_id==null or .to_id==null)'
```

**Status:** ⏳ TODO

---

## ACCEPTANCE CRITERIA

Before merge, must pass:

1. ✅ Config assertions work (pipeline fails fast, web app graceful error)
2. ✅ Config version stamped in telemetry
3. ✅ Stage2 seed guardrail rejects cooked/processed
4. ✅ Cherry/grape tomatoes, mushrooms, green beans variants added
5. ⏳ Zero stage0 for produce in 50-batch re-run
6. ⏳ No apple→croissant, strawberry→ice cream leakage
7. ⏳ All Stage2 conversions have `stage2_seed_guardrail: passed`
8. ⏳ Stage1b telemetry visible (scores, thresholds, pool sizes)
9. ⏳ Unit tests pass

---

## NEXT STEPS

1. **Complete Stage1b transparency** (15 min)
2. **Add produce penalties** (10 min)
3. **Write unit tests** (30 min)
4. **Create diagnose_batch.sh** (5 min)
5. **Run 50-batch validation** (5 min)
6. **Review results & iterate** (20 min)

**Total remaining:** ~90 minutes

---

## FILES CHANGED

**Modified:**
- `nutritionverse-tests/src/adapters/alignment_adapter.py` (+40 lines)
- `nutritionverse-tests/src/nutrition/alignment/align_convert.py` (+35 lines)
- `configs/variants.yml` (+38 lines)
- `configs/category_allowlist.yml` (+38 lines)

**To Create:**
- `nutritionverse-tests/tests/test_produce_alignment.py`
- `scripts/diagnose_batch.sh`

---

## SUMMARY

**P0 (Safety):** 2/2 complete ✅
**P1 (Produce Gaps):** 2/2 complete ✅
**P0+P1 Observability:** 1/2 complete (Stage1b telemetry remains)
**Testing & Validation:** 0/2 complete

**Overall Progress:** 5/8 tasks complete (62.5%)
