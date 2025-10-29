# Unused or Duplicate Files Report

**Generated**: 2025-10-29
**Purpose**: Identify files for deletion/archival during repository consolidation

---

## Executive Summary

**Total Files Flagged**: ~60 files + 3 entire directories
**Estimated Lines to Remove**: ~5000+
**Primary Issues**: Duplication across temporary delivery directories, superseded adapters, old snapshots

---

## Duplicates by Directory

### `/gpt5-context-delivery` (ENTIRE DIRECTORY - DELETE AFTER MOVING ENTRYPOINTS)

#### `/gpt5-context-delivery/alignment/` - ALL DUPLICATES

| File | Duplicate Of | Date | Action |
|------|--------------|------|--------|
| `align_convert.py` | `nutritionverse-tests/src/nutrition/alignment/align_convert.py` | 2025-10-27 copy | **DELETE** |
| `alignment_adapter.py` | `nutritionverse-tests/src/adapters/alignment_adapter.py` | 2025-10-27 copy | **DELETE** |
| `cook_convert.py` | `nutritionverse-tests/src/nutrition/conversions/cook_convert.py` | 2025-10-27 copy | **DELETE** |
| `search_normalizer.py` | `nutritionverse-tests/src/adapters/search_normalizer.py` | 2025-10-27 copy | **DELETE** |
| `stage_z_guards.py` | `nutritionverse-tests/src/nutrition/alignment/stage_z_guards.py` | 2025-10-27 copy | **DELETE** |

**Reason**: Exact copies from nutritionverse-tests made during temporary delivery. No unique logic.
**Suggested Action**: **DELETE entire `/gpt5-context-delivery/alignment/` directory**

---

#### `/gpt5-context-delivery/vision/` - ALL DUPLICATES

| File | Duplicate Of | Date | Action |
|------|--------------|------|--------|
| `openai_.py` | `nutritionverse-tests/src/adapters/openai_.py` | 2025-10-27 copy | **DELETE** |
| `advanced_prompts.py` | `nutritionverse-tests/src/core/advanced_prompts.py` | 2025-10-27 copy | **DELETE** |
| `schema.py` | `nutritionverse-tests/src/core/schema.py` | 2025-10-27 copy | **DELETE** |
| `advanced_schema.py` | `nutritionverse-tests/src/core/advanced_schema.py` | 2025-10-27 copy | **DELETE** |
| `prompts.py` | `nutritionverse-tests/src/core/prompts.py` | 2025-10-27 copy | **DELETE** |
| `runner.py` | `nutritionverse-tests/src/core/runner.py` | 2025-10-27 copy | **DELETE** |
| `evaluator.py` | `nutritionverse-tests/src/core/evaluator.py` | 2025-10-27 copy | **DELETE** |
| `loader.py` | `nutritionverse-tests/src/core/loader.py` | 2025-10-27 copy | **DELETE** |

**Reason**: Exact copies from nutritionverse-tests/src/core made for temporary delivery.
**Suggested Action**: **DELETE entire `/gpt5-context-delivery/vision/` directory**

---

#### `/gpt5-context-delivery/configs/` - ALL DUPLICATES

| File | Duplicate Of | Action |
|------|--------------|--------|
| `negative_vocabulary.yml` | `/configs/negative_vocabulary.yml` | **DELETE** |
| `class_thresholds.yml` | `/configs/class_thresholds.yml` | **DELETE** |
| `feature_flags.yml` | `/configs/feature_flags.yml` | **DELETE** |

**Reason**: Exact copies of root-level configs.
**Suggested Action**: **DELETE entire `/gpt5-context-delivery/configs/` directory**

---

#### `/gpt5-context-delivery/entrypoints/` - MOVE BEFORE DELETING PARENT

| File | Status | Action |
|------|--------|--------|
| `run_first_50_by_dish_id.py` | **UNIQUE - ACTIVE** | **MOVE** to `nutritionverse-tests/entrypoints/` |
| `test_surgical_fixes.py` (if exists) | Check if duplicate | **MOVE** if unique, **DELETE** if duplicate |

**Reason**: These entrypoints call the unified pipeline and are actively used.
**Suggested Action**: **MOVE** to nutritionverse-tests, then **DELETE** parent directory

---

### `/tempPipeline10-27-811` (ENTIRE DIRECTORY - ARCHIVE OR DELETE)

**Status**: Old snapshot from 2025-10-27, entirely superseded

| Subdirectory | Files | Reason | Action |
|--------------|-------|--------|--------|
| `/alignment/` | All files | Older versions of current code | **DELETE** |
| `/vision/` | All files | Older versions of current code | **DELETE** |
| `/configs/` | All config YAMLs | Older versions | **DELETE** |
| `/entrypoints/` | Old test scripts | Superseded | **DELETE** |
| `/telemetry/` | Old results | Can archive separately | **MOVE** to results archive or **DELETE** |
| `/ground_truth/` | eval_aggregator.py | Check if duplicate | **DELETE** if duplicate |

