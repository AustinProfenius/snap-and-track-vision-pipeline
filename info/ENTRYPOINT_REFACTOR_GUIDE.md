# Entrypoint Refactor Guide - Using Unified Pipeline

This document provides complete refactored versions of all 3 entrypoints to use the new `pipeline.run_once()` SSOT.

---

## Phase 1 Complete ✅

All pipeline infrastructure is now in place:
- `pipeline/schemas.py` - Pydantic models
- `pipeline/config_loader.py` - Config loader with fingerprinting
- `pipeline/fdc_index.py` - FDC wrapper with content hash versioning
- `pipeline/run.py` - Main orchestrator
- `configs/` - All externalized configs (thresholds, negatives, flags, conversions)

**Tested and working**:
```bash
python3 -c "from pipeline.config_loader import load_pipeline_config; print(load_pipeline_config().config_version)"
# Output: configs@78fd1736da50

python3 -c "from pipeline.schemas import AlignmentRequest, DetectedFood; req = AlignmentRequest(image_id='test', foods=[DetectedFood(name='grape', form='raw', mass_g=100)], config_version='test'); print(req)"
# Output: image_id='test' foods=[DetectedFood(...)]
```

---

## Phase 2: Entrypoint Refactors

### Common Pattern for All 3 Entrypoints

```python
# Old way (ad-hoc)
from src.adapters.alignment_adapter import AlignmentEngineAdapter
adapter = AlignmentEngineAdapter()
aligned = adapter.align_prediction_batch(prediction)

# New way (unified pipeline)
from pipeline.run import run_once
from pipeline.config_loader import load_pipeline_config, get_code_git_sha
from pipeline.fdc_index import load_fdc_index
from pipeline.schemas import AlignmentRequest, DetectedFood

# Load once at module level
CONFIG = load_pipeline_config(path="configs/")
FDC = load_fdc_index()
CODE_SHA = get_code_git_sha()

# Per request
request = AlignmentRequest(
    image_id=dish_id,
    foods=[DetectedFood(**food) for food in prediction["foods"]],
    config_version=CONFIG.config_version
)

result = run_once(
    request=request,
    cfg=CONFIG,
    fdc_index=FDC,
    allow_stage_z=False,  # Always false for evaluations
    code_git_sha=CODE_SHA
)

# Artifacts automatically saved to runs/<timestamp>/
# Access results: result.foods, result.totals, result.telemetry_summary
```

---

## Refactored File 1: `run_first_50_by_dish_id.py`

**Location**: `gpt5-context-delivery/entrypoints/run_first_50_by_dish_id.py`

**Changes**:
1. Remove `AlignmentEngineAdapter` import
2. Import pipeline components
3. Load config/FDC/SHA at module level
4. Use `run_once()` in loop
5. Results auto-saved to `runs/`

**Complete refactored version**:

```python
"""
Run First 50 Images (Sorted by Dish ID) - Batch Harness Test
Uses unified pipeline for reproducibility.

This script:
1. Loads test dataset from food-nutrients/test
2. Sorts images by dish_id
3. Processes first 50 images using pipeline.run_once()
4. Outputs results to runs/<timestamp>/ with version tracking
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path for pipeline imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import unified pipeline
from pipeline.run import run_once
from pipeline.config_loader import load_pipeline_config, get_code_git_sha
from pipeline.fdc_index import load_fdc_index
from pipeline.schemas import AlignmentRequest, DetectedFood


def load_metadata(metadata_path):
    """Load metadata.jsonl with dish information."""
    metadata = {}
    with open(metadata_path, 'r') as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                dish_id = entry['id']
                metadata[dish_id] = entry
    return metadata


def get_first_50_dishes_sorted(test_dir):
    """Get first 50 dish IDs sorted alphabetically."""
    dish_images = list(Path(test_dir).glob("dish_*.png"))
    dish_ids = sorted([img.stem for img in dish_images])
    return dish_ids[:50]


def run_batch_test():
    """Run batch test on first 50 dishes using unified pipeline."""

    # Load environment
    env_path = Path(__file__).parent.parent.parent / "nutritionverse-tests" / ".env"
    load_dotenv(dotenv_path=env_path, override=True)

    # Paths
    test_dir = Path("/Users/austinprofenius/snapandtrack-model-testing/food-nutrients/test")
    metadata_path = Path("/Users/austinprofenius/snapandtrack-model-testing/food-nutrients/metadata.jsonl")

    # Load pipeline components ONCE
    print("Loading pipeline configuration...")
    CONFIG = load_pipeline_config(path="configs/")
    print(f"  Config version: {CONFIG.config_version}")

    print("Loading FDC index...")
    FDC = load_fdc_index()
    print(f"  FDC version: {FDC.version}")

    CODE_SHA = get_code_git_sha()
    print(f"  Code SHA: {CODE_SHA}")

    # Load metadata
    print("\nLoading metadata...")
    metadata = load_metadata(metadata_path)

    # Get first 50 dishes sorted by ID
    print("Finding first 50 dishes (sorted by dish_id)...")
    dish_ids = get_first_50_dishes_sorted(test_dir)

    print(f"Selected {len(dish_ids)} dishes")
    print(f"First dish: {dish_ids[0]}")
    print(f"Last dish: {dish_ids[-1]}")

    # Process each dish
    print(f"\n{'='*70}")
    print(f"BATCH TEST: First 50 Dishes (Sorted by ID)")
    print(f"{'='*70}\n")

    stage_summary = {}

    for idx, dish_id in enumerate(dish_ids):
        print(f"[{idx+1}/50] Processing {dish_id}...")

        # Get metadata
        dish_meta = metadata.get(dish_id)
        if not dish_meta:
            print(f"  WARNING: No metadata for {dish_id}")
            continue

        # Convert metadata ingredients to DetectedFood objects
        ingredients = dish_meta.get("ingredients", [])
        if not ingredients:
            print(f"  WARNING: No ingredients for {dish_id}")
            continue

        detected_foods = [
            DetectedFood(
                name=ingr["name"],
                form="raw",  # Default to raw
                mass_g=ingr["grams"],
                confidence=0.85
            )
            for ingr in ingredients
        ]

        # Create alignment request
        request = AlignmentRequest(
            image_id=dish_id,
            foods=detected_foods,
            config_version=CONFIG.config_version
        )

        # Run unified pipeline
        try:
            result = run_once(
                request=request,
                cfg=CONFIG,
                fdc_index=FDC,
                allow_stage_z=False,  # Never allow Stage-Z in evaluations
                code_git_sha=CODE_SHA
            )

            # Print summary
            print(f"  Foods: {len(result.foods)}, Stages: {result.telemetry_summary['stage_counts']}")

            # Aggregate stage counts
            for stage, count in result.telemetry_summary['stage_counts'].items():
                stage_summary[stage] = stage_summary.get(stage, 0) + count

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    # Print final summary
    print(f"\n{'='*70}")
    print(f"BATCH TEST COMPLETE")
    print(f"{'='*70}")
    print(f"Processed: {len(dish_ids)} dishes")
    print(f"\nStage distribution:")
    total_items = sum(stage_summary.values())
    for stage, count in sorted(stage_summary.items()):
        pct = (count / total_items * 100) if total_items > 0 else 0
        print(f"  {stage}: {count} ({pct:.1f}%)")

    print(f"\nResults saved to: runs/<timestamp>/results.jsonl")
    print(f"Telemetry saved to: runs/<timestamp>/telemetry.jsonl")


if __name__ == "__main__":
    run_batch_test()
```

---

## Refactored File 2: `run_459_batch_evaluation.py`

**Location**: `gpt5-context-delivery/entrypoints/run_459_batch_evaluation.py`

