# Entrypoints and Orchestration Documentation

## Overview

This document describes **all entrypoints** that invoke the vision model and alignment engine in the NutritionVerse pipeline.

## Architecture

```
┌─────────────────┐
│  Vision Model   │ ← OpenAI GPT-4V/GPT-5
│  (GPT-4V/GPT-5) │    Detects foods, forms, masses
└────────┬────────┘
         │ prediction: {foods: [{name, form, mass_g}]}
         ▼
┌─────────────────┐
│  Alignment      │ ← FDCAlignmentWithConversion
│  Engine         │    Stage 1b/2/3/4/5/Z alignment
└────────┬────────┘
         │ aligned: {foods: [{fdc_id, fdc_name, macros}]}
         ▼
┌─────────────────┐
│  Output         │
│  (JSON/UI)      │
└─────────────────┘
```

## Entrypoints

### 1. **Streamlit Web App** (Interactive UI)

**File**: `nutritionverse_app.py`

**Purpose**: Interactive web interface for testing vision model + alignment on individual dishes.

**Usage**:
```bash
cd /Users/austinprofenius/snapandtrack-model-testing/nutritionverse-tests
streamlit run nutritionverse_app.py
```

**Key Features**:
- Load FoodNutrients dataset (metadata.jsonl + images)
- Select dish by ID from dropdown
- Choose vision model: `gpt-4-vision-preview`, `gpt-5`
- Include/exclude micronutrients
- Run prediction + alignment
- View results with telemetry
- Export results to JSON

**Vision Integration** (lines 400-450):
```python
from src.adapters.openai_ import OpenAIAdapter
from src.core.nutritionverse_prompts import get_macro_only_prompt, parse_json_response

# Initialize vision model
openai_adapter = OpenAIAdapter(model=selected_model)

# Get prompt based on micronutrient selection
if include_micros:
    prompt = get_micro_macro_prompt(image_path)
else:
    prompt = get_macro_only_prompt(image_path)

# Call vision model
raw_response = await openai_adapter.analyze_image_async(image_path, prompt)

# Parse JSON response
prediction = parse_json_response(raw_response)
# prediction = {"foods": [{"name": "chicken", "form": "grilled", "mass_g": 150}]}
```

**Alignment Integration** (lines 500-550):
```python
from src.adapters.alignment_adapter import AlignmentEngineAdapter

# Initialize alignment engine (Stage 5)
adapter = AlignmentEngineAdapter()

# Align prediction with FDC database
aligned = adapter.align_prediction_batch(prediction)
# aligned = {"foods": [{"fdc_id": 171477, "fdc_name": "Chicken...", "calories": 165}]}
```

**Output Format**:
```json
{
  "dish_id": "dish_1556572657",
  "image_filename": "dish_1556572657.png",
  "prediction": {
    "foods": [{"name": "olive", "form": "raw", "mass_g": 40}],
    "_metadata": {"model": "gpt-5", "tokens_total": 1932}
  },
  "database_aligned": {
    "foods": [{
      "fdc_id": 171413,
      "fdc_name": "Oil olive salad or cooking",
      "alignment_stage": "stage1b_raw_foundation_direct",
      "calories": 47.7,
      "telemetry": {...}
    }]
  }
}
```

### 2. **Batch Runner** (459-Image Evaluation)

**File**: `run_459_batch_evaluation.py`

**Purpose**: Run alignment engine on **synthetic test batch** (no vision model, generates predictions programmatically).

**Usage**:
```bash
cd /Users/austinprofenius/snapandtrack-model-testing/nutritionverse-tests
python run_459_batch_evaluation.py
```

**Key Features**:
- Generates 459 synthetic food items (no actual images)
- Tests all alignment stages (Stage 1b/2/3/4/5/Z)
- Validates telemetry schema
- Computes stage distribution statistics
- Exports JSON results with full telemetry

**Synthetic Prediction Generation** (lines 43-150):
```python
test_foods = [
    # Stage 5 proxy targets
    ("mixed salad greens", "raw", 18),
    ("yellow squash", "raw", 18),

    # Conversion layer targets (Stage 2)
    ("chicken breast", "grilled", 165),
    ("potato", "roasted", 110),

    # Raw items (Stage 1b)
    ("tomato", "raw", 18),
    ("grape", "raw", 69),
]

# Generate batch predictions
predictions = []
for food_name, form, kcal in test_foods:
    predictions.append({
        "name": food_name,
        "form": form,
        "mass_g": 100,
        "confidence": 0.85
    })
```

**No Vision Model**: This script bypasses the vision model and directly tests alignment logic.

**Output**: `results/batch_459_results_<timestamp>.json`

### 3. **First 50 Dishes Runner** (Batch Harness for Comparison)

**File**: `run_first_50_by_dish_id.py`

**Purpose**: Run alignment on **first 50 dishes sorted by dish_id** using ground truth ingredients (no vision model).

