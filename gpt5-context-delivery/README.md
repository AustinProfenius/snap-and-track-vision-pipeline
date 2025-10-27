# GPT-5 Context Delivery - Complete Pipeline Materials

**Created**: 2025-10-27 09:10
**Purpose**: Complete context for GPT-5 agent analysis of alignment pipeline

---

## Directory Structure

```
gpt5-context-delivery/
├── README.md                           # This file
├── SURGICAL_FIXES_COMPLETE.md          # A-E2 fixes (morning)
├── STAGE1B_FIXES_COMPLETE.md           # Critical fixes (evening)
├── entrypoints/                        # Orchestration & batch runners
├── alignment/                          # Core alignment logic
├── data/                               # FDC database loaders
├── configs/                            # Configuration & conversion data
├── telemetry/                          # Baseline test results
├── vision/                             # Vision model adapters ✅
├── ground_truth/                       # Evaluation scripts & ground truth data ✅
└── web_app_logs/                       # Web app results (TBD - you'll add)
```

---

## 1. Entrypoints & Orchestration

### Batch Runners

| File | Purpose | Output |
|------|---------|--------|
| `nutritionverse_app.py` | **Streamlit web app** (vision + alignment) | Interactive UI + JSON export |
| `run_459_batch_evaluation.py` | 459-image synthetic batch (no vision) | JSON with telemetry |
| `run_first_50_by_dish_id.py` | First 50 dishes batch (ground truth) | Batch harness JSON |
| `test_surgical_fixes.py` | Single-item validation | Console output |

**See [entrypoints/ENTRYPOINTS.md](entrypoints/ENTRYPOINTS.md) for complete documentation**

### How to Run First 50 Test (Batch Harness)

```bash
cd entrypoints
python run_first_50_by_dish_id.py

# Output: telemetry/batch_harness_first50_sorted_<timestamp>.json
```

This script:
1. Loads test dataset from `food-nutrients/test`
2. Sorts images by dish_id alphabetically
3. Processes first 50 dishes
4. Outputs results with full telemetry (stage, FDC name, variant chosen, etc.)

**You will run the same 50 dishes in the web app and provide those results.**

---

## 2. Alignment & Conversion

### Core Files

| File | Lines | Purpose | Key Sections |
|------|-------|---------|--------------|
| `alignment/align_convert.py` | 1650 | Main alignment engine | See below |
| `alignment/alignment_adapter.py` | 275 | Web app interface | `align_prediction_batch()` line 46 |
| `alignment/search_normalizer.py` | 234 | Query variant generation | `generate_query_variants()` line 120 |
| `alignment/stage_z_guards.py` | 191 | Stage-Z eligibility | `can_use_stageZ()` line 87 |
| `alignment/conversions/cook_convert.py` | ~300 | Raw→cooked conversion | `convert_from_raw()` |
| `alignment/conversions/energy_atwater.py` | ~200 | Energy validation | Atwater factor validation |

### Key Sections in align_convert.py

| Section | Lines | Purpose | Status |
|---------|-------|---------|--------|
| **Stage 1b** | 497-658 | Raw Foundation direct match | ✅ FIXED 2025-10-27 |
| **Stage 1c** | 619-672 | Cooked SR direct (proteins) | ✅ NEW 2025-10-27 |
| **Stage 2** | 661-760 | Raw + conversion (canonical base) | ✅ FIXED 2025-10-27 |
| **Hard Negatives** | 605-609 | Filter "strudel apple" before scoring | ✅ FIXED 2025-10-27 |
| **Single-Token Leniency** | 617-628 | Grape scores 0.95 (was 0.20) | ✅ FIXED 2025-10-27 |
| **Class Thresholds** | 600-609 | grape/almond/melon: 0.30 | ✅ FIXED 2025-10-27 |

### Negative Vocabulary (Embedded)

**Location**: `align_convert.py` lines 552-559

