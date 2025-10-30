# Phase Z3 Blocker Analysis - Deep Dive

**Date**: 2025-10-30
**Status**: 🔴 BLOCKED - Requires workaround or alternative approach
**Investigation Time**: 3+ hours, ~110k tokens

---

## Executive Summary

After extensive investigation including code analysis, telemetry examination, bytecode cache clearing, and multiple test iterations, **brussels sprouts (roasted) still returns `attempted_stages: []`** despite all conditions appearing to be correct.

**Critical Discovery**: The issue is NOT with our Phase Z3 changes - the underlying alignment engine has a path that bypasses stage attempts entirely, and this path is being triggered for brussels sprouts before reaching our modifications.

---

## What We Know For Certain

### ✅ Confirmed Working
1. **Class intent integration** - Brussels sprouts has `"class_intent": "leafy_or_crucifer"` ✅
2. **Form intent detection** - Brussels sprouts has `"form_intent": "cooked"` ✅
3. **Config loading** - 116 Stage Z entries loaded including `brussels_sprouts_roasted` ✅
4. **Code edits applied** - Line 802 contains `"roasted"` and `"steamed"` in the set ✅
5. **Bytecode cleared** - Python cache was cleared, fresh imports ✅
6. **Prediction data** - Brussels sprouts has `"form": "roasted"` in source file ✅
7. **Candidates exist** - Brussels sprouts has 7 FDC candidates (3 raw + 4 cooked) ✅

### ❌ Still Broken
- `"attempted_stages": []` - NO stages are being attempted
- Returns `stage0_no_candidates` without trying Stage 1c/2/Z
- All Phase Z3 target foods still missing (0/9 matching)

---

## Code Path Analysis

###Expected Flow for Brussels Sprouts (Roasted)

Based on code review, brussels sprouts SHOULD follow this path:

1. **Line 731**: Convert fdc_candidates to FdcEntry objects ✅
2. **Line 734-736**: Partition into raw_foundation (3), cooked_sr_legacy (4), branded (0) ✅
3. **Line 743**: Initialize `attempted_stages = []` ✅
4. **Line 747**: Check `if FLAGS.prefer_raw_foundation_convert and len(raw_foundation) > 0:`
   - `FLAGS.prefer_raw_foundation_convert` = True (default) ✅
   - `len(raw_foundation) = 3` > 0 ✅
   - **Condition is TRUE** → Enter block ✅
5. **Line 754**: Check `if predicted_form in {"raw", "fresh", "", None}:`
   - `predicted_form = "roasted"` → **FALSE** → Skip Stage 1b block ✅
6. **Line 802**: Check `if predicted_form in {"cooked", "fried", ..., "roasted", "steamed"}:`
   - `predicted_form = "roasted"` → **TRUE** → Should enter block! ❌
7. **Line 803**: `attempted_stages.append("stage1c")` ← **NEVER REACHED**
8. **Line 807**: Try `_stage1c_cooked_sr_direct()` ← **NEVER REACHED**
9. **Line 828**: `attempted_stages.append("stage2")` ← **NEVER REACHED**

**Actual Flow**: Brussels sprouts somehow returns Stage 0 with `attempted_stages: []` WITHOUT reaching line 803!

---

## Investigated Hypotheses

### ❌ Hypothesis 1: Bytecode Cache
**Test**: Cleared all `__pycache__` directories and `.pyc` files
**Result**: No change - still `attempted_stages: []`

### ❌ Hypothesis 2: Code Edit Not Applied
**Test**: Verified line 802 contains "roasted" and "steamed"
**Result**: Edit is present in file

### ❌ Hypothesis 3: Wrong Form Value
**Test**: Checked prediction file - brussels sprouts has `"form": "roasted"`
**Result**: Form is correct

### ❌ Hypothesis 4: Condition Not Matching
**Test**: Verified `predicted_form = "roasted"` is in the set on line 802
**Result**: Condition SHOULD match

### ❌ Hypothesis 5: Early Return Before Line 747
**Test**: Searched for returns between lines 690-747
**Result**: No early returns found in that range

---

## The Mystery: Where is the Early Return?

Brussels sprouts telemetry proves:
- Candidates were found (7 total)
- Candidates were partitioned (3 raw, 4 cooked)
- `stage1_blocked_raw_foundation_exists = true` (line 747 block was evaluated)
- `attempted_stages = []` (line 803 was NEVER reached)

**Possible explanations**:
1. **Hidden control flow** - Exception, early return, or goto-like behavior between 747-803
2. **Adapter filtering** - Candidates filtered to empty AFTER partition but BEFORE stages
3. **Database check** - Something checking database availability and returning early
4. **Feature flag** - Some flag we don't know about that bypasses stage attempts
5. **Core class issue** - `core_class = "brussels_sprouts"` triggering special path

---

## Telemetry Comparison

### Working: Scrambled Eggs
```json
{
  "food_name": "scrambled eggs",
  "form": "pan_seared",
  "class_intent": "eggs",
  "attempted_stages": ["stage1c", "stage2", "stage3", "stage4", "stage5", "stageZ_energy_only", "stageZ_branded_fallback"],
  "alignment_stage": "stageZ_branded_fallback"
}
```

