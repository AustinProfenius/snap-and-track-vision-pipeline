# Phase Z2: Close Alignment Misses - Implementation Guide

**Goal**: Reduce 54 unique alignment misses to ≤10 through verified CSV mappings, normalization fixes, and systematic ignore rules.

---

## 🎯 Quick Start

```bash
# 1. Run the quick start script to execute completed tools
./phase_z2_quickstart.sh

# 2. Review the detailed implementation status
cat docs/phase_z2_implementation_status.md

# 3. Continue with remaining tasks (see below)
```

---

## 📊 Current Progress

### ✅ Completed (40% Complete)

1. **CSV Merge Tool** - [tools/merge_verified_fallbacks.py](tools/merge_verified_fallbacks.py)
   - Parses `missed_food_names.csv` (104 rows → ~54 unique foods)
   - DB validation with precedence rules (verified entries protected)
   - Kcal inference for all food categories
   - Special case handling (cherry tomato, chicken, chilaquiles, orange with peel)
   - Generates verified YAML and merge report JSON

2. **Config Validation Tool** - [tools/validate_stageZ_config.py](tools/validate_stageZ_config.py)
   - Validates duplicate keys, kcal ranges, FDC IDs, synonym conflicts
   - Produces summary table and detailed validation report
   - Exit code 1 on critical errors (safe for CI/CD)

### 🔄 In Progress / Remaining (60%)

3. **Normalization Fixes** (30 min) - `align_convert.py::_normalize_for_lookup()`
4. **Config Updates** (10 min) - Add celery, tatsoi, alcohol entries
5. **Telemetry Enhancements** (30 min) - coverage_class, Stage Z source tracking
6. **Test Suite** (45 min) - Comprehensive Phase Z2 tests
7. **Integration & Validation** (30 min) - Run tests, analyze misses

---

## 🛠️ Completed Tools Usage

### CSV Merge Tool

**Purpose**: Ingest verified FDC mappings from CSV into Stage Z config

**Command**:
```bash
python tools/merge_verified_fallbacks.py \
  --csv ./missed_food_names.csv \
  --out configs/stageZ_branded_fallbacks_verified.yml \
  --merge-into configs/stageZ_branded_fallbacks.yml \
  --report runs/csv_merge_report.json
```

**Key Features**:
- **DB Validation**: Checks each FDC ID exists; marks `fdc_id_missing_in_db=true` if not
- **Precedence Rules**: Won't overwrite DB-verified entries with unverified CSV rows
- **Special Cases**:
  - Cherry tomato: Uses Foundation 321360 only if DB-verified
  - Chicken: Adds token constraint for "breast" queries only
  - Chilaquiles: Marks low confidence, adds reject patterns
  - Orange with peel: Normalizes to "orange", adds peel hint
- **Kcal Inference**: Auto-calculates ranges based on food type if not in CSV
- **Error Handling**: Skips malformed rows, logs to report, doesn't fail entire merge

**Outputs**:
- `configs/stageZ_branded_fallbacks_verified.yml` - Generated YAML from CSV
- `configs/stageZ_branded_fallbacks.yml` - Updated with merged entries
- `runs/csv_merge_report.json` - Detailed merge statistics

**Report Contents**:
```json
{
  "parsing": {
    "total_rows": 104,
    "parsed": 98,
    "skipped": 6,
    "skipped_rows": [15, 23, ...]
  },
  "generation": {
    "unique_keys": 54,
    "kcal_inferred_count": 42
  },
  "merge": {
    "replaced_keys": [...],
    "new_keys": [...],
    "skipped_due_to_precedence": [...],
    "db_validation_summary": {
      "verified": 45,
      "missing": 9,
      "unknown": 0
    }
  }
}
```

---

### Config Validation Tool

**Purpose**: Validate Stage Z config for consistency and correctness

**Command**:
```bash
python tools/validate_stageZ_config.py configs/stageZ_branded_fallbacks.yml
```

