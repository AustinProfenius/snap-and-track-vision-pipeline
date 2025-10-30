# Phase Z3: Precision Coverage Improvements

**Date**: 2025-10-30
**Status**: In Progress
**Owner**: Alignment Team

---

## Objective

Raise Stage Z usage to ≥20% and drop miss rate to ≤25% on the 630-image prediction replay while **preserving Foundation/SR → Stage 2 precedence**.

---

## Current Baseline (Pre-Z3)

**Source**: `runs/replay_630_withconfigs/`

| Metric | Value |
|--------|-------|
| Total foods | 1,818 |
| Stage 0 (misses) | 539 (29.6%) |
| Stage Z usage | 264 (14.5%) |

**Top Missing Foods**:
- Roasted vegetables: 143 instances (sweet potato, potatoes, brussels sprouts, cauliflower)
- Proteins/starches: 28 instances (egg whites, rice, hash browns, bagels)
- Raw vegetables: 37 instances (bell pepper, corn, zucchini, yellow squash, asparagus)

---

## Phase Z3 Targets

| Metric | Current | Target | Delta |
|--------|---------|--------|-------|
| Stage Z usage | 264 (14.5%) | 363+ (20%+) | +99 foods (+5.5%) |
| Miss rate | 539 (29.6%) | ≤454 (25%) | -85 misses (-4.6%) |

---

## Key Guardrails

### 1. Preserve Foundation/SR Precedence
**Principle**: Foundation/SR (1b/1c) → Stage 2 (conversion) → Stage Z (verified) → Stage Z (generic)

**Never**:
- Let Stage Z "win" by default if Foundation raw + Stage 2 path exists
- Force alignment paths based on form inference
- Bypass Stage 2 when Foundation raw is available

### 2. Advisory Form Inference Only
**Score adjustments**: +0.05 for form match, -0.10 for form conflict
**Application**: AFTER base similarity scoring, not before
**No path forcing**: Form inference is a hint, not a mandate

### 3. Egg Whites: Foundation/SR First
**Preferred**: Foundation/SR raw egg white + Stage 2 conversion
**Stage Z**: Only if Foundation/SR + Stage 2 fails

### 4. Complex Dishes: Phase Z4
**Deferred**: Pizza, chia pudding, other multi-component dishes
**Approach**: Add to `PHASE_Z4_BACKLOG.md`, don't add broad fallbacks

---

## Implementation Scope

### Task 1: Advisory Cooked/Raw Form Detection
**File**: `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

**Added**:
- `_infer_cooked_form_from_tokens()` - Detect "roasted", "baked", "grilled", etc.
- Form inference returns: "cooked", "raw", or None (ambiguous)

**Integration**: Small score adjustments in alignment scoring logic
- Match: +0.05 (e.g., "roasted potato" + SR cooked entry)
- Conflict: -0.10 (e.g., "raw chicken" + SR cooked entry)

**Impact**: Better scoring for 143 roasted vegetable instances

---

### Task 2: Vegetable Class Intent
**File**: `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

**Added**:
- `_PRODUCE_VEGETABLES` list: 10 vegetables (yellow squash, zucchini, asparagus, etc.)
- `_is_produce_vegetable()` - Check if food matches vegetable list

**Logic**: When Foundation/SR fails for these foods → Stage Z eligible (subject to feature flags)

**Impact**: Handle 37 vegetable instances lacking Foundation/SR entries

---

### Task 3: Stage Z Verified Fallbacks
**File**: `configs/stageZ_branded_fallbacks.yml`

**Added 9 entries** (with FDC validation):
1. `egg_white` - FDC 748967 (48-58 kcal)
2. `potato_roasted` - FDC 170032 (85-135 kcal)
3. `sweet_potato_roasted` - FDC 168482 (85-120 kcal)
4. `rice_white_cooked` - FDC 168878 (110-145 kcal)
5. `rice_brown_cooked` - FDC 168876 (108-130 kcal)
6. `brussels_sprouts_roasted` - FDC 170379 (35-60 kcal)
7. `cauliflower_roasted` - FDC 170390 (20-50 kcal)
8. `hash_browns` - FDC 170033 (140-230 kcal)
9. `bagel_plain` - FDC 172676 (245-285 kcal)

