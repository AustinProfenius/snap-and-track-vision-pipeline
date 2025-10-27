# Advanced Prompt Engineering for Nutrition Estimation

This document describes the advanced prompt engineering system implemented for highly accurate meal nutrition estimation using GPT-5 vision models and FDC database integration.

## Overview

The system implements battle-tested prompt engineering techniques from OpenAI's best practices, including:

- **Two-pass detection workflow**: Separate detection from nutrition computation
- **Structured JSON output**: Using JSON Schema for deterministic responses
- **FDC database integration**: Leverage USDA Foundation/Legacy foods for accuracy
- **Uncertainty quantification**: 5th-95th percentile confidence intervals
- **Multi-candidate matching**: Top-3 FDC matches with confidence scores
- **Scale-aware estimation**: Explicit plate diameter and reference objects

## Architecture

### Single-Pass Workflow

```
Image → GPT-5 Vision → Full Meal Estimate (JSON)
```

**Pros**: Fast, one API call
**Cons**: Less accurate nutrition values (model-computed)

### Two-Pass Workflow (Recommended)

```
Pass A: Image → GPT-5 Vision → Detection Only (items + portions)
         ↓
Database: Query FDC → Compute Nutrition (deterministic)
         ↓
Pass B: Review → GPT-5 (optional) → Final Estimate (JSON)
```

**Pros**: Traceable, repeatable nutrition values from USDA database
**Cons**: Slightly slower (but faster with concurrency)

## JSON Schemas

### MealEstimate (Full Output)

```json
{
  "items": [
    {
      "name": "chicken breast, grilled",
      "bbox": [0.2, 0.3, 0.4, 0.5],
      "fdc_candidates": [
        {
          "fdc_id": "171477",
          "match_name": "Chicken, broilers or fryers, breast, meat only, cooked, roasted",
          "confidence": 0.95
        }
      ],
      "portion_estimate_g": 150,
      "macros": {
        "protein_g": 31.0,
        "carbs_g": 0,
        "fat_g": 3.6
      },
      "calories_kcal": 165,
      "confidence": 0.92
    }
  ],
  "totals": {
    "mass_g": 350,
    "calories_kcal": 425,
    "protein_g": 45.2,
    "carbs_g": 32.1,
    "fat_g": 12.3
  },
  "uncertainty": {
    "kcal_low": 340,
    "kcal_high": 510,
    "mass_low_g": 280,
    "mass_high_g": 420
  },
  "notes": {
    "assumptions": ["Plate diameter assumed 27cm", "Chicken breast skinless"],
    "ambiguities": ["Hidden portion under salad", "Exact cooking method unclear"],
    "recommended_followups": ["Side view to estimate depth", "Close-up of chicken texture"]
  }
}
```

### FoodDetection (Pass A)

Simplified schema for detection only:

```json
{
  "items": [
    {
      "name": "chicken breast",
      "bbox": [0.2, 0.3, 0.4, 0.5],
      "portion_estimate_g": 150,
      "portion_range_g": {"low": 120, "high": 180},
      "confidence": 0.9,
      "description": "grilled, appears skinless"
    }
  ],
  "context": {
    "plate_diameter_cm": 27,
    "view_angle_deg": 30,
    "assumptions": ["Standard dinner plate"],
    "ambiguities": ["Partial occlusion by fork"]
  }
}
```

## Prompts

### System Prompt Principles

1. **Role definition**: "You are a professional nutrition estimation model..."
2. **Workflow steps**: Detect → Portion → Map → Compute
3. **Output constraints**: "Return ONLY valid JSON, no reasoning text"
4. **Failure modes**: Explicit handling of low confidence / ambiguity
5. **FDC priority**: Foundation Foods > SR Legacy > Branded (only if logo visible)

### User Prompt Template

```python
Context for estimation:
- Plate diameter: 27 cm
- Known scale objects: standard fork (18.5 cm) in frame
- Image angle: ~30° from vertical
- Region: USA; default to USDA FDC naming
- Return ONLY JSON conforming to MealEstimate schema

Instructions:
1) List visible food items with bbox per item (normalized 0-1)
2) Estimate portion in grams (best single-point estimate)
3) Map to up to 3 USDA FDC candidates (Foundation/Legacy only)
4) Compute macros and calories per item and totals
5) Give uncertainty range for total calories (5-95%)
6) Populate notes.assumptions/ambiguities/recommended_followups
```

## FDC Database Integration

### Database Schema

The Neon PostgreSQL database contains USDA FDC data with the following structure:

- **fdc_id**: Unique food identifier
- **name**: Food name (searchable)
- **data_type**: `foundation_food`, `sr_legacy_food`, `branded_food`, etc.
- **food_category_description**: Category (e.g., "Poultry Products")
- **serving_gram_weight**: Serving size in grams
- **Nutrition values** (per 100g unless serving specified):
  - calories_value, protein_value, carbohydrates_value, total_fat_value
  - Micronutrients: calcium, iron, magnesium, potassium, sodium, vitamins

### Search & Compute Flow

```python
# 1. Search for food
results = db.search_foods(
    query="chicken breast grilled",
    limit=3,
    data_types=["foundation_food", "sr_legacy_food"]
)

# 2. Get best match
fdc_id = results[0]["fdc_id"]

# 3. Compute nutrition for portion
nutrition = db.compute_nutrition(
    fdc_id=fdc_id,
    portion_g=150
)
# Returns: {calories, protein_g, carbs_g, fat_g, ...}
```

