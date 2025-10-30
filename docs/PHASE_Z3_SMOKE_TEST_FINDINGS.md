# Phase Z3 Smoke Test - Critical Findings

**Date**: 2025-10-30
**Test**: 10 predictions, 36 foods
**Config**: 116 Stage Z fallback entries loaded
**Result**: ⚠️ **CRITICAL ISSUE DISCOVERED** - Stage Z entries not being attempted

---

## Executive Summary

**Critical Finding**: Added 9 Phase Z3 Stage Z fallback entries successfully loaded (116 total config entries), but **Stage Z is not being attempted** for foods like "brussels sprouts roasted" even though fallback entries exist.

**Root Cause**: Brussels sprouts has 7 Foundation/SR candidates (3 raw + 4 cooked), but **all 7 are rejected** during scoring. Instead of continuing to Stage Z, the engine stops at Stage 0 with `attempted_stages: []`.

**Impact**: Phase Z3 entries (brussels_sprouts_roasted, sweet_potato_roasted, cauliflower_roasted, etc.) are **completely unused** in current implementation.

---

## Smoke Test Results

### Overall Metrics
| Metric | Value |
|--------|-------|
| Total foods | 36 |
| Stage Z usage | 4 (11.1%) |
| Stage 0 misses | 9 (25.0%) |
| Config entries loaded | 116 ✅ |

### Stage Z Usage Breakdown
- **scrambled eggs** → `stageZ_branded_fallback` ✅ (existing config)
- **broccoli florets** → `stageZ_branded_fallback` ✅ (existing config)
- **steak** → `stageZ_energy_only` ✅ (energy proxy)
- **Total**: 4 foods using Stage Z

### Phase Z3 Target Foods - All MISSING ❌
- **brussels sprouts (roasted)** → Stage 0 (NOT attempted)
- **brussels sprouts (steamed)** → Stage 0 (NOT attempted)
- **sweet potato (roasted)** → Stage 0 (NOT attempted)
- **cauliflower (steamed)** → Stage 0 (NOT attempted)
- **bell pepper (raw)** → Stage 0 (NOT attempted)

---

## Critical Issue: Stage Z Not Attempted

### Brussels Sprouts Telemetry Analysis

**Food**: brussels sprouts (roasted)

**Telemetry**:
```json
{
  "alignment_stage": "stage0_no_candidates",
  "method": "roasted",
  "candidate_pool_size": 7,
  "candidate_pool_raw_foundation": 3,
  "candidate_pool_cooked_sr_legacy": 4,
  "candidate_pool_branded": 0,
  "attempted_stages": [],  // <-- CRITICAL: NO STAGES ATTEMPTED
  "variant_chosen": "brussels sprouts",
  "search_variants_tried": 3,
  "foundation_pool_count": 7
}
```

**What This Means**:
1. ✅ Config loaded successfully (116 entries including `brussels_sprouts_roasted`)
2. ✅ Foundation/SR database found 7 candidates for "brussels sprouts"
   - 3 raw Foundation entries
   - 4 cooked SR Legacy entries
3. ❌ **All 7 candidates rejected during scoring**
4. ❌ **Engine stopped at Stage 0** - did NOT attempt Stage Z

### Comparison: Successful Stage Z Usage (Scrambled Eggs)

**Food**: scrambled eggs (pan_seared)

**Telemetry**:
```json
{
  "alignment_stage": "stageZ_branded_fallback",
  "attempted_stages": [
    "stage1c",
    "stage2",
    "stage3",
    "stage4",
    "stage5",
    "stageZ_energy_only",
    "stageZ_branded_fallback"
  ],  // <-- SUCCESS: All stages attempted, Stage Z succeeded
  "stage1_all_rejected": true,
  "had_candidates_to_score": true,
  "stageZ_branded_fallback": {
    "reason": "not_in_foundation_sr",
    "canonical_key": "scrambled_egg",
    "brand": "Generic",
    "fdc_id": 450876,
    "source": "existing_config"
  }
}
```

