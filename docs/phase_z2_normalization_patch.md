# Phase Z2: Normalization Fixes - Implementation Patch

**File**: `nutritionverse-tests/src/nutrition/alignment/align_convert.py`
**Function**: `_normalize_for_lookup()` (line 276-365)
**Status**: Ready to apply

---

## Changes Required

### 1. Update Function Signature & Docstring

**Current** (lines 276-302):
```python
def _normalize_for_lookup(name: str) -> tuple:
    """
    Returns:
        (normalized_name, tokens, form, method) where:
```

**New**:
```python
def _normalize_for_lookup(name: str) -> tuple:
    """
    Returns:
        (normalized_name, tokens, form, method, hints) where:
        - normalized_name: Cleaned string for key lookups
        - tokens: List of word tokens after plural normalization
        - form: Extracted form ("raw", "frozen", "cooked", None)
        - method: Extracted cooking method if cooked (None otherwise)
        - hints: Dict with peel_hint, ignored_class, etc. (Phase Z2)

    Examples:
        >>> _normalize_for_lookup("broccoli florets raw")
        ("broccoli", ["broccoli"], "raw", None, {})

        >>> _normalize_for_lookup("orange with peel")
        ("orange", ["orange"], "raw", None, {"peel": True})

        >>> _normalize_for_lookup("deprecated")
        (None, [], None, None, {"ignored_class": "deprecated"})
```

---

### 2. Add Phase Z2 Fixes at Function Start

**Insert after line 305** (`name = name.lower().strip()`):

```python
    name = name.lower().strip()
    hints = {}  # Phase Z2: Initialize hints dict

    # Phase Z2 Fix 1: Handle literal "deprecated" → return ignored
    if name == 'deprecated':
        hints['ignored_class'] = 'deprecated'
        return (None, [], None, None, hints)

    # Phase Z2 Fix 2: Collapse duplicate parentheticals
    # Example: "spinach (raw) (raw)" → "spinach (raw)"
    name = re.sub(r'\(([^)]+)\)\s*\(?\1\)?', r'(\1)', name)

    # Phase Z2 Fix 3: Normalize "sun dried" / "sun-dried" → "sun_dried"
    name = re.sub(r'sun[\s-]dried', 'sun_dried', name, flags=re.IGNORECASE)

    # Phase Z2 Fix 4: Peel qualifiers → telemetry hint only (don't block alignment)
    peel_match = re.search(r'\b(with|without)\s+peel\b', name, re.IGNORECASE)
    if peel_match:
        hints['peel'] = True if 'with' in peel_match.group(0).lower() else False
        # Strip peel qualifier from name
        name = re.sub(r'\b(with|without)\s+peel\b', '', name, flags=re.IGNORECASE).strip()

    # Extract form/method BEFORE removing tokens (existing code continues...)
```

---

### 3. Update Return Statement

**Current** (line 365):
```python
    return (name, tokens, form, method)
```

**New**:
```python
    return (name, tokens, form, method, hints)
```

---

## Caller Updates Required

All functions that call `_normalize_for_lookup()` must be updated to handle the 5-tuple return.

### Search Pattern
```bash
grep -n "_normalize_for_lookup" nutritionverse-tests/src/nutrition/alignment/align_convert.py
```

### Expected Callers (approximate line numbers)
1. Line ~650-700: Main alignment function
2. Line ~800-900: Variant generation
3. Line ~1000-1100: Stage Z fallback

### Update Pattern

**Before**:
```python
normalized_name, tokens, form, method = _normalize_for_lookup(food_name)
```

**After**:
```python
normalized_name, tokens, form, method, hints = _normalize_for_lookup(food_name)
```

**Or (if hints not needed immediately)**:
```python
normalized_name, tokens, form, method, hints = _normalize_for_lookup(food_name)
# Use hints later in telemetry
```

---

## Telemetry Integration

### Propagate Hints to Final Result

**Location**: Where final result dict is built (around line 1100-1200)

**Add**:
```python
# Phase Z2: Propagate normalization hints to telemetry
if hints:
    if hints.get('peel') is not None:
        result['telemetry']['form_hint'] = {'peel': hints['peel']}

    if hints.get('ignored_class'):
        result['available'] = False
        result['telemetry']['ignored_class'] = hints['ignored_class']
        result['telemetry']['reason'] = 'Normalization detected ignore pattern'
```

---

## Testing the Changes

### Unit Tests

