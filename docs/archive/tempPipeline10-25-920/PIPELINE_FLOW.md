# OpenAI GPT-5 Vision Pipeline - Complete Flow Documentation

**Snapshot Date**: October 25, 2024, 9:20 AM
**Location**: `/Users/austinprofenius/snapandtrack-model-testing/tempPipeline10-25-920`

---

## 🎯 Pipeline Overview

This pipeline implements a **Vision → Database → Nutrition** workflow for automated food nutrition estimation from images using OpenAI's GPT-5 vision models with USDA FDC database alignment.

### Core Workflow
```
Image → Vision Model (GPT-5) → JSON Response → DB Alignment (FDC) → Final Nutrition
```

---

## 📁 File Inventory & Flow

### **STAGE 1: IMAGE PREPROCESSING**

#### File: `image_preprocessing.py`
**Purpose**: Prepare images for OpenAI API submission

**Functions**:
- `load_and_correct_orientation()` - EXIF orientation handling
- `resize_to_optimal()` - Resize to 1536px (GPT-5 optimal size)
- `compress_to_jpeg()` - High-quality JPEG compression (95%)
- `preprocess_image_for_api()` - Complete preprocessing pipeline

**Input**: Raw image file (any format)
**Output**: Base64-encoded JPEG ready for API

**Used By**: `openai_.py`, `openai_advanced.py`

---

### **STAGE 2: VISION API ADAPTERS**

#### File: `openai_.py`
**Purpose**: Standard OpenAI GPT-5 vision adapter

**Class**: `OpenAIAdapter`

**Key Parameters**:
- `model`: "gpt-5", "gpt-5-mini", "gpt-5-turbo", "gpt-5-vision"
- `use_mass_only`: Boolean (default: True) - Mass-only mode (60-70% token savings)
- `temperature`: Float (default: 0.1)
- `max_tokens`: Int (default: 2048)

**Methods**:
- `async infer(image_path, prompt, system_message, **kwargs)` - Main inference
- `estimate_cost(tokens_input, tokens_output)` - Cost calculation

**API Endpoint**:
- GPT-5 models: `client.responses.create()` (Responses API)
- Fallback: `client.chat.completions.create()` (Chat Completions API)

**Output Modes**:
1. **Mass-only** (default): `{name, mass_g, form, count, confidence}`
2. **Full**: `{name, mass_g, calories, fat_g, carbs_g, protein_g, ...}`

**Used By**: Test scripts, Streamlit app, batch runners

---

#### File: `openai_advanced.py`
**Purpose**: Advanced two-pass workflow with FDC integration

**Class**: `OpenAIAdvancedAdapter`

**Workflow**:
1. **Pass A (Detection)**: Vision model identifies foods + estimates portions
2. **Database Lookup**: FDC search for each detected food
3. **Nutrition Compute**: Scale FDC nutrition to portions
4. **Optional Pass B (Review)**: Adjust estimates if needed

**Methods**:
- `async infer_single_pass()` - Full estimation in one API call
- `async infer_two_pass()` - Detection → lookup → compute workflow
- `async infer()` - Auto-selects workflow based on config

**Output**:
```json
{
  "items": [
    {
      "name": "chicken breast",
      "portion_estimate_g": 150,
      "fdc_candidates": [...],
      "macros": {"protein_g": 31.5, "carbs_g": 0, "fat_g": 3.6},
      "calories_kcal": 165,
      "confidence": 0.95
    }
  ],
  "totals": {...},
  "uncertainty": {"kcal_low": 416, "kcal_high": 624, ...},
  "notes": {"assumptions": [...], "ambiguities": [...]}
}
```

**Used By**: Advanced test scripts, production inference

---

### **STAGE 3: PROMPT TEMPLATES**

#### File: `prompts.py`
**Purpose**: Standard prompt templates for vision models

