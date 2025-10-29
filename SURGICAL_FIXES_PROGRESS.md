# Surgical Fixes Implementation Progress

## STATUS: 3/8 tasks complete (~37%)

## Completed ✅

### 1. Class Intent Lexicon Expansion
**File:** `align_convert.py` lines 181-247
**Changes:**
- Replaced early-return pattern with multi-intent flag accumulation
- Added expanded produce lexicon (apple, strawberry, raspberry, blackberry, grape, melon, cherry, etc.)
- Added mushroom to vegetables
- Added potatoes/tubers (potato, yam, sweet potato)
- Added meat/protein synonyms (chicken, steak, beef, pork, bacon, fish, salmon, tuna, sirloin, chuck, ribeye, turkey)
- Added expanded leafy vegetables (romaine, spring mix, arugula, mesclun)
- Priority resolution: eggs > leafy_or_crucifer > produce > protein

**Impact:** Apple/strawberry will now get `class_intent="produce"` and receive dessert penalty

### 2. Normalization Helper Function
**File:** `align_convert.py` lines 276-365
**Function:** `_normalize_for_lookup(name: str) -> tuple`
**Features:**
- Safe plural→singular with PLURAL_MAP whitelist (prevents "glass"→"glas" bugs)
- Extracts form/method BEFORE removing tokens
- Treats "fresh" as soft hint toward raw (doesn't override explicit form)
- Removes harmless modifiers: florets, floret, pieces, cuts, whole, fresh
- Returns: (normalized_name, tokens, form, method)

**Impact:** "broccoli florets" → "broccoli", "cherry tomatoes" → "cherry tomato"

### 3. Variant Lookup Update
**File:** `align_convert.py` lines 2440-2459
**Changes:**
- Calls `_normalize_for_lookup()` on canonical_name
- Tries 5 key variants: original, original_underscore, normalized, normalized_underscore, normalized_space
- Deduplicates results

**Impact:** Will now find variants for "cherry tomatoes", "broccoli florets", "green beans"

---

## Remaining Tasks ⏳

### 4. Scrambled Eggs Bypass [CRITICAL]
**Location:** `align_convert.py` ~line 1000 (START of Stage1b scoring loop)
**What to do:**
```python
# BEFORE guardrails, at top of _stage1b_raw_foundation() method
base_class_lower = base_class.lower()
has_scrambled = any(tok in base_class_lower for tok in ["scrambled", "scramble"])
has_egg = any(tok in base_class_lower for tok in ["egg", "eggs"])

scrambled_bypass_candidates = []
if has_scrambled and has_egg:
    for entry in raw_foundation:
        entry_name_lower = entry.name.lower()

        # Whitelist SR scrambled entries
        scrambled_whitelist = ["egg, whole, cooked, scrambled", "egg, scrambled"]
        is_scrambled_match = any(w in entry_name_lower for w in scrambled_whitelist)

        # Hard block fast food
        has_fast_food = "fast foods" in entry_name_lower or "fast food" in entry_name_lower

        if is_scrambled_match and not has_fast_food:
            scrambled_bypass_candidates.append(entry)
        elif has_fast_food:
            entry._fast_food_penalty = True  # Tag for later penalty

# Prioritize bypass candidates
if scrambled_bypass_candidates:
    raw_foundation = scrambled_bypass_candidates + [e for e in raw_foundation if e not in scrambled_bypass_candidates]
```

**In scoring loop (~line 1140), add:**
```python
# Fast food penalty (after other penalties)
if hasattr(entry, '_fast_food_penalty') and entry._fast_food_penalty:
    score -= 0.60  # Strong penalty
```

### 5. Stage1b Failure Telemetry Enhancement [CRITICAL]
**Location:** `align_convert.py` ~line 1000 (during Stage1b scoring loop)

**During scoring loop, track candidates:**
```python
scored_candidates = []  # Initialize before loop

# Inside loop after computing score:
scored_candidates.append({
    "entry": entry,
    "pre_score": jaccard * 0.7 + energy_sim * 0.3,
    "post_score": score,
    "penalties": penalty_tokens if penalty_applied else [],
    "applied_threshold": threshold,
    "passed": score >= threshold
})
```

**When returning None (all rejected, ~line 1265):**
```python
# Get top 3 rejected
top3_rejected = sorted([c for c in scored_candidates if not c["passed"]],
                       key=lambda x: x["post_score"], reverse=True)[:3]

rejected_telemetry = []
for cand_data in top3_rejected:
    entry = cand_data["entry"]
    reasons = []
    if cand_data["penalties"]:
        reasons.append(f"penalties={cand_data['penalties']}")
    if cand_data["post_score"] < cand_data["applied_threshold"]:
        reasons.append(f"{cand_data['post_score']:.3f} < thr {cand_data['applied_threshold']:.3f}")

    rejected_telemetry.append({
        "name": entry.name,
        "fdc_id": entry.fdc_id,
        "pre_score": round(cand_data["pre_score"], 3),
        "post_score": round(cand_data["post_score"], 3),
        "reason": "; ".join(reasons) or "other"
    })

stage1b_telemetry = {
    "candidate_pool_size": len(raw_foundation),
    "threshold": threshold,
    "rejected_candidates": rejected_telemetry,
    "stage1b_dropped_despite_pool": True
}
```

### 6. Update variants.yml [REQUIRED]
**File:** `configs/variants.yml`
**Add these keys (both singular/plural, underscore/space):**

```yaml
# Cherry tomatoes (all key variants)
cherry_tomato:
  - cherry tomatoes
  - cherry tomato
  - Tomatoes, cherry, raw

cherry tomato:
  - cherry tomatoes
  - Tomatoes, cherry, raw

cherry_tomatoes:
  - cherry tomatoes
  - Tomatoes, cherry, raw

# Grape tomatoes
grape_tomato:
  - grape tomatoes
  - grape tomato
  - Tomatoes, grape, raw

grape tomato:
  - grape tomatoes
  - Tomatoes, grape, raw

grape_tomatoes:
  - grape tomatoes
  - Tomatoes, grape, raw

# Mushrooms (add portobello)
mushroom:
  - mushrooms
  - button mushrooms
  - white mushrooms
  - cremini
  - portobello
  - portabella
  - Mushrooms, white, raw

mushrooms:
  - mushrooms
  - Mushrooms, white, raw

# Green beans
green_bean:
  - green beans
  - string beans
  - snap beans
  - Beans, snap, green, raw

green beans:
  - green beans
  - Beans, snap, green, raw

green_beans:
  - green beans
  - Beans, snap, green, raw

# Broccoli (florets normalized away, just base)
broccoli:
  - broccoli
  - broccoli florets
  - Broccoli, raw
```

### 7. Add Unit Tests
**File:** `nutritionverse-tests/tests/test_produce_alignment.py`
**Add 3 new tests:**

1. `test_normalization_preserves_form()` - Tests _normalize_for_lookup
2. `test_scrambled_eggs_not_stage0_with_health_check()` - Tests eggs bypass
3. `test_dessert_leak_guard()` - Tests produce penalty (apple/strawberry)

**See plan for full test code**

### 8. Run Validation Tests
```bash
./run_tests.sh quick
./run_tests.sh unit
./run_tests.sh 50batch
```

---

## Verification Checklist

After completing remaining tasks, verify:
- [ ] Cherry/grape tomatoes → stage1b (not stage0)
- [ ] Mushrooms → stage1b
- [ ] Broccoli florets → stage1b
- [ ] Scrambled eggs → SR or Stage2 (NO fast food, NO stage0)
- [ ] Apple → "Apples raw" (NOT croissant)
- [ ] Strawberry → "Strawberries raw" (NOT ice cream)
- [ ] Stage1b telemetry shows top 3 rejected with reasons
- [ ] No "glass"→"glas" bugs (plural whitelist working)

---

## Next Steps

1. Complete task 4: Scrambled eggs bypass
2. Complete task 5: Stage1b telemetry enhancement
3. Complete task 6: Update variants.yml
4. Complete task 7: Add unit tests
5. Complete task 8: Run validation tests
6. Verify all acceptance criteria pass

**Total estimated remaining: ~150 lines across 2 files**
