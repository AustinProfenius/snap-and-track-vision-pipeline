# Complete Alignment Pipeline - tempPipeline10-27-811

**Created**: 2025-10-27
**Purpose**: Complete, reproducible alignment pipeline for web app and batch testing

## Directory Structure

```
tempPipeline10-27-811/
├── README.md                  # This file
├── entrypoints/              # Orchestration & batch runners
├── alignment/                # Core alignment logic & conversions
├── data/                     # FDC database loaders
├── configs/                  # Configuration files & data
├── telemetry/                # Test results & logs
├── vision/                   # Vision model adapters
└── ground_truth/             # Evaluation data & metrics
```

---

## 1. Entrypoints / Orchestration

### Batch Runners

**File**: `entrypoints/run_459_batch_evaluation.py`
- Runs 459-image batch evaluation
- Produces JSON results with full telemetry
- Used for regression testing

**File**: `entrypoints/run_50_image_test.py` (if exists)
- Smaller 50-image subset for quick validation
- Same format as 459-image test

**File**: `entrypoints/test_surgical_fixes.py`
- Quick validation test for specific fixes (grapes, almonds, etc.)
- Tests single items without full batch

### Web App Entry Point

**File**: `alignment/alignment_adapter.py`
- `AlignmentEngineAdapter.align_prediction_batch()` is the main entry point
- Takes prediction dict from vision model
- Returns aligned foods with FDC matches
- Used by Flask/FastAPI web app

**Usage**:
```python
from alignment_adapter import AlignmentEngineAdapter

adapter = AlignmentEngineAdapter()
prediction = {
    "foods": [
        {"name": "grapes", "form": "raw", "mass_g": 100, ...}
    ]
}
result = adapter.align_prediction_batch(prediction)
```

---

## 2. Alignment & Conversion

### Core Alignment Engine

**File**: `alignment/align_convert.py`
- **Class**: `FDCAlignmentWithConversion`
- **Main Method**: `align_food_item()` (line 131)
- **Stages**:
  - Stage 0: No candidates
  - Stage 1: Cooked exact match (Foundation/SR Legacy)
  - **Stage 1b**: Raw Foundation direct match (NEW - lines 497-658)
  - **Stage 1c**: Cooked SR direct (proteins) (NEW - lines 619-672)
  - Stage 2: Raw + conversion (PREFERRED)
  - Stage 3: Branded cooked
  - Stage 4: Branded energy
  - Stage 5: Proxy alignment
  - **Stage-Z**: Energy-only last resort (NEW)

**Critical Fixes Applied** (2025-10-27):
- **Single-token leniency** (lines 617-628): `grape` query scores 0.95 with "Grapes, raw"
- **Hard negative filter** (lines 605-609): Skips "Strudel apple" before scoring
- **Class-specific thresholds** (lines 600-609): grape/almond/melon = 0.30

### Search Normalization

**File**: `alignment/search_normalizer.py`
- **Function**: `generate_query_variants()` (line 120)
- Generates plural/singular variants
- FDC-specific hints (melons, berries, nuts)
- **NEW**: Plural preference for grapes/almonds (lines 213-221)
- **NEW**: Corn variants (lines 231-234)
- **NEW**: Cherry/grape tomato variants (lines 237-242)

### Negative Vocabulary

**Location**: `alignment/align_convert.py` (lines 552-559)

```python
NEGATIVES_BY_CLASS = {
    "apple": {"strudel", "pie", "juice", "sauce", "chip", "dried"},
    "grape": {"juice", "jam", "jelly", "raisin"},
    "almond": {"oil", "butter", "flour", "meal", "paste"},  # NEW
    "potato": {"bread", "flour", "starch", "powder"},
    "sweet_potato": {"leave", "leaf", "flour", "starch", "powder"},
}
```

**Export to Config**: See `configs/negative_vocabulary.yml`

### Stage-Z Guards

**File**: `alignment/stage_z_guards.py`
- **Function**: `can_use_stageZ()` (line 87)
- **Meat Exception** (lines 120-122): Allows Stage-Z for meats even if raw Foundation exists
- **Hard Block**: Fruits/nuts/vegetables NEVER allowed in Stage-Z

### Method Profiles & Conversions

**File**: `configs/data/cook_conversions.v2.json`
- Hydration factors (e.g., rice: 2.5x mass gain)
- Shrinkage factors (e.g., chicken: 0.75x)
- Oil uptake (e.g., frying: +10g fat per 100g)
- Energy bands for plausibility

