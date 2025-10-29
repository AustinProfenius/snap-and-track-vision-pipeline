# Pipeline Manifest - Complete File Listing

**Directory**: `tempPipeline10-27-811`
**Created**: 2025-10-27 08:15
**Purpose**: Complete, reproducible alignment pipeline

---

## Directory Tree

```
tempPipeline10-27-811/
├── README.md                                    # Main documentation
├── INVENTORY.md                                 # Detailed file inventory
├── MANIFEST.md                                  # This file
├── SURGICAL_FIXES_COMPLETE.md                   # A-E2 fixes (AM)
├── STAGE1B_FIXES_COMPLETE.md                    # Final fixes (PM)
├── requirements.txt                             # Python dependencies
├── .env.template                                # Environment variables template
│
├── entrypoints/                                 # Orchestration & runners
│   ├── run_459_batch_evaluation.py              # Full batch test
│   └── test_surgical_fixes.py                   # Single-item validation
│
├── alignment/                                   # Core alignment logic
│   ├── align_convert.py                         # Main engine (1650 lines)
│   ├── alignment_adapter.py                     # Web app interface (275 lines)
│   ├── search_normalizer.py                     # Query variants (234 lines)
│   ├── stage_z_guards.py                        # Stage-Z eligibility (191 lines)
│   └── conversions/                             # Conversion logic
│       ├── cook_convert.py                      # Raw→cooked conversion
│       └── energy_atwater.py                    # Energy validation
│
├── data/                                        # FDC database integration
│   └── fdc_database.py                          # PostgreSQL search
│
├── configs/                                     # Configuration files
│   ├── negative_vocabulary.yml                  # Hard filter negatives
│   ├── class_thresholds.yml                     # Stage-1b thresholds
│   ├── feature_flags.yml                        # Engine behavior flags
│   └── data/                                    # Conversion configs
│       ├── cook_conversions.v2.json             # 250+ method profiles
│       ├── energy_bands.json                    # Plausibility ranges
│       └── proxy_alignment_rules.json           # Stage 5 proxies
│
├── telemetry/                                   # Test results & logs
│   └── results/                                 # 52 JSON test files
│       ├── gpt_5_50images_20251026_204653.json  # BASELINE (before fixes)
│       ├── gpt_5_10images_20251026_192517.json  # 10-image test
│       └── gpt_5_459images_20251026_092433.json # Full evaluation
│
├── vision/                                      # Vision model adapters
│   ├── openai_.py                               # GPT-4V/GPT-5 integration
│   └── core/                                    # Prompts & types
│       ├── prompts.py                           # System prompts
│       └── types.py                             # Type definitions
│
└── ground_truth/                                # Evaluation (TO BE ADDED)
    ├── ground_truth.csv                         # ⚠️  MISSING
    └── eval_aggregator.py                       # ⚠️  MISSING
```

---

## File Count & Size

| Category | Files | Size | Status |
|----------|-------|------|--------|
| **Documentation** | 5 | 37 KB | ✅ Complete |
| **Entrypoints** | 2 | 25 KB | ⚠️  Missing run_50_image_test.py |
| **Alignment Code** | 9 | 500 KB | ✅ Complete |
| **Config Files** | 6 | 2 MB | ✅ Complete |
| **Data Loaders** | 1 | 15 KB | ✅ Complete |
| **Telemetry/Results** | 52 | 45 MB | ✅ Complete |
| **Vision Adapters** | 15+ | 100 KB | ✅ Complete |
| **Ground Truth** | 0 | 0 | ⚠️  MISSING |
| **Total** | **90+** | **~48 MB** | **85% Complete** |

---

## Critical Files Checklist

### Must Have (Pipeline Core) ✅

- [x] `alignment/align_convert.py` - Main alignment engine
- [x] `alignment/alignment_adapter.py` - Web app interface
- [x] `alignment/search_normalizer.py` - Query variants
- [x] `alignment/stage_z_guards.py` - Stage-Z logic
- [x] `data/fdc_database.py` - FDC search
- [x] `configs/data/cook_conversions.v2.json` - Method profiles
- [x] `configs/negative_vocabulary.yml` - Hard filters
- [x] `configs/class_thresholds.yml` - Stage-1b thresholds
- [x] `requirements.txt` - Dependencies
- [x] `.env.template` - Environment setup

### Should Have (Testing) ⚠️

- [x] `entrypoints/run_459_batch_evaluation.py` - Batch runner
- [ ] `entrypoints/run_50_image_test.py` - Quick validation (MISSING)
- [x] `telemetry/results/gpt_5_50images_20251026_204653.json` - Baseline
- [ ] `ground_truth/ground_truth.csv` - Evaluation data (MISSING)
- [ ] `ground_truth/eval_aggregator.py` - Accuracy metrics (MISSING)

### Nice to Have (Documentation)

- [x] `README.md` - Complete guide
- [x] `INVENTORY.md` - File inventory
- [x] `MANIFEST.md` - This file
- [x] `SURGICAL_FIXES_COMPLETE.md` - A-E2 fixes
- [x] `STAGE1B_FIXES_COMPLETE.md` - Final fixes

---

## Key Changes Applied (2025-10-27)

### Morning Session (A-E2 Fixes)

1. **Variant Search Enhancement** (alignment_adapter.py:102-183)
   - Score by (foundation_count, total_count, raw_bias)
   - New telemetry: variant_chosen, foundation_pool_count

2. **Stage-1b Class-Specific Negatives** (align_convert.py:552-589)
   - Added NEGATIVES_BY_CLASS with apple/grape/potato/sweet_potato
   - Lowered threshold for processing-heavy foods