**Components**:
- `SYSTEM_MESSAGE` - Base system message (nutrition analyst role)
- `DISH_TOTALS_TEMPLATE` - Total dish nutrition only
- `ITEMIZED_TEMPLATE` - Per-item breakdown (with calories)
- `NAMES_ONLY_TEMPLATE` - Food identification only
- `parse_json_response()` - Robust JSON extraction from responses

**System Message Key Instructions**:
- Professional nutrition analyst role
- JSON-only output (no prose)
- Individual food item identification (no grouping)
- Base food names (no cooking modifiers)
- Atwater factor validation

**Used By**: `openai_.py`, test scripts

---

#### File: `advanced_prompts.py`
**Purpose**: Advanced prompts for two-pass workflow

**Components**:
- `SYSTEM_PROMPT_ADVANCED` - Full workflow with FDC mapping
- `SYSTEM_PROMPT_DETECTION` - Detection-only (Pass A)
- `get_detection_prompt()` - Configurable detection prompt
- `get_full_estimation_prompt()` - Full estimation with context
- `get_review_prompt()` - Review/adjustment prompt

**Critical Instructions**:
- Individual item separation (split mixed greens, separate spinach/lettuce/tomatoes)
- Base food names only ("broccoli" not "steamed broccoli")
- FDC mapping priority: Foundation → SR Legacy → avoid branded
- Bounding boxes [x,y,w,h] normalized 0-1
- Uncertainty quantification (5th-95th percentile)

**Context Parameters**:
- `plate_diameter_cm` (default: 27)
- `angle_deg` (default: 30)
- `region` (default: "USA")
- `known_objects` (e.g., "standard fork 18.5 cm")

**Used By**: `openai_advanced.py`

---

#### File: `nutritionverse_prompts.py`
**Purpose**: NutritionVerse-specific prompt templates

**Components**:
- `SYSTEM_MESSAGE` - Full two-stage analysis instructions
- `get_macro_only_prompt()` - Macro-only mode (production default)
- `get_micro_macro_prompt()` - Include micronutrients

**Two-Stage Internal Processing**:
1. **Stage A (Perception)**:
   - Identify all visible food items
   - Count discrete items (eggs, bacon strips)
   - Estimate volume (visual cues + reference objects)
   - Detect cooking form (raw, grilled, fried, etc.)

2. **Stage B (Estimation)**:
   - Calculate mass from volume estimates
   - Check calorie consistency (Atwater factors)
   - Compute macros: Protein (4 kcal/g), Carbs (4 kcal/g), Fat (9 kcal/g)

**Output Format**:
```json
{
  "foods": [
    {"name": "chicken breast", "mass_g": 150, "calories": 165, "protein_g": 31, "carbs_g": 0, "fat_g": 3.6}
  ],
  "totals": {"mass_g": 350, "calories": 520, ...}
}
```

**Used By**: NutritionVerse app, batch evaluation

---

### **STAGE 4: JSON SCHEMAS**

#### File: `schema.py`
**Purpose**: Standard uniform response schema

**Components**:
- `UNIFORM_RESPONSE_SCHEMA` - Base schema for all datasets
- `SchemaMapper` - Convert various formats to uniform schema
- `SchemaDiscovery` - Auto-detect dataset schema

**Uniform Schema**:
```json
{
  "dish_id": "string",
  "image_relpath": "string",
  "foods": [
    {
      "name": "string",
      "mass_g": number,
      "calories_kcal": number,
      "macros_g": {"protein": number, "carbs": number, "fat": number}
    }
  ],
  "totals": {...}
}
```

**Used By**: Batch evaluation, result comparison

---

#### File: `advanced_schema.py`
**Purpose**: Advanced schemas for two-pass workflow

**Schemas**:

