# Phase Z2 Implementation Status

**Last Updated**: 2025-10-30
**Goal**: Reduce 54 unique alignment misses to ≤10 through verified CSV mappings, normalization fixes, and systematic ignore rules.

---

## Current State

### Baseline Metrics (Pre-Phase Z2)
- **Total processed items**: 21,098
- **Unique missed foods**: 54
- **Top misses**: olive oil (1,401×), cherry tomatoes (444×), spinach (409×), wheat berry (284×), chicken (275×)
- **Miss rate**: ~1.4% (≈300 actual misses from 99.7% pass rate)

### Key Principle: Precedence Order
**Foundation/SR > Stage 2 (cooked conversion) > Stage Z (verified CSV) > Stage Z (generic branded)**

---

## ✅ Completed Tasks

### 1. CSV Merge Tool (`tools/merge_verified_fallbacks.py`)
**Status**: ✅ Complete and tested
**File**: [tools/merge_verified_fallbacks.py](../tools/merge_verified_fallbacks.py)

**Capabilities**:
- Parses `missed_food_names.csv` with case-insensitive column handling
- Required fields: `name`, `fdc_id`
- Optional fields: `normalized_key`, `synonyms`, `kcal_min`, `kcal_max`, `notes`
- Auto-derives normalized keys: `name.lower() → spaces_to_underscores → strip_punctuation`

**DB Validation & Precedence**:
```python
if fdc_id not in fdc_database:
    mark fdc_id_missing_in_db = True
    if existing_key_is_db_verified:
        SKIP row  # Don't overwrite known-good
    else:
        INCLUDE with warning
```

**Kcal Inference Defaults**:
- Produce/leafy: `[10, 100]` (spinach/lettuce: `[10, 50]`)
- Proteins: `[100, 300]`
- Grains raw: `[300, 400]` | cooked: `[100, 200]`
- Oils/sauces: `[60, 900]`

**Special Case Handling** (per user spec):
1. **Cherry tomato** (CSV line 24): Uses Foundation 321360 ONLY if DB-verified, else keeps current branded entry
2. **Chicken** (CSV line 25): Applies 2646170 only when query contains "breast" tokens; generic "chicken" uses raw + Stage 2
3. **Chilaquiles** (CSV line 29): Adds `note="low_confidence_mapping"`, kcal guard `[120, 200]`, reject patterns: `["with sauce", "cheese", "refried"]`
4. **Orange with peel** (CSV line 59): Normalizes to "orange", adds `telemetry.form_hint.peel=true`

**Outputs**:
- `configs/stageZ_branded_fallbacks_verified.yml` (generated)
- Merged into `configs/stageZ_branded_fallbacks.yml` (idempotent)
- `runs/<timestamp>/csv_merge_report.json` with:
  - `replaced_keys`: existing keys updated
  - `new_keys`: newly added keys
  - `skipped_due_to_precedence`: verified entries preserved
  - `skipped_rows`: malformed CSV rows
  - `kcal_inferred_vs_provided`: audit trail
  - `db_validation_summary`: verified/missing/unknown counts

**Usage**:
```bash
python tools/merge_verified_fallbacks.py \
  --csv ./missed_food_names.csv \
  --out configs/stageZ_branded_fallbacks_verified.yml \
  --merge-into configs/stageZ_branded_fallbacks.yml \
  --report runs/csv_merge_report.json
```

---

### 2. Config Validation Tool (`tools/validate_stageZ_config.py`)
**Status**: ✅ Complete and tested
**File**: [tools/validate_stageZ_config.py](../tools/validate_stageZ_config.py)

**Validation Checks**:
1. **Duplicate keys** (critical error)
2. **Kcal ranges**: `kcal_min < kcal_max`, no negatives, warns if `kcal_max > 1000`
3. **FDC ID validation** (if DB available): Checks if each FDC ID exists
4. **Synonym conflicts**: Warns if same synonym maps to multiple keys

**Output**:
- Summary table: `key | fdc_id | kcal_bounds | synonyms_count | db_verified`
- DB validation stats: verified/missing/unknown counts
- Exit code 1 on critical errors (duplicates, invalid ranges)
- Exit code 0 on pass (warnings allowed)

**Usage**:
```bash
python tools/validate_stageZ_config.py configs/stageZ_branded_fallbacks.yml
```

---

## 🔄 Remaining Tasks