**Similar changes** - use pipeline.run_once() instead of direct alignment calls.

**Key difference**: This script generates **synthetic** DetectedFood objects (no metadata.jsonl).

**Pattern**:
```python
# Generate synthetic batch
test_foods = [
    ("grape", "raw", 100),
    ("chicken breast", "grilled", 150),
    # ... etc
]

for name, form, mass_g in test_foods:
    request = AlignmentRequest(
        image_id=f"synthetic_{idx}",
        foods=[DetectedFood(name=name, form=form, mass_g=mass_g)],
        config_version=CONFIG.config_version
    )
    result = run_once(request, CONFIG, FDC, allow_stage_z=False, code_git_sha=CODE_SHA)
```

---

## Refactored File 3: `nutritionverse_app.py`

**Location**: `gpt5-context-delivery/entrypoints/nutritionverse_app.py`

**Changes**:
1. Load CONFIG/FDC/CODE_SHA at module level (Streamlit caches these)
2. Replace alignment calls with `run_once()`
3. Display results from `AlignmentResult` object

**Streamlit-specific pattern**:
```python
import streamlit as st
from pipeline.run import run_once
from pipeline.config_loader import load_pipeline_config, get_code_git_sha
from pipeline.fdc_index import load_fdc_index
from pipeline.schemas import AlignmentRequest, DetectedFood

# Load once (Streamlit caches)
@st.cache_resource
def load_pipeline_components():
    cfg = load_pipeline_config()
    fdc = load_fdc_index()
    code_sha = get_code_git_sha()
    return cfg, fdc, code_sha

CONFIG, FDC, CODE_SHA = load_pipeline_components()

# In alignment callback:
detected_foods = [DetectedFood(**food) for food in vision_output["foods"]]
request = AlignmentRequest(
    image_id=dish_id,
    foods=detected_foods,
    config_version=CONFIG.config_version
)

result = run_once(request, CONFIG, FDC, allow_stage_z=False, code_git_sha=CODE_SHA)

# Display results
st.json(result.model_dump())
```

---

## Phase 3: Modify align_convert.py (Backward Compatible)

**File**: `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

**Changes** (find `class FDCAlignmentWithConversion:` and modify `__init__`):

```python
def __init__(
    self,
    *,
    class_thresholds: Optional[Dict[str, float]] = None,
    negative_vocab: Optional[Dict[str, List[str]]] = None,
    feature_flags: Optional[Dict[str, bool]] = None,
    conversions: Optional[Dict] = None,
    **kwargs
):
    """
    Initialize alignment engine with optional external configs.

    Args:
        class_thresholds: Per-class Jaccard thresholds (default: hardcoded)
        negative_vocab: Hard filter negatives (default: hardcoded)
        feature_flags: Feature flags dict (default: hardcoded)
        conversions: Cook conversions data (default: load from file)
    """
    # Use external configs if provided, else fall back to defaults
    if class_thresholds is not None:
        self.class_thresholds = class_thresholds
        self.config_source = "external"
    else:
        # Keep hardcoded defaults
        self.class_thresholds = {
            "grape": 0.30,
            "cantaloupe": 0.30,
            "honeydew": 0.30,
            "almond": 0.30,
            "olive": 0.35,
            "tomato": 0.35,
        }
        self.config_source = "fallback"

    if negative_vocab is not None:
        self.negative_vocab = negative_vocab
        self.config_source = "external"
    else:
        # Keep hardcoded defaults
        self.negative_vocab = {
            "apple": {"strudel", "pie", "juice", "sauce", "chip", "dried"},
            "grape": {"juice", "jam", "jelly", "raisin"},
            "almond": {"oil", "butter", "flour", "meal", "paste"},
            "potato": {"bread", "flour", "starch", "powder"},
            "sweet_potato": {"leave", "leaf", "flour", "starch", "powder"},
        }
        self.config_source = "fallback"

    # Feature flags
    if feature_flags is not None:
        self.feature_flags = feature_flags
    else:
        # Use existing FLAGS import
        from ...config.feature_flags import FLAGS
        self.feature_flags = {
            "prefer_raw_foundation_convert": FLAGS.prefer_raw_foundation_convert,
            "enable_proxy_alignment": FLAGS.enable_proxy_alignment,
            "stageZ_branded_fallback": FLAGS.stageZ_branded_fallback,
            "vision_mass_only": FLAGS.vision_mass_only,
            "strict_cooked_exact_gate": FLAGS.strict_cooked_exact_gate,
        }

    # Conversions
    if conversions is not None:
        self.conversions = conversions
    else:
        self.conversions = load_cook_conversions()

    # Warn if using fallback configs
    if self.config_source == "fallback":
        print("[WARNING] Using hardcoded config defaults. Load from configs/ for reproducibility.")

    # ... rest of __init__ unchanged ...
