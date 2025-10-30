# Continue Here - Snap & Track Model Testing

**Last Updated**: 2025-10-30
**Current Phase**: Phase Z3 - Precision Coverage Improvements 🔄 IN PROGRESS
**Previous Phase**: Phase Z2 - Config Wiring & Replay Validation ✅ COMPLETE

---

## 🎯 Current Status

### 🔄 Phase Z3 In Progress (2025-10-30)

**Objective**: Raise Stage Z usage to ≥20% and drop miss rate to ≤25%

**Current Baseline** (from runs/replay_630_withconfigs/):
- Total foods: 2,140
- Stage Z usage: 300 (14.0%)
- Miss rate: 600 (28.0%)

**Phase Z3 Targets**:
- Stage Z usage: ≥428 (20%+) → Need +128 foods
- Miss rate: ≤535 (25%) → Need -65 misses

**Progress So Far**:
- ✅ Phase Z3 helper functions added to align_convert.py
  - `_infer_cooked_form_from_tokens()` - Advisory form inference
  - `_is_produce_vegetable()` - Vegetable class intent
- ✅ 9 new Stage Z verified entries added (egg_white, potato_roasted, sweet_potato_roasted, rice_cooked, rice_brown_cooked, brussels_sprouts_roasted, cauliflower_roasted, hash_browns, bagel_plain)
- ✅ Documentation suite created (PLAN, RUNBOOK, CHANGELOG, EVAL_BASELINES, Z4_BACKLOG)
- ⏸️ **PENDING**: Integration of form inference into scoring logic
- ⏸️ **PENDING**: Analyzer baseline comparison method
- ⏸️ **PENDING**: 2 new tests
- ⏸️ **PENDING**: Full 630-image Z3 validation replay

---

## 🚀 Next Actions (Phase Z3)

### Immediate Tasks
1. **Add baseline comparison to analyzer** - Create `compare_with_baseline()` method in `analyze_batch_results.py`
2. **Run quick smoke test** - Test Phase Z3 changes with `--limit 10` before full replay
3. **Add 2 new tests**:
   - `test_intent_cooked_bonus()` - Verify advisory score adjustments
   - `test_stageZ3_fallback_coverage()` - Verify new Z3 entries trigger
4. **Run full 630-image Z3 replay** - Critical validation step
5. **Generate Z3_RESULTS.md** - Auto-generate in run directory with TL;DR + deltas
6. **Integrate form inference** - Wire `_infer_cooked_form_from_tokens()` into scoring logic (optional enhancement)

### Quick Start Commands

**Run Phase Z3 Smoke Test (10 predictions)**:
```bash
cd /Users/austinprofenius/snapandtrack-model-testing/nutritionverse-tests
python entrypoints/replay_from_predictions.py \
  --in results/gpt_5_630images_20251027_151930.json \
  --out /tmp/replay_z3_smoke \
  --limit 10
```

**Run Full Phase Z3 Replay (630 predictions)**:
```bash
python entrypoints/replay_from_predictions.py \
  --in results/gpt_5_630images_20251027_151930.json \
  --out ../runs/replay_z3_$(date +%Y%m%d_%H%M%S)
```

**Analyze with Baseline Comparison**:
```bash
cd /Users/austinprofenius/snapandtrack-model-testing
python analyze_batch_results.py runs/replay_z3_*/results.jsonl \
  --compare runs/replay_630_withconfigs
```

**Run Tests**:
```bash
cd nutritionverse-tests
pytest -xvs tests/test_prediction_replay.py
```

---

## 📚 Phase Z3 Documentation

### Created Documentation
- 📄 [docs/PHASE_Z3_PLAN.md](docs/PHASE_Z3_PLAN.md) - Comprehensive plan with goals, guardrails, scope
- 📄 [docs/RUNBOOK.md](docs/RUNBOOK.md) - Exact commands for replays and analysis
- 📄 [docs/CHANGELOG.md](docs/CHANGELOG.md) - Change history with Phase Z3 additions
- 📄 [docs/EVAL_BASELINES.md](docs/EVAL_BASELINES.md) - Baseline tracking and how to add new baselines
- 📄 [docs/PHASE_Z4_BACKLOG.md](docs/PHASE_Z4_BACKLOG.md) - Deferred complex dishes (pizza, chia pudding)

### Key Guardrails (from PHASE_Z3_PLAN.md)
1. **Preserve Foundation/SR precedence**: Foundation/SR (1b/1c) → Stage 2 → Stage Z
2. **Advisory form inference only**: Small ±score adjustments (+0.05/-0.10), never force paths
3. **Egg whites special handling**: Prefer Foundation/SR raw egg white + Stage 2
4. **Complex dishes deferred**: Pizza, chia pudding → Phase Z4 backlog

---

## 📂 Key Files & Locations

### Modified in Phase Z3
- **Alignment Engine**: `nutritionverse-tests/src/nutrition/alignment/align_convert.py` (+60 lines)
  - Added `_infer_cooked_form_from_tokens()` helper
  - Added `_is_produce_vegetable()` helper
- **Stage Z Config**: `configs/stageZ_branded_fallbacks.yml` (+9 entries, now 116 total)

### Replay System
- **Entrypoint**: `nutritionverse-tests/entrypoints/replay_from_predictions.py`
- **Parsers**: `nutritionverse-tests/parsers/` (V1/V2 schema support)
- **Adapter Hook**: `nutritionverse-tests/src/adapters/alignment_adapter.py`

### Configs
- **Stage Z Fallbacks**: `configs/stageZ_branded_fallbacks.yml` (116 entries)
- **Feature Flags**: `configs/feature_flags.yml`
- **Negative Vocabulary**: `configs/negative_vocabulary.yml`