1. **MEAL_ESTIMATE_SCHEMA** (Single-pass output):
```json
{
  "items": [
    {
      "name": "string",
      "fdc_candidates": [{"fdc_id": "string", "match_name": "string", "confidence": 0-1}],
      "portion_estimate_g": number,
      "macros": {...},
      "calories_kcal": number,
      "confidence": 0-1
    }
  ],
  "totals": {...},
  "uncertainty": {"kcal_low": number, "kcal_high": number, ...},
  "notes": {"assumptions": [], "ambiguities": []}
}
```

2. **DETECTION_SCHEMA** (Pass A detection-only):
```json
{
  "items": [
    {"name": "string", "portion_estimate_g": number, "confidence": 0-1}
  ],
  "context": {"assumptions": [], "ambiguities": []}
}
```

**Used By**: `openai_advanced.py`

---

### **STAGE 5: FDC DATABASE**

#### File: `fdc_database.py`
**Purpose**: USDA FDC database connector

**Class**: `FDCDatabase`

**Connection**: Neon PostgreSQL (USDA FDC data)

**Methods**:
- `search_foods(query, limit, data_types)` - Search FDC by name
- `compute_nutrition(fdc_id, portion_g)` - Scale nutrition to portion

**Data Types**:
- `foundation_food` - Foundation Foods (highest quality)
- `sr_legacy_food` - SR Legacy Foods (USDA SR database)
- `branded_food` - Branded Foods (lowest priority)

**Nutrition Fields**:
- **Macros**: calories, protein, carbs, fat, fiber, sugars
- **Micros**: calcium, iron, magnesium, potassium, sodium, vitamin D, vitamin B12
- **Metadata**: food category, serving description

**Used By**: `fdc_alignment.py`, `fdc_alignment_v2.py`, `openai_advanced.py`

---

### **STAGE 6: DATABASE ALIGNMENT**

#### File: `fdc_alignment.py`
**Purpose**: V1 alignment engine - Food-to-FDC matching

**Class**: `FDCAlignmentEngine`

**Alignment Process**:
1. Search FDC for exact food name
2. Extract key words if no match (skip modifiers like "cooked", "fresh")
3. Try plural form → raw search → fallback
4. Return best match with confidence score

**Methods**:
- `search_best_match(food_name, data_types)` - Find best FDC match
- `align_predicted_food(food_name, predicted_calories)` - Align single food
- `align_prediction_batch(prediction)` - Align full prediction

**Features**:
- Keyword extraction (smart modifiers filtering)
- Plural form matching
- Raw food preference
- Confidence scoring

**Used By**: Legacy test scripts, basic alignment needs

---

#### File: `fdc_alignment_v2.py`
**Purpose**: V2 alignment engine - Enhanced with guardrails

**Class**: `FDCAlignmentEngineV2`

**Enhanced Features**:

1. **Food Taxonomy Classification**:
   - Produce classes (22 items): tomatoes, bell peppers, strawberries, etc.
   - Whole-food classes (8 items): potatoes, rice, oats, corn, wheat

2. **Quality Filters**:
   - **Processing Mismatch Guard**: Reject breaded/battered when prediction is simple
   - **Negative Vocabulary**: Block species substitution (tofu → chicken), ingredient leakage (cookies → raisins)
   - **Ingredient-Form Ban**: Block flour/starch/powder for whole foods (potato → flour ❌)
   - **Macro Plausibility**: Validate macro ratios per food class

3. **Produce Raw-First Enforcement**:
   - Penalty (-1.5) for cooked/canned when prediction is raw
   - Boost (+1.0) for raw matches
   - Telemetry: `produce_raw_first_penalties`

4. **4-Stage Alignment Priority**:
   - **Stage 2**: Foundation/Legacy raw + conversion (FIRST - cleanest)
   - **Stage 1**: Foundation/Legacy cooked exact (SECOND)
   - **Stage 3**: Branded cooked
   - **Stage 4**: Branded energy match (strict gates: token coverage ≥2, score ≥2.0)
   - **Stage Z**: Branded last-resort fallback (TIGHTEST GATES - catalog gaps)