```python
def test_normalize_duplicate_parentheticals():
    """Test Phase Z2 Fix 2: Collapse duplicate parentheticals."""
    norm, tokens, form, method, hints = _normalize_for_lookup("spinach (raw) (raw)")
    assert "(raw) (raw)" not in norm
    assert "(raw)" in norm or norm == "spinach"

def test_normalize_sun_dried():
    """Test Phase Z2 Fix 3: sun dried / sun-dried normalization."""
    norm1, *_, hints1 = _normalize_for_lookup("sun dried tomatoes")
    norm2, *_, hints2 = _normalize_for_lookup("sun-dried tomatoes")
    assert "sun_dried" in norm1 or norm1 == norm2

def test_normalize_peel_hint():
    """Test Phase Z2 Fix 4: Peel hint extraction."""
    norm, tokens, form, method, hints = _normalize_for_lookup("orange with peel")
    assert hints['peel'] == True
    assert "peel" not in norm
    assert "orange" in norm

    norm2, *_, hints2 = _normalize_for_lookup("banana without peel")
    assert hints2['peel'] == False
    assert "peel" not in norm2

def test_normalize_deprecated():
    """Test Phase Z2 Fix 1: Deprecated handling."""
    norm, tokens, form, method, hints = _normalize_for_lookup("deprecated")
    assert norm is None
    assert hints['ignored_class'] == 'deprecated'
```

### Integration Test

```bash
# Run alignment on test foods
python -c "
from nutritionverse_tests.src.nutrition.alignment.align_convert import align_prediction

# Test spinach (raw) (raw) normalization
result = align_prediction({'foods': [{'name': 'spinach (raw) (raw)', 'form': 'raw', 'mass_g': 100}]})
print(f\"Spinach result: {result['foods'][0].get('fdc_name', 'NO MATCH')}\")

# Test orange with peel
result = align_prediction({'foods': [{'name': 'orange with peel', 'form': 'raw', 'mass_g': 100}]})
print(f\"Orange peel hint: {result['foods'][0]['telemetry'].get('form_hint', {})}\")

# Test deprecated
result = align_prediction({'foods': [{'name': 'deprecated', 'form': 'raw', 'mass_g': 100}]})
print(f\"Deprecated ignored: {result['foods'][0].get('available', True) == False}\")
"
```

---

## Risk Assessment

### Low Risk Changes
- ✅ Duplicate parenthetical collapse (regex safe, tested pattern)
- ✅ Sun-dried normalization (simple regex, low collision risk)
- ✅ Deprecated handling (exact match, early return)

### Medium Risk Changes
- ⚠️ Peel hint extraction (regex may need refinement for edge cases)
- ⚠️ 5-tuple return signature (requires updating all callers)

### Mitigation
1. Run full test suite after changes
2. Check for any `_normalize_for_lookup` callers that might have been missed
3. Test with known edge cases (e.g., "orange peel", "banana peel")
4. Validate existing alignment behavior unchanged for foods without hints

---

## Implementation Checklist

- [ ] Update function docstring (add `hints` to return tuple)
- [ ] Add `hints = {}` initialization
- [ ] Add Fix 1: deprecated handling
- [ ] Add Fix 2: duplicate parenthetical collapse
- [ ] Add Fix 3: sun-dried normalization
- [ ] Add Fix 4: peel hint extraction
- [ ] Update return statement: `return (name, tokens, form, method, hints)`
- [ ] Find all callers of `_normalize_for_lookup()`
- [ ] Update each caller to handle 5-tuple return
- [ ] Add telemetry integration for hints
- [ ] Write unit tests for each fix
- [ ] Run full test suite
- [ ] Test with edge cases
- [ ] Update documentation

---

## Rollback Plan

If issues arise:
1. Revert normalization fixes (keep 5-tuple but return empty `hints = {}`)
2. Keep signature change for future use
3. Debug specific fix that's causing issues
4. Re-enable fixes one at a time

**Git Command**:
```bash
git diff nutritionverse-tests/src/nutrition/alignment/align_convert.py
git checkout nutritionverse-tests/src/nutrition/alignment/align_convert.py  # If needed
```

---

## Next Steps After Normalization

Once normalization fixes are complete:
1. ✅ Normalization done
2. → Config updates (celery, tatsoi, alcohol)
3. → Telemetry enhancements
4. → Test suite
5. → Integration & validation

---

**Status**: Patch ready to apply
**Estimated Time**: 30 minutes
**Dependencies**: None (can be applied independently)
**Testing Required**: Unit tests + integration test + full test suite