**Code**: `alignment/conversions/cook_convert.py`
- `convert_from_raw()` function applies conversions
- Uses method profiles from JSON config

---

## 3. Data & Candidate Pools

### FDC Database Loader

**File**: `data/fdc_database.py`
- **Class**: `FDCDatabase`
- **Method**: `search_foods(query, limit=50)`
- Connects to Neon PostgreSQL (USDA FoodData Central mirror)
- Returns Foundation, SR Legacy, and Branded entries

**Environment Variable**: `NEON_CONNECTION_URL`

### Candidate Pool Partitioning

**Location**: `alignment/align_convert.py` (lines 184-191)

```python
raw_foundation = [e for e in fdc_entries if self.is_foundation_raw(e)]
cooked_sr_legacy = [e for e in fdc_entries if self.is_foundation_or_sr_cooked(e)]
branded = [e for e in fdc_entries if self.is_branded(e)]
```

### Synonym Tables

**Embedded in**: `alignment/search_normalizer.py`
- `PLURAL_MAP` (line 19): almonds → almond raw, grapes → grapes raw
- `SYNONYMS` (line 38): cantaloupe → melons cantaloupe raw
- `FDC_HINTS` (line 172): Exact FDC titles for common items

**US↔UK Spellings**: Not currently implemented (add if needed)

---

## 4. Telemetry & Results

### Batch Test Results

**Location**: `telemetry/results/`

**Key Files**:
- `gpt_5_50images_20251026_204653.json` - 50-image test (BEFORE fixes)
- `gpt_5_10images_20251026_192517.json` - 10-image test (BEFORE fixes)
- Future: Re-run after fixes to compare

**Format**:
```json
{
  "timestamp": "20251026_204653",
  "model": "gpt-5",
  "total_images": 50,
  "results": [
    {
      "dish_id": "dish_1234",
      "prediction": {...},
      "database_aligned": {
        "foods": [
          {
            "name": "grapes",
            "alignment_stage": "stage1b_raw_foundation_direct",
            "fdc_name": "Grapes, red or green, raw",
            "telemetry": {
              "variant_chosen": "grapes raw",
              "foundation_pool_count": 50,
              "search_variants_tried": 4,
              "stage1b_score": 0.95
            }
          }
        ]
      }
    }
  ]
}
```

### Telemetry Fields

**Critical Fields** (added 2025-10-27):
- `variant_chosen`: Which search variant was selected
- `foundation_pool_count`: Number of Foundation entries in pool
- `search_variants_tried`: Number of variants attempted
- `stage1b_score`: Stage 1b Jaccard + energy score
- `stage1b_jaccard`: Token overlap score
- `stage1b_energy_sim`: Energy similarity score

### Adapter Logs

**Location**: Console output from `alignment_adapter.py`
- Shows query variant selection
- Foundation pool sizes
- Stage decisions

**Enable Verbose Mode**: `export ALIGN_VERBOSE=1`

---

## 5. Vision Stage

### Vision Model Adapter

**File**: `vision/openai_.py`
- Uses GPT-4V or GPT-5 for image detection
- Outputs structured predictions

### Prediction Format

```python
{
  "foods": [
    {
      "name": "grapes",           # Food name (string)
      "form": "raw",              # Cooking method
      "mass_g": 150,              # Estimated mass
      "count": 1,                 # Item count
      "modifiers": ["red"],       # Descriptors
      "confidence": 0.85          # Model confidence
    }
  ]
}
```

### Category/Label Maps

**File**: `vision/core/prompts.py` (if exists)
- System prompts for vision model
- Category definitions
- Form/method vocabulary

---

## 6. Ground Truth / Evaluation

### Ground Truth Data

**Location**: `ground_truth/` (TO BE ADDED)

**Required Files**:
- `ground_truth.csv` or `ground_truth.json`
- Contains: dish_id, food_name, true_fdc_id, true_calories, true_macros

**Format**:
```csv
dish_id,food_name,mass_g,true_fdc_id,true_calories,true_protein_g,true_carbs_g,true_fat_g
dish_1558029923,bacon,22.0,168322,119.02,10.45,0.0,9.60
dish_1558029923,yam,111.0,169314,137.75,2.11,32.45,0.22
```

### Metric Code

**Location**: `tools/eval_aggregator.py` (TO BE COPIED)

