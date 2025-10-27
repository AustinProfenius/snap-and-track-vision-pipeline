# Raw→Cooked Conversion System

**Version**: 2.0
**Status**: ✅ Implemented
**Goal**: Raise kcal accuracy on cooked foods by ≥10 points without relying on branded databases

---

## Overview

This system implements **method-aware raw→cooked conversion** with a **4-stage alignment priority** to improve nutrition estimation accuracy for cooked foods (rice, pasta, meats, vegetables).

### Key Problem

Vision models often predict cooked foods (e.g., "grilled chicken", "boiled rice") but FDC database has limited cooked entries. Previous approach:
- ❌ Align to raw entries → massive error (raw rice 365 kcal/100g vs boiled rice 130 kcal/100g)
- ❌ Align to branded entries → inconsistent quality, missing nutrients

### Solution

**Stage 2 (PREFERRED PATH)**: Find Foundation/Legacy **raw** entry + apply **physics-based conversion** to cooked equivalent using method-specific factors (hydration, shrinkage, fat rendering, oil uptake).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Vision Model Prediction                                     │
│ "chicken breast" + "grilled" + 168 kcal/100g               │
└────────────────┬────────────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────────────┐
│ 4-Stage Alignment with Conversion Priority                 │
│                                                             │
│ Stage 1: Foundation/Legacy cooked exact match              │
│          (if exists, use directly)                         │
│                                                             │
│ Stage 2: Foundation/Legacy raw + conversion (PREFERRED)    │
│          ├─> Find: "Chicken, broilers, breast, raw"       │
│          ├─> Convert: apply grilled method profile        │
│          └─> Result: 165 kcal/100g, high confidence       │
│                                                             │
│ Stage 3: Branded cooked exact match                        │
│          (branded penalty: -0.20 confidence)               │
│                                                             │
│ Stage 4: Branded closest energy density (LAST RESORT)      │
│          (branded + energy fallback: -0.40 confidence)     │
└─────────────────────────────────────────────────────────────┘
```

---

## Conversion Kernels (Stackable)

### 1. Hydration (Grains, Pasta, Legumes)
**Effect**: Mass increases, nutrients dilute per 100g

```python
# Raw rice → Boiled rice
raw_kcal_100g = 365.0
hydration_factor = 2.8  # Absorbs 2.8× its mass in water
cooked_kcal_100g = 365.0 / 2.8 = 130.4 kcal/100g ✓
```

**Profiles**:
- Rice (boiled): 2.8×
- Pasta (boiled): 2.4×
- Quinoa (boiled): 2.5×

### 2. Shrinkage (Meats, Poultry, Fish)
**Effect**: Mass decreases (water loss), nutrients concentrate per 100g

```python
# Raw chicken → Grilled chicken
raw_kcal_100g = 120.0
shrinkage_fraction = 0.29  # Loses 29% mass
cooked_kcal_100g = 120.0 / 0.71 = 169.0 kcal/100g ✓
```

**Profiles**:
- Chicken breast (grilled): 29% shrinkage
- Beef steak (grilled): 29% shrinkage
- Salmon (grilled): 20% shrinkage

### 3. Fat Rendering (Meats)
**Effect**: Fat melts and drips away during cooking

```python
# After shrinkage concentration
fat_100g = 10.0g
fat_render_fraction = 0.25  # 25% fat lost
remaining_fat = 10.0 × 0.75 = 7.5g
kcal_lost = 2.5g × 9 kcal/g = 22.5 kcal
```

**Profiles**:
- Beef steak (grilled): 25% fat loss
- Pork chop (grilled): 20% fat loss

### 4. Oil Uptake (Fried Foods)
**Effect**: Surface oil absorption during frying

```python
# Fried chicken
oil_uptake_g_per_100g = 8.0g
added_fat = 8.0g
added_kcal = 8.0g × 9 kcal/g = 72 kcal
```

**Profiles**:
- Rice (fried): +4g oil/100g
- Chicken (fried): +8g oil/100g
- Potato (hash browns): +12g oil/100g

### 5. Macro Retention
**Effect**: Some nutrients lost during cooking

```python
# Example: Spinach (boiled)
protein_retention = 0.95  # 5% loss
carbs_retention = 0.90    # 10% loss
fat_retention = 1.00      # No loss
```

### 6. Energy Clamping
**Effect**: Constrain to method-aware plausible bounds

Uses [energy_bands.json](src/data/energy_bands.json) with 50+ food+method combinations:
```json
{
  "rice_white.boiled": {"min": 110, "max": 150},
  "chicken_breast.grilled": {"min": 140, "max": 200},
  "beef_steak.grilled": {"min": 180, "max": 300}
}
```

### 7. Atwater Validation
**Effect**: Ensure kcal ≈ 4P + 4C + 9F (±12% tolerance)

If violated, apply **soft correction** (70% Atwater + 30% original).

---

## Method Resolution

**Priority Cascade**:
1. **Explicit match**: Model says "grilled", config has "grilled" → use "grilled"
2. **Alias expansion**: Model says "sauteed" → normalize to "pan_seared"
3. **Class fallback**: Rice without method → use rice fallback (boiled)
4. **Category fallback**: Meat without method → use meat category default (grilled)
5. **First available**: No hints → use first method in config

**Aliases**:
```python
{
    "sauteed": "pan_seared",
    "baked": "roasted_oven",
    "poached": "boiled",
    "deep-fried": "fried",
    "stir-fried": "fried"
}
```

**Confidence Penalties**:
- Explicit: -0.0 (no penalty)
- Alias: -0.05
- Class fallback: -0.10
- Category fallback: -0.15
- First available: -0.20

---

## Data Files

### [cook_conversions.v2.json](src/data/cook_conversions.v2.json)
40+ food classes with method-specific conversion profiles:
```json
{
  "rice_white": {
    "method_profiles": {
      "boiled": {
        "mass_change": {"type": "hydration", "factor_mean": 2.8, "factor_sd": 0.2}
      },
      "fried": {
        "mass_change": {"type": "hydration", "factor_mean": 2.2},
        "surface_oil_uptake_g_per_100g": {"mean": 4.0, "sd": 1.5}
      }
    },
    "fallback": "boiled"
  }
}
```

### [energy_bands.json](src/data/energy_bands.json)
Method-aware kcal/100g bounds for energy clamping:
```json
{
  "rice_white.boiled": {"min": 110, "max": 150},
  "potato_russet.fries": {"min": 190, "max": 320}
}
```

---

## Module Structure

```
src/nutrition/
├── types.py                    # FdcEntry, ConversionFactors, ConvertedEntry, AlignmentResult
├── utils/
│   └── method_resolver.py      # resolve_method(), normalize_method()
├── conversions/
│   └── cook_convert.py         # convert_from_raw(), apply_*() kernels
├── rails/
│   └── energy_atwater.py       # clamp_energy_to_band(), validate_atwater_consistency()
└── alignment/
    └── align_convert.py        # FDCAlignmentWithConversion (4-stage priority)
