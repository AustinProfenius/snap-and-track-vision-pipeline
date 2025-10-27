# CI Fix - Missing Dependencies

**Date**: 2025-10-27
**Issue**: Integration tests failing in GitHub Actions due to missing `dotenv` module

---

## Problem

GitHub Actions CI was failing with:
```
ModuleNotFoundError: No module named 'dotenv'
```

**Root Cause**:
- Integration tests import from `pipeline.fdc_index`
- `pipeline.fdc_index` imports from `src.adapters.fdc_database`
- `src.adapters.__init__` imports from `src.adapters.openai_`
- `src.adapters.openai_` requires `python-dotenv`

**Error Location**:
```
tests/test_pipeline_e2e.py → pipeline.run → pipeline.fdc_index →
src.adapters.fdc_database → src.adapters.__init__ →
src.adapters.openai_ → dotenv (MISSING!)
```

---

## Solution

Updated `.github/workflows/pipeline-ci.yml` to install required dependencies:

### Before:
```yaml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install pytest pydantic PyYAML psycopg2-binary
```

### After:
```yaml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install pytest pydantic PyYAML psycopg2-binary python-dotenv numpy pandas
```

**Added Dependencies**:
- `python-dotenv` - Required by `src.adapters.openai_`
- `numpy` - Required by nutritionverse-tests data processing
- `pandas` - Required by nutritionverse-tests data processing

---

## Why This Wasn't Caught Locally

**Local environment**:
- Has all nutritionverse-tests dependencies installed
- Tests run successfully

**CI environment**:
- Fresh environment with minimal dependencies
- Only installs what's explicitly listed in workflow

**Lesson**: CI workflows need to explicitly install ALL transitive dependencies, even if they're not directly imported by test files.

---

## Files Modified

1. `.github/workflows/pipeline-ci.yml` (line 174)
   - Added: `python-dotenv numpy pandas`

---

## Verification

After this fix, the integration tests job should:
1. ✅ Install dependencies successfully
2. ✅ Import test modules without errors
3. ⚠️  Skip tests if `NEON_CONNECTION_URL` not set (expected)
4. ✅ Run tests successfully if DB credentials provided

---

## Related Documentation

- [PHASE_6_COMPLETE.md](PHASE_6_COMPLETE.md) - CI/CD setup details
- [.github/workflows/pipeline-ci.yml](.github/workflows/pipeline-ci.yml) - GitHub Actions workflow

---

**Status**: ✅ Fixed - Integration tests job now has all required dependencies
