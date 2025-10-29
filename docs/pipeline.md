# Pipeline Architecture

Unified nutrition alignment pipeline for Snap & Track vision system.

## Overview

The pipeline takes detected foods from vision analysis and aligns them to USDA FDC (FoodData Central) database entries. It runs through multiple stages with progressive fallbacks to ensure every food gets matched.

## Architecture

```
Vision Detection → Alignment Adapter → Stage 1b → Stage 1c → Stage 2 → Stage 5B → (Stage Z)
                                                                                          ↓
                                                                           FDC Database Entry
```

### Components

1. **Vision Detection** (`nutritionverse-tests/src/core/`): OpenAI GPT-4V extracts foods from images
2. **Alignment Adapter** (`nutritionverse-tests/src/adapters/alignment_adapter.py`): Wrapper for batch processing
3. **Alignment Engine** (`nutritionverse-tests/src/nutrition/alignment/align_convert.py`): Core stage logic
4. **Pipeline Orchestrator** (`pipeline/run.py`): Coordinates stages, writes telemetry
5. **Config Loader** (`pipeline/config_loader.py`): Loads YAML configs from `/configs`

## Alignment Stages

### Stage 1b: Raw Foundation Direct

**Goal:** Match raw foods directly to Foundation Foods in FDC

**How it works:**
1. Generate search variants (e.g., "blackberries" → "blackberry", "blackberries fresh")
2. Search FDC Foundation Foods only
3. Filter by negative vocabulary (e.g., block "blackberries with cream")
4. Score candidates by semantic similarity
5. Return best match if score ≥ threshold

**Success rate:** ~65% of foods

**Config files:**
- `negative_vocabulary.yml` - Blocked terms
- `class_thresholds.yml` - Per-class confidence thresholds
- `variants.yml` - Search variants

### Stage 1c: Raw-First Preference (NEW - Phase 7.4)

**Goal:** Prefer raw foundation foods over processed variants

**How it works:**
1. If Stage 1b matched a non-raw foundation food (e.g., "blackberries frozen unsweetened")
2. Check if a raw variant exists (e.g., "blackberries raw")
3. If raw variant found AND passes guardrails, switch to it
4. Log switch in telemetry: `stage1c_switched: {"from": "...", "to": "..."}`

**Guardrails:**
- Must be Foundation Food
- Must have "raw" in description
- Must pass Atwater energy check (±25%)
- Must not be blocked by negative vocabulary

**Telemetry:** `stage1c_switched` field logs all switches

**Config files:**
- Same as Stage 1b (shares guardrails)

### Stage 2: Semantic → Foundation

**Goal:** Match semantic foods (e.g., "grilled chicken") to Foundation equivalents

**How it works:**
1. Extract base food (e.g., "chicken") from semantic query
2. Search Foundation Foods for base food
3. Apply method inference (e.g., "grilled" → "dry heat")
4. Return Foundation match with inferred method

**Success rate:** ~15% of foods (catches semantic queries missed by 1b)

**Config files:**
- `cook_conversions.v2.json` - Raw→cooked conversions

### Stage 5B: Proxy Alignment Fallback

**Goal:** Match to closest available FDC entry (Foundation, SR Legacy, or Branded)

**How it works:**
1. Search all FDC categories (Foundation, SR Legacy, Branded)
2. Score candidates by semantic similarity
3. Apply category allowlist (prefer Foundation > SR Legacy > Branded)
4. Return best match regardless of food form

**Success rate:** ~18% of foods

**Config files:**
- `category_allowlist.yml` - FDC category preferences
- `proxy_alignment_rules.json` - Proxy matching rules

### Stage Z: Branded Fallback (DISABLED IN EVALUATIONS)

**Goal:** Fallback to branded foods when no Foundation/SR Legacy match exists

**How it works:**
1. Search Branded foods only
2. Return best semantic match
3. Log as "Stage-Z" match

**Usage:** NEVER used in batch evaluations (`allow_stage_z=False`)

**Config files:**
- `branded_fallbacks.yml` - Branded food mappings

## Guardrails

### Negative Vocabulary

Blocks search terms containing unwanted qualifiers:

```yaml
# negative_vocabulary.yml
- "with cream"
- "in syrup"
- "chocolate covered"
```

Prevents matching "blackberries with cream" when user wants plain "blackberries".

### Sodium Gate

Blocks matches with excessive sodium (>500mg/100g for most categories).

**Purpose:** Prevent matching pickled/canned variants for fresh foods.

### Atwater Energy Check

Validates macronutrient energy matches calculated energy (±25%).

**Formula:** `(protein*4 + carbs*4 + fat*9) ≈ energy_kcal`

**Purpose:** Catch data quality issues in FDC database.

### Class Thresholds

Per-food-class confidence thresholds:

```yaml
# class_thresholds.yml
vegetables: 0.70
fruits: 0.75
proteins: 0.80
```

Higher thresholds for ambiguous categories (e.g., proteins need 0.80 to avoid false positives).

## Conversion System

### Raw → Cooked Conversions

When user detects cooked food but we match raw FDC entry:

```json
{
  "food": "chicken breast",
  "method": "dry_heat",
  "retention_factors": {
    "protein": 0.96,
    "fat": 0.89,
    "carbs": 1.0
  },
  "moisture_loss": 0.25
}
```

**Process:**
1. Match raw Foundation food (e.g., "Chicken breast raw")
2. Apply retention factors for cooking method
3. Adjust mass for moisture loss
4. Return converted nutrients

**Config:** `cook_conversions.v2.json`

### Method Inference

Infers cooking method from detection:

- "grilled chicken" → `dry_heat`
- "boiled eggs" → `moist_heat`
- "fried fish" → `deep_fry`

**Config:** `cook_conversions.v2.json` (includes method mappings)

## Telemetry

Every food alignment produces a telemetry event:

```json
{
  "image_id": "dish_001",
  "food_idx": 0,
  "query": "blackberries",
  "alignment_stage": "stage1b_raw_foundation_direct",
  "fdc_id": 173946,
  "fdc_name": "Blackberries raw",
  "stage1c_switched": {"from": "blackberries frozen", "to": "blackberries raw"},
  "candidate_pool_size": 5,
  "foundation_pool_count": 5,
  "stage1b_score": 0.92,
  "match_score": 0.70,
  "conversion_applied": false,
  "negative_vocab_blocks": [],
  "sodium_gate_blocks": null,
  "atwater_ok": true,
  "atwater_deviation_pct": 0.11,
  "code_git_sha": "289c6a4",
  "config_version": "configs@9c1be3db",
  "fdc_index_version": "fdc@unknown"
}
```

**Saved to:** `runs/<timestamp>/telemetry.jsonl`

**Uses:**
- Debugging alignment failures
- Tracking stage1c switches
- Measuring stage distribution
- Evaluating guardrail effectiveness

## Configuration Files

All configs live in `/configs`:

| File | Purpose |
|------|---------|
| `negative_vocabulary.yml` | Blocked search terms |
| `class_thresholds.yml` | Per-class confidence thresholds |
| `variants.yml` | Search variants & normalization |
| `unit_to_grams.yml` | Unit conversion factors |
| `branded_fallbacks.yml` | Stage-Z fallback mappings |
| `category_allowlist.yml` | FDC category preferences |
| `cook_conversions.v2.json` | Raw→cooked conversions |
| `proxy_alignment_rules.json` | Proxy matching rules |
| `feature_flags.yml` | Feature toggles |

**Schema:** See `pipeline/config_loader.py`

**Version tracking:** Config version is hashed and logged in telemetry

## Feature Flags

```yaml
# feature_flags.yml
enable_stage1c: true
enable_sodium_gate: true
enable_atwater_check: true
enable_proxy_fallback: true
```

**Purpose:** Toggle experimental features during calibration

## Adding a New Stage

1. **Implement logic** in `align_convert.py`:
   ```python
   def stage_new(query, fdc_index, config):
       # Your logic here
       return match, telemetry
   ```

2. **Add telemetry fields** in `pipeline/schemas.py`:
   ```python
   class TelemetryEvent(BaseModel):
       # ... existing fields ...
       stage_new_data: Optional[Dict] = None
   ```

3. **Extract telemetry** in `pipeline/run.py`:
   ```python
   stage_new_data = telemetry.get("stage_new_data")
   ```

4. **Add unit tests** in `nutritionverse-tests/tests/`:
   ```python
   def test_stage_new():
       # Test your stage
   ```

5. **Document** in this file (pipeline.md)

## Performance

Typical batch run (50 dishes):

- **Stage 1b**: 65% of foods (~32 foods)
- **Stage 1c**: 5% switches (~2-3 foods)
- **Stage 2**: 15% of foods (~7 foods)
- **Stage 5B**: 18% of foods (~9 foods)
- **Stage Z**: 0% (disabled)

**Total time:** ~2-3 minutes (depends on database latency)

## Error Handling

Stages fail gracefully:

1. Stage 1b fails → Try Stage 1c
2. Stage 1c fails → Try Stage 2
3. Stage 2 fails → Try Stage 5B
4. Stage 5B fails → Try Stage Z (if enabled)
5. Stage Z fails → Log error, continue

**No food is ever dropped** - all foods get a best-effort match.

## Maintenance

### Config Updates

1. Edit YAML file in `/configs`
2. Restart pipeline (configs loaded at startup)
3. Config version auto-updates (based on git hash)

### Database Updates

FDC database lives in Neon PostgreSQL:

- **Connection:** `NEON_CONNECTION_URL` env var
- **Schema:** Standard FDC schema (food, nutrient, etc.)
- **Updates:** Manual sync from USDA FDC (rare)

### Stage Tuning

To tune a stage:

1. Run batch evaluation: `python run_459_batch_evaluation.py`
2. Analyze telemetry: `grep '"alignment_stage"' runs/*/telemetry.jsonl | sort | uniq -c`
3. Adjust thresholds in configs
4. Re-run evaluation
5. Compare stage distribution

## See Also

- [README.md](../README.md) - Repository overview
- [REPO_SNAPSHOT.md](REPO_SNAPSHOT.md) - Code census
- [nutritionverse-tests/entrypoints/README.md](../nutritionverse-tests/entrypoints/README.md) - Batch runners