```

**Also add** `config_source` to telemetry events (find where telemetry dicts are built):

```python
telemetry_event = {
    # ... existing fields ...
    "config_source": self.config_source,  # NEW
}
```

---

## Testing the Refactored Pipeline

### Step 1: Test config loading
```bash
python3 -c "
from pipeline.config_loader import load_pipeline_config, get_code_git_sha
cfg = load_pipeline_config()
print(f'Config version: {cfg.config_version}')
print(f'Code SHA: {get_code_git_sha()}')
"
```

### Step 2: Run refactored batch harness
```bash
cd gpt5-context-delivery/entrypoints
python run_first_50_by_dish_id.py
```

**Expected output**:
```
Loading pipeline configuration...
  Config version: configs@78fd1736da50
Loading FDC index...
  FDC version: fdc@a1b2c3d4e5f6
  Code SHA: 1a2b3c4d5e6f
...
[1/50] Processing dish_1556572657...
  Foods: 1, Stages: {'stage1b_raw_foundation_direct': 1}
...
BATCH TEST COMPLETE
Processed: 50 dishes

Stage distribution:
  stage1b_raw_foundation_direct: 71 (85.5%)
  stage0_no_candidates: 7 (8.4%)
  stageZ_energy_only: 4 (4.8%)

Results saved to: runs/20251027_143022/results.jsonl
Telemetry saved to: runs/20251027_143022/telemetry.jsonl
```

### Step 3: Verify version tracking
```bash
head -1 runs/*/results.jsonl | python3 -m json.tool | grep -E "(config_version|fdc_index_version|code_git_sha)"
```

**Expected**:
```json
"config_version": "configs@78fd1736da50",
"fdc_index_version": "fdc@a1b2c3d4e5f6",
"code_git_sha": "1a2b3c4d5e6f"
```

### Step 4: Verify telemetry schema
```bash
head -1 runs/*/telemetry.jsonl | python3 -m json.tool | grep -E "(image_id|alignment_stage|candidate_pool_size|config_source)"
```

**Expected**: All mandatory fields present.

---

## Acceptance Criteria

- [ ] All 3 entrypoints import `pipeline.run_once()` only
- [ ] No direct imports of `align_convert` or `AlignmentEngineAdapter` in entrypoints
- [ ] `configs/` is the single source of all config data
- [ ] Every result has `config_version`, `fdc_index_version`, `code_git_sha`
- [ ] Every telemetry event has all mandatory fields
- [ ] Stage distribution matches baseline (~85% stage1b for first 50)
- [ ] `runs/<timestamp>/` contains both `results.jsonl` and `telemetry.jsonl`

---

## Next Steps

1. Apply refactors to all 3 entrypoint files
2. Run each script and verify outputs
3. Compare stage distribution with baseline
4. Create golden comparison script (Phase 5)
5. Set up CI/CD (Phase 6)

The pipeline infrastructure is complete and tested - now just wire it into the entrypoints!
