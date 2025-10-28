# Pipeline Convergence Implementation Progress

**Started**: 2025-10-27
**Status**: Phase 1 ~60% Complete

---

## ✅ Completed

### Phase 1: SSOT Package & Config Externalization

**Package Structure**:
- ✅ `pipeline/__init__.py` - Package marker
- ✅ `pipeline/schemas.py` - Complete Pydantic models:
  - `DetectedFood` (vision output)
  - `AlignmentRequest` (input to pipeline)
  - `FoodAlignment` (aligned food result)
  - `Totals` (aggregated macros)
  - `AlignmentResult` (complete result with version tracking)
  - `TelemetryEvent` (per-food event with all mandatory fields)

- ✅ `pipeline/config_loader.py` - Configuration loader:
  - Loads YAML/JSON from `configs/`
  - Computes SHA256 fingerprint for drift detection
  - Returns `PipelineConfig` with `config_version`
  - `get_code_git_sha()` utility for code version tracking

**Config Files**:
- ✅ `configs/class_thresholds.yml` - Per-class thresholds:
  - grape/cantaloupe/honeydew/almond: 0.30
  - olive/tomato: 0.35
  - default: 0.45

- ✅ `configs/negative_vocabulary.yml` - Hard filters (enhanced):
  - Original: apple/grape/almond/potato/sweet_potato
  - **NEW**: cucumber (prevent sea cucumber)
  - **NEW**: olive (prevent olive oil)

- ✅ `configs/feature_flags.yml`:
  - `prefer_raw_foundation_convert: true`
  - `enable_proxy_alignment: true`
  - **`stageZ_branded_fallback: false`** (default for evaluations)
  - `vision_mass_only: true`
  - `strict_cooked_exact_gate: true`

- ✅ `configs/cook_conversions.v2.json` - Copied from nutritionverse-tests

---

## 🚧 Remaining Work

### Phase 1 (Continued):

**Still needed**:
1. ❌ `pipeline/fdc_index.py` - FDC database wrapper:
   - Wrap existing `fdc_database.py`
   - Compute `fdc_index_version` via content hash (deterministic export)
   - Expose `.search(query)` method

2. ❌ `pipeline/run.py` - Main orchestrator:
   - `run_once()` function
   - Call existing `FDCAlignmentWithConversion` with external configs
   - Emit telemetry with all mandatory fields
   - Write JSONL artifacts to `runs/<timestamp>/`

3. ❌ Create optional config files (if needed):
   - `configs/energy_bands.json` (if exists in nutritionverse-tests)
   - `configs/proxy_alignment_rules.json` (if exists)
   - `configs/variants.yml` (optional for now)

### Phase 2: Refactor Entrypoints

❌ Modify 3 entrypoint files to use `pipeline.run_once()`:
1. `gpt5-context-delivery/entrypoints/nutritionverse_app.py`
2. `gpt5-context-delivery/entrypoints/run_first_50_by_dish_id.py`
3. `gpt5-context-delivery/entrypoints/run_459_batch_evaluation.py`

**Pattern**:
```python
from pipeline.run import run_once
from pipeline.config_loader import load_pipeline_config, get_code_git_sha
from pipeline.fdc_index import load_fdc_index
from pipeline.schemas import AlignmentRequest, DetectedFood

# Load once at startup
CONFIG = load_pipeline_config(path="configs/")
FDC = load_fdc_index()
CODE_SHA = get_code_git_sha()

# Per request
request = AlignmentRequest(...)
result = run_once(request, CONFIG, FDC, allow_stage_z=False, code_git_sha=CODE_SHA)
```

### Phase 3: Modify align_convert.py

❌ Add external config support to `FDCAlignmentWithConversion.__init__()`:
```python
def __init__(
    self,
    *,
    class_thresholds: Optional[Dict] = None,
    negative_vocab: Optional[Dict] = None,
    feature_flags: Optional[Dict] = None,
    conversions: Optional[Dict] = None,
    **kwargs
):
    self.class_thresholds = class_thresholds or DEFAULT_CLASS_THRESHOLDS
    self.negative_vocab = negative_vocab or DEFAULT_NEGATIVES_BY_CLASS
    self.feature_flags = feature_flags or DEFAULT_FEATURE_FLAGS
    self.conversions = conversions or load_cook_conversions()
    self.config_source = "external" if any([...]) else "fallback"

    if self.config_source == "fallback":
        print("[WARNING] Using hardcoded defaults. Load from configs/ for reproducibility.")
```