**Validation**: All FDC IDs from Foundation/SR Legacy databases

**Impact**: Address 236+ missing protein/starch/vegetable instances

---

## Out of Scope (Phase Z4)

**Complex Dishes** (30 instances):
- Cheese pizza (21)
- Pizza (9)
- Chia pudding (6)

**Why deferred**: Require multi-component decomposition or specialty verified entries

**Approach**: Document in `docs/PHASE_Z4_BACKLOG.md` for future phase

---

## Acceptance Criteria

✅ **Stage Z usage ≥ 20%** (≥363 foods)
✅ **Miss rate ≤ 25%** (≤454 misses)
✅ **Tests ≥ 6 and all passing**
✅ **Foundation/SR precedence respected** (Stage 2 preferred when viable)
✅ **Documentation complete** (PLAN, RUNBOOK, CHANGELOG, EVAL_BASELINES, Z4_BACKLOG)
✅ **Auto-generated run report** with TL;DR + deltas

---

## Validation Approach

1. **Run replay**: 630-image batch with Z3 changes
2. **Analyze results**: Compare with baseline (`runs/replay_630_withconfigs/`)
3. **Generate report**: Auto-create `Z3_RESULTS.md` with metrics + deltas
4. **Update docs**: Point `CONTINUE_HERE.md` to latest run

**Command**:
```bash
python nutritionverse-tests/entrypoints/replay_from_predictions.py \
  --in nutritionverse-tests/results/gpt_5_630images_20251027_151930.json \
  --out runs/replay_z3_$(date +%Y%m%d_%H%M%S) \
  --config-dir configs/ --schema auto
```

---

## Files Modified

| File | Lines | Changes |
|------|-------|---------|
| `align_convert.py` | +60 | Form inference + vegetable intent |
| `stageZ_branded_fallbacks.yml` | +115 | 9 new fallback entries |
| `analyze_batch_results.py` | +70 | Baseline comparison method |
| `test_prediction_replay.py` | +45 | 2 new tests |
| **Documentation** | +600 | 6 new docs |

**Total**: ~890 lines (code + tests + docs)

---

## Timeline

| Task | Duration | Status |
|------|----------|--------|
| Form detection helpers | 20 min | ✅ Complete |
| Vegetable intent | 10 min | ✅ Complete |
| Stage Z fallbacks | 30 min | ✅ Complete |
| Documentation suite | 40 min | 🔄 In Progress |
| Baseline comparison | 30 min | ⏸️ Pending |
| Test additions | 30 min | ⏸️ Pending |
| Validation replay | 15 min | ⏸️ Pending |
| Results analysis | 15 min | ⏸️ Pending |

**Total**: ~3 hours

---

---

## Phase Z3.1: Stabilization & Infrastructure (2025-10-30)

**Objective**: Stabilize Z3 foundation, resolve blockers, and add CI testing infrastructure.

### Tasks Completed

1. ✅ **Analyzer Baseline Alignment** - Schema normalization for accurate delta comparison
2. ✅ **Feature Flag Enforcement** - Assertions to prevent silent feature_flags=None failures
3. ✅ **Stage Z Scoring Guard** - Preventive guard for form bonus overshadowing
4. ✅ **Mini-Replay Test Fixture** - 15-food CI test running in <30s
5. ✅ **Telemetry Slimming** - --compact-telemetry flag to reduce output size

### Next Steps

1. Run full 630-image Z3.1 validation replay
2. Investigate brussels sprouts early return blocker (Stage 0 with empty attempted_stages)
3. Generate Z3_1_RESULTS.md with baseline comparison
4. Review Phase Z3 targets vs actuals

---

**See also**:
- `docs/RUNBOOK.md` - Execution commands
- `docs/EVAL_BASELINES.md` - Baseline definitions
- `docs/PHASE_Z4_BACKLOG.md` - Deferred items
- `docs/PHASE_Z3.1_IMPLEMENTATION_SUMMARY.md` - Z3.1 implementation details
