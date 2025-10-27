# Phase 2: Conversion Layer & Alignment Implementation - COMPLETE

**Status**: ✅ All Features Implemented - 34/34 tests passing
**Date**: 2025-10-25
**Focus**: Stricter cooked SR/Legacy gate + Sodium gating integration + Enhanced telemetry

---

## 🎯 Implementation Summary

Phase 2 builds on Phase 1 (method aliases, fried family profiles, salad canonicalization) by implementing:

1. **Stricter Cooked SR/Legacy Gate** - Hard-gate Stage 1 when raw Foundation exists
2. **Sodium Gate Integration** - Integrated into alignment scoring pipeline
3. **Enhanced Telemetry Tracking** - Comprehensive metrics in eval aggregator
4. **Feature Flag System** - `prefer_raw_foundation_convert` flag added
5. **Test Coverage** - 2 new tests (34/34 passing total)

---

## ✅ Features Implemented

### **Feature #1: Stricter Cooked SR/Legacy Gate** 🔴 CRITICAL

**Problem**: Stage 1 (cooked SR/Legacy) was competing with Stage 2 (raw + convert), allowing foods to bypass the conversion layer even when raw Foundation entries existed.

**Solution**: Hard-gate Stage 1 when raw Foundation entry exists for the same class.

**Implementation** ([align_convert.py:237-252](src/nutrition/alignment/align_convert.py#L237-L252)):

```python
# In _stage1_cooked_exact():
if FLAGS.prefer_raw_foundation_convert:
    has_raw_foundation = any(
        entry.source == "foundation" and entry.form == "raw" and entry.core_class == core_class
        for entry in candidates
    )

    if has_raw_foundation:
        # Block Stage 1 - raw Foundation exists, should use Stage 2 (raw + convert)
        self.telemetry["stage1_blocked_raw_foundation_exists"] = \
            self.telemetry.get("stage1_blocked_raw_foundation_exists", 0) + 1
        print(f"[ALIGN] Stage 1 blocked: raw Foundation exists for {core_class}, prefer Stage 2 (raw + convert)")
        return None
```

**Feature Flag** ([feature_flags.py:71-75](src/config/feature_flags.py#L71-L75)):
```python
# NEW: Prefer raw Foundation + conversion over cooked SR/Legacy (conversion layer improvement)
# When enabled, hard-gate Stage 1 (cooked SR/Legacy) when raw Foundation exists
# Forces Stage 2 (raw + convert) path to make conversion layer "unmissable"
# Target: conversion_hit_rate ≥60%
prefer_raw_foundation_convert: bool = os.getenv("PREFER_RAW_FOUNDATION_CONVERT", "true").lower() == "true"
```

**Expected Impact**:
- Conversion hit rate: Target ≥60% (forces raw + convert path)
- Prevents cooked SR/Legacy bypass when raw Foundation available
- Ensures oil uptake, macro retention, and method-specific transformations are applied

**Telemetry**:
- `stage1_blocked_raw_foundation_exists`: Count of Stage 1 blocks due to raw Foundation existing

**Files Modified**:
- `src/nutrition/alignment/align_convert.py` (+17 lines)
- `src/config/feature_flags.py` (+5 lines, +1 flag)

**Test**: `test_prefer_raw_foundation_flag()` ✅

---

### **Feature #2: Sodium Gate Integration** 🟡 HIGH-IMPACT

**Problem**: Sodium gating function existed but wasn't integrated into the alignment scoring pipeline.

**Solution**: Integrated `check_sodium_gate()` into `search_best_match()` candidate filtering.

**Implementation** ([fdc_alignment_v2.py:1029-1043](src/adapters/fdc_alignment_v2.py#L1029-L1043)):

```python
# After macro plausibility check, before scoring:
sodium_mg_100g = r.get("sodium_mg_100g", 0.0) or 0.0
passes_sodium_gate, sodium_reason = check_sodium_gate(
    food_name, r["name"], sodium_mg_100g
)
if not passes_sodium_gate:
    print(f"[ALIGN] Rejected {r['name']}: {sodium_reason}")
    if telemetry is not None:
        telemetry["sodium_gate_blocks"] = telemetry.get("sodium_gate_blocks", 0) + 1
    continue
elif sodium_reason:  # Gate passed with explicit reason
    if telemetry is not None:
        telemetry["sodium_gate_passes"] = telemetry.get("sodium_gate_passes", 0) + 1
    print(f"[ALIGN] Sodium gate passed: {sodium_reason}")
```

**How It Works**:
1. For each FDC candidate, extract `sodium_mg_100g` field
2. Call `check_sodium_gate(food_name, candidate_name, sodium_mg)`
3. If gate fails (low sodium for pickled item), reject candidate and log
4. If gate passes explicitly, log success for telemetry

**Gate Configuration** (already implemented in Phase 1):
```python
SODIUM_GATE_ITEMS = {
    "pickles": {"min_sodium_mg_per_100g": 600, "keywords": ["pickle", "pickled", "gherkin", "dill"]},
    "olives": {"min_sodium_mg_per_100g": 600, "keywords": ["olive", "olives", "kalamata"]},
    "capers": {"min_sodium_mg_per_100g": 1500, "keywords": ["caper", "capers"]},
    "kimchi": {"min_sodium_mg_per_100g": 500, "keywords": ["kimchi"]},
    "sauerkraut": {"min_sodium_mg_per_100g": 500, "keywords": ["sauerkraut", "kraut"]},
    "fermented": {"min_sodium_mg_per_100g": 400, "keywords": ["fermented", "pickled"]},
}
```

**Expected Impact**:
- "Olives" require ≥600 mg sodium/100g (prevents raw olive fruit alignment at ~3 mg/100g)
- "Pickles" require ≥600 mg sodium/100g (prevents fresh cucumber alignment at ~2 mg/100g)
- Reduces calorie errors from raw/pickled misalignment

**Telemetry**:
- `sodium_gate_blocks`: Count of candidates rejected by sodium gate
- `sodium_gate_passes`: Count of candidates that passed sodium gate

**Files Modified**:
- `src/adapters/fdc_alignment_v2.py` (+15 lines)

**Test**: `test_sodium_gate_integration()` ✅

---

### **Feature #3: Enhanced Telemetry Tracking** 🔧 INFRASTRUCTURE

**Problem**: No automated way to track conversion application, method inference, sodium gating, and alignment stages from evaluation results.

**Solution**: Added `compute_telemetry_stats()` function to eval aggregator.

**Implementation** ([eval_aggregator.py:258-300](tools/eval_aggregator.py#L258-L300)):

```python
def compute_telemetry_stats(items: List[Dict]) -> Dict[str, Any]:
    """Compute telemetry statistics from evaluation items."""
    telemetry_stats = {
        "conversion_applied_count": 0,
        "method_inferred_count": 0,
        "sodium_gate_blocks": 0,
        "sodium_gate_passes": 0,
        "stage1_blocked_raw_foundation_exists": 0,
        "alignment_stages": {},
        "oil_uptake_applied": 0,
    }

    for item in items:
        prov = item.get('provenance', {})
        telemetry = item.get('telemetry', {})

        # Track conversion application
        if prov.get('conversion_applied') or telemetry.get('conversion_applied'):
            telemetry_stats["conversion_applied_count"] += 1

        # Track method inference
        if prov.get('method_reason') in ['conversion_config', 'class_default', 'category_default']:
            telemetry_stats["method_inferred_count"] += 1

        # Track sodium gates
        telemetry_stats["sodium_gate_blocks"] += telemetry.get('sodium_gate_blocks', 0)
        telemetry_stats["sodium_gate_passes"] += telemetry.get('sodium_gate_passes', 0)

        # Track Stage 1 blocks
        telemetry_stats["stage1_blocked_raw_foundation_exists"] += telemetry.get('stage1_blocked_raw_foundation_exists', 0)

        # Track alignment stages
        stage = prov.get('alignment_stage', 'unknown')
        telemetry_stats["alignment_stages"][stage] = telemetry_stats["alignment_stages"].get(stage, 0) + 1

        # Track oil uptake
        if telemetry.get('oil_uptake_g_per_100g', 0) > 0:
            telemetry_stats["oil_uptake_applied"] += 1

    return telemetry_stats
```

**Output Format** (in eval_aggregator):
```
------------------------------------------------------------
TELEMETRY STATS
------------------------------------------------------------
   Conversion Applied: 245/413 (59.3%)
   Method Inferred: 123
   Sodium Gate Blocks: 4
   Sodium Gate Passes: 12
   Stage 1 Blocks (raw Foundation exists): 87
   Oil Uptake Applied: 56

   Alignment Stages:
      stage2_raw_convert: 245 (59.3%)
      stage1_cooked_exact: 98 (23.7%)
      stage4_branded_energy: 45 (10.9%)
      stageZ_branded_last_resort: 25 (6.1%)
```

**Metrics Tracked**:
1. **conversion_applied_count** - How many items went through raw + convert
2. **method_inferred_count** - How many used inferred methods (not explicit)
3. **sodium_gate_blocks/passes** - Sodium gating effectiveness
4. **stage1_blocked_raw_foundation_exists** - Stricter gate effectiveness
5. **alignment_stages** - Distribution across stages (target: Stage 2 ≥60%)
6. **oil_uptake_applied** - Fried food conversion tracking

**Files Modified**:
- `tools/eval_aggregator.py` (+106 lines)

**Usage**:
```bash
python tools/eval_aggregator.py path/to/evaluation.json --verbose
```

---

## 📊 Test Results

**Total Tests**: 34/34 passing ✅ (up from 32)

**New Tests Added** (2):
1. `test_prefer_raw_foundation_flag()` - Validates feature flag exists and defaults to True
2. `test_sodium_gate_integration()` - Validates sodium gate is integrated and working

**Test Execution**:
```bash
$ python tests/test_alignment_guards.py
============================================================
TEST RESULTS: 34 passed, 0 failed
============================================================
```

**Test Coverage**:
- Feature flags: ✅
- Sodium gate integration: ✅
- Method aliases: ✅ (from Phase 1)
- Hash browns routing: ✅ (from Phase 1)
- Olive sodium gating: ✅ (from Phase 1)
- Mixed salad canonicalization: ✅ (from Phase 1)
- Homefries oil uptake: ✅ (from Phase 1)

---

## 📁 Files Modified Summary

| File | Lines Added/Modified | Purpose |
|------|---------------------|---------|
| `src/nutrition/alignment/align_convert.py` | +17 | Stricter cooked SR/Legacy gate in Stage 1 |
| `src/config/feature_flags.py` | +5 | Added prefer_raw_foundation_convert flag |
| `src/adapters/fdc_alignment_v2.py` | +15 | Integrated sodium gate into search_best_match |
| `tools/eval_aggregator.py` | +106 | Added compute_telemetry_stats + enhanced output |
| `tests/test_alignment_guards.py` | +50 | Added 2 new test functions |

**Total**: ~193 lines of new code/modifications

---

## 🎯 Expected Performance Improvements

### Phase 1 + Phase 2 Combined Impact:

**Conversion Hit Rate**:
- Before: ~0% (conversion layer not applied)
- After Phase 1: ~60% (method aliases + fried profiles)
- **After Phase 2: Target ≥65%** (stricter gate forces conversion)

**Accuracy Gains**:
- **Hash Browns**: +50-80 kcal from 11.5g oil uptake (Phase 1)
- **Home Fries**: +35-50 kcal from 7.5g oil uptake (Phase 1)
- **Olives**: Prevent raw fruit misalignment (3 mg → 600+ mg sodium requirement) (Phase 1+2)
- **Pickles**: Prevent fresh cucumber misalignment (Phase 1+2)
- **Broiled/Toasted/Charred Foods**: Proper method conversion (Phase 1)

**Pipeline Metrics**:
- **Conversion Hit Rate**: Expected ≥65% (stricter gate + method aliases)
- **Top-1 Name Alignment**: Expected to maintain ≥75-78% (salad canonicalization helps)
- **Calorie MAPE**: Expected slight improvement from fried food accuracy + sodium gating
- **Branded Fallback Rate**: Expected to maintain ≤5%

---

## 🔄 How It Works (End-to-End)

### Example: "Hash Browns, Cooked"

**Step 1: Class Synonym Resolution** (Phase 1)
```
"hash browns" → class_synonyms.json → "potato_russet"
```

**Step 2: Method Alias Resolution** (Phase 1)
```
"cooked" → method_resolver.py → infer_method_from_class("potato_russet", "cooked")
→ cook_conversions.v2.json → "hash_browns" method
```

**Step 3: Alignment with Stricter Gate** (Phase 2)
```
Candidates found:
- FDC 12345: "Potatoes, hash brown, frozen, plain, unprepared" (Foundation, raw)
- FDC 67890: "Potatoes, hash brown, home-prepared" (SR Legacy, cooked)

Stage 1 Check (cooked SR/Legacy):
  - prefer_raw_foundation_convert flag is True
  - Raw Foundation (FDC 12345) exists for potato_russet
  → BLOCK Stage 1, force Stage 2

Stage 2 (raw + convert):
  - Select FDC 12345 (raw Foundation)
  - Apply hash_browns method from cook_conversions.v2.json:
    • mass_change: shrinkage 0.24 (24% moisture loss)
    • surface_oil_uptake: 11.5 g/100g
    • macro_retention: protein 0.98, fat 1.0, carbs 0.97
  → Conversion applied ✓
```

**Step 4: Telemetry Tracking** (Phase 2)
```
provenance: {
  alignment_stage: "stage2_raw_convert",
  conversion_applied: true,
  method: "hash_browns",
  method_reason: "conversion_config"
}

telemetry: {
  oil_uptake_g_per_100g: 11.5,
  mass_change_factor: 0.76,
  stage1_blocked_raw_foundation_exists: 1
}
```

**Result**:
- Raw potato (77 kcal/100g) → +24% moisture loss → +11.5g oil/100g
- Final: ~170 kcal/100g (vs ~77 if raw bypassed)
- **+93 kcal/100g accuracy gain**

---

### Example: "Olives" (Sodium Gating)

**Step 1: Search Candidates**
```
Query: "olives"
Candidates:
- FDC 11111: "Olives, ripe, canned (small-extra large)" (sodium: 735 mg/100g)
- FDC 22222: "Olives, raw" (sodium: 3 mg/100g)
```

**Step 2: Sodium Gate Check** (Phase 2)
```
For FDC 11111 (canned):
  check_sodium_gate("olives", "Olives, ripe, canned", 735.0)
  → Gate requires ≥600 mg for "olives"
  → 735 ≥ 600 → PASS ✓
  telemetry["sodium_gate_passes"] += 1

For FDC 22222 (raw):
  check_sodium_gate("olives", "Olives, raw", 3.0)
  → Gate requires ≥600 mg for "olives"
  → 3 < 600 → FAIL ✗
  → REJECT candidate
  telemetry["sodium_gate_blocks"] += 1
```

**Result**:
- Canned olives selected (115 kcal/100g)
- Raw olives rejected (prevented ~50 kcal error)

---

## 🚀 Integration with Previous Work

### Phase 1 Improvements (Implemented Earlier):
1. ✅ Evaluation aggregator tool
2. ✅ Method aliases (broiled, toasted, charred, air-fried)
3. ✅ Hash browns + home fries oil profiles
4. ✅ Salad greens canonicalization
5. ✅ Sodium gate function + config

### Phase 2 Improvements (This Session):
6. ✅ Stricter cooked SR/Legacy gate (hard-gate when raw Foundation exists)
7. ✅ Sodium gate integration (into search_best_match)
8. ✅ Enhanced telemetry tracking (eval aggregator)
9. ✅ Feature flag system extension

### Previous Sessions:
- **Mass-Only Enhancements** (9 phases): Alignment enrichers, form inference, sparse-signal scoring, color enforcement
- **Advanced Fixes** (6 P0/P1 fixes): Class synonyms, egg whites/yolk, corn kernel/flour, plausibility bands

**Combined Impact**: Comprehensive mass-only pipeline with:
- Multi-stage alignment (Stage 2 first, stricter gates)
- Method resolution (synonyms + aliases + inference)
- Multiple validation layers (plausibility + sodium + processing + macro gates)
- Accurate cooking transformations (oil uptake + macro retention + moisture changes)

---

## 📝 Usage Guide

### For Engineers:

**Enabling/Disabling Stricter Gate**:
```bash
# Enable (default)
export PREFER_RAW_FOUNDATION_CONVERT=true

# Disable for A/B testing
export PREFER_RAW_FOUNDATION_CONVERT=false
```

**Checking Telemetry in Evaluation**:
```python
# In evaluation JSON output:
{
  "items": [
    {
      "predicted_name": "hash browns",
      "provenance": {
        "alignment_stage": "stage2_raw_convert",
        "conversion_applied": true,
        "method": "hash_browns",
        "method_reason": "conversion_config"
      },
      "telemetry": {
        "oil_uptake_g_per_100g": 11.5,
        "sodium_gate_blocks": 0,
        "sodium_gate_passes": 0,
        "stage1_blocked_raw_foundation_exists": 1
      }
    }
  ]
}
```

**Running Evaluation with Telemetry**:
```bash
# Run evaluation (produces JSON)
python run_evaluation.py --output results.json

# Analyze with telemetry
python tools/eval_aggregator.py results.json --verbose
```

### Debugging:

**Log Messages to Look For**:
```
[ALIGN] Stage 1 blocked: raw Foundation exists for potato_russet, prefer Stage 2 (raw + convert)
[ALIGN] Rejected Olives, raw: sodium_gate_fail_olives_3mg_below_600mg
[ALIGN] Sodium gate passed: sodium_gate_pass_olives_735mg
```

**Telemetry Counters**:
- High `stage1_blocked_raw_foundation_exists` → Stricter gate working
- High `sodium_gate_blocks` for pickled items → Gate preventing misalignment
- High `conversion_applied_count` → Conversion layer "unmissable"

---

## 🎓 Key Learnings

1. **Hard Gates Work**: Blocking Stage 1 when raw Foundation exists forces conversion path
2. **Telemetry Essential**: Tracking conversion application reveals pipeline behavior
3. **Feature Flags Critical**: Allow A/B testing and gradual rollout
4. **Integration Matters**: Sodium gate only effective when integrated into scoring pipeline
5. **Alignment Stage Distribution**: Stage 2 should dominate (≥60%) for clean alignments

---

## ✅ Completion Checklist

### Phase 2 (Complete):
- [x] Stricter cooked SR/Legacy gate implemented
- [x] Feature flag `prefer_raw_foundation_convert` added
- [x] Sodium gate integrated into search_best_match
- [x] Enhanced telemetry in eval aggregator
- [x] Telemetry output includes conversion, sodium gates, stages
- [x] 2 new tests added and passing (34/34 total)
- [x] Documentation complete

### Ready for Validation:
- [ ] Run 413-image evaluation to measure impact
- [ ] Verify conversion_hit_rate ≥65%
- [ ] Verify top1_name_alignment ≥75-78%
- [ ] Verify calorie_MAPE ≤20%
- [ ] Verify branded_fallback_rate ≤5%
- [ ] Analyze telemetry for stage distribution

**Status**: ✅ **Phase 2 COMPLETE** - Ready for evaluation

---

## 🔗 Related Documentation

- [CONVERSION_LAYER_IMPROVEMENTS.md](CONVERSION_LAYER_IMPROVEMENTS.md) - Phase 1 documentation
- [ADVANCED_ALIGNMENT_FIXES.md](ADVANCED_ALIGNMENT_FIXES.md) - Previous advanced fixes
- [MASS_ONLY_ENHANCEMENT_SUMMARY.md](MASS_ONLY_ENHANCEMENT_SUMMARY.md) - Mass-only mode enhancements

---

**Next Recommended Action**: Run 413-image evaluation with all Phase 1 + Phase 2 improvements to validate:
1. Conversion hit rate improvement (target ≥65%)
2. Sodium gating effectiveness (olives, pickles correctly aligned)
3. Fried food accuracy (hash browns, home fries with oil uptake)
4. Stage distribution (Stage 2 should be ≥60%)

```bash
python tools/eval_aggregator.py ../tempPipeline10-25-920/results/gpt_5_302images_20251025_153955.json --verbose
```
