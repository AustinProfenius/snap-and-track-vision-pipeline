# Entrypoints

Batch runners for pipeline evaluation and testing.

## Available Scripts

### run_first_50_by_dish_id.py

Runs first 50 dishes sorted alphabetically by dish_id.

**Usage:**
```bash
cd nutritionverse-tests/entrypoints
python run_first_50_by_dish_id.py
```

**Output:**
- `runs/<timestamp>/results.jsonl` - Per-food alignment results
- `runs/<timestamp>/telemetry.jsonl` - Detailed per-food telemetry

**Purpose:** Quick validation test for pipeline changes.

### run_459_batch_evaluation.py

Runs full 459-dish ground truth evaluation.

**Usage:**
```bash
cd nutritionverse-tests/entrypoints
python run_459_batch_evaluation.py
```

**Output:**
- Same as run_first_50 but for all 459 dishes
- Includes accuracy metrics against ground truth

**Purpose:** Full evaluation before production deployment.

## How Entrypoints Work

All entrypoints follow this pattern:

1. Load `.env` from repo root
2. Load pipeline config from `/configs`
3. Load FDC index from database
4. For each dish:
   - Load metadata from `food-nutrients/metadata.jsonl`
   - Convert ingredients to `DetectedFood` objects
   - Call `pipeline.run.run_once()`
   - Aggregate telemetry
5. Save results to `runs/<timestamp>/`

## Environment Setup

Entrypoints require:

- `NEON_CONNECTION_URL` in `.env` (FDC database)
- Python path includes repo root (handled by scripts)

## Output Format

### results.jsonl

```json
{
  "image_id": "dish_001",
  "foods": [
    {
      "query": "blackberries",
      "fdc_id": 173946,
      "fdc_name": "Blackberries raw",
      "mass_g": 100.0,
      ...
    }
  ],
  "telemetry_summary": {
    "stage_counts": {"stage1b_raw_foundation_direct": 1}
  }
}
```

### telemetry.jsonl

One line per food item with full telemetry:

```json
{
  "image_id": "dish_001",
  "food_idx": 0,
  "query": "blackberries",
  "alignment_stage": "stage1b_raw_foundation_direct",
  "fdc_id": 173946,
  "stage1c_switched": {"from": "...", "to": "..."},
  ...
}
```

## Adding a New Entrypoint

1. Create script in `nutritionverse-tests/entrypoints/`
2. Import from `pipeline.run`, `pipeline.config_loader`, `pipeline.schemas`
3. Use repo root for paths:
   ```python
   repo_root = Path(__file__).parent.parent.parent
   env_path = repo_root / ".env"
   configs_path = repo_root / "configs"
   ```
4. Call `pipeline.run.run_once()` for each dish
5. Save artifacts to `runs/<timestamp>/`

## Utility Scripts

Root-level convenience scripts:

- `scripts/run_first_50.sh` - Wrapper for run_first_50_by_dish_id.py
- `scripts/grep_stage1c.sh` - Search stage1c_switched events