### 3. Normalization Fixes (`align_convert.py::_normalize_for_lookup()`)
**Status**: ❌ Not started
**File**: `nutritionverse-tests/src/nutrition/alignment/align_convert.py`
**Function**: `_normalize_for_lookup()` (around line 276)

**Required Changes**:

```python
def _normalize_for_lookup(name: str) -> tuple:
    """
    [Existing docstring...]

    Returns:
        (normalized_name, tokens, form, method, hints) where:
        - hints: Dict with peel_hint, ignored_class, etc.
    """
    import re

    name = name.lower().strip()
    hints = {}

    # 1. Collapse duplicate parentheticals
    # Example: "spinach (raw) (raw)" → "spinach (raw)"
    name = re.sub(r'\(([^)]+)\)\s*\(?\1\)?', r'(\1)', name)

    # 2. Normalize "sun dried" / "sun-dried" → "sun_dried"
    name = re.sub(r'sun[\s-]dried', 'sun_dried', name, flags=re.IGNORECASE)

    # 3. Peel qualifiers → telemetry hint only (don't block alignment)
    peel_match = re.search(r'\b(with|without)\s+peel\b', name, re.IGNORECASE)
    if peel_match:
        hints['peel'] = True if 'with' in peel_match.group(0).lower() else False
        # Strip peel qualifier from name
        name = re.sub(r'\b(with|without)\s+peel\b', '', name, flags=re.IGNORECASE).strip()

    # 4. Handle literal "deprecated" → return ignored
    if name.strip().lower() == 'deprecated':
        hints['ignored_class'] = 'deprecated'
        return (None, [], None, None, hints)

    # [Continue with existing normalization logic...]
    # Extract form/method, plurals, etc.

    # Return with new hints parameter
    return (normalized_name, tokens, form, method, hints)
```

**Integration Points**:
- All callers of `_normalize_for_lookup()` must handle the new `hints` return value
- Propagate hints to telemetry in final result dict

---

### 4. Stage Z Config Updates (Celery Root)
**Status**: ❌ Not started
**File**: `configs/stageZ_branded_fallbacks.yml`

**Add Entry**:
```yaml
celery:
  synonyms: ["celery root", "celeriac", "celery stalk", "celery stalks"]
  primary:
    brand: "Generic"
    fdc_id: 2346405  # From CSV line 22
    kcal_per_100g: [10, 25]
  alternates: []
```

**Rationale**: Celery root should map to celery raw (same plant, same nutrition); prevents Stage 0 misses.

---

### 5. Negative Vocabulary Updates (Ignore Rules)
**Status**: ❌ Not started
**File**: `configs/negative_vocabulary.yml`

**Add Entries**:
```yaml
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
  # Add more as needed

# Explicit deprecated handling
deprecated:
  - all  # Return ignored_class="deprecated"
```

**Code Integration** (`align_convert.py`):
- Check negative vocab BEFORE Stage Z attempt
- If matched, return:
  ```python
  {
      "available": False,
      "telemetry": {
          "ignored_class": "leafy_unavailable" | "alcoholic_beverage" | "deprecated",
          "reason": "Negative vocabulary match"
      }
  }
  ```

---

### 6. Telemetry Enhancements
**Status**: ❌ Not started
**Files**:
- `nutritionverse-tests/src/nutrition/alignment/align_convert.py`
- `nutritionverse-tests/src/nutrition/alignment/stageZ_branded_fallback.py`

**Required Additions**:

**A. Global `coverage_class` Field** (all results):
```python
telemetry['coverage_class'] = one_of(
    'foundation',           # Stage 1b/1c Foundation/SR match
    'converted',            # Stage 2 cooked conversion applied
    'branded_verified_csv', # Stage Z with CSV-sourced mapping
    'branded_generic',      # Stage Z with pre-existing config
    'proxy',                # Stage 5 proxy (if implemented)
    'ignored'               # Negative vocab match
)
```

**B. Stage Z Telemetry Block** (`stageZ_branded_fallback.py::resolve()`):
```python
telemetry['stageZ_branded_fallback'] = {
    'source': 'manual_verified_csv' | 'existing_config',
    'canonical_key': '<normalized_key>',
    'fdc_id': <id>,
    'fdc_id_missing_in_db': <bool>,  # If CSV entry wasn't DB-verified
    'kcal_bounds': [min, max],
    'note': 'low_confidence_mapping'  # If applicable (chilaquiles, etc.)
}
```

**C. Form Hints** (from normalization):
```python
if hints.get('peel') is not None:
    telemetry['form_hint'] = {'peel': hints['peel']}
```