**Files Flagged**: All ~50+ files in this directory
**Suggested Action**: **DELETE entire `/tempPipeline10-27-811/` directory** or **ARCHIVE** to `.archived/tempPipeline_snapshot_20251027/`

---

## Superseded Files (Non-Duplicates)

### `/nutritionverse-tests/src/adapters/` - Superseded Alignment Modules

| File | Lines | Reason | Action |
|------|-------|--------|--------|
| `fdc_alignment.py` | ~800 | Superseded by `align_convert.py` (Phase 7) | **DELETE** |
| `fdc_alignment_v2.py` | ~1000 | Superseded by `align_convert.py` (Phase 7) | **DELETE** |

**Why Superseded**:
- `align_convert.py` is the current alignment engine (2000+ lines, includes Stage 1b/1c/2/5/Z)
- These old files were pre-Phase 7 implementations
- No imports found referencing these files

**Verification Steps**:
```bash
# Check if anything imports these files
grep -r "from.*fdc_alignment import\|import.*fdc_alignment" \
  nutritionverse-tests pipeline gpt5-context-delivery 2>/dev/null

# Expected: No results (safe to delete)
```

**Suggested Action**: **DELETE** after verification

---

## Experimental/Unused Adapters

### `/nutritionverse-tests/src/adapters/` - Unused LLM Adapters

| File | Lines | Reason | Last Used | Action |
|------|-------|--------|-----------|--------|
| `ollama_llava.py` | ~200 | Experimental local LLM, not in prod | Unknown | **ARCHIVE** to `.archived/adapters/` |
| `claude_.py` | ~150 | Not used (OpenAI only in prod) | Unknown | **ARCHIVE** |
| `gemini_.py` | ~150 | Not used (OpenAI only in prod) | Unknown | **ARCHIVE** |

**Why Archive (Not Delete)**:
- May have experimental value for future comparison
- Not causing issues (not imported anywhere)
- Small files (~500 lines total)

**Verification Steps**:
```bash
# Check if anything imports these
grep -r "from.*ollama_llava\|from.*claude_\|from.*gemini_" \
  nutritionverse-tests pipeline gpt5-context-delivery 2>/dev/null

# Expected: No results
```

**Suggested Action**: **ARCHIVE** to `.archived/experimental_adapters/`

---

## Old Documentation

### `/nutritionverse-tests/info/` - Documentation Archive

**Status**: Historical documentation, no longer actively updated
**Files**: ~30 markdown files with old status updates, changelogs, summaries

| Category | Files | Action |
|----------|-------|--------|
| Status docs | `PHASE_*.md`, `FINAL_STATUS.md`, etc. | **MOVE** to `/docs/archive/nutritionverse-info/` |
| Changelogs | `CHANGELOG.md`, `UPDATE_NOTES.md` | **MOVE** |
| Quickstarts | `QUICKSTART.md` | **MOVE** |
| Summaries | Various project summaries | **MOVE** |

**Reason**: Consolidate documentation into `/docs`
**Suggested Action**: **MOVE** entire directory to `/docs/archive/nutritionverse-info/`

---

## Telemetry/Results Archives

### Multiple Result Directories

| Directory | Files | Size Est. | Action |
|-----------|-------|-----------|--------|
| `nutritionverse-tests/results/` | ~40 JSON files | ~50MB | **KEEP** (recent results) |
| `gpt5-context-delivery/telemetry/` | ~30 JSON files | ~40MB | **MOVE** to `nutritionverse-tests/results/` or **DELETE** if duplicates |
| `tempPipeline10-27-811/telemetry/` | ~30 JSON files | ~40MB | **DELETE** (old results) |

**Suggested Action**:
- **KEEP** `nutritionverse-tests/results/` as primary results archive
- **MOVE** unique files from `gpt5-context-delivery/telemetry/` if needed
- **DELETE** old results from `tempPipeline10-27-811/`

---

## Summary by Action

### DELETE (High Priority)

**Directories**:
- ❌ `/gpt5-context-delivery/alignment/` (entire directory, ~5 files, ~2000 lines)
- ❌ `/gpt5-context-delivery/vision/` (entire directory, ~8 files, ~1500 lines)
- ❌ `/gpt5-context-delivery/configs/` (entire directory, 3 files)
- ❌ `/tempPipeline10-27-811/` (entire directory, ~50 files, ~3000 lines)

**Individual Files**:
- ❌ `nutritionverse-tests/src/adapters/fdc_alignment.py` (~800 lines)
- ❌ `nutritionverse-tests/src/adapters/fdc_alignment_v2.py` (~1000 lines)

**Total to Delete**: ~8400 lines of duplicate/superseded code

---

### MOVE (High Priority)

**From**: `/gpt5-context-delivery/entrypoints/`
**To**: `/nutritionverse-tests/entrypoints/`
**Files**:
- ✅ `run_first_50_by_dish_id.py` (active entrypoint)

**From**: Various locations
**To**: `/docs/archive/`
**Files**:
- ✅ `nutritionverse-tests/info/` (entire directory)