```

---

## Integration Points

### 1. Prompt Updates ([nutritionverse_prompts.py](src/core/nutritionverse_prompts.py))

Added cooking method detection instructions:
```python
STAGE A - PERCEPTION:
5. For COOKED items, identify cooking method if visible:
   - Look for grill marks → "grilled"
   - Look for browning/crust → "pan_seared" or "roasted"
   - Look for wetness/steam → "boiled" or "steamed"
   - Look for oil sheen/crispy edges → "fried"
   - If method unclear but clearly cooked → "cooked"
```

Schema updated to accept cooking methods in `form` field:
```json
{
  "form": "grilled/boiled/steamed/fried/pan_seared/roasted/baked"
}
```

### 2. FDC Alignment V2 ([fdc_alignment_v2.py](src/adapters/fdc_alignment_v2.py))

Modified `align_predicted_food()` to:
1. Detect cooked foods (check for cooking keywords in `form`)
2. If cooked + conversion enabled + energy density available:
   - Get FDC candidates (Foundation, Legacy, Branded)
   - Call `conversion_engine.align_food_item()` for 4-stage alignment
   - Scale nutrition to predicted mass/calories
3. Else: fall back to legacy search

---

## Example: Grilled Chicken Breast

```python
# Vision model predicts:
{
  "name": "chicken breast",
  "form": "grilled",
  "mass_g": 150,
  "calories": 248,
  "kcal_per_100g_est": 165
}

# Stage 1: No Foundation "chicken breast, grilled" → skip
# Stage 2: Find Foundation "Chicken, broilers, breast, raw" (FDC 171705)
#          Convert using grilled method profile:

# Raw entry (per 100g):
raw_entry = {
  "protein": 22.5g,
  "fat": 2.6g,
  "carbs": 0.0g,
  "kcal": 120.0
}

# Apply shrinkage (29% loss):
cooked_protein = 22.5 / 0.71 = 31.7g/100g
cooked_fat = 2.6 / 0.71 = 3.7g/100g
cooked_kcal = 120.0 / 0.71 = 169.0 kcal/100g

# Apply fat rendering (5% fat loss):
cooked_fat = 3.7 × 0.95 = 3.5g/100g
cooked_kcal -= (0.2g × 9) = 167.2 kcal/100g

# Clamp to energy band [140-200]:
clamped_kcal = 167.2  # Within band ✓

# Atwater validation:
atwater_kcal = 4×31.7 + 4×0 + 9×3.5 = 158.3 kcal
deviation = |167.2 - 158.3| / 158.3 = 5.6% < 12% ✓

# Final result (per 100g):
converted_entry = {
  "protein": 31.7g,
  "carbs": 0.0g,
  "fat": 3.5g,
  "kcal": 167.2,
  "source": "foundation",
  "fdc_id": 171705,
  "method": "grilled",
  "conversion_applied": True,
  "confidence": 0.75,  # (0.85 base - 0.10 method penalty)
  "provenance": ["shrinkage_29%", "fat_render_5%"]
}

# Scale to predicted mass (150g):
final_nutrition = {
  "mass_g": 150,
  "calories": 250.8,  # 167.2 × 1.5
  "protein_g": 47.6,  # 31.7 × 1.5
  "fat_g": 5.3        # 3.5 × 1.5
}