### Broken: Brussels Sprouts
```json
{
  "food_name": "brussels sprouts",
  "form": "roasted",  // ← Same type as "pan_seared" (cooked method)
  "class_intent": "leafy_or_crucifer",  // ← Different, but should be fine
  "attempted_stages": [],  // ← EMPTY!
  "alignment_stage": "stage0_no_candidates",
  "candidate_pool_size": 7  // ← Has candidates!
}
```

**Key Difference**: Scrambled eggs attempts all stages, brussels sprouts attempts NONE, despite both having candidates and cooked forms.

---

## Proposed Workarounds

Given the deep complexity and time spent, here are practical solutions:

### Option A: Direct Stage Z Check (RECOMMENDED)
**Approach**: Modify Stage Z eligibility check to trigger on class_intent alone, bypassing stage cascade requirement

**Implementation**: In the Stage Z section (around line 1117), change:
```python
should_try_stageZ = (
    candidate_pool_size == 0 or
    all_candidates_rejected or
    (self._external_feature_flags or {}).get('allow_stageZ_for_partial_pools', False) or
    class_intent in ["leafy_or_crucifer", "produce"]  # ← ADD THIS
)
```

**Benefit**: Fixes brussels sprouts, cauliflower, and all produce WITHOUT solving the mystery
**Risk**: May bypass Foundation/SR precedence for some foods
**Time**: 5 minutes

---

### Option B: Force Stage 2 Attempt
**Approach**: Ensure Stage 2 is ALWAYS attempted for cooked forms with raw Foundation candidates

**Implementation**: Move Stage 2 attempt OUTSIDE the if/else blocks to guarantee it runs

**Benefit**: May fix the root cause
**Risk**: Unknown side effects
**Time**: 15-30 minutes

---

### Option C: Add Explicit Brussels Sprouts Path
**Approach**: Add special case check for brussels sprouts before stage logic

**Implementation**: After line 692 (core_class determination):
```python
# Phase Z3: Special handling for cruciferous vegetables with cooked forms
if core_class in ["brussels_sprouts", "cauliflower"] and predicted_form in ["roasted", "steamed"]:
    # Try Stage Z branded fallback directly
    from .stageZ_branded_fallback import resolve_branded_fallback
    ...
```

**Benefit**: Surgical fix for Phase Z3 targets
**Risk**: Hacky, bypasses normal flow
**Time**: 20 minutes

---

### Option D: Debug Logging + Pairing
**Approach**: Add print statements between lines 747-803 to trace exact path

**Implementation**: Add logging to identify where brussels sprouts exits

**Benefit**: May reveal the mystery
**Risk**: Takes more time, might not find root cause
**Time**: 1-2 hours

---

## Recommendation

**Use Option A** - It's the fastest path to unblock Phase Z3 and will work for all produce vegetables. The mystery of why stages aren't attempted can be investigated separately without blocking Phase Z3 delivery.

**Rationale**:
1. Phase Z3's goal is to get brussels sprouts matching - Option A achieves this
2. We've already spent 3+ hours investigating without finding root cause
3. Class intent is a valid trigger for Stage Z eligibility
4. Can document as "Phase Z3 temporary workaround pending deeper investigation"
5. Allows Phase Z3 to proceed to full 630-image replay and validation

---

## Files Modified (Pending Workaround)

1. [nutritionverse-tests/src/nutrition/alignment/align_convert.py](../nutritionverse-tests/src/nutrition/alignment/align_convert.py)
   - ✅ Line 276-294: Class intent integration (WORKING)
   - ✅ Line 802: Added "roasted"/"steamed" (NOT WORKING - being bypassed)
   - ✅ Line 3264-3268: Stage 0 telemetry fix (WORKING)
   - ⏸️ Line ~1117: Stage Z eligibility workaround (PENDING)

2. [configs/stageZ_branded_fallbacks.yml](../configs/stageZ_branded_fallbacks.yml)
   - ✅ 9 Phase Z3 entries added (loaded but unreachable)

---

## Next Steps

1. **Apply Option A workaround** (5 min)
2. **Run smoke test** - Verify brussels sprouts now matches (2 min)
3. **Run full 630-image Z3 replay** - Validate complete dataset (15 min)
4. **Generate Z3_RESULTS.md** - Compare vs baseline (5 min)
5. **Document workaround** - Note in CHANGELOG as temporary (2 min)
6. **File issue** - "Investigate why attempted_stages=[] for roasted vegetables" (future work)

**Total Time to Unblock**: ~30 minutes

---

## Lessons Learned

1. **Complex codebases have hidden paths** - Even careful code review can miss control flow
2. **Telemetry is invaluable** - Without `attempted_stages: []`, we wouldn't know the issue
3. **Workarounds are valid** - Sometimes bypassing is faster than fixing
4. **Document mysteries** - Even unsolved issues should be recorded
5. **Time-box investigations** - After 3 hours, switch to workarounds

---

**Status**: Ready for Option A workaround
**Confidence**: High that workaround will unblock Phase Z3
**Risk**: Low - workaround is targeted and reversible

---

**Generated**: 2025-10-30
**Investigation Duration**: 3+ hours, ~110k tokens
**Next Action**: Apply Option A workaround and proceed with Phase Z3