**Checks**:
1. ✅ No duplicate keys (critical error)
2. ✅ `kcal_min < kcal_max` for all entries (critical error)
3. ⚠️ FDC IDs exist in DB (warning if missing)
4. ⚠️ No conflicting synonyms (warning only)
5. ⚠️ Unusually high kcal values (warning if >1000)

**Output**:
```
================================================================================
STAGE Z CONFIG SUMMARY
================================================================================
Key                            FDC ID       Kcal Bounds     Synonyms   DB Verified
------------------------------------------------------------------------------------
cherry_tomato                  383842       [15, 35]        3          ✓
grape_tomato                   447986       [15, 35]        3          ✓
spinach                        1750352      [10, 50]        2          ✓
eggplant                       2685577      [10, 100]       1          ✓
...
------------------------------------------------------------------------------------
Total entries: 60
FDC IDs checked: 72
  ✓ Verified: 68
  ❌ Missing: 4
  ? Unknown: 0
================================================================================
✓ VALIDATION PASSED (with 4 warnings)
```

**Exit Codes**:
- `0` - Validation passed (warnings OK)
- `1` - Critical errors found (duplicates, invalid ranges)

---

## 📋 Next Steps (Remaining Work)

### Step 1: Run Completed Tools (5 min)

```bash
# Execute quick start script
./phase_z2_quickstart.sh

# Or run manually:
python tools/merge_verified_fallbacks.py \
  --csv ./missed_food_names.csv \
  --out configs/stageZ_branded_fallbacks_verified.yml \
  --merge-into configs/stageZ_branded_fallbacks.yml \
  --report runs/csv_merge_report.json

python tools/validate_stageZ_config.py configs/stageZ_branded_fallbacks.yml
```

**Expected Results**:
- ~54 new Stage Z entries merged
- Config validation passes (warnings OK for missing DB IDs)
- Merge report shows stats (new keys, replaced keys, skipped)

---

### Step 2: Normalization Fixes (30 min)

**File**: `nutritionverse-tests/src/nutrition/alignment/align_convert.py`
**Function**: `_normalize_for_lookup()` (around line 276)

**Required Changes**:

```python
def _normalize_for_lookup(name: str) -> tuple:
    """
    [...existing docstring...]

    Returns:
        (normalized_name, tokens, form, method, hints) where:
        - hints: Dict with peel_hint, ignored_class, etc.
    """
    import re

    name = name.lower().strip()
    hints = {}  # NEW: Initialize hints dict

    # NEW FIX 1: Collapse duplicate parentheticals
    # Example: "spinach (raw) (raw)" → "spinach (raw)"
    name = re.sub(r'\(([^)]+)\)\s*\(?\1\)?', r'(\1)', name)

    # NEW FIX 2: Normalize "sun dried" / "sun-dried" → "sun_dried"
    name = re.sub(r'sun[\s-]dried', 'sun_dried', name, flags=re.IGNORECASE)

    # NEW FIX 3: Peel qualifiers → telemetry hint only
    peel_match = re.search(r'\b(with|without)\s+peel\b', name, re.IGNORECASE)
    if peel_match:
        hints['peel'] = True if 'with' in peel_match.group(0).lower() else False
        name = re.sub(r'\b(with|without)\s+peel\b', '', name, flags=re.IGNORECASE).strip()

    # NEW FIX 4: Handle literal "deprecated" → return ignored
    if name.strip().lower() == 'deprecated':
        hints['ignored_class'] = 'deprecated'
        return (None, [], None, None, hints)

    # [...continue with existing normalization logic...]

    # MODIFIED RETURN: Add hints parameter
    return (normalized_name, tokens, form, method, hints)
```

**Integration**:
- Update all callers of `_normalize_for_lookup()` to handle 5-tuple return (add `hints`)
- Propagate `hints` to telemetry in final result dict