```python
NEGATIVES_BY_CLASS = {
    "apple": {"strudel", "pie", "juice", "sauce", "chip", "dried"},
    "grape": {"juice", "jam", "jelly", "raisin"},
    "almond": {"oil", "butter", "flour", "meal", "paste"},
    "potato": {"bread", "flour", "starch", "powder"},
    "sweet_potato": {"leave", "leaf", "flour", "starch", "powder"},
}
```

**Behavior**: Hard filter applied at line 605-609 (skip candidate entirely before scoring)

### Class-Specific Thresholds

**Location**: `align_convert.py` lines 600-609

```python
CLASS_THRESHOLDS = {
    "grape": 0.30,
    "cantaloupe": 0.30,
    "honeydew": 0.30,
    "almond": 0.30,
    "olive": 0.35,
    "tomato": 0.35,
}
```

### Method Profiles & Conversions

**Location**: `configs/data/cook_conversions.v2.json`

**Contains**:
- 250+ method profiles (grilling, frying, boiling, etc.)
- Hydration factors (e.g., rice: 2.5x mass gain)
- Shrinkage factors (e.g., chicken: 0.75x)
- Oil uptake (e.g., frying: +10g fat per 100g)
- Energy bands for plausibility checking

**Usage**: `alignment/conversions/cook_convert.py` → `convert_from_raw()`

### Stage-Z Guards

**Location**: `alignment/stage_z_guards.py`

**Critical Functions**:
- `can_use_stageZ()` (line 87): Eligibility check
- `build_energy_only_proxy()` (line 135): Energy-only proxy construction

**Key Behavior**:
- **NEVER** allowed for fruits/nuts/vegetables (hard block)
- Allowed for meats even if raw Foundation exists (line 120-122)
- Only provides energy (kcal), not macros

---

## 3. Data & Candidate Pools

### FDC Database Loader

**File**: `data/fdc_database.py`

**Class**: `FDCDatabase`
**Method**: `search_foods(query, limit=50)`

**Environment Variable**: `NEON_CONNECTION_URL`

**Returns**: List of candidates (Foundation, SR Legacy, Branded)

### Candidate Pool Partitioning

**Location**: `alignment/align_convert.py` lines 184-191

```python
raw_foundation = [e for e in fdc_entries if self.is_foundation_raw(e)]
cooked_sr_legacy = [e for e in fdc_entries if self.is_foundation_or_sr_cooked(e)]
branded = [e for e in fdc_entries if self.is_branded(e)]
```

### Synonym & Mapping Tables

**Embedded in**: `alignment/search_normalizer.py`

| Map | Lines | Count | Purpose |
|-----|-------|-------|---------|
| `PLURAL_MAP` | 19-35 | 13 | almonds→almond raw, grapes→grapes raw |
| `SYNONYMS` | 38-61 | 23 | cantaloupe→melons cantaloupe raw |
| `FDC_HINTS` | 172-204 | 36 | Exact FDC titles for common items |

**NEW Variants** (2025-10-27):
- Corn: "corn sweet yellow raw", "corn sweet raw", "corn raw"
- Cherry tomatoes: "tomatoes cherry raw", "tomato cherry raw"
- Grape tomatoes: "tomatoes grape raw", "tomato grape raw"

**Plural Preference** (lines 213-221):
- grapes, almonds, berries → plural_raw → plural → singular_raw → singular

---

## 4. Telemetry & Results

### Baseline Test Results (BEFORE Fixes)

| File | Images | Date | Notes |
|------|--------|------|-------|
| `telemetry/baseline_50images_before_fixes.json` | 50 | 2025-10-26 | **Primary baseline** |
| `telemetry/baseline_10images_before_fixes.json` | 10 | 2025-10-26 | Quick validation |
| `telemetry/baseline_459images_before_fixes.json` | 459 | 2025-10-26 | Full evaluation |

### Key Failures in Baseline (50-image)