**Why This Worked**:
1. Foundation/SR had 1 candidate
2. Candidate was rejected (`stage1_all_rejected: true`)
3. **Engine attempted all stages** including Stage Z
4. Stage Z fallback matched successfully

---

## Root Cause Analysis

### Why Brussels Sprouts Fails

**Hypothesis 1**: Candidate pool exists but scoring fails early, engine doesn't continue to Stage Z

**Evidence**:
- `candidate_pool_size: 7` (has candidates)
- `attempted_stages: []` (no stages attempted)
- Contrast with scrambled eggs: `attempted_stages: ["stage1c", ...]` (all stages attempted)

**Hypothesis 2**: Stage Z activation requires specific conditions not met by brussels sprouts

**Possible Conditions**:
1. `allow_stageZ_for_partial_pools` flag (✅ TRUE in config)
2. `class_intent` must be set (❓ may be missing for brussels sprouts)
3. Specific threshold or guard preventing Stage Z attempt

### Why Scrambled Eggs Succeeds

**Evidence**:
- `class_intent: "eggs"` (✅ set)
- `guardrail_eggs_applied: true` (✅ special handling)
- `attempted_stages: [all stages]` (✅ full cascade)
- `had_candidates_to_score: true` (✅ candidates found but rejected)

**Key Difference**: Scrambled eggs has `class_intent` and special guardrails that may trigger full stage cascade including Stage Z.

---

## Proposed Fixes

### Option 1: Add Class Intent to Produce Vegetables ⭐ RECOMMENDED

**Implementation**: Modify `_is_produce_vegetable()` helper to set `class_intent = "produce"` for vegetables, enabling Stage Z eligibility.

**Location**: `nutritionverse-tests/src/nutrition/alignment/align_convert.py` (already added in Phase Z3)

**Status**: ✅ Helper function exists, ⏸️ NOT integrated into scoring logic

**Expected Impact**: Brussels sprouts, cauliflower, etc. would get `class_intent = "produce"`, triggering full stage cascade → Stage Z.

---

### Option 2: Modify Stage Z Activation Logic

**Implementation**: Change Stage Z activation to attempt when `candidate_pool_size > 0` BUT `stage1_all_rejected = true`.

**Location**: `nutritionverse-tests/src/nutrition/alignment/align_convert.py` - Stage Z activation logic

**Risk**: ⚠️ May violate Foundation/SR precedence guardrail if not careful

**Status**: ⏸️ Requires careful analysis of alignment engine code

---

### Option 3: Improve Foundation/SR Scoring for Roasted Vegetables

**Implementation**: Adjust scoring threshold or add bonus for roasted vegetables when matching cooked SR entries.

**Location**: `nutritionverse-tests/src/nutrition/alignment/align_convert.py` - Scoring logic

**Benefit**: May fix issue at source (Foundation/SR matching), avoiding need for Stage Z

**Status**: ⏸️ Requires investigation of why 4 cooked SR brussels sprouts entries are being rejected

---

## Immediate Next Steps

### 1. Investigate Stage Z Activation Logic 🔍
**Goal**: Understand exactly when Stage Z is attempted vs. skipped

**Actions**:
1. Read alignment engine code around Stage Z activation
2. Identify conditions that trigger Stage Z attempt
3. Document guardrails and thresholds

**Priority**: **HIGH** - blocking Phase Z3 success

---

### 2. Integrate Class Intent Helper 🔧
**Goal**: Wire `_is_produce_vegetable()` into scoring logic to set `class_intent = "produce"`

**Actions**:
1. Find where `class_intent` is set in alignment engine
2. Add call to `_is_produce_vegetable()` for vegetables
3. Test with brussels sprouts smoke test

**Priority**: **HIGH** - likely fixes issue

---