**Test**:
```python
# Test duplicate parentheticals
norm, *_, hints = _normalize_for_lookup("spinach (raw) (raw)")
assert "(raw) (raw)" not in norm

# Test sun-dried normalization
norm1, *_ = _normalize_for_lookup("sun dried tomatoes")
norm2, *_ = _normalize_for_lookup("sun-dried tomatoes")
assert "sun_dried" in norm1 or norm1 == norm2

# Test peel hint
norm, *_, hints = _normalize_for_lookup("orange with peel")
assert hints['peel'] == True
assert "peel" not in norm

# Test deprecated
norm, tokens, form, method, hints = _normalize_for_lookup("deprecated")
assert hints['ignored_class'] == 'deprecated'
assert norm is None
```

---

### Step 3: Config Updates (10 min)

#### A. Add Celery Root Mapping

**File**: `configs/stageZ_branded_fallbacks.yml`

```yaml
# Add after existing entries:
celery:
  synonyms: ["celery root", "celeriac", "celery stalk", "celery stalks"]
  primary:
    brand: "Generic"
    fdc_id: 2346405  # From CSV line 22
    kcal_per_100g: [10, 25]
  alternates: []
```

#### B. Add Ignore Rules

**File**: `configs/negative_vocabulary.yml`

```yaml
# Add at end of file:

# Ignored leafy greens (no reliable FDC entries)
tatsoi:
  - all  # Block all matches; return ignored_class="leafy_unavailable"

# Alcoholic beverages (out of scope for nutrition tracking)
alcoholic_beverage:
  - white_wine
  - red_wine
  - beer
  - wine
  - vodka
  - whiskey
  - rum
  - tequila
  - sake

# Explicit deprecated handling
deprecated:
  - all  # Return ignored_class="deprecated"
```

#### C. Implement Negative Vocab Check

**File**: `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

**Location**: Before Stage Z attempt (around line 950-1000)

```python
# Check negative vocabulary BEFORE Stage Z
if normalized_name in NEGATIVE_VOCAB or \
   any(normalized_name in neg_list for neg_list in NEGATIVE_VOCAB.values()):

    ignored_class = None
    if normalized_name == 'tatsoi' or 'tatsoi' in search_variants:
        ignored_class = 'leafy_unavailable'
    elif any(alc in normalized_name for alc in ['wine', 'beer', 'vodka', ...]):
        ignored_class = 'alcoholic_beverage'
    elif normalized_name == 'deprecated':
        ignored_class = 'deprecated'

    if ignored_class:
        return _build_result(
            ...,
            available=False,
            telemetry={
                'ignored_class': ignored_class,
                'reason': 'Negative vocabulary match'
            }
        )
```

---

### Step 4: Telemetry Enhancements (30 min)

**Files**:
- `align_convert.py` (global coverage_class, form_hint, ignored_class)
- `stageZ_branded_fallback.py` (Stage Z source tracking)

#### A. Add coverage_class (all results)

**File**: `align_convert.py` (in `_build_result()` or equivalent)

```python
telemetry['coverage_class'] = determine_coverage_class(alignment_stage, source_info)

def determine_coverage_class(stage: str, source: Dict) -> str:
    """Determine coverage class for telemetry."""
    if stage.startswith('stage1'):
        return 'foundation'
    elif stage.startswith('stage2'):
        return 'converted'
    elif stage == 'stageZ_branded_fallback':
        if source.get('from_verified_csv'):
            return 'branded_verified_csv'
        return 'branded_generic'
    elif stage.startswith('stage5'):
        return 'proxy'
    elif not stage or stage == 'stage0_no_candidates':
        return 'ignored'
    return 'unknown'
```

#### B. Enhance Stage Z Telemetry

**File**: `stageZ_branded_fallback.py` (in `resolve()` method)

```python
# When Stage Z match found:
metadata = fallback_config.get('_metadata', {})