3. **Melon Synonyms** (align_convert.py:1317-1321)
   - honeydew → "honeydew", cantaloupe → "cantaloupe"

4. **Canonical Base Selection** (align_convert.py:619-720)
   - Excludes leaves/flour/starch from Stage 2 base
   - Sweet potato selects tuber, not leaves

5. **Stage-1c Cooked SR Direct** (align_convert.py:619-672, 227-246)
   - NEW stage for bacon/eggs/sausage
   - Whitelist: bacon, egg_scrambled, egg_fried, etc.

6. **Stage-Z Meat Exception** (stage_z_guards.py:82-132)
   - Allows Stage-Z for meats even if raw Foundation exists
   - Fruits/vegetables still strictly blocked

7. **Fruit/Melon Variant Ordering** (search_normalizer.py:209-242)
   - Grapes: plural preferred
   - Honeydew/Cantaloupe: "melons X raw" first

### Evening Session (Stage-1b Critical Fixes)

8. **Hard Filter Negatives** (align_convert.py:605-609)
   - Check entry_name_lower BEFORE scoring
   - Skip "Strudel apple" entirely (don't just penalize)

9. **Add Almond Negatives** (align_convert.py:556)
   - "almond": {"oil", "butter", "flour", "meal", "paste"}

10. **Single-Token Core Class Leniency** (align_convert.py:617-628)
    - For len(class_tokens) == 1: require core token + simplicity scoring
    - "grape" query scores 0.95 with "Grapes, raw" (was 0.20)

11. **Class-Specific Thresholds** (align_convert.py:600-609)
    - grape/cantaloupe/honeydew/almond: 0.30 (was 0.45-0.50)

12. **Prefer Plural Variants** (search_normalizer.py:213-221)
    - Reorder: plural_raw → plural → singular_raw → singular

13. **Corn & Tomato Variants** (search_normalizer.py:231-242)
    - "corn" → ["corn sweet yellow raw", ...]
    - "cherry tomatoes" → ["tomatoes cherry raw", ...]

---

## Expected Impact

### Before Fixes (50-image baseline)

| Item | Result | Stage | Pool Size |
|------|--------|-------|-----------|
| Grapes (30) | ❌ 30/30 stage0 | stage0_no_candidates | 50 Foundation |
| Almonds (27) | ❌ 27/27 stage0 | stage0_no_candidates | 49 Foundation |
| Cantaloupe (12) | ❌ 12/12 stage0 | stage0_no_candidates | 3 Foundation |
| Apple (26) | ❌ 26/26 "Strudel" | stage1b | Negative leak |

### After Fixes (expected)

| Item | Result | Stage | Score |
|------|--------|-------|-------|
| Grapes (30) | ✅ 30/30 match | stage1b_raw_foundation_direct | ~0.95 |
| Almonds (27) | ✅ 27/27 match | stage1b_raw_foundation_direct | ~0.95 |
| Cantaloupe (12) | ✅ 12/12 match | stage1b_raw_foundation_direct | ~0.90 |
| Apple (26) | ✅ 0/26 negatives | stage1b (clean matches only) | - |

**Expected Shift**: ~70 items from stage0 → stage1b (major improvement)

---

## Usage Instructions

### 1. Setup Environment

```bash
# Copy environment template
cp .env.template .env

# Edit .env with your credentials
# - NEON_CONNECTION_URL (required)
# - OPENAI_API_KEY (required)

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Batch Test

```bash
cd entrypoints
python run_459_batch_evaluation.py

# Or quick 50-image test (if available)
python run_50_image_test.py
```

### 3. Compare Results

```bash
# Compare with baseline
diff telemetry/results/baseline.json telemetry/results/new_test.json
```

### 4. Web App Integration

```python
from alignment.alignment_adapter import AlignmentEngineAdapter

adapter = AlignmentEngineAdapter()
prediction = {"foods": [...]}  # From vision model
result = adapter.align_prediction_batch(prediction)
```

---

## Validation Checklist

Before deploying:

- [ ] Re-run 50-image test
- [ ] Verify grapes/almonds/melons: 100% stage1b
- [ ] Verify apple: 0% negative leaks
- [ ] Check Stage-Z produce count == 0
- [ ] Run 459-image full evaluation
- [ ] Compare accuracy metrics vs baseline
- [ ] Test web app integration

---

## Known Issues / TODOs

### High Priority

1. **Ground Truth Missing**: Need `ground_truth.csv` for accuracy evaluation
2. **Eval Metrics Missing**: Need `eval_aggregator.py` for pass/fail computation
3. **50-Image Runner Missing**: Quick validation script not found

### Medium Priority

4. **FDC Index Documentation**: How to rebuild FDC candidate pools
5. **Web App Routes**: Flask/FastAPI integration examples
6. **Unit Tests**: Coverage for alignment stages

### Low Priority

7. **Performance Benchmarks**: Latency metrics for each stage
8. **API Documentation**: OpenAPI/Swagger specs
9. **Monitoring**: Telemetry dashboards

---

## Contact & Support

**Created By**: Claude (Anthropic)
**Date**: 2025-10-27
**Session**: Surgical fixes implementation + pipeline consolidation

**For Questions**:
1. Review `README.md` for complete guide
2. Check `INVENTORY.md` for file details
3. See `SURGICAL_FIXES_COMPLETE.md` and `STAGE1B_FIXES_COMPLETE.md` for change history

**Repository**: This pipeline is self-contained and can be run independently of the main nutritionverse-tests repo.