**Usage**:
```bash
cd /Users/austinprofenius/snapandtrack-model-testing/gpt5-context-delivery/entrypoints
python run_first_50_by_dish_id.py
```

**Key Features**:
- Loads metadata.jsonl for ground truth ingredients
- Sorts dishes alphabetically by dish_id
- Processes first 50 dishes
- Uses **ground truth ingredient names** as predictions (no vision model)
- Outputs JSON with full telemetry for comparison with web app

**Prediction from Ground Truth** (lines 97-114):
```python
# Load metadata.jsonl
metadata = load_metadata("food-nutrients/metadata.jsonl")

# Get first 50 dishes sorted
dish_ids = get_first_50_dishes_sorted(test_dir)

for dish_id in dish_ids:
    dish_meta = metadata[dish_id]
    ingredients = dish_meta["ingredients"]

    # Convert ground truth ingredients to prediction format
    prediction = {
        "foods": [
            {
                "name": ingr["name"],  # Ground truth name (e.g., "olives")
                "form": "raw",  # Default to raw
                "mass_g": ingr["grams"],
                "confidence": 0.85
            }
            for ingr in ingredients
        ]
    }

    # Align with FDC
    aligned = adapter.align_prediction_batch(prediction)
```

**Output**: `telemetry/batch_harness_first50_sorted_<timestamp>.json`

**Comparison Use Case**: User runs same 50 dishes through web app with vision model, then compares:
- Batch harness: Ground truth ingredient names → alignment
- Web app: Vision model detections → alignment

### 4. **Vision Model Runner** (Standalone)

**File**: `vision/runner.py`

**Purpose**: Standalone vision model runner for testing GPT-4V/GPT-5 detection without alignment.

**Usage**:
```python
from vision.runner import analyze_single_image
from vision.nutritionverse_prompts import get_macro_only_prompt

result = analyze_single_image(
    image_path="food-nutrients/test/dish_1556572657.png",
    model="gpt-5",
    prompt_fn=get_macro_only_prompt
)

print(result)
# {
#   "foods": [{"name": "olive", "form": "raw", "mass_g": 40, "count": 10}],
#   "_metadata": {"model": "gpt-5", "tokens_total": 1932}
# }
```

**Key Functions**:
- `analyze_single_image()`: Process one image
- `analyze_batch()`: Process multiple images in parallel
- `parse_json_response()`: Extract structured JSON from model output

### 5. **Test Scripts** (Unit/Integration Tests)

**Files**:
- `test_surgical_fixes.py`: Validates 7 surgical fixes (grape/almond/melon alignment)
- `test_stage_z_batch.py`: Tests Stage-Z branded fallback
- `test_alignment.py`: General alignment tests

**Usage**:
```bash
cd /Users/austinprofenius/snapandtrack-model-testing/nutritionverse-tests
python test_surgical_fixes.py
```

**No Vision Model**: Tests use hardcoded predictions to validate alignment logic.

## Vision Model Output Structure

All entrypoints that call the vision model receive predictions in this format:

```python
{
  "foods": [
    {
      "name": str,           # Food name (e.g., "chicken breast")
      "form": str,           # Cooking form (e.g., "grilled", "raw", "baked")
      "mass_g": float,       # Mass in grams
      "count": int,          # Optional: item count (e.g., 3 strawberries)
      "modifiers": [str],    # Optional: descriptors (e.g., ["boneless", "skinless"])
      "confidence": float    # Optional: 0.0-1.0 confidence score
    }
  ],
  "_metadata": {
    "model": str,            # Model used (e.g., "gpt-5")
    "tokens_input": int,     # Input tokens
    "tokens_output": int,    # Output tokens
    "tokens_total": int      # Total tokens
  }
}
```

**Notes**:
- `name` + `form` are passed to alignment engine for FDC matching
- `mass_g` is used for nutrition calculation after alignment
- `count` and `modifiers` are informational (not used in alignment)

## Alignment Engine Input/Output

All entrypoints pass vision predictions to the alignment adapter:

### Input (to `align_prediction_batch`)

```python
prediction = {
    "foods": [
        {"name": "chicken breast", "form": "grilled", "mass_g": 150, "confidence": 0.85}
    ]
}
```

### Output (from `align_prediction_batch`)

```python
aligned = {
    "available": True,
    "foods": [
        {
            "name": "chicken breast",
            "form": "grilled",
            "mass_g": 150,
            "calories": 247.5,
            "protein_g": 46.5,
            "carbs_g": 0.0,
            "fat_g": 5.4,
            "fdc_id": 171477,
            "fdc_name": "Chicken broilers or fryers breast meat only cooked roasted",
            "match_score": 0.95,
            "alignment_stage": "stage2_raw_convert",
            "conversion_applied": True,
            "telemetry": {
                "alignment_stage": "stage2_raw_convert",
                "method": "roasted",
                "conversion_applied": True,
                "raw_fdc_id": 171075,
                "raw_fdc_name": "Chicken broilers or fryers breast meat only raw",
                "cook_method": "roasted",
                "retention_factor": 0.95,
                "candidate_pool_size": 50,
                "stage1b_score": 0.95
            }
        }
    ],
    "totals": {
        "mass_g": 150,
        "calories": 247.5,
        "protein_g": 46.5,
        "carbs_g": 0.0,
        "fat_g": 5.4
    },
    "telemetry": {
        "total_items": 1,
        "alignment_stages": {"stage2_raw_convert": 1},
        "conversion_applied_count": 1,
        "stage5_proxy_count": 0,
        "conversion_rate": 1.0
    }
}
```

