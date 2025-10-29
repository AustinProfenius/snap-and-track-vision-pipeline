# Pipeline Inventory - Complete File List

**Created**: 2025-10-27
**Purpose**: Comprehensive inventory of all pipeline files, their purpose, and status

---

## 1. Entrypoints / Orchestration ✅

### Batch Evaluation Scripts

| File | Status | Purpose | Lines |
|------|--------|---------|-------|
| `entrypoints/run_459_batch_evaluation.py` | ✅ COPIED | Full 459-image batch evaluation | ~500 |
| `entrypoints/run_50_image_test.py` | ⚠️  MISSING | 50-image quick validation | - |
| `entrypoints/test_surgical_fixes.py` | ✅ COPIED | Single-item validation tests | 162 |

**Missing**: Need to locate or recreate `run_50_image_test.py`

---

## 2. Alignment & Conversion ✅

### Core Alignment Engine

| File | Status | Purpose | Key Functions |
|------|--------|---------|---------------|
| `alignment/align_convert.py` | ✅ COPIED | Main alignment engine with all stages | `align_food_item()` (line 131) |
| `alignment/alignment_adapter.py` | ✅ COPIED | Web app adapter interface | `align_prediction_batch()` (line 46) |
| `alignment/search_normalizer.py` | ✅ COPIED | Query variant generation | `generate_query_variants()` (line 120) |
| `alignment/stage_z_guards.py` | ✅ COPIED | Stage-Z eligibility & energy proxy | `can_use_stageZ()` (line 87) |

**Critical Code Sections in align_convert.py**:
- Stage 1b (lines 497-658): Raw Foundation direct match with single-token leniency
- Stage 1c (lines 619-672): Cooked SR direct (proteins)
- Stage 2 canonical base selection (lines 619-720): Excludes leaves/flour/starch
- Hard negative filter (lines 605-609): Skips "strudel apple" before scoring
- Class thresholds (lines 600-609): grape/almond/melon = 0.30

### Conversion Logic

| File | Status | Purpose |
|------|--------|---------|
| `alignment/conversions/cook_convert.py` | ✅ COPIED | Raw→cooked conversion logic |
| `alignment/conversions/energy_atwater.py` | ✅ COPIED | Energy validation & Atwater |
| `configs/data/cook_conversions.v2.json` | ✅ COPIED | Method profiles & factors |
| `configs/data/energy_bands.json` | ✅ COPIED | Plausibility bands by category |

---

## 3. Data & FDC Integration ✅

### Database Loaders

| File | Status | Purpose |
|------|--------|---------|
| `data/fdc_database.py` | ✅ COPIED | PostgreSQL FDC search |
| `data/fdc_indexer.py` | ⚠️  MISSING | FDC index builder (if exists) |

**Environment Variables Required**:
- `NEON_CONNECTION_URL`: PostgreSQL connection string

### Synonym & Mapping Tables

**Embedded in search_normalizer.py**:
- `PLURAL_MAP` (line 19): 13 mappings (almonds→almond raw, grapes→grapes raw)
- `SYNONYMS` (line 38): 23 mappings (cantaloupe→melons cantaloupe raw)
- `FDC_HINTS` (line 172): 36 exact FDC title hints

**Status**: ✅ All embedded, no separate files needed

---

## 4. Configuration Files ✅

### New Exports (Created 2025-10-27)

| File | Status | Source |
|------|--------|--------|
| `configs/negative_vocabulary.yml` | ✅ CREATED | Extracted from align_convert.py:553-559 |
| `configs/class_thresholds.yml` | ✅ CREATED | Extracted from align_convert.py:600-609 |
| `configs/feature_flags.yml` | ✅ CREATED | Extracted from config/feature_flags.py |

### Existing Data Configs

| File | Status | Purpose |
|------|--------|---------|
| `configs/data/cook_conversions.v2.json` | ✅ COPIED | 250+ method profiles |
| `configs/data/energy_bands.json` | ✅ COPIED | Plausibility ranges |
| `configs/data/proxy_alignment_rules.json` | ✅ COPIED | Stage 5 proxy mappings |

---

## 5. Telemetry & Results ✅

### Test Results (JSON)

| File | Status | Images | Date | Notes |
|------|--------|--------|------|-------|
| `telemetry/results/gpt_5_50images_20251026_204653.json` | ✅ COPIED | 50 | 2025-10-26 | **BASELINE** - Before fixes |
| `telemetry/results/gpt_5_10images_20251026_192517.json` | ✅ COPIED | 10 | 2025-10-26 | Before fixes |
| `telemetry/results/gpt_5_50images_20251026_150143.json` | ✅ COPIED | 50 | 2025-10-26 | Earlier test |
| `telemetry/results/gpt_5_459images_20251026_092433.json` | ✅ COPIED | 459 | 2025-10-26 | Full evaluation |

**Total Results Files**: 52 JSON files copied (various dates)

**Key Metrics from Baseline** (50-image 20251026_204653):
- Grapes: 30/30 failures (stage0_no_candidates)
- Almonds: 27/27 failures
- Cantaloupe: 12/12 failures
- Apple: 26/26 "Strudel apple" matches (negative leak)

### Log Format

**Telemetry Fields** (as of 2025-10-27):
```json
{
  "alignment_stage": "stage1b_raw_foundation_direct",
  "variant_chosen": "grapes raw",
  "foundation_pool_count": 50,
  "search_variants_tried": 4,
  "stage1b_score": 0.95,
  "stage1b_jaccard": 0.93,
  "stage1b_energy_sim": 1.0,
  "candidate_pool_size": 50,
  "candidate_pool_raw_foundation": 50,
  "candidate_pool_cooked_sr_legacy": 0,
  "candidate_pool_branded": 0
}
```