**Metrics**:
- **Conversion Rate**: % of items successfully aligned (not stage0)
- **Stage Distribution**: Count by stage
- **Calorie Accuracy**: Within ±20% tolerance
- **Macro Accuracy**: Protein/carbs/fat within tolerance
- **Stage-Z Violations**: Produce in Stage-Z (MUST BE 0)

**Tolerances**:
```python
CALORIE_TOLERANCE = 0.20  # ±20%
MACRO_TOLERANCE = 5.0     # ±5g absolute
```

---

## 7. Known Issues & Regression Set

### Pre-Fix Issues (from 50-image test 20251026_204653)

1. **Grapes**: 30/30 `stage0_no_candidates` despite 50 Foundation entries
2. **Almonds**: 27/27 `stage0_no_candidates` despite 49 Foundation entries
3. **Cantaloupe**: 12/12 `stage0_no_candidates` despite 3 Foundation entries
4. **Apple**: 26/26 matching "Strudel apple" (negative leak)
5. **Cucumber**: Matched "Cucumber, sea cucumber" (wrong taxonomy)

### Fixes Applied (2025-10-27)

See `STAGE1B_FIXES_COMPLETE.md` and `SURGICAL_FIXES_COMPLETE.md` for details.

**Expected Post-Fix**:
- Grapes: 30/30 stage1b ✅
- Almonds: 27/27 stage1b ✅
- Cantaloupe: 13/13 stage1b ✅
- Apple: 0/26 strudel matches ✅

---

## 8. Running the Pipeline

### Batch Test (Full Pipeline)

```bash
# Set database connection
export NEON_CONNECTION_URL="postgresql://..."

# Run 50-image test
cd entrypoints
python run_50_image_test.py

# Run 459-image test (full evaluation)
python run_459_batch_evaluation.py
```

### Web App Integration

```python
# In Flask/FastAPI route
from alignment.alignment_adapter import AlignmentEngineAdapter

adapter = AlignmentEngineAdapter()

@app.route('/align', methods=['POST'])
def align_food():
    prediction = request.json  # From vision model
    result = adapter.align_prediction_batch(prediction)
    return jsonify(result)
```

### Single-Item Test

```python
from alignment.alignment_adapter import AlignmentEngineAdapter

adapter = AlignmentEngineAdapter()
prediction = {
    "foods": [{"name": "grapes", "form": "raw", "mass_g": 100, "confidence": 0.85}]
}
result = adapter.align_prediction_batch(prediction)
print(result['foods'][0]['fdc_name'])
```

---

## 9. Configuration Files

### Negative Vocabulary

**File**: `configs/negative_vocabulary.yml`

```yaml
apple:
  - strudel
  - pie
  - juice
  - sauce
  - chip
  - dried

grape:
  - juice
  - jam
  - jelly
  - raisin

almond:
  - oil
  - butter
  - flour
  - meal
  - paste
```

### Class Thresholds

**File**: `configs/class_thresholds.yml`

```yaml
# Stage-1b matching thresholds
stage1b_thresholds:
  default: 0.50

  # Single-token classes (require core token + simplicity scoring)
  grape: 0.30
  cantaloupe: 0.30
  honeydew: 0.30
  almond: 0.30

  # Processing-heavy classes
  olive: 0.35
  tomato: 0.35
```

### Feature Flags

**File**: `configs/feature_flags.yml`

```yaml
# Alignment feature flags
prefer_raw_foundation_convert: true
enable_proxy_alignment: true
stageZ_branded_fallback: true
vision_mass_only: true
strict_cooked_exact_gate: true
```

---

## 10. Dependencies

```
psycopg2-binary>=2.9.0
python-dotenv>=0.19.0
openai>=1.0.0  # For vision model
```

---

## 11. Validation Checklist

Before deploying changes:

- [ ] Run 50-image test and compare to baseline
- [ ] Verify Stage-Z produce count == 0
- [ ] Check grapes/almonds/melons: 100% Stage-1b
- [ ] Check apple: 0% negative leaks (no strudel/pie/juice)
- [ ] Run 459-image test for full accuracy metrics
- [ ] Test web app integration with sample images
- [ ] Review telemetry for unexpected stage distributions

---

## 12. Contact & Maintenance

**Last Updated**: 2025-10-27
**Fixes Applied**: Stage-1b critical fixes (single-token leniency, hard negatives, variant ordering)
**Next Steps**: Re-run batch tests to validate fixes