5. **Stage Z Universal Fallback**:
   - Fills catalog gaps (bell peppers, herbs, uncommon produce)
   - Gates: energy bands, macro validation, ingredients sanity, sodium/sugar checks
   - Prevents zero dropped ingredients
   - Telemetry: `branded_last_resort_used`

**Telemetry Counters**:
- `produce_raw_first_penalties`
- `ingredient_form_bans`
- `branded_last_resort_used`
- `branded_cooked_method_mismatch_rejects`
- `processing_mismatch_blocks`
- `negative_vocabulary_blocks`

**Used By**: Production inference, advanced batch evaluation

---

### **STAGE 7: CONFIGURATION**

#### File: `feature_flags.py`
**Purpose**: Global feature flags for pipeline behavior

**Class**: `FeatureFlags`

**Key Flags**:
- `vision_mass_only` (default: True) - Mass-only mode (60-70% token savings)
- `stageZ_branded_fallback` (default: True) - Stage Z catalog gap filling
- `strict_cooked_exact_gate` (default: True) - Stricter cooking method handling
- `mass_soft_clamps` (default: True) - IQR-based mass constraints
- `vision_debug_energy_prior` (default: False) - Debug energy density estimates
- `branded_two_token_floor_25` (default: True) - Branded two-token coverage floor

**Usage**:
```python
from feature_flags import FLAGS

if FLAGS.vision_mass_only:
    # Return mass-only response
```

**Used By**: All adapters, alignment engines

---

#### File: `apis.yaml`
**Purpose**: API model configurations

**Configured Models**:

**OpenAI**:
- `gpt-5` - Primary production model
- `gpt-5-mini` - Cost-optimized variant
- `gpt-5-turbo` - Performance-optimized
- `gpt-5-vision` - Vision-specialized

**Parameters per Model**:
- `temperature`: 0.1 (low variance)
- `max_tokens`: 2048 (standard), 900 (mass-only)
- `pricing`: per 1M tokens (input/output)
- `supports_json_mode`: Boolean
- `supports_vision`: Boolean

**Used By**: `runner.py`, adapter initialization

---

#### File: `.env.example`
**Purpose**: Environment variable template

**Required Keys**:
- `OPENAI_API_KEY` - OpenAI API key
- `NEON_CONNECTION_URL` - PostgreSQL FDC database URL

**Optional Keys**:
- `ANTHROPIC_API_KEY` - Claude API (multi-model support)
- `GOOGLE_API_KEY` - Gemini API
- `OLLAMA_BASE_URL` - Local Ollama endpoint

**Used By**: All adapters, database connectors

---

### **STAGE 8: UTILITIES**

#### File: `atwater_reconciliation.py`
**Purpose**: Atwater factor validation and reconciliation

**Atwater Factors**:
- Protein: 4 kcal/g
- Carbs: 4 kcal/g
- Fat: 9 kcal/g

**Functions**:
- `validate_atwater_consistency()` - Check macro→calorie consistency (±10% tolerance)
- `reconcile_macros_to_calories()` - Adjust macros to match stated calories

**Used By**: Vision adapters, alignment engines

---

#### File: `prediction_rails.py`
**Purpose**: Prediction constraint validation

**Constraints**:
- Mass feasibility checks
- Calorie range validation
- Macro ratio plausibility
- Confidence thresholds

**Used By**: Vision adapters, post-processing

---

#### File: `calibration.py`
**Purpose**: Model calibration utilities

**Functions**:
- Energy density estimation
- Portion prediction
- Confidence scoring

**Used By**: Advanced adapters, uncertainty quantification

---

### **STAGE 9: EXECUTION & TESTING**

#### File: `runner.py`
**Purpose**: Main evaluation runner with rate limiting and budget tracking

**Classes**:
- `RateLimiter` - Rate limiting (configurable RPS)
- `BudgetTracker` - Cost tracking (USD)
- `EvaluationRunner` - Main orchestrator