| Item | Count | Stage | Pool Size | Issue |
|------|-------|-------|-----------|-------|
| **Grapes** | 30 | stage0_no_candidates | 50 Foundation | Token mismatch |
| **Almonds** | 27 | stage0_no_candidates | 49 Foundation | Token mismatch |
| **Cantaloupe** | 12 | stage0_no_candidates | 3 Foundation | Token mismatch |
| **Apple** | 26 | stage1b | N/A | Matched "Strudel apple" |

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
  "candidate_pool_raw_foundation": 50
}
```

### Expected After Fixes

| Item | Before | After (Expected) |
|------|--------|------------------|
| Grapes | 30/30 stage0 ❌ | 30/30 stage1b ✅ |
| Almonds | 27/27 stage0 ❌ | 27/27 stage1b ✅ |
| Cantaloupe | 12/12 stage0 ❌ | 12/12 stage1b ✅ |
| Apple | 26/26 "Strudel" ❌ | 0/26 negatives ✅ |

---

## 5. Vision Stage

### Vision Model Adapter

**File**: `vision/openai_.py`

**Purpose**: GPT-4V or GPT-5 image detection

**Output Format**:
```python
{
  "foods": [
    {
      "name": "grapes",
      "form": "raw",
      "mass_g": 150,
      "count": 1,
      "modifiers": ["red"],
      "confidence": 0.85
    }
  ]
}
```

### Prompts & Schemas

**File**: `vision/core/prompts.py`

Contains:
- System prompts for vision model
- Category definitions
- Form/method vocabulary

---

## 6. Vision Model Adapters

**Directory**: `vision/`

| File | Purpose |
|------|---------|
| `openai_.py` | OpenAI API adapter (GPT-4V, GPT-5) |
| `runner.py` | Vision model batch runner |
| `nutritionverse_prompts.py` | Prompts for food detection |
| `advanced_prompts.py` | Advanced prompting strategies |
| `image_preprocessing.py` | Image preprocessing utilities |

**Output Format** (from vision model):
```json
{
  "foods": [
    {"name": "chicken breast", "form": "grilled", "mass_g": 150, "confidence": 0.85}
  ],
  "_metadata": {"model": "gpt-5", "tokens_total": 1932}
}
```

This prediction format is passed directly to the alignment engine.

---

## 7. Ground Truth & Evaluation

### Ground Truth Data

**Status**: ✅ **INCLUDED**

**File**: `ground_truth/metadata.jsonl`

**Format**: JSONL (3260 dishes with ingredient-level ground truth)

```json
{
  "id": "dish_1556572657",
  "file_name": "test/dish_1556572657.png",
  "ingredients": [
    {"name": "olives", "grams": 36.0, "calories": 41.4, "fat": 3.852, "carb": 2.268, "protein": 0.288}
  ],
  "total_calories": 41.4,
  "total_mass": 36.0
}
```

### Evaluation Scripts

**Status**: ✅ **INCLUDED**

**File**: `ground_truth/eval_aggregator.py`

**Functions**:
- `validate_telemetry_schema()`: Validates alignment telemetry structure
- `compute_telemetry_stats()`: Computes stage distribution and conversion rate

**Metrics Computed**:
- Conversion rate (% items using Stage 2 raw→cooked)
- Stage distribution (Stage 1b/2/3/4/5/Z breakdown)
- Unknown stage/method detection
- Stage-Z violations (for produce)

---

## 8. FDC Database Structure

**File**: `data/FDC_DATABASE.md`

Complete documentation of the USDA FoodData Central PostgreSQL database including:
- Database schema (foods table, nutrition columns)
- Data types (Foundation, SR Legacy, Branded)
- Search query patterns
- **Deterministic rebuild instructions**
- Database snapshot export/import
- Validation checklist

**Connection**: Set `NEON_CONNECTION_URL` in `.env` file

Both batch harness and web app must connect to the **same database** to ensure identical candidate pools.

---

## 9. Fixes Applied (2025-10-27)

See `SURGICAL_FIXES_COMPLETE.md` and `STAGE1B_FIXES_COMPLETE.md` for details.

### Morning (A-E2):
1. Variant search scoring (Foundation count + raw bias)
2. Stage-1b negatives (apple/grape/potato/sweet_potato)
3. Melon synonyms (honeydew, cantaloupe)
4. Canonical base selection (excludes leaves/flour/starch)
5. Stage-1c cooked SR direct (bacon/eggs/sausage)
6. Stage-Z meat exception
7. Fruit/melon variant ordering

### Evening (Critical):
8. **Hard filter negatives BEFORE scoring** (line 605-609)
9. **Add almond negatives** (oil/butter/flour)
10. **Single-token core class leniency** (lines 617-628)
11. **Class-specific thresholds** (grape/almond/melon: 0.30)
12. **Prefer plural variants** (grapes before grape)
13. **Corn & tomato variants**

---

## 8. Testing Protocol

### Step 1: Batch Harness (Claude will run)

```bash
cd /Users/austinprofenius/snapandtrack-model-testing/gpt5-context-delivery/entrypoints
python run_first_50_by_dish_id.py