# Match to prediction: 250.8 vs 248 kcal → 1.1% error ✓
```

---

## Testing

### Unit Tests ([tests/test_cook_convert.py](tests/test_cook_convert.py))

Tests each conversion kernel independently:
- ✅ Method resolution (explicit, alias, fallback)
- ✅ Hydration kernel (rice: 365 → 130 kcal/100g)
- ✅ Shrinkage kernel (chicken: 120 → 169 kcal/100g)
- ✅ Fat rendering (beef: 10g fat → 7.5g)
- ✅ Oil uptake (fried: +4g oil → +36 kcal)
- ✅ Energy clamping (200 kcal → 150 kcal if above band)
- ✅ Atwater validation (4P + 4C + 9F within ±12%)

Run tests:
```bash
python tests/test_cook_convert.py
```

### Test Fixtures ([tests/fixtures/fdc_stubs.json](tests/fixtures/fdc_stubs.json))

Sample FDC entries for:
- Foundation raw foods (rice, chicken, salmon, spinach)
- Foundation cooked foods (rice cooked, chicken roasted)
- Branded cooked foods
- Conversion test cases with expected outputs

---

## Performance Targets

### Accuracy Improvement
- **Target**: ≥10 point improvement on 19-image test set
- **Baseline**: Raw alignment (e.g., rice: 365 kcal/100g)
- **Expected**: Converted alignment (e.g., rice: 130 kcal/100g)

### Quality Metrics
- **Atwater violations**: <2% of items
- **Energy clamps**: <20% of items (indicates large model deviations)
- **Conversion confidence**: ≥0.70 for Stage 2 (Foundation conversion)

### Telemetry
Every converted item logs:
```json
{
  "alignment_stage": "stage2_raw_convert",
  "method": "grilled",
  "method_reason": "explicit",
  "conversion_applied": true,
  "conversion_steps": ["shrinkage_29%", "fat_render_5%"],
  "atwater_ok": true,
  "atwater_deviation_pct": 0.056,
  "energy_clamped": false,
  "raw_fdc_id": 171705,
  "raw_source": "foundation"
}
```

---

## Usage

### Enable/Disable Conversion

```python
from src.adapters.fdc_alignment_v2 import FDCAlignmentEngineV2

# Enable (default)
engine = FDCAlignmentEngineV2(enable_conversion=True)

# Disable (legacy behavior)
engine = FDCAlignmentEngineV2(enable_conversion=False)
```

### Align with Conversion

```python
# Prediction from vision model
predicted_food = {
    "name": "rice",
    "form": "boiled",
    "mass_g": 200,
    "calories": 260,
    "kcal_per_100g_est": 130,
    "confidence": 0.85
}

# Align to database (will use Stage 2 conversion if available)
alignment = engine.align_predicted_food("rice", predicted_food)

# Result:
{
    "fdc_id": 168874,  # Raw rice FDC ID
    "matched_name": "Rice, white, long-grain, regular, raw (boiled)",
    "data_type": "foundation",
    "confidence": 0.75,  # Adjusted for method fallback
    "nutrition": {
        "mass_g": 200,
        "calories": 260,
        "protein_g": 5.4,
        "carbs_g": 56.3,
        "fat_g": 0.6
    },
    "provenance": {
        "alignment_stage": "stage2_raw_convert",
        "method": "boiled",
        "conversion_applied": True,
        "conversion_steps": ["hydration_×2.80"],
        "atwater_ok": True
    }
}
```

---

## Confidence Mathematics

```python
# Base confidence from model
conf = 0.85

# Method resolution penalty
if method_reason == "explicit": conf -= 0.0
if method_reason == "alias": conf -= 0.05
if method_reason == "class_fallback": conf -= 0.10

# Alignment stage penalty
if stage == "stage3_branded_cooked": conf -= 0.20
if stage == "stage4_branded_energy": conf -= 0.40

# Energy similarity bonus
if energy_diff_pct <= 15%: conf += 0.10

# Conversion quality penalties
if energy_clamped: conf -= 0.10
if not atwater_ok: conf -= 0.05

# Final confidence
conf = min(max(conf, 0.05), 0.99)
```

---

## Future Improvements

1. **Vision-based method hints**: Detect grill marks, browning, wetness from image
2. **Uncertainty quantification**: Per-kernel uncertainty propagation
3. **Multi-modal fusion**: Combine text + vision for method detection
4. **Adaptive thresholds**: Learn energy band bounds from validation data
5. **Micronutrient conversion**: Extend to vitamins/minerals (currently macros only)

---

## References

- [cook_conversions.v2.json](src/data/cook_conversions.v2.json) - Conversion profiles
- [energy_bands.json](src/data/energy_bands.json) - Energy density bounds
- [USDA FoodData Central](https://fdc.nal.usda.gov/) - Foundation & SR Legacy foods
- [Atwater factors](https://en.wikipedia.org/wiki/Atwater_system) - Energy calculation

---

**Status**: ✅ Implementation complete. Ready for validation on 19-image test set.