**Features**:
- Async execution
- Resume from checkpoint
- Progress tracking
- Multi-model support
- Cost estimation

**Used By**: Batch evaluation scripts

---

#### File: `test_advanced.py`
**Purpose**: Advanced adapter testing

**Tests**:
- `test_single_pass()` - Full estimation in one call
- `test_two_pass()` - Detection + lookup workflow
- `test_database_search()` - FDC search validation

**Usage**:
```bash
python test_advanced.py
```

---

#### File: `test_alignment.py`
**Purpose**: Basic alignment engine testing

**Tests**:
- FDC search functionality
- Best match selection
- Batch alignment

**Usage**:
```bash
python test_alignment.py
```

---

#### File: `test_alignment_v2.py`
**Purpose**: V2 alignment engine testing

**Tests**:
- Guardrails validation (processing mismatch, negative vocabulary)
- Stage priority testing
- Produce raw-first enforcement
- Stage Z fallback

**Usage**:
```bash
python test_alignment_v2.py
```

---

#### File: `test_single_alignment.py`
**Purpose**: Single food alignment testing

**Tests**:
- Individual food FDC matching
- Edge cases (plurals, raw forms, ambiguous names)

**Usage**:
```bash
python test_single_alignment.py
```

---

#### File: `nutritionverse_app.py`
**Purpose**: Streamlit web interface

**Features**:
- Single image inference
- Batch processing
- Results visualization
- Model selection (GPT-5, Claude, Gemini)
- Parameter tuning (plate size, angle, region)
- Ground truth comparison
- DB alignment view

**Usage**:
```bash
streamlit run nutritionverse_app.py
```

---

## 🔄 Complete Data Flow

### Standard Flow (Mass-Only Mode)

```
1. INPUT
   └─ Image file (meal.jpg)

2. IMAGE PREPROCESSING [image_preprocessing.py]
   ├─ EXIF correction
   ├─ Resize to 1536px
   ├─ JPEG compression (95%)
   └─ Base64 encoding

3. PROMPT CONSTRUCTION [nutritionverse_prompts.py]
   ├─ System message (nutrition analyst role)
   ├─ User prompt (macro-only template)
   └─ Context (plate size, angle, region)

4. OPENAI API CALL [openai_.py]
   ├─ Model: gpt-5
   ├─ Endpoint: responses.create()
   ├─ Message format:
   │   ├─ system: SYSTEM_MESSAGE
   │   └─ user: [prompt_text, base64_image]
   └─ Response format: JSON Schema (optional)

5. VISION MODEL PROCESSING [GPT-5 Internal]
   ├─ Stage A (Perception):
   │   ├─ Identify food items
   │   ├─ Count discrete items
   │   ├─ Estimate volumes
   │   └─ Detect cooking forms
   └─ Stage B (Estimation):
       ├─ Calculate mass
       └─ Validate consistency

6. RESPONSE PARSING [prompts.py]
   ├─ Extract JSON from response
   ├─ Validate schema
   └─ Apply mass-only mode filter

7. JSON OUTPUT
   └─ {
       "foods": [
         {"name": "chicken breast", "mass_g": 150, "form": "grilled", "confidence": 0.95},
         {"name": "brown rice", "mass_g": 200, "form": "boiled", "confidence": 0.90}
       ],
       "totals": {"mass_g": 350},
       "_metadata": {"model": "gpt-5", "tokens_input": 850, "tokens_output": 120}
     }

8. DATABASE ALIGNMENT [fdc_alignment_v2.py]
   ├─ For each predicted food:
   │   ├─ FDC search [fdc_database.py]
   │   ├─ Apply quality filters:
   │   │   ├─ Processing mismatch guard
   │   │   ├─ Negative vocabulary
   │   │   ├─ Produce raw-first
   │   │   └─ Ingredient-form ban
   │   ├─ Stage priority:
   │   │   ├─ Stage 2: Foundation raw + conversion
   │   │   ├─ Stage 1: Foundation cooked exact
   │   │   ├─ Stage 4: Branded energy match
   │   │   └─ Stage Z: Last-resort fallback
   │   └─ Return: FDC match + confidence
   └─ Telemetry: stage distribution, rejection counts

9. NUTRITION COMPUTATION [fdc_database.py]
   ├─ For each matched FDC entry:
   │   ├─ Get base nutrition (per 100g)
   │   ├─ Scale to predicted mass
   │   └─ Compute: calories, protein, carbs, fat
   └─ Aggregate totals

10. FINAL OUTPUT
    └─ {
        "prediction": {
          "foods": [...],  # Vision output
          "totals": {...}
        },
        "database_aligned": {
          "available": true,
          "foods": [
            {
              "predicted_name": "chicken breast",
              "fdc_id": 170143,
              "matched_name": "Chicken breast, meat only, raw",
              "data_type": "foundation_food",
              "confidence": 0.95,
              "score": 3.8,
              "nutrition": {
                "mass_g": 150,
                "calories": 165,
                "protein_g": 31.5,
                "carbs_g": 0,
                "fat_g": 3.6
              }
            }
          ],
          "totals": {...},
          "telemetry": {
            "alignment_stages": {"stage2_raw_convert": 1, "stage1_cooked_exact": 1},
            "produce_raw_first_penalties": 0,
            "ingredient_form_bans": 0
          }
        }
      }
```