**D. Stage 0 Misses** (enhance existing telemetry):
```python
telemetry.update({
    'normalized_key': normalized_name,
    'queries_tried': search_variants_tried,  # Already exists
    'why_no_candidates': 'empty_pool' | 'all_rejected'  # Already partially exists
})
```

**E. Ignored Classes**:
```python
if ignored:
    result['available'] = False
    result['telemetry']['ignored_class'] = 'deprecated' | 'leafy_unavailable' | 'alcoholic_beverage'
```

---

### 7. Test Suite (`tests/test_phaseZ2_verified.py`)
**Status**: ❌ Not started
**File**: `nutritionverse-tests/tests/test_phaseZ2_verified.py` (new file)

**Test Categories**:

#### A. CSV Merge Tests
```python
def test_csv_verified_entry_loaded():
    """Spinach (CSV row 78) loads into stageZ config with expected FDC ID."""
    config = load_yaml('configs/stageZ_branded_fallbacks.yml')
    assert 'spinach' in config['fallbacks']
    # FDC 1750352 (spinach baby) or 1999633 (spinach mature)
    assert config['fallbacks']['spinach']['primary']['fdc_id'] in [1750352, 1999633]

def test_csv_conflict_resolution():
    """Existing DB-verified entry NOT overwritten by CSV row with missing-in-DB ID."""
    # Assumes button_mushroom exists and is verified
    config = load_yaml('configs/stageZ_branded_fallbacks.yml')
    assert config['fallbacks']['button_mushroom']['primary']['fdc_id'] == 565950  # Original

def test_cherry_tomato_foundation_priority():
    """Cherry tomato uses Foundation 321360 if DB-verified, else branded fallback."""
    config = load_yaml('configs/stageZ_branded_fallbacks.yml')
    entry = config['fallbacks']['cherry_tomato']
    # If DB has 321360, should use it; else keep 383842 (existing branded)
    # Test requires DB availability to fully validate
    assert entry['primary']['fdc_id'] in [321360, 383842]
```

#### B. Special Case Tests
```python
def test_chicken_generic_not_forced_to_breast():
    """Generic 'chicken' doesn't hard-map to breast (2646170)."""
    result = align("chicken", form="raw")
    # Should NOT be 2646170 unless it went through Stage 2 conversion
    if result['fdc_id'] == 2646170:
        assert result['alignment_stage'] == 'stage2_cooked_intent'

def test_chicken_breast_explicit_mapping():
    """'chicken breast' query maps to 2646170 if DB-verified."""
    result = align("chicken breast", form="raw")
    assert result['fdc_id'] == 2646170

def test_orange_with_peel_hint_only():
    """'orange with peel' aligns to orange FDC, adds peel=True telemetry."""
    result = align("orange with peel", form="raw")
    assert 'orange' in result['fdc_name'].lower()
    assert result['telemetry']['form_hint']['peel'] == True
    # Nutrition should be same as "orange" (peel doesn't change FDC)

def test_chilaquiles_low_confidence():
    """Chilaquiles maps with low_confidence_mapping note."""
    result = align("chilaquiles", form="raw")
    assert result.get('telemetry', {}).get('stageZ_branded_fallback', {}).get('note') == 'low_confidence_mapping'
```

#### C. No-Result Food Tests
```python
def test_celery_root_maps_to_celery():
    """'celery root' resolves to celery raw (FDC 2346405) via Stage Z."""
    result = align("celery root", form="raw")
    assert result['alignment_stage'] == 'stageZ_branded_fallback'
    assert result['fdc_id'] == 2346405

def test_tatsoi_ignored():
    """'tatsoi' returns available=False with ignored_class."""
    result = align("tatsoi", form="raw")
    assert result['available'] == False
    assert result['telemetry']['ignored_class'] == 'leafy_unavailable'

def test_alcohol_ignored():
    """'white wine' returns available=False with alcoholic_beverage class."""
    result = align("white wine", form="raw")
    assert result['available'] == False
    assert result['telemetry']['ignored_class'] == 'alcoholic_beverage'

def test_deprecated_token_ignored():
    """Literal 'deprecated' name skipped with ignored_class."""
    result = align("deprecated", form="raw")
    assert result['telemetry']['ignored_class'] == 'deprecated'
```