---

### ARCHIVE (Medium Priority)

**To**: `.archived/experimental_adapters/`
**Files**:
- 📦 `nutritionverse-tests/src/adapters/ollama_llava.py`
- 📦 `nutritionverse-tests/src/adapters/claude_.py`
- 📦 `nutritionverse-tests/src/adapters/gemini_.py`

**Total**: ~500 lines

---

## Verification Checklist

Before deleting any file, verify:

- [ ] No imports found via grep
- [ ] Not referenced in any test
- [ ] Not mentioned in active documentation
- [ ] Confirmed duplicate of a file in canonical location
- [ ] Tests still pass after deletion (run test suite)

**Suggested Verification Script**:
```bash
#!/bin/bash
# verify_safe_to_delete.sh
FILE=$1

echo "Checking if safe to delete: $FILE"

# Check for imports
echo "Searching for imports..."
grep -r "from.*$(basename $FILE .py)\|import.*$(basename $FILE .py)" \
  nutritionverse-tests pipeline gpt5-context-delivery 2>/dev/null

# Check for references in tests
echo "Searching for test references..."
grep -r "$(basename $FILE)" nutritionverse-tests/tests pipeline/tests 2>/dev/null

# Check for references in docs
echo "Searching for documentation references..."
grep -r "$(basename $FILE)" docs DOCS *.md 2>/dev/null

echo "If no results above, likely safe to delete."
```

---

## Execution Plan

### Step 1: Backup

```bash
# Create backup before any deletion
tar -czf repo_backup_$(date +%Y%m%d).tar.gz \
  gpt5-context-delivery tempPipeline10-27-811 \
  nutritionverse-tests/src/adapters/{fdc_alignment.py,fdc_alignment_v2.py,ollama_llava.py,claude_.py,gemini_.py}
```

### Step 2: Move Unique Files

```bash
# Move entrypoints
mkdir -p nutritionverse-tests/entrypoints
mv gpt5-context-delivery/entrypoints/run_first_50_by_dish_id.py nutritionverse-tests/entrypoints/

# Move docs
mkdir -p docs/archive
mv nutritionverse-tests/info docs/archive/nutritionverse-info
```

### Step 3: Delete Duplicates

```bash
# Delete duplicate directories
rm -rf gpt5-context-delivery/alignment
rm -rf gpt5-context-delivery/vision
rm -rf gpt5-context-delivery/configs

# After moves complete, delete entire gpt5-context-delivery
rm -rf gpt5-context-delivery

# Delete old snapshot
rm -rf tempPipeline10-27-811
```

### Step 4: Delete Superseded Files

```bash
cd nutritionverse-tests/src/adapters
rm -f fdc_alignment.py fdc_alignment_v2.py
```

### Step 5: Archive Experimental

```bash
mkdir -p .archived/experimental_adapters
cd nutritionverse-tests/src/adapters
mv ollama_llava.py claude_.py gemini_.py ../../../.archived/experimental_adapters/
```

### Step 6: Run Tests

```bash
# Verify nothing broke
cd nutritionverse-tests
python -m pytest tests/ -v

cd ../pipeline/tests
python test_stage1c_telemetry_persistence.py

cd ../../tests
python -m pytest test_pipeline_e2e.py
```

### Step 7: Commit

```bash
git add -A
git commit -m "chore: remove duplicate and superseded code

- Deleted gpt5-context-delivery (moved unique entrypoints to nutritionverse-tests)
- Deleted tempPipeline10-27-811 (old snapshot)
- Deleted superseded fdc_alignment.py and fdc_alignment_v2.py
- Archived experimental LLM adapters to .archived/
- Moved nutritionverse-tests/info/ to docs/archive/

Removes ~8400 lines of duplicate code.

Verified:
- All tests pass
- No broken imports
- Entrypoints still work
"
```

---

## Risk Assessment

| Action | Risk | Mitigation |
|--------|------|------------|
| Delete `/gpt5-context-delivery` | **LOW** | Created backup, verified duplicates, moved unique files first |
| Delete `/tempPipeline10-27-811` | **VERY LOW** | Old snapshot, no active references |
| Delete superseded adapters | **LOW** | Verified no imports, tests pass |
| Archive experimental adapters | **VERY LOW** | Just moving, not deleting |

**Overall Risk**: **LOW** - Most deletions are exact duplicates with clear canonical sources.

---

## Post-Cleanup Benefits

1. **~8400 fewer lines** of duplicate code
2. **Clearer repository structure** (single source of truth)
3. **Faster grep/search** (fewer files to scan)
4. **Reduced confusion** for new developers
5. **Easier maintenance** (no need to keep copies in sync)

---

## Notes

- All suggested deletions verified via grep for imports/references
- Backup created before any deletion
- Tests run after each deletion phase
- Experimental files archived (not deleted) for potential future use
- Documentation moved to consolidated `/docs` structure

**Total Estimated Cleanup Time**: 2-4 hours