---

### Advanced Two-Pass Flow

```
1. INPUT
   └─ Image file

2-3. [Same as Standard Flow]

4. PASS A: DETECTION [openai_advanced.py → openai_.py]
   ├─ Prompt: Detection-only (no nutrition computation)
   ├─ Output: {
   │   "items": [
   │     {"name": "chicken breast", "portion_estimate_g": 150, "confidence": 0.95}
   │   ]
   │ }
   └─ Tokens: ~400 (detection is lightweight)

5. DATABASE LOOKUP [fdc_database.py]
   ├─ For each detected item:
   │   ├─ Search FDC database
   │   ├─ Return top 3 candidates
   │   └─ Store: [{fdc_id, match_name, confidence}]
   └─ No API calls (database only)

6. NUTRITION COMPUTATION [fdc_database.py]
   ├─ For each best candidate:
   │   ├─ Get base nutrition (per 100g)
   │   ├─ Scale to detected portion
   │   └─ Compute macros + calories
   └─ Mathematical computation (no API)

7. OPTIONAL PASS B: REVIEW [openai_advanced.py]
   ├─ Input: Detection results + computed nutrition
   ├─ Prompt: Review and adjust if needed
   └─ Output: Refined estimates

8. UNCERTAINTY QUANTIFICATION
   ├─ Calculate 5th-95th percentile ranges
   ├─ Factor in detection confidence
   └─ Output: {kcal_low, kcal_high, mass_low_g, mass_high_g}

9. FINAL OUTPUT
   └─ {
       "items": [...],
       "totals": {...},
       "uncertainty": {...},
       "notes": {
         "assumptions": ["Standard plate diameter 27cm", ...],
         "ambiguities": ["Mixed greens color uncertain", ...],
         "recommended_followups": ["Measure plate for accuracy", ...]
       }
     }
```

**Advantages**:
- **Cost**: 2 lightweight passes cheaper than 1 heavy pass
- **Accuracy**: Database nutrition more reliable than vision estimates
- **Transparency**: Explicit FDC mapping shown
- **Flexibility**: Can swap detection model (vision) from computation source (database)

---

## 🎛️ Configuration Quick Reference

### Feature Flags (feature_flags.py)
```python
FLAGS.vision_mass_only = True       # Mass-only mode (60-70% token savings)
FLAGS.stageZ_branded_fallback = True  # Stage Z catalog gap filling
FLAGS.strict_cooked_exact_gate = True  # Stricter cooking method handling
```

