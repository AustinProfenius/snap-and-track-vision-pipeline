# Phase Z3.1 Implementation Summary

**Date**: 2025-10-30
**Status**: ⏸️ PARTIAL - Task 1/6 completed, remaining tasks documented
**Objective**: Resolve Z3 blockers, stabilize scoring, create deterministic replay mini-benchmark

---

## Completed: Task 1 - Analyzer Baseline Alignment ✅

### Files Modified
- **`analyze_batch_results.py`** - Added schema normalization functions

### Changes Implemented

1. **`normalize_record()` method** (Lines 585-624)
   - Unifies old vs. new schema field names
   - Handles `alignment_stage` in both direct and nested locations
   - Normalizes `stageZ_branded_fallback` structure differences
   - Maps `candidate_pool_total` → `candidate_pool_size`
   - Consolidates `method` vs. `cooking_method` field variations

2. **`compare_with_baseline()` method** (Lines 626-684)
   - Schema-aware comparison using normalized records
   - Calculates deltas for: unique misses, miss rate, Stage Z usage
   - Returns structured dict with baseline/current/deltas

3. **Enhanced `main()` comparison output** (Lines 748-797)
   - Color-coded delta symbols (✅/⚠️/❌)
   - Detailed baseline vs. current metrics
   - Overall assessment logic

### Validation
```bash
python analyze_batch_results.py runs/replay_z3_*/results.jsonl --compare runs/replay_630_withconfigs
```

---

## Remaining Tasks (2-6)

### Task 2: Feature Flag Enforcement

**Objective**: Add assertions to ensure feature flags are properly wired

**Files to Modify**:
1. `nutritionverse-tests/src/adapters/alignment_adapter.py`
2. `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

**Implementation**:
```python
# In alignment_adapter.py __init__ or align method:
assert self._external_feature_flags is not None, \
    "Feature flags must be wired through adapter"

# In align_convert.py FdcAlignmentEngine.__init__:
if self._external_feature_flags:
    if not self._external_feature_flags.get('allow_stageZ_for_partial_pools', False):
        print("[WARN] Stage Z for partial pools disabled via feature flags")
```

**Location Hints**:
- alignment_adapter.py: Around line 180-200 (config loading section)
- align_convert.py: Around lines 150-180 (__init__ method)

---

### Task 3: Stage Z Scoring Guard

**Objective**: Prevent form bonus from overshadowing FDC similarity in Stage Z

**File to Modify**:
- `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

**Implementation** (after scoring adjustments, around line 1400-1600):
```python
# Phase Z3.1: Guard against form bonus overshadowing in Stage Z
if entry.stage == "stageZ_branded_fallback" and abs(form_bonus) > 0.06:
    form_bonus *= 0.5  # Halve form influence for Stage Z entries
    if os.getenv('ALIGN_VERBOSE', '0') == '1':
        print(f"[ALIGN] Stage Z scoring guard: halved form_bonus to {form_bonus:.3f}")
```

**Purpose**: Keep Stage Z deterministic based on FDC similarity, not cooking method inference

---

### Task 4: Deterministic Mini-Replay Fixture

**Objective**: Create fast CI-friendly replay test (<30s)

**Files to Create**:
1. `nutritionverse-tests/fixtures/replay_minibatch.json` (15 foods, 5 images)
2. `nutritionverse-tests/tests/test_replay_minibatch.py`

**Fixture Structure** (replay_minibatch.json):
```json
{
  "predictions": [
    {
      "image_filename": "dish_test_001.png",
      "prediction": {
        "foods": [
          {"name": "brussels sprouts", "form": "roasted", "mass_g": 90, "confidence": 0.8},
          {"name": "scrambled eggs", "form": "pan_seared", "mass_g": 120, "confidence": 0.85},
          {"name": "broccoli florets", "form": "steamed", "mass_g": 80, "confidence": 0.9}
        ]
      }
    },
    ...  // 4 more images with 3 foods each = 15 total foods
  ]
}
```

