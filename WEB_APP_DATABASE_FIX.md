# Web App Database Connection Fix

**Date:** 2025-10-29
**Issue:** Database alignment returning `"available": false` in web app results
**Status:** ✅ FIXED

## Problem

When running nutrition detection from the web app, the database alignment was failing:

```json
{
  "database_aligned": {
    "available": false,
    "foods": [],
    "totals": {
      "mass_g": 0,
      "calories": 0,
      ...
    }
  }
}
```

## Root Cause

The `AlignmentEngineAdapter` was refactored in Phase 7.3 to use **dependency injection**:

```python
# Phase 7.3 refactor (pipeline/run.py pattern)
adapter = AlignmentEngineAdapter()
adapter.alignment_engine = engine  # ← Injected by pipeline
adapter.fdc_db = fdc_db           # ← Injected by pipeline
```

However, the **web app** was still using the old pattern:

```python
# Web app (nutritionverse_app.py)
alignment_engine = AlignmentEngineAdapter()  # ← No injection!
result = alignment_engine.align_prediction_batch(prediction)
```

Since `alignment_engine` and `fdc_db` were never injected, they remained `None`, causing the adapter to return:

```python
if self.alignment_engine is None or self.fdc_db is None:
    return {"available": False, ...}  # ← Always returned this!
```

## Solution

Added **auto-initialization** to the adapter to support both patterns:

### 1. Updated `__init__` to accept optional injections:

```python
def __init__(self, enable_conversion: bool = True, alignment_engine=None, fdc_db=None):
    """
    Initialize alignment engine adapter.

    For web app compatibility: If alignment_engine and fdc_db are not provided,
    they will be auto-initialized on first use.
    """
    self.alignment_engine = alignment_engine
    self.fdc_db = fdc_db
    self._auto_init_attempted = False
```

### 2. Added `_auto_initialize()` method:

```python
def _auto_initialize(self):
    """Auto-initialize engine and database if not provided (for web app compatibility)."""
    if self._auto_init_attempted:
        return

    self._auto_init_attempted = True

    try:
        # Check for database connection
        neon_url = os.getenv("NEON_CONNECTION_URL")
        if not neon_url:
            print("[ADAPTER] ERROR: NEON_CONNECTION_URL not found in environment")
            self.db_available = False
            return

        # Initialize FDC database
        self.fdc_db = FDCDatabase()

        # Initialize alignment engine
        self.alignment_engine = FDCAlignmentWithConversion(fdc_db=self.fdc_db)

        self.db_available = True

    except Exception as e:
        print(f"[ADAPTER] ERROR: Failed to auto-initialize: {e}")
        self.db_available = False
```

### 3. Updated `align_prediction_batch()` to trigger auto-init:

```python
def align_prediction_batch(self, prediction: Dict[str, Any]) -> Dict[str, Any]:
    # Auto-initialize if not injected by pipeline
    if self.alignment_engine is None or self.fdc_db is None:
        self._auto_initialize()

    # ... rest of method
```

## Benefits

1. **Backward compatible** - Web app works without code changes
2. **Forward compatible** - Pipeline can still inject dependencies
3. **Clear error messages** - Logs explain what's happening
4. **Fail-safe** - Returns `{"available": false}` if initialization fails

## Usage Patterns

### Pattern 1: Web App (Auto-initialize)

```python
# No injection needed
adapter = AlignmentEngineAdapter()
result = adapter.align_prediction_batch(prediction)
# ✅ Auto-initializes on first use
```

### Pattern 2: Pipeline (Dependency Injection)

```python
# Inject pre-configured engine and database
fdc_db = FDCDatabase()
engine = FDCAlignmentWithConversion(fdc_db=fdc_db, configs=CONFIG)

adapter = AlignmentEngineAdapter(alignment_engine=engine, fdc_db=fdc_db)
result = adapter.align_prediction_batch(prediction)
# ✅ Uses injected dependencies (no auto-init)
```

## Verification

Tested with blackberries:

```bash
$ python3 -c "..." # Test auto-initialization

[ADAPTER] Auto-initializing alignment engine and database...
[ADAPTER] FDC Database initialized
[ADAPTER] Alignment engine initialized
[ADAPTER] ===== Starting batch alignment (Stage 5 Engine) =====
[ADAPTER] DB Available: True
[ADAPTER] Processing 1 foods
[TELEMETRY] stage1c_switched: {'from': 'blackberries frozen', 'to': 'blackberries raw'}
[ADAPTER]   ✓ Matched: Blackberries raw

Result:
  Available: True  ✅
  Foods aligned: 1
  First food: Blackberries raw
  Calories: 61.9
```

## Requirements

For auto-initialization to work, the `.env` file must contain:

```bash
NEON_CONNECTION_URL=postgresql://...
```

If missing, adapter will gracefully fail and return `{"available": false}`.

## Files Changed

1. **nutritionverse-tests/src/adapters/alignment_adapter.py**
   - Updated `__init__()` to accept optional dependencies
   - Added `_auto_initialize()` method
   - Updated `align_prediction_batch()` to trigger auto-init

## Testing

```bash
# Test with web app
cd nutritionverse-tests
streamlit run nutritionverse_app.py

# Upload an image
# Check that database_aligned.available = true
# Verify foods are aligned with FDC matches
```

## Future Improvements

Optional (not required):

1. **Update web app to use injection pattern:**
   ```python
   # nutritionverse_app.py
   fdc_db = FDCDatabase()
   engine = FDCAlignmentWithConversion(fdc_db=fdc_db)
   adapter = AlignmentEngineAdapter(alignment_engine=engine, fdc_db=fdc_db)
   ```

2. **Load configs in adapter:**
   Currently auto-init uses hardcoded config defaults. Could load from `/configs`:
   ```python
   from pipeline.config_loader import load_pipeline_config
   CONFIG = load_pipeline_config(root="../configs")
   engine = FDCAlignmentWithConversion(fdc_db=fdc_db, configs=CONFIG)
   ```

## Related Issues

- Phase 7.3: Dependency injection refactor
- Phase 7.4: Stage 1c raw-first preference
- Repository refactor: Consolidated structure

---

**Status:** ✅ Database connection restored. Web app now returns proper FDC alignments.