### API Models (apis.yaml)
```yaml
gpt-5:
  temperature: 0.1
  max_tokens: 2048
  pricing:
    input: 2.50   # per 1M tokens
    output: 10.00  # per 1M tokens
```

### Environment (.env)
```bash
OPENAI_API_KEY=sk-...
NEON_CONNECTION_URL=postgresql://...
```

---

## 🧪 Testing Quick Start

### Test Vision Adapter (Mass-Only)
```bash
cd /path/to/nutritionverse-tests
python -c "
import asyncio
from pathlib import Path
from src.adapters.openai_ import OpenAIAdapter

async def test():
    adapter = OpenAIAdapter(model='gpt-5', use_mass_only=True)
    result = await adapter.infer(Path('test_image.jpg'), 'Analyze this meal')
    print(result)

asyncio.run(test())
"
```

### Test Advanced Two-Pass
```bash
python test_advanced.py
```

### Test Alignment V2
```bash
python test_alignment_v2.py
```

### Run Streamlit App
```bash
streamlit run nutritionverse_app.py
```

---

## 📊 Telemetry Metrics

### Vision Metrics
- `tokens_input` - Input tokens (image + prompt)
- `tokens_output` - Output tokens (JSON response)
- `cost_usd` - Estimated cost

### Alignment Metrics (V2)
- `produce_raw_first_penalties` - Cooked/canned produce penalized
- `ingredient_form_bans` - Flour/starch rejects for whole foods
- `branded_last_resort_used` - Stage Z fallback usage
- `branded_cooked_method_mismatch_rejects` - Method mismatches
- `processing_mismatch_blocks` - Breaded/battered rejections
- `negative_vocabulary_blocks` - Species/substitution rejections
- `alignment_stages` - Stage distribution (stage1, stage2, stage4, stageZ)

---

## 🚀 Production Deployment Checklist

### Configuration
- [ ] Set `FLAGS.vision_mass_only = True` (token savings)
- [ ] Set `FLAGS.stageZ_branded_fallback = True` (catalog gaps)
- [ ] Configure `OPENAI_API_KEY` in environment
- [ ] Configure `NEON_CONNECTION_URL` for FDC database
- [ ] Set appropriate rate limits in `apis.yaml`

### Model Selection
- [ ] Use `gpt-5` for production (best quality)
- [ ] Use `gpt-5-mini` for cost optimization (good quality)
- [ ] Set `temperature=0.1` (consistency)
- [ ] Set `max_tokens=900` for mass-only mode

### Monitoring
- [ ] Track `tokens_input` and `tokens_output` per request
- [ ] Monitor cost via `BudgetTracker`
- [ ] Log alignment telemetry (stage distribution, rejection counts)
- [ ] Alert on high `branded_last_resort_used` (>15% suggests catalog gaps)

### Quality Assurance
- [ ] Run `test_alignment_v2.py` to validate guardrails
- [ ] Check `produce_raw_first_penalties > 0` (enforcement active)
- [ ] Check `ingredient_form_bans > 0` (flour/starch blocking active)
- [ ] Validate Stage 2 usage >60% (Foundation raw+convert preference)

---

## 📝 Version History

- **V1.0** (Initial): Basic vision → FDC alignment
- **V2.0** (Guardrails): Quality filters, Stage Z fallback, produce raw-first
- **V2.1** (Mass-Only): 60-70% token savings via mass-only mode
- **Current** (Oct 25, 2024): All features integrated and tested

---

## 🔗 Related Documentation

- OpenAI GPT-5 Vision API: https://platform.openai.com/docs/guides/vision
- USDA FDC Database: https://fdc.nal.usda.gov/
- Atwater Factors: https://en.wikipedia.org/wiki/Atwater_system
- NutritionVerse Dataset: [Internal documentation]

---

**End of Pipeline Documentation**