---

## 6. Vision Stage ✅

### Vision Model Adapters

| File | Status | Purpose |
|------|--------|---------|
| `vision/openai_.py` | ✅ COPIED | GPT-4V/GPT-5 image detection |
| `vision/core/prompts.py` | ✅ COPIED | System prompts & schemas |
| `vision/core/types.py` | ✅ COPIED | Type definitions |

**Prediction Format**:
```python
{
  "foods": [
    {
      "name": str,         # e.g., "grapes"
      "form": str,         # e.g., "raw", "grilled", "boiled"
      "mass_g": int,       # Estimated mass
      "count": int,        # Item count
      "modifiers": list,   # e.g., ["red", "seedless"]
      "confidence": float  # 0.0-1.0
    }
  ]
}
```

---

## 7. Ground Truth / Evaluation ⚠️

### Ground Truth Data

| File | Status | Purpose |
|------|--------|---------|
| `ground_truth/ground_truth.csv` | ⚠️  MISSING | True FDC IDs & macros |
| `ground_truth/ground_truth.json` | ⚠️  MISSING | Alternative JSON format |

**Required Columns**:
- `dish_id`: Unique dish identifier
- `food_name`: Item name
- `mass_g`: Ground truth mass
- `true_fdc_id`: Correct FDC database ID
- `true_calories`, `true_protein_g`, `true_carbs_g`, `true_fat_g`

**Action Required**: Export ground truth from evaluation dataset

### Metric Code

| File | Status | Purpose |
|------|--------|---------|
| `ground_truth/eval_aggregator.py` | ⚠️  MISSING | Accuracy computation |
| `ground_truth/metrics.py` | ⚠️  MISSING | Tolerance checks |

**Action Required**: Copy from `nutritionverse-tests/tools/eval_aggregator.py`

---

## 8. Documentation ✅

### Implementation Docs

| File | Status | Purpose |
|------|--------|---------|
| `README.md` | ✅ CREATED | Complete pipeline guide |
| `INVENTORY.md` | ✅ CREATED | This file |
| `SURGICAL_FIXES_COMPLETE.md` | ⚠️  COPY | A-E2 fixes from 2025-10-26 AM |
| `STAGE1B_FIXES_COMPLETE.md` | ⚠️  COPY | Final fixes from 2025-10-26 PM |

**Action Required**: Copy fix documentation from nutritionverse-tests/

---

## 9. Dependencies & Environment

### Python Requirements

**File**: `requirements.txt` (TO BE CREATED)

```
psycopg2-binary>=2.9.0
python-dotenv>=0.19.0
openai>=1.0.0
pydantic>=2.0.0
```

### Environment Variables

**File**: `.env.template` (TO BE CREATED)

```bash
# FDC Database
NEON_CONNECTION_URL=postgresql://user:pass@host/database

# OpenAI (for vision)
OPENAI_API_KEY=sk-...

# Optional
ALIGN_VERBOSE=0  # Set to 1 for debug logging
```

---

## 10. Missing Files / Action Items

### High Priority ⚠️

1. **Ground Truth Data**:
   - [ ] Export `ground_truth.csv` from evaluation dataset
   - [ ] Copy `eval_aggregator.py` for accuracy metrics

2. **Batch Runner**:
   - [ ] Locate or recreate `run_50_image_test.py`
   - [ ] Verify `run_459_batch_evaluation.py` is complete

3. **Documentation**:
   - [ ] Copy `SURGICAL_FIXES_COMPLETE.md`
   - [ ] Copy `STAGE1B_FIXES_COMPLETE.md`

4. **Dependencies**:
   - [ ] Create `requirements.txt`
   - [ ] Create `.env.template`

### Medium Priority

5. **FDC Index Builder** (if exists):
   - [ ] Copy `fdc_indexer.py` or document index structure

6. **Web App Integration**:
   - [ ] Copy Flask/FastAPI routes that call alignment adapter
   - [ ] Document API endpoints

### Low Priority

7. **Additional Tests**:
   - [ ] Unit tests for alignment stages
   - [ ] Integration tests for full pipeline

---

## 11. File Size Summary

```
Total Files: 75+
Total Size: ~50MB (mostly JSON results)

Breakdown:
- Telemetry/Results: 52 files, ~45MB
- Alignment Code: 15 files, ~500KB
- Config Data: 8 files, ~2MB
- Documentation: 5 files, ~100KB
```

---

## 12. Validation Checklist

Before using this pipeline:

- [x] All core alignment files copied
- [x] Configuration files exported
- [x] Baseline test results available
- [ ] Ground truth data added
- [ ] Evaluation metrics code added
- [ ] Requirements.txt created
- [ ] .env.template created
- [ ] Documentation complete

**Status**: 80% Complete (core functionality ready, missing ground truth & metrics)

---

## 13. Next Steps

1. **Immediate** (Required for testing):
   - Add ground truth CSV
   - Copy eval_aggregator.py
   - Create requirements.txt

2. **Short-term** (Validation):
   - Re-run 50-image test with fixes
   - Compare to baseline results
   - Verify Stage-Z produce count == 0

3. **Long-term** (Deployment):
   - Web app integration testing
   - API documentation
   - Performance benchmarking