### 3. Test Integration with Brussels Sprouts 🧪
**Goal**: Verify that adding `class_intent = "produce"` triggers Stage Z

**Actions**:
1. Run smoke test with integrated class intent
2. Check telemetry for `attempted_stages` including Stage Z
3. Verify brussels sprouts matches `brussels_sprouts_roasted` fallback

**Priority**: **HIGH** - validation step

---

## Phase Z3 Impact Assessment

### Expected vs. Actual Results

**Expected** (from Phase Z3 plan):
- Stage Z usage: 14% → ≥20% (+128 foods)
- Miss rate: 28% → ≤25% (-65 misses)
- New Z3 entries: 9 foods (brussels sprouts, sweet potato, etc.) **all matching**

**Actual** (smoke test):
- Stage Z usage: 11.1% (4/36 foods) - **BELOW baseline**
- Miss rate: 25.0% (9/36 foods) - **AT target but with different foods**
- New Z3 entries: **0 foods matching** ❌

**Conclusion**: Phase Z3 implementation is **incomplete**. Config entries added successfully, but integration logic missing.

---

## Recommendations

### Immediate Actions (Before Full Replay)

1. ✅ **DO NOT run full 630-image Z3 replay yet** - will waste time without integration
2. 🔧 **Integrate class intent helper** - wire `_is_produce_vegetable()` into scoring
3. 🧪 **Re-run smoke test** - validate integration works
4. 📊 **Analyze updated telemetry** - confirm `attempted_stages` includes Stage Z
5. ✅ **Verify Z3 entries match** - confirm brussels sprouts, sweet potato, etc. match

### Medium-term Actions (Phase Z3 Completion)

6. 🔍 **Investigate Foundation/SR scoring** - understand why cooked SR rejected
7. 📝 **Document Stage Z activation logic** - add to PHASE_Z3_PLAN.md
8. 🧪 **Add regression tests** - test that brussels sprouts triggers Stage Z
9. ✅ **Run full 630-image Z3 replay** - only after smoke test passes
10. 📊 **Generate Z3_RESULTS.md** - compare vs. baseline

---

## Files Referenced

### Code
- [nutritionverse-tests/src/nutrition/alignment/align_convert.py](../nutritionverse-tests/src/nutrition/alignment/align_convert.py) - Alignment engine + Phase Z3 helpers
- [configs/stageZ_branded_fallbacks.yml](../configs/stageZ_branded_fallbacks.yml) - 116 Stage Z entries (✅ loaded)

### Results
- `/tmp/replay_z3_smoke/results.jsonl` - Smoke test alignment results
- `/tmp/replay_z3_smoke/telemetry.jsonl` - Detailed telemetry showing Stage 0 misses
- `/tmp/replay_z3_smoke/replay_manifest.json` - Replay metadata

### Documentation
- [docs/PHASE_Z3_PLAN.md](PHASE_Z3_PLAN.md) - Original Phase Z3 plan
- [docs/RUNBOOK.md](RUNBOOK.md) - Replay commands
- [CONTINUE_HERE.md](../CONTINUE_HERE.md) - Updated with Z3 status

---

## Key Learnings

1. **Config loading ≠ Config usage**: Just because 116 entries loaded doesn't mean they're being used
2. **Telemetry is critical**: `attempted_stages: []` revealed the real issue
3. **Class intent matters**: Foods with `class_intent` (eggs) reach Stage Z, foods without (vegetables) don't
4. **Smoke tests are valuable**: Caught critical issue before wasting time on full 630-image replay

---

**Status**: 🔴 **BLOCKED** - Phase Z3 implementation incomplete, integration required
**Next Action**: Integrate `_is_produce_vegetable()` into class intent logic
**Priority**: **HIGH** - blocking Phase Z3 success

---

**Generated**: 2025-10-30
**Test Run**: /tmp/replay_z3_smoke/
**Config**: 116 Stage Z fallback entries loaded