#### D. Normalization Tests
```python
def test_spinach_duplicate_parenthetical():
    """'spinach (raw) (raw)' normalizes to 'spinach raw' or 'spinach'."""
    norm, tokens, form, method, hints = _normalize_for_lookup("spinach (raw) (raw)")
    assert '(raw) (raw)' not in norm  # Duplicate removed

def test_sun_dried_tomato_normalization():
    """'sun dried tomatoes' and 'sun-dried tomatoes' produce same key."""
    norm1, *_ = _normalize_for_lookup("sun dried tomatoes")
    norm2, *_ = _normalize_for_lookup("sun-dried tomatoes")
    assert 'sun_dried' in norm1 or norm1 == norm2
```

---

## 📋 Execution Plan (Next Steps)

### Step 1: Run CSV Merge (5 min)
```bash
cd /Users/austinprofenius/snapandtrack-model-testing

# Run merge
python tools/merge_verified_fallbacks.py \
  --csv ./missed_food_names.csv \
  --out configs/stageZ_branded_fallbacks_verified.yml \
  --merge-into configs/stageZ_branded_fallbacks.yml \
  --report runs/csv_merge_report.json

# Validate merged config
python tools/validate_stageZ_config.py configs/stageZ_branded_fallbacks.yml
```

**Expected Output**:
- `configs/stageZ_branded_fallbacks_verified.yml` created
- `configs/stageZ_branded_fallbacks.yml` updated with ~54 new entries
- `runs/csv_merge_report.json` with merge stats
- Validation passes (warnings OK for missing DB IDs)

---

### Step 2: Normalization Fixes (30 min)
1. Read `_normalize_for_lookup()` in `align_convert.py` (line ~276)
2. Add 4 fixes (duplicate parentheticals, sun-dried, peel hints, deprecated)
3. Update return signature to include `hints` dict
4. Update all callers to handle new return value
5. Propagate hints to telemetry

**Key Files**:
- `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

---

### Step 3: Config Updates (10 min)
1. Add celery entry to `configs/stageZ_branded_fallbacks.yml`
2. Add tatsoi, alcohol, deprecated to `configs/negative_vocabulary.yml`
3. Implement negative vocab check in `align_convert.py` (before Stage Z)

**Key Files**:
- `configs/stageZ_branded_fallbacks.yml`
- `configs/negative_vocabulary.yml`
- `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

---

### Step 4: Telemetry Enhancements (30 min)
1. Add `coverage_class` field (all results)
2. Enhance Stage Z telemetry with `source`, `fdc_id_missing_in_db`, `note`
3. Add `form_hint` for peel qualifier
4. Add `ignored_class` for negative vocab matches
5. Enhance Stage 0 telemetry with `normalized_key`, `why_no_candidates`

**Key Files**:
- `nutritionverse-tests/src/nutrition/alignment/align_convert.py`
- `nutritionverse-tests/src/nutrition/alignment/stageZ_branded_fallback.py`

---

### Step 5: Test Suite (45 min)
1. Create `nutritionverse-tests/tests/test_phaseZ2_verified.py`
2. Implement all test categories (CSV merge, special cases, no-result, normalization)
3. Run test suite: `pytest tests/test_phaseZ2_verified.py -v`

---

### Step 6: Integration & Validation (30 min)
```bash
# Run consolidated test
python nutritionverse-tests/entrypoints/run_first_50_consolidated.py

# Analyze misses
python analyze_consolidated_misses.py

# Spot-check Stage Z selections
jq -r '.results[] | select(.alignment_stage=="stageZ_branded_fallback") |
  [.name, .telemetry.stageZ_branded_fallback.source, .fdc_id] | @tsv' \
  runs/first_50_batch_*/results.json | sort -u | head -50

# Check ignored classes
jq -r '.results[] | select(.available==false) |
  [.name, .telemetry.ignored_class] | @tsv' \
  runs/first_50_batch_*/results.json | sort -u
```

---

## 🎯 Acceptance Criteria

**Must Pass**:
- [ ] Unique misses: 54 → ≤10
- [ ] No Stage 0 for: cherry/grape tomatoes, spinach (raw), wheat berry, green beans, sun-dried tomatoes, button mushrooms, scrambled eggs, eggplant, potatoes, chicken (generic)
- [ ] Generic proteins behave correctly (no forced breast mapping)
- [ ] Peel hints recorded but don't change nutrition
- [ ] Ignored classes return `available=false` with clear reasons
- [ ] No regressions: Stage 5B, mass propagation, dessert blocking intact
- [ ] Config validation passes
- [ ] CSV precedence respected: Foundation/SR > Stage 2 > verified CSV > generic branded