### Analysis
- **Batch Analyzer**: `analyze_batch_results.py`
- **Current Baseline**: `runs/replay_630_withconfigs/` (Phase Z2 baseline)
- **Next Baseline**: `runs/replay_z3_*/` (to be created)

---

## 📊 Baseline Tracking

### Phase Z2 Baseline: runs/replay_630_withconfigs/
**Date**: 2025-10-30 17:27 UTC
**Config**: configs@d6bb07ee076f
**Source**: prediction_replay

**Metrics**:
| Metric | Value | Percentage |
|--------|-------|------------|
| Total foods | 2,140 | - |
| Matched | 1,540 | 72.0% |
| Misses | 600 | 28.0% |
| Stage Z usage | 300 | 14.0% |
| Foundation (1b) | 930 | 43.5% |
| SR Legacy (1c) | 148 | 6.9% |
| Stage 2 conversion | 50 | 2.3% |
| Salad decomp (5B) | 108 | 5.0% |

**Stage Z Breakdown**:
- Branded fallback: 239 foods
- Energy-only proxy: 61 foods

### Phase Z3 Target Metrics
| Metric | Z2 Baseline | Z3 Target | Delta Needed |
|--------|-------------|-----------|--------------|
| Stage Z usage | 14.0% (300) | ≥20% (428+) | +128 foods |
| Miss rate | 28.0% (600) | ≤25% (535) | -65 misses |

---

## 🎯 Phase Z3 Implementation Status

### ✅ Completed
1. **Helper functions added** (align_convert.py)
   - `_infer_cooked_form_from_tokens()` - Detects roasted/baked/boiled/steamed/grilled/fried
   - `_is_produce_vegetable()` - Identifies vegetables for Stage Z eligibility
2. **Stage Z verified entries** (stageZ_branded_fallbacks.yml)
   - egg_white (FDC 748967)
   - potato_roasted (FDC 170032)
   - sweet_potato_roasted (FDC 168482)
   - rice_white_cooked (FDC 168878)
   - rice_brown_cooked (FDC 168876)
   - brussels_sprouts_roasted (FDC 170379)
   - cauliflower_roasted (FDC 170390)
   - hash_browns (FDC 170033)
   - bagel_plain (FDC 172676)
3. **Documentation suite** (5 docs created)

### ⏸️ Pending
1. **Integration of form inference into scoring** - Helpers exist, scoring not yet wired
2. **Analyzer baseline comparison** - Need `compare_with_baseline()` method
3. **2 new tests** - test_intent_cooked_bonus(), test_stageZ3_fallback_coverage()
4. **Full Z3 validation replay** - 630-image run with Z3 changes
5. **Z3_RESULTS.md generation** - Auto-create summary with metrics

---

## 🐛 Known Issues & Targeted Fixes

### Phase Z3 Targets

**Roasted Vegetables (143 instances)**:
- brussels sprouts roasted → ✅ Added to Stage Z
- sweet potato roasted → ✅ Added to Stage Z
- potato roasted → ✅ Added to Stage Z
- cauliflower roasted → ✅ Added to Stage Z

**Proteins/Starches (28 instances)**:
- egg white → ✅ Added to Stage Z
- rice cooked → ✅ Added to Stage Z (white + brown)
- hash browns → ✅ Added to Stage Z
- bagel → ✅ Added to Stage Z

**Raw Vegetables (37 instances)**:
- bell pepper, corn, zucchini, asparagus → ✅ Added to class intent via `_is_produce_vegetable()`

### Deferred to Phase Z4
- Pizza & cheese pizza (30 instances) → Multi-component decomposition
- Chia pudding (6 instances) → Verified branded entry needed

---

## 🔗 Related Documentation

### Phase Z3
- [docs/PHASE_Z3_PLAN.md](docs/PHASE_Z3_PLAN.md) - Comprehensive Z3 plan
- [docs/RUNBOOK.md](docs/RUNBOOK.md) - Exact commands
- [docs/CHANGELOG.md](docs/CHANGELOG.md) - Change tracking
- [docs/EVAL_BASELINES.md](docs/EVAL_BASELINES.md) - Baseline definitions
- [docs/PHASE_Z4_BACKLOG.md](docs/PHASE_Z4_BACKLOG.md) - Deferred items

### Phase Z2
- [PREDICTION_REPLAY_STATUS.md](PREDICTION_REPLAY_STATUS.md) - Replay system status
- [PREDICTION_REPLAY_IMPLEMENTATION.md](PREDICTION_REPLAY_IMPLEMENTATION.md) - Technical implementation

---

## 📝 Quick Notes

### Phase Z3 Strategy
1. **Conservative approach**: Only verified FDC IDs from Foundation/SR databases
2. **Advisory inference**: Form detection gives small score adjustments, never forces paths
3. **Targeted coverage**: Address top 3 miss patterns (roasted veg, proteins, raw veg)
4. **Document deferrals**: Complex dishes (pizza, chia pudding) → Phase Z4

### Phase Z2 Learnings
1. **Stage Z is critical**: Handles 14% of all food alignments
2. **Config wiring works**: All configs load correctly through replay
3. **Replay is fast**: 630 predictions in 13 minutes
4. **Cost savings confirmed**: $31.50-$63.00 per run vs vision API

---

**Navigation**: Start here → Check [docs/PHASE_Z3_PLAN.md](docs/PHASE_Z3_PLAN.md) → Run smoke test → Add tests → Run full Z3 replay → Analyze results