## Running Full Pipeline End-to-End

### Web App with Vision Model

```bash
# 1. Set environment
export NEON_CONNECTION_URL="postgresql://..."
export OPENAI_API_KEY="sk-..."

# 2. Run web app
cd nutritionverse-tests
streamlit run nutritionverse_app.py

# 3. Select dish, model (gpt-5), run prediction
# 4. View results with telemetry
# 5. Export to JSON (saved in results/)
```

### Batch Harness (No Vision)

```bash
# 1. Set environment
export NEON_CONNECTION_URL="postgresql://..."

# 2. Run batch test
cd gpt5-context-delivery/entrypoints
python run_first_50_by_dish_id.py

# 3. Check output
cat telemetry/batch_harness_first50_sorted_<timestamp>.json
```

### Comparison Test (Web App vs Batch Harness)

**Goal**: Verify both pipelines produce identical alignment results for same dishes.

**Steps**:

1. **Batch Harness** (ground truth ingredients):
   ```bash
   cd gpt5-context-delivery/entrypoints
   python run_first_50_by_dish_id.py
   # Output: telemetry/batch_harness_first50_sorted_20251027_091933.json
   ```

2. **Web App** (vision model):
   ```bash
   cd nutritionverse-tests
   streamlit run nutritionverse_app.py
   # Manually run first 50 dishes sorted by dish_id
   # Export results: web-app-gpt_5_first50_images_20251027_092832.json
   ```

3. **Compare Results**:
   ```python
   import json

   batch = json.load(open("batch_harness_first50_sorted_20251027_091933.json"))
   webapp = json.load(open("web-app-gpt_5_first50_images_20251027_092832.json"))

   for i in range(50):
       batch_stages = [f["alignment_stage"] for f in batch["results"][i]["database_aligned"]["foods"]]
       webapp_stages = [f["alignment_stage"] for f in webapp["results"][i]["database_aligned"]["foods"]]

       if batch_stages != webapp_stages:
           print(f"Mismatch: {batch['results'][i]['dish_id']}")
           print(f"  Batch: {batch_stages}")
           print(f"  WebApp: {webapp_stages}")
   ```

## Environment Variables

All entrypoints require these environment variables (set in `.env`):

```bash
# FDC Database (required for alignment)
NEON_CONNECTION_URL="postgresql://user:pass@host/db?sslmode=require"

# OpenAI API (required for vision model)
OPENAI_API_KEY="sk-..."

# Optional: Enable verbose alignment logging
ALIGN_VERBOSE=1
```

## Troubleshooting

### Vision model returns empty `foods` array

**Cause**: Image preprocessing failed or model refused to analyze
**Fix**: Check `_metadata.error` field, verify image path exists

### Alignment returns `stage0_no_candidates`

**Cause**: No FDC entries match the food name
**Fix**:
1. Check variant generation in `search_normalizer.py`
2. Verify FDC database has Foundation/SR Legacy entries for that food
3. Use ALIGN_VERBOSE=1 to see search variants tried

### Web app and batch harness produce different stages

**Possible causes**:
1. **Different food names**: Vision model detected different name than ground truth
2. **Different database**: Web app and batch harness using different NEON_CONNECTION_URL
3. **Code mismatch**: Web app using old alignment code, batch harness using new fixes

**Fix**: Compare `prediction.foods[i].name` between web app and batch harness outputs

## Summary

| Entrypoint | Vision Model? | Alignment? | Use Case |
|------------|---------------|------------|----------|
| `nutritionverse_app.py` | ✅ GPT-4V/GPT-5 | ✅ Stage 1-5+Z | Interactive testing with real images |
| `run_459_batch_evaluation.py` | ❌ Synthetic | ✅ Stage 1-5+Z | Alignment validation (no vision) |
| `run_first_50_by_dish_id.py` | ❌ Ground truth | ✅ Stage 1-5+Z | Batch harness for comparison |
| `vision/runner.py` | ✅ GPT-4V/GPT-5 | ❌ | Vision model testing only |
| `test_surgical_fixes.py` | ❌ Hardcoded | ✅ Stage 1b/2 | Unit tests for surgical fixes |

For GPT-5 agent analysis, compare results from:
- **Batch harness**: `run_first_50_by_dish_id.py` (ground truth ingredients)
- **Web app**: `nutritionverse_app.py` (vision model detections)

Both should produce identical `alignment_stage` and `fdc_id` when given the same food names.