## Usage

### Basic Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add:
# - OPENAI_API_KEY=sk-...
# - NEON_CONNECTION_URL=postgresql://...
```

### Single-Pass Mode

```python
from pathlib import Path
from src.adapters.openai_advanced import OpenAIAdvancedAdapter

adapter = OpenAIAdvancedAdapter(
    model="gpt-5",
    use_two_pass=False  # Single-pass mode
)

result = await adapter.infer(Path("meal.jpg"))
print(f"Calories: {result['totals']['calories_kcal']:.1f} kcal")
```

### Two-Pass Mode (with FDC Database)

```python
adapter = OpenAIAdvancedAdapter(
    model="gpt-5",
    use_two_pass=True  # Two-pass mode (requires NEON_CONNECTION_URL)
)

result = await adapter.infer(
    Path("meal.jpg"),
    plate_diameter_cm=27,
    angle_deg=30,
    region="USA",
    include_micros=True
)

# FDC-computed nutrition
for item in result['items']:
    print(f"{item['name']}: {item['portion_estimate_g']}g")
    print(f"  FDC Match: {item['fdc_candidates'][0]['match_name']}")
    print(f"  Calories: {item['calories_kcal']:.1f} kcal")
```

### Testing

```bash
# Run test suite
python test_advanced.py
```

Tests include:
1. FDC database search functionality
2. Single-pass workflow
3. Two-pass workflow with database integration

## Performance Optimizations

### Concurrency

Use `asyncio.gather()` to process multiple images concurrently:

```python
tasks = [adapter.infer(img) for img in image_paths]
results = await asyncio.gather(*tasks)
```

### Batch Processing

The existing batch testing system (from `nutritionverse_app.py`) supports:
- 1-10 concurrent requests (configurable slider)
- Progress tracking
- Automatic result logging

## Accuracy Improvements

### Scale Hints

Always provide:
- Plate diameter (default 27cm)
- Reference objects (fork ≈ 18.5cm)
- Camera angle (helps account for foreshortening)

### Multi-Hypothesis

Request 1-3 FDC candidates per food item:
- Allows review of alternatives
- Confidence scores indicate certainty
- Can select best match manually if needed

### Uncertainty Quantification

- `kcal_low` / `kcal_high`: 5th-95th percentile range
- Higher uncertainty for:
  - Oblique angles
  - Mixed dishes
  - Hidden ingredients
  - Ambiguous cooking methods

### Failure Mode Reporting

The model explicitly reports:
- **Assumptions**: What was assumed (e.g., "skinless chicken")
- **Ambiguities**: What's unclear (e.g., "hidden portion under salad")
- **Recommended followups**: What additional photo/angle would help

## Integration with Existing System

The advanced adapter is compatible with the existing `nutritionverse_app.py`:

```python
# In nutritionverse_app.py, replace:
from src.adapters.openai_ import OpenAIAdapter

# With:
from src.adapters.openai_advanced import OpenAIAdvancedAdapter as OpenAIAdapter
```

All existing features work:
- Single image testing
- Batch testing
- Results viewer
- Concurrent requests

**Plus** new features:
- FDC database integration
- Uncertainty quantification
- Multi-candidate matching
- Structured JSON Schema output

## Best Practices

1. **Always use two-pass workflow** when FDC database is available
2. **Provide scale hints**: plate diameter, reference objects
3. **Request uncertainty ranges**: helps calibrate confidence
4. **Review FDC candidates**: sometimes alternative matches are better
5. **Log ambiguities**: use for follow-up questions or additional photos
6. **Filter data types**: Foundation/Legacy foods are most accurate
7. **Validate confidence**: items <0.3 confidence may need manual review

## Troubleshooting

### Database Connection Issues

```python
# Test database connection
from src.adapters.fdc_database import FDCDatabase

with FDCDatabase() as db:
    results = db.search_foods("chicken breast", limit=3)
    print(f"Found {len(results)} results")
```

If this fails, check:
- `NEON_CONNECTION_URL` in `.env`
- Network connectivity
- Database credentials

### JSON Schema Validation Errors

If GPT-5 returns invalid JSON:
- Check that `strict: true` is set in schema
- Verify all required fields are present
- Review system prompt constraints

### Low Accuracy

If predictions are far from ground truth:
- **Add scale hints**: plate diameter, reference objects
- **Use two-pass workflow**: FDC database more accurate than model estimates
- **Provide camera angle**: helps adjust for foreshortening
- **Request multiple candidates**: review alternatives for better matches
- **Check confidence scores**: low confidence = needs review

## Future Enhancements

- [ ] Multi-angle fusion (combine 2-3 views of same meal)
- [ ] Recipe database integration (for complex dishes)
- [ ] Self-consistency sampling (run N=3, median portions)
- [ ] Active learning (flag low-confidence items for human review)
- [ ] Regional cuisine priors (US vs UK vs EU portion norms)

## References

- [OpenAI Platform - Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
- [OpenAI Platform - Vision](https://platform.openai.com/docs/guides/vision)
- [OpenAI Platform - Best Practices](https://platform.openai.com/docs/guides/prompt-engineering)
- [USDA FDC Database](https://fdc.nal.usda.gov/)