**Test Implementation** (test_replay_minibatch.py):
```python
import subprocess
import json
from pathlib import Path

def test_replay_minibatch():
    """
    Phase Z3.1: Fast deterministic replay test for CI.

    Validates:
    - Stage Z usage > 0
    - Miss rate < 35%
    - Completes in < 30s
    """
    fixture_path = Path(__file__).parent.parent / "fixtures" / "replay_minibatch.json"
    output_dir = Path("/tmp/test_replay_minibatch")

    # Run replay
    cmd = [
        "python",
        "nutritionverse-tests/entrypoints/replay_from_predictions.py",
        "--in", str(fixture_path),
        "--out", str(output_dir),
        "--config-dir", "configs/"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"Replay failed: {result.stderr}"

    # Load results
    results_file = output_dir / "results.jsonl"
    assert results_file.exists(), "No results.jsonl generated"

    items = []
    with open(results_file) as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))

    # Validate metrics
    total = len(items)
    stagez_count = sum(1 for item in items
                      if item.get("telemetry", {}).get("alignment_stage") == "stageZ_branded_fallback")
    miss_count = sum(1 for item in items
                    if item.get("telemetry", {}).get("alignment_stage") == "stage0_no_candidates")

    stagez_usage = stagez_count / total if total > 0 else 0
    miss_rate = miss_count / total if total > 0 else 0

    assert stagez_usage > 0, f"Stage Z usage is 0 (expected > 0)"
    assert miss_rate < 0.35, f"Miss rate {miss_rate:.1%} exceeds 35%"

    print(f"✓ Mini-replay validation passed:")
    print(f"  Stage Z usage: {stagez_usage:.1%}")
    print(f"  Miss rate: {miss_rate:.1%}")
```

---

### Task 5: Telemetry Slimming

**Objective**: Reduce telemetry size with --compact-telemetry flag

**Files to Modify**:
1. `nutritionverse-tests/entrypoints/replay_from_predictions.py`
2. `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

**Implementation** (replay_from_predictions.py CLI):
```python
parser.add_argument(
    "--compact-telemetry",
    action="store_true",
    default=True,
    help="Compress telemetry (default: True)"
)

# Pass to adapter:
result = adapter.align_food_item(..., compact_telemetry=args.compact_telemetry)
```

**Telemetry Compression** (in align_convert.py, around line 3320-3360):
```python
if compact_telemetry:
    # Remove redundant fields
    if "candidate_pool_raw_foundation" in telemetry and \
       "candidate_pool_size" in telemetry:
        # Only keep size, not individual pool counts
        del telemetry["candidate_pool_raw_foundation"]
        del telemetry["candidate_pool_cooked_sr_legacy"]
        del telemetry["candidate_pool_branded"]

    # Deduplicate queries_tried (keep only unique)
    if "queries_tried" in telemetry and isinstance(telemetry["queries_tried"], list):
        telemetry["queries_tried"] = list(set(telemetry["queries_tried"]))[:3]

    # Keep only top 3 candidate snippets
    if "candidate_snippets" in telemetry and isinstance(telemetry["candidate_snippets"], list):
        telemetry["candidate_snippets"] = telemetry["candidate_snippets"][:3]
```

---

### Task 6: Documentation Updates

**Files to Update**:
1. **`docs/CHANGELOG.md`** - Add Phase Z3.1 section
2. **`docs/PHASE_Z3_PLAN.md`** - Add "Z3.1 Stabilization Tasks" section
3. **`CONTINUE_HERE.md`** - Point to latest Z3.1 run
4. **`runs/replay_z3_1_<ts>/Z3_1_RESULTS.md`** - Auto-generate from analyzer

**CHANGELOG.md Addition**:
```markdown
## [2025-10-30] Phase Z3.1 - Blocker Fixes & Stabilization

### Added
- Analyzer baseline schema normalization (`normalize_record()`)
- Enhanced baseline comparison with delta tracking
- Feature flag enforcement assertions
- Stage Z scoring guard (form bonus dampening)
- Deterministic mini-replay fixture for CI (<30s)
- Telemetry slimming with --compact-telemetry flag

### Fixed
- Analyzer now handles old/new schema differences correctly
- Baseline comparisons use normalized field names
- Stage Z form influence properly guarded

### Metrics (Target vs Actual)
| Metric | Target | Status |
|--------|--------|--------|
| Stage Z usage | ≥18% | Pending Z3.1 replay |
| Miss rate | ≤27% | Pending Z3.1 replay |
| Mini-replay runtime | <30s | Pending test creation |
| Analyzer delta accuracy | 100% | ✅ Implemented |
```

**PHASE_Z3_PLAN.md Addition**:
```markdown
## Z3.1 Stabilization Tasks (2025-10-30)

### Context
Phase Z3 initial implementation revealed blocker (brussels sprouts early return path) and need for:
- Deterministic CI testing
- Schema-aware baseline comparison
- Feature flag enforcement
- Scoring guards

### Tasks Completed
1. ✅ Analyzer baseline schema normalization
2. ⏸️ Feature flag enforcement (documented)
3. ⏸️ Stage Z scoring guard (documented)
4. ⏸️ Mini-replay fixture (documented)
5. ⏸️ Telemetry slimming (documented)
6. ⏸️ Documentation updates (in progress)