telemetry['stageZ_branded_fallback'] = {
    'source': 'manual_verified_csv' if metadata.get('from_csv') else 'existing_config',
    'canonical_key': canonical_key,
    'fdc_id': fdc_id,
    'fdc_id_missing_in_db': metadata.get('fdc_id_missing_in_db', False),
    'kcal_bounds': kcal_range,
    'note': metadata.get('note')  # e.g., "low_confidence_mapping"
}
```

#### C. Add Form Hints

**File**: `align_convert.py` (after normalization)

```python
# Propagate hints from _normalize_for_lookup() to telemetry
if hints.get('peel') is not None:
    telemetry['form_hint'] = {'peel': hints['peel']}
```

#### D. Enhance Stage 0 Misses

**File**: `align_convert.py` (in Stage 0 handler)

```python
# For misses (no match found):
telemetry.update({
    'normalized_key': normalized_name,
    'queries_tried': search_variants_tried,  # Already exists
    'why_no_candidates': 'empty_pool' if candidate_pool_size == 0 else 'all_rejected'
})
```

---

### Step 5: Test Suite (45 min)

**File**: `nutritionverse-tests/tests/test_phaseZ2_verified.py` (new file)

**See**: [docs/phase_z2_implementation_status.md](docs/phase_z2_implementation_status.md) for complete test suite specification

**Test Categories**:
1. CSV Merge Tests (3 tests)
2. Special Case Tests (4 tests)
3. No-Result Food Tests (4 tests)
4. Normalization Tests (2 tests)

**Run**:
```bash
pytest nutritionverse-tests/tests/test_phaseZ2_verified.py -v
```

---

### Step 6: Integration & Validation (30 min)

```bash
# 1. Run consolidated test
cd nutritionverse-tests/entrypoints
python run_first_50_consolidated.py

# 2. Analyze misses
cd ../..
python analyze_consolidated_misses.py

# 3. Spot-check Stage Z selections
jq -r '.results[] | select(.alignment_stage=="stageZ_branded_fallback") |
  [.name, .telemetry.stageZ_branded_fallback.source, .fdc_id] | @tsv' \
  runs/first_50_batch_*/results.json | sort -u | head -50

# 4. Check ignored classes
jq -r '.results[] | select(.available==false) |
  [.name, .telemetry.ignored_class] | @tsv' \
  runs/first_50_batch_*/results.json | sort -u

