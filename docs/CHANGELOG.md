# Changelog

All notable changes to the Snap & Track alignment pipeline.

**Format**: [Date] Phase Name - Description

---

## [2025-10-30] Phase Z3 - Precision Coverage Improvements

### Added
- **Advisory cooked/raw form inference** (`align_convert.py`)
  - New function: `_infer_cooked_form_from_tokens()` - Detect cooking methods in food names
  - Returns: "cooked" (roasted/baked/grilled/etc.), "raw", or None
  - **Application**: Small score adjustments (+0.05 match, -0.10 conflict) AFTER base scoring
  - **Guardrail**: Advisory only, never forces paths or bypasses Stage 2

- **Vegetable class intent** (`align_convert.py`)
  - New list: `_PRODUCE_VEGETABLES` - 10 vegetables (yellow squash, zucchini, asparagus, etc.)
  - New function: `_is_produce_vegetable()` - Check if food matches list
  - **Impact**: Makes Stage Z eligible for vegetables when Foundation/SR fails

- **Stage Z verified fallbacks** (`configs/stageZ_branded_fallbacks.yml`)
  - Added 9 new entries with FDC validation:
    1. `egg_white` (FDC 748967, 48-58 kcal)
    2. `potato_roasted` (FDC 170032, 85-135 kcal)
    3. `sweet_potato_roasted` (FDC 168482, 85-120 kcal)
    4. `rice_white_cooked` (FDC 168878, 110-145 kcal)
    5. `rice_brown_cooked` (FDC 168876, 108-130 kcal)
    6. `brussels_sprouts_roasted` (FDC 170379, 35-60 kcal)
    7. `cauliflower_roasted` (FDC 170390, 20-50 kcal)
    8. `hash_browns` (FDC 170033, 140-230 kcal)
    9. `bagel_plain` (FDC 172676, 245-285 kcal)
  - All FDC IDs from Foundation/SR Legacy databases
  - Total fallbacks: 107 → 116 (+9)

- **Documentation suite**
  - `docs/PHASE_Z3_PLAN.md` - Goals, targets, scope, guardrails
  - `docs/RUNBOOK.md` - Exact commands for replays and analysis
  - `docs/EVAL_BASELINES.md` - Baseline definitions and how to add more
  - `docs/PHASE_Z4_BACKLOG.md` - Complex dishes deferred to Phase Z4
  - This file: `docs/CHANGELOG.md`

- **Tests** (`nutritionverse-tests/tests/test_prediction_replay.py`)
  - Total tests: 4 → 6 (+2)
  - New: `test_intent_cooked_bonus()` - Verify advisory score adjustments
  - New: `test_stageZ3_fallback_coverage()` - Verify Z3 entries load and trigger

### Changed
- `align_convert.py`: Added Phase Z3 helper functions (60 lines)
- `stageZ_branded_fallbacks.yml`: Extended with 9 entries (115 lines)
- `test_prediction_replay.py`: Added 2 tests (45 lines)

### Metrics (Target vs Actual)
| Metric | Baseline | Target | Actual | Status |
|--------|----------|--------|--------|--------|
| Stage Z usage | 14.5% (264) | ≥20% (363+) | TBD | 🔄 Pending Z3 replay |
| Miss rate | 29.6% (539) | ≤25% (454) | TBD | 🔄 Pending Z3 replay |
| Tests passing | 4/4 | 6/6 | 6/6 | ✅ Complete |
| Fallbacks | 107 | 116+ | 116 | ✅ Complete |

### Deferred to Phase Z4
- Complex multi-component dishes (pizza, chia pudding)
- See `docs/PHASE_Z4_BACKLOG.md` for details

---

## [2025-10-30] Config Wiring & Z2 Activation

### Added
- **Config loading in replay** (`entrypoints/replay_from_predictions.py`)
  - Auto-initialization of configs from `configs/` directory
  - Print [CFG] summary on startup: fallbacks, feature flags, DB status
  - Hard assertions: Exit if Stage Z usage == 0 on ≥50 predictions

- **Feature flag** (`configs/feature_flags.yml`)
  - New: `allow_stageZ_for_partial_pools: true`
  - Enables Stage Z when Foundation/SR have candidates but all rejected

- **Test suite** (`nutritionverse-tests/tests/test_prediction_replay.py`)
  - 4 tests validating replay functionality
  - Tests: source tracking, config loading, Stage Z usage, miss telemetry

### Changed
- `replay_from_predictions.py`: Complete rewrite (338 lines)
  - Added `--config-dir` CLI argument
  - Trigger auto-init from AlignmentEngineAdapter
  - Hard assertions for Z2 activation
  - Telemetry extraction from foods array

### Metrics
- Stage Z usage: 300/2032 foods (14.8%) ✅
- Config loading: 107 fallbacks, feature flags active ✅
- Tests: 4/4 passing ✅

---

## [2025-10-30] Prediction Replay Implementation

### Added
- **Prediction replay system** - Zero-cost alignment iteration
  - Schema parsers: V1 (GPT-5 batch format), V2 (future)
  - Auto-detection of schema version
  - Entrypoint: `entrypoints/replay_from_predictions.py`
  - Outputs: results.jsonl, telemetry.jsonl, replay_manifest.json

- **Adapter hook** (`alignment_adapter.py`)
  - New method: `run_from_prediction_dict()` - Replay without vision API
  - Reuses existing `align_prediction_batch()` logic

- **Analyzer updates** (`analyze_batch_results.py`)
  - JSONL format support
  - Replay directory structure handling
  - Source detection (prediction_replay vs dataset_metadata)

- **Documentation**
  - `PREDICTION_REPLAY_IMPLEMENTATION.md` - Full implementation guide
  - `PREDICTION_REPLAY_STATUS.md` - Status & metrics

### Metrics
- 630 predictions → 2,140 foods processed in 13 minutes
- Stage Z usage: 300 foods (14.0%)
- Zero vision API calls ($0 vs $31.50-$63.00)

---

## [Earlier] Pre-Documentation Phases

### Phase Z2 - Branded Universal Fallback
- Implemented Stage Z with CSV-verified entries
- Added 107 fallback entries to `stageZ_branded_fallbacks.yml`
- Feature flag: `allow_branded_when_foundation_missing`

### Phase Z1 - Stage 5B Proxy Alignment
- Proxy alignment for classes lacking Foundation/SR entries
- Salad decomposition (caesar salad, greek salad, etc.)
- Energy-only proxies (beef_steak, tuna_steak, etc.)

### Phase 5 - Raw Foundation + Conversion Priority
- Stage 2 runs FIRST (before Stage 1 cooked exact)
- Preferred path: Foundation raw + conversion
- Reduced processing noise from breaded/battered variants

---

## Format Notes

**Entry Structure**:
```markdown
## [Date] Phase Name - Description

### Added
- Feature 1
- Feature 2

### Changed
- File 1: Description
- File 2: Description

### Removed
- Deprecated feature

### Metrics
- Key metric 1
- Key metric 2
```

**Status Indicators**:
- ✅ Complete
- 🔄 In Progress
- ⏸️ Pending
- ❌ Failed/Blocked

---

## See Also

- `docs/PHASE_Z3_PLAN.md` - Current phase details
- `docs/RUNBOOK.md` - How to run replays
- `docs/EVAL_BASELINES.md` - Baseline tracking
- `CONTINUE_HERE.md` - Latest run pointer