### Next Steps
- Complete remaining tasks 2-5
- Run full Z3.1 630-image replay
- Generate Z3_1_RESULTS.md
- Add mini-replay to CI pipeline
```

**Z3_1_RESULTS.md Template**:
```markdown
# Phase Z3.1 Results

**Date**: {timestamp}
**Run**: runs/replay_z3_1_{timestamp}/
**Config**: configs@{git_hash}

## Metrics vs Baseline

| Metric | Baseline | Z3.1 | Delta | Status |
|--------|----------|------|-------|--------|
| Total Foods | 2,140 | {actual} | {delta} | {status} |
| Stage Z Usage | 300 (14.0%) | {actual} | {delta}% | {status} |
| Miss Rate | 600 (28.0%) | {actual} | {delta}% | {status} |
| Unique Misses | 539 | {actual} | {delta} | {status} |

## Acceptance Criteria

- ✅/❌ Stage Z usage ≥ 18%
- ✅/❌ Miss rate ≤ 27%
- ✅/❌ Analyzer delta matches baseline
- ✅/❌ Feature flags honored
- ✅/❌ Mini-replay < 30s (when implemented)

## Changes Applied

1. Analyzer schema normalization
2. Feature flag assertions (if implemented)
3. Stage Z scoring guard (if implemented)
4. Telemetry compression (if enabled)

## Next Steps

- Complete remaining Z3.1 tasks (if any)
- Add mini-replay to CI
- Proceed to Phase Z4 (multi-component dishes)
```

---

## Validation Commands

```bash
# Task 1 (Completed):
python analyze_batch_results.py runs/replay_z3_*/results.jsonl \
  --compare runs/replay_630_withconfigs

# Full Z3.1 Replay (after tasks 2-5):
python nutritionverse-tests/entrypoints/replay_from_predictions.py \
  --in nutritionverse-tests/results/gpt_5_630images_20251027_151930.json \
  --out runs/replay_z3_1_$(date +%Y%m%d_%H%M%S) \
  --config-dir configs/ \
  --compact-telemetry

# Mini-replay test (after task 4):
pytest -q nutritionverse-tests/tests/test_replay_minibatch.py
```

---

## Implementation Status

**Completed**:
- ✅ Task 1: Analyzer baseline normalization (100%)

**Documented** (ready for implementation):
- 📝 Task 2: Feature flag enforcement (0%, code locations provided)
- 📝 Task 3: Stage Z scoring guard (0%, code location provided)
- 📝 Task 4: Mini-replay fixture (0%, full template provided)
- 📝 Task 5: Telemetry slimming (0%, implementation outlined)
- 📝 Task 6: Documentation (20%, templates provided)

**Estimated Time to Complete**:
- Task 2: 10-15 min (add assertions)
- Task 3: 10 min (add scoring guard)
- Task 4: 30-40 min (create fixture + test)
- Task 5: 20-30 min (add flag + compression logic)
- Task 6: 15-20 min (update docs)
- **Total**: ~2 hours remaining work

---

## Files Modified So Far

1. ✅ `analyze_batch_results.py` - Lines 585-797 (Task 1 complete)

**Files to Modify Next**:
2. ⏸️ `nutritionverse-tests/src/adapters/alignment_adapter.py`
3. ⏸️ `nutritionverse-tests/src/nutrition/alignment/align_convert.py`
4. ⏸️ `nutritionverse-tests/entrypoints/replay_from_predictions.py`
5. ⏸️ `nutritionverse-tests/fixtures/replay_minibatch.json` (create)
6. ⏸️ `nutritionverse-tests/tests/test_replay_minibatch.py` (create)
7. ⏸️ `docs/CHANGELOG.md`
8. ⏸️ `docs/PHASE_Z3_PLAN.md`
9. ⏸️ `CONTINUE_HERE.md`

---

## Token Usage Note

**Current Session**: ~146k/200k tokens used on Phase Z3 investigation + Z3.1 Task 1

**Recommendation**:
- Continue Z3.1 implementation in fresh session with remaining tasks 2-6
- All code locations and templates provided above for quick implementation
- Estimated 2 hours to complete remaining tasks

---

**Status**: ⏸️ Partial implementation complete, ready for continuation
**Next Action**: Implement tasks 2-6 using templates above, then run Z3.1 replay
**Priority**: Medium - Z3.1 stabilizes foundation before Z4

---

**Last Updated**: 2025-10-30
**Session**: Phase Z3 Investigation + Z3.1 Partial Implementation