---

## 📂 Key File Locations

### Tools (Completed)
- `tools/merge_verified_fallbacks.py` ✅
- `tools/validate_stageZ_config.py` ✅

### Configs (Partially Complete)
- `configs/stageZ_branded_fallbacks.yml` (needs celery entry)
- `configs/stageZ_branded_fallbacks_verified.yml` (generated by merge tool)
- `configs/negative_vocabulary.yml` (needs tatsoi, alcohol)

### Source Code (Not Started)
- `nutritionverse-tests/src/nutrition/alignment/align_convert.py` (normalization, telemetry, ignore checks)
- `nutritionverse-tests/src/nutrition/alignment/stageZ_branded_fallback.py` (telemetry enhancements)

### Tests (Not Started)
- `nutritionverse-tests/tests/test_phaseZ2_verified.py` (new file)

### Reports (Generated)
- `runs/csv_merge_report.json` (generated by merge tool)
- `runs/first_50_batch_<timestamp>.json` (consolidated test results)
- `consolidated_misses_report.json` (miss analysis)

---

## 🔗 References

### CSV Data
- Source: `missed_food_names.csv` (104 rows, 54 unique food names after grouping)
- Top entries to verify: spinach (rows 78-80), chicken (rows 25-28), cherry tomato (row 24), eggplant (rows 32-33)

### Existing Stage Z Entries (Pre-Phase Z2)
- cherry_tomato, grape_tomato, broccoli, egg_scrambled, scrambled_egg, green_bean, button_mushroom, white_mushroom

### Current Miss Analysis
- Total unique misses: 54
- Top 10 misses account for ~4,400 instances (80% of all misses)
- Most critical: olive oil (1,401×), cherry tomatoes (444×), spinach (409×)

---

## 💡 Implementation Notes

### Precedence Rule Logic
```python
# In merge_verified_fallbacks.py
if existing_entry:
    existing_fdc_id = existing_entry['primary']['fdc_id']
    existing_db_verified = validate_fdc_id(existing_fdc_id, fdc_db)

    csv_fdc_id = yaml_entry['primary']['fdc_id']
    csv_db_verified = validate_fdc_id(csv_fdc_id, fdc_db)

    # Don't overwrite verified with unverified
    if existing_db_verified is True and csv_db_verified is False:
        skip_csv_row()
        continue
```

### Normalization Hints Pattern
```python
# In align_convert.py
hints = {}
if peel_detected:
    hints['peel'] = True
if deprecated_detected:
    hints['ignored_class'] = 'deprecated'

return (normalized_name, tokens, form, method, hints)
```

### Stage Z Telemetry Pattern
```python
# In stageZ_branded_fallback.py
telemetry = {
    'coverage_class': 'branded_verified_csv',
    'stageZ_branded_fallback': {
        'source': 'manual_verified_csv' if from_csv else 'existing_config',
        'canonical_key': canonical_key,
        'fdc_id': fdc_id,
        'fdc_id_missing_in_db': metadata.get('fdc_id_missing_in_db', False),
        'kcal_bounds': kcal_range
    }
}
```

---

## ⚠️ Common Pitfalls

1. **Token Constraints**: When implementing chicken→breast mapping, ensure "breast" token check happens at alignment time, not config time
2. **Peel Normalization**: Strip peel qualifier from name BEFORE other normalization steps to avoid interaction bugs
3. **Negative Vocab Check Order**: Must check BEFORE Stage Z to prevent attempting alignment on ignored items
4. **Hints Propagation**: Ensure hints dict from normalization reaches final telemetry (may require threading through multiple function calls)
5. **DB Validation Failures**: Don't fail hard on missing DB; mark entries and continue (production may not have DB access)

---

## 🚀 Quick Start (Resume Work)

```bash
# 1. Review completed tools
cat tools/merge_verified_fallbacks.py
cat tools/validate_stageZ_config.py

# 2. Run CSV merge
python tools/merge_verified_fallbacks.py \
  --csv ./missed_food_names.csv \
  --out configs/stageZ_branded_fallbacks_verified.yml \
  --merge-into configs/stageZ_branded_fallbacks.yml \
  --report runs/csv_merge_report.json

# 3. Validate config
python tools/validate_stageZ_config.py configs/stageZ_branded_fallbacks.yml

# 4. Continue with normalization fixes in align_convert.py
# (See Step 2 in Execution Plan above)
```

---

**End of Phase Z2 Implementation Status Document**