❌ Add `config_source` to telemetry events

### Phase 4: Tests

❌ Create test files:
1. `tests/test_telemetry_schema.py` - Enforce mandatory fields
2. `tests/test_config_loader.py` - Config fingerprint stability
3. `tests/test_pipeline_e2e.py` - Grape/almond/melon regression
4. `tests/test_negative_vocab.py` - Cucumber/olive safeguards

### Phase 5: Golden Comparison

❌ Create `scripts/compare_runs.py`:
- Compare alignment stages between web app and batch harness
- Assert identical results for same inputs
- Generate markdown summary of any mismatches

### Phase 6: CI/CD

❌ Create `.pre-commit-config.yaml`
❌ Create `.github/workflows/pipeline-ci.yml`

---

## Key Design Decisions Made

1. **Config location**: Repo root `configs/` (not inside gpt5-context-delivery/)
2. **FDC versioning**: Content hash of deterministic export (not table counts alone)
3. **Stage-Z default**: `false` in feature_flags.yml (explicit opt-in for graceful mode)
4. **Safeguards added**:
   - cucumber: prevent "Sea cucumber yane (Alaska Native)"
   - olive: prevent "Oil olive salad or cooking"
5. **Backward compatibility**: align_convert.py keeps hardcoded defaults but warns when used

---

## Next Steps

When continuing this implementation:

1. **Complete Phase 1**:
   - Create `pipeline/fdc_index.py`
   - Create `pipeline/run.py`
   - Test config loading: `python -c "from pipeline.config_loader import load_pipeline_config; print(load_pipeline_config().config_version)"`

2. **Phase 2**: Refactor entrypoints (straightforward once run.py exists)

3. **Phase 3**: Modify align_convert.py (backward compatible change)

4. **Phase 4-6**: Tests and CI/CD

---

## Files Created This Session

```
pipeline/
├── __init__.py                        # ✅ Empty package marker
├── schemas.py                         # ✅ Pydantic models (complete)
├── config_loader.py                   # ✅ Config loader with fingerprinting
├── fdc_index.py                       # ❌ TODO
└── run.py                             # ❌ TODO

configs/
├── class_thresholds.yml               # ✅ Per-class thresholds
├── negative_vocabulary.yml            # ✅ Hard filters (enhanced)
├── feature_flags.yml                  # ✅ Feature flags
└── cook_conversions.v2.json           # ✅ Copied from nutritionverse-tests
```

---

## Testing the Completed Work

Once `fdc_index.py` and `run.py` are complete, test with:

```bash
# Test config loading
python -c "from pipeline.config_loader import load_pipeline_config; cfg = load_pipeline_config(); print(f'Config version: {cfg.config_version}')"

# Test schemas
python -c "from pipeline.schemas import AlignmentRequest, DetectedFood; req = AlignmentRequest(image_id='test', foods=[DetectedFood(name='grape', form='raw', mass_g=100)], config_version='test'); print(req)"

# Run first 50 dishes (after entrypoint refactor)
cd gpt5-context-delivery/entrypoints
python run_first_50_by_dish_id.py
# Check: runs/<timestamp>/results.jsonl should have config_version, fdc_index_version
```

---

## Acceptance Criteria (from plan)

- [ ] Web app and batch both import **only** `pipeline.run_once()`
- [ ] `configs/` is single config source for both
- [ ] `fdc_index_version`, `config_fingerprint`, `code_git_sha` in **every** result
- [ ] Golden first-50 comparison: **no per-food mismatches**
- [ ] Tests cover normalization, negatives, conversions, telemetry schema
- [ ] CI blocks config/behavior drift

Current status: **~35% complete** (7/20 major deliverables done)