# 5. Verify no regressions (Stage 5B, dessert blocking)
pytest nutritionverse-tests/tests/test_salad_decomposition.py -v
pytest nutritionverse-tests/tests/test_dessert_blocking.py -v
```

**Success Criteria**:
- ✅ Unique misses: 54 → ≤10
- ✅ No Stage 0 for: cherry/grape tomatoes, spinach, wheat berry, green beans, sun-dried tomatoes, mushrooms, scrambled eggs, eggplant, potatoes, chicken
- ✅ Config validation passes
- ✅ All tests pass
- ✅ No regressions

---

## 📁 File Structure

```
snapandtrack-model-testing/
├── phase_z2_quickstart.sh              ← Quick start script (RUN THIS FIRST)
├── PHASE_Z2_README.md                  ← This file
├── docs/
│   └── phase_z2_implementation_status.md  ← Detailed implementation status
├── tools/
│   ├── merge_verified_fallbacks.py     ← ✅ CSV merge tool (COMPLETE)
│   └── validate_stageZ_config.py       ← ✅ Config validator (COMPLETE)
├── configs/
│   ├── stageZ_branded_fallbacks.yml    ← Stage Z config (TO BE UPDATED)
│   ├── stageZ_branded_fallbacks_verified.yml  ← Generated by merge tool
│   └── negative_vocabulary.yml         ← Ignore rules (TO BE UPDATED)
├── nutritionverse-tests/
│   ├── src/nutrition/alignment/
│   │   ├── align_convert.py            ← Normalization fixes needed
│   │   └── stageZ_branded_fallback.py  ← Telemetry enhancements needed
│   └── tests/
│       └── test_phaseZ2_verified.py    ← Test suite (TO BE CREATED)
├── runs/
│   └── csv_merge_report.json           ← Generated by merge tool
└── missed_food_names.csv               ← Input CSV (104 rows)
```

---

## 🎯 Acceptance Criteria

**Phase Z2 is complete when**:

- [ ] **Miss Reduction**: Unique misses drop from 54 to ≤10
- [ ] **No Stage 0 Misses** for verified foods:
  - [ ] Cherry tomatoes, grape tomatoes
  - [ ] Spinach (raw)
  - [ ] Wheat berry
  - [ ] Green beans
  - [ ] Sun-dried tomatoes
  - [ ] Button/white mushrooms
  - [ ] Scrambled eggs
  - [ ] Eggplant
  - [ ] Potatoes
  - [ ] Chicken (generic)
- [ ] **Special Cases Work**:
  - [ ] Generic "chicken" doesn't force-map to breast
  - [ ] "Chicken breast" explicitly maps correctly
  - [ ] Peel hints recorded but don't change nutrition
  - [ ] Orange with peel aligns to orange
- [ ] **Ignore Rules Work**:
  - [ ] Tatsoi returns `available=false` with `ignored_class="leafy_unavailable"`
  - [ ] White wine returns `available=false` with `ignored_class="alcoholic_beverage"`
  - [ ] "Deprecated" returns `ignored_class="deprecated"`
- [ ] **Config Valid**: `validate_stageZ_config.py` passes with no critical errors
- [ ] **Tests Pass**: All Phase Z2 tests pass
- [ ] **No Regressions**: Stage 5B, mass propagation, dessert blocking intact
- [ ] **Precedence Respected**: Foundation/SR > Stage 2 > verified CSV > generic branded

---

## 💡 Key Concepts

### Precedence Order
```
Foundation/SR (Stage 1) > Cooked Conversion (Stage 2) > Stage Z (Verified CSV) > Stage Z (Generic) > Stage 0 (Miss)
```

### DB Validation Logic
```python
if csv_fdc_id not in database:
    mark_as_missing = True
    if existing_entry_is_verified:
        SKIP csv row  # Protect known-good entries
    else:
        INCLUDE with warning  # Still useful, just flag it
```

### Coverage Classes
- `foundation`: Stage 1b/1c match (Foundation or SR Legacy)
- `converted`: Stage 2 cooked conversion applied
- `branded_verified_csv`: Stage Z with CSV-sourced mapping
- `branded_generic`: Stage Z with pre-existing config
- `proxy`: Stage 5 proxy (if implemented)
- `ignored`: Negative vocabulary match

---

## ⚠️ Common Pitfalls

1. **Token Constraints**: Chicken→breast mapping must check tokens at alignment time, not config generation time
2. **Peel Normalization**: Strip peel BEFORE other normalization to avoid interaction bugs
3. **Negative Vocab Order**: Check negative vocab BEFORE Stage Z to avoid wasted alignment attempts
4. **Hints Propagation**: Must thread hints dict through multiple function calls to reach telemetry
5. **DB Validation**: Don't fail hard on missing DB; mark entries and continue (production may lack DB)

---

## 📞 Support

**Documentation**:
- Detailed status: [docs/phase_z2_implementation_status.md](docs/phase_z2_implementation_status.md)
- CSV format: See `missed_food_names.csv` (104 rows, columns: name, fdc_id, data_type, etc.)

**Tools**:
- CSV merge: `python tools/merge_verified_fallbacks.py --help`
- Config validator: `python tools/validate_stageZ_config.py --help`

**Quick Commands**:
```bash
# Run completed tools
./phase_z2_quickstart.sh

# Check tool help
python tools/merge_verified_fallbacks.py --help
python tools/validate_stageZ_config.py --help

# Run miss analysis
python analyze_consolidated_misses.py
```

---

**Last Updated**: 2025-10-30
**Progress**: 40% Complete (2/7 major tasks done)
**Next Step**: Run `./phase_z2_quickstart.sh` to test completed tools