# Output: telemetry/batch_harness_first50_sorted_<timestamp>.json
```

This produces JSON with:
- First 50 dishes sorted by dish_id
- Full telemetry for each food item
- Stage decisions, variant chosen, scores, etc.

### Step 2: Web App (You will run)

**You will**:
1. Run the same 50 dishes (sorted by dish_id) through the web app
2. Capture the alignment results (stage, FDC name, telemetry)
3. Save to `web_app_logs/webapp_first50_sorted_<timestamp>.json`
4. Provide to GPT-5 agent

### Step 3: Comparison (GPT-5 agent will analyze)

GPT-5 will compare:
- Batch harness results
- Web app results
- Identify discrepancies
- Verify both use same alignment code
- Check for environment/config differences

---

## 9. Critical Questions for GPT-5

1. **Batch vs Web App Divergence**:
   - Are stages consistent for same foods?
   - Do variants match?
   - Are scores identical?

2. **Stage-1b Performance**:
   - Are grapes/almonds/melons hitting Stage-1b?
   - Are scores ≥0.30 threshold?
   - Is variant_chosen showing "grapes raw" (not "grape")?

3. **Negative Filter**:
   - Are apple queries avoiding "strudel/pie/juice"?
   - Are almond queries avoiding "oil/butter/flour"?

4. **Stage-Z Violations**:
   - Are any fruits/nuts/vegetables in Stage-Z? (MUST BE 0)

5. **Conversion Issues**:
   - Brussels sprouts selecting "sprouts" not "leaves"?
   - Sweet potato selecting "tuber" not "leaves"?

---

## 10. Environment Requirements

### Database

**Required**: `NEON_CONNECTION_URL` (PostgreSQL with FDC data)

```bash
export NEON_CONNECTION_URL="postgresql://user:pass@host:5432/database"
```

### Vision Model

**Optional** (only if re-running predictions):
```bash
export OPENAI_API_KEY="sk-proj-..."
```

### Debug Logging

**Optional**:
```bash
export ALIGN_VERBOSE=1  # Detailed stage decisions
```

---

## 11. Files Summary

| Category | Files | Purpose |
|----------|-------|---------|
| **Documentation** | 3 | README, fix histories |
| **Entrypoints** | 3 | Batch runners |
| **Alignment Core** | 9 | Engine, adapter, normalizer, guards, conversions |
| **Data Loaders** | 1 | FDC database search |
| **Configs** | 6+ | Method profiles, energy bands, proxies |
| **Telemetry** | 3 | Baseline test results (before fixes) |
| **Vision** | 3+ | GPT-4V/GPT-5 adapters |
| **Total** | **28+** | Complete pipeline context |

---

## 12. Next Steps

1. ✅ **Claude runs**: `run_first_50_by_dish_id.py` → batch harness results
2. ⏳ **You run**: Same 50 dishes through web app → web app results
3. ⏳ **You provide**: Web app JSON to GPT-5 agent
4. ⏳ **GPT-5 analyzes**: Compares batch vs web app, identifies issues

---

## Contact

**Created By**: Claude (Anthropic)
**Date**: 2025-10-27
**Session**: Surgical fixes + context delivery for GPT-5

**Location**: `/Users/austinprofenius/snapandtrack-model-testing/gpt5-context-delivery/`
