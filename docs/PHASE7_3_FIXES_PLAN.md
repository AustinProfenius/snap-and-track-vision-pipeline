# Phase 7.3 Post-Implementation Fixes - Implementation Plan

**Date**: 2025-10-28
**Status**: IN PROGRESS
**Estimated Time**: 4-6 hours
**Approach**: Option A - Sequential implementation of all 10 tasks

---

## Context

Phase 7.3 salad decomposition was implemented but needs critical fixes to work in production:
- Configs not loading (falling back to hardcoded defaults)
- Stage 5B not triggering properly before stage0_no_candidates
- Missing cooking intent detection (scrambled eggs → yolk mismatch)
- Missing produce safety guards (fresh produce → pickled/babyfood)
- Mass allocation broken (no unit→gram conversion, ratios not propagating)
- Validation metrics incomplete (can't see what's failing)

**Current Test Results** (from gpt_5_212images_20251028_092804.json):
- Config banner likely showing "hardcoded defaults"
- salads_decomposed probably = 0
- Eggs scrambled likely matching yolk/pasteurized
- Item mass MAPE likely ~1.0 (broken)
- Dish calorie MAPE likely > 0.40

---

## Task 1: Force Config Loading (Kill Hardcoded Defaults) ⏳

**Status**: NOT STARTED
**Priority**: CRITICAL - Foundation for all other tasks
**Time**: 30 minutes

### Files to Modify
1. `nutritionverse-tests/src/nutrition/alignment/align_convert.py`
2. `gpt5-context-delivery/entrypoints/run_first_50_by_dish_id.py`
3. `pipeline/config_loader.py`

### Changes Required

#### align_convert.py
- Add import: `from pathlib import Path`
- Replace silent fallback with hard fail:
  ```python
  cfg_env = os.environ.get("ALIGN_CONFIGS")
  dev_allow = os.environ.get("DEV_ALLOW_HARDCODED", "0") == "1"
  if cfg_env:
      self._cfg_root = cfg_env
  else:
      if dev_allow:
          self._cfg_root = "configs"
      else:
          raise RuntimeError(
              "ALIGN_CONFIGS not set. Set ALIGN_CONFIGS=/abs/path/to/configs "
              "or run with DEV_ALLOW_HARDCODED=1 for local dev only."
          )
  ```
- Load branded_fallbacks.yml and unit_to_grams.yml as required:
  ```python
  self._external_branded_fallbacks = self._load_yaml(os.path.join(self._cfg_root, "branded_fallbacks.yml"))
  self._unit_to_grams = self._load_yaml(os.path.join(self._cfg_root, "unit_to_grams.yml"), required=False) or {}
  ```
- Print config banner:
  ```python
  print(f"[CONFIG] Using configs at: {Path(self._cfg_root).resolve()}")
  ```

#### run_first_50_by_dish_id.py
- Add CLI argument: `parser.add_argument("--configs", default=None, help="Path to /configs directory")`
- Set environment variable:
  ```python
  if args.configs:
      os.environ["ALIGN_CONFIGS"] = args.configs
  else:
      if "ALIGN_CONFIGS" not in os.environ:
          print("[WARN] ALIGN_CONFIGS not set; set it or run with --configs")
  ```

#### config_loader.py
- Add branded_fallbacks.yml to required configs
- Add unit_to_grams.yml as optional config

### Success Criteria
- ✅ NO "hardcoded config defaults" warning appears
- ✅ Config banner shows: `[CONFIG] Using configs at: /abs/path/to/configs`
- ✅ RuntimeError if configs missing (unless DEV_ALLOW_HARDCODED=1)

---

## Task 2: Wire Stage 5B Pre-Stage0 with Flattened Output ⏳

**Status**: NOT STARTED
**Priority**: CRITICAL - Core decomposition fix
**Time**: 45 minutes

### Files to Modify
1. `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

### Changes Required

#### In align_food_item() method (around line 491-515)
Replace:
```python
if not fdc_entries:
    return {"alignment_stage": "stage0_no_candidates", ...}
```

With:
```python
if not fdc_entries:
    # Try Salad Decomposition BEFORE stage0 return
    decomp = self._try_stage5b_salad_decomposition(predicted_name, predicted_form, predicted_mass_g)
    if decomp and decomp.get("expanded_foods"):
        # Normalize to flattened foods list; tag components
        for comp in decomp["expanded_foods"]:
            comp["alignment_stage"] = "stage5b_salad_component"
        return {
            "alignment_stage": "stage5b_salad_decomposition",
            "expanded_foods": decomp["expanded_foods"],
            "decomposition_recipe": decomp.get("decomposition_recipe"),
        }
    return {"alignment_stage": "stage0_no_candidates", ...}
```

#### Update VALID_STAGES (around line 2078)
Add:
```python
"stage5b_salad_decomposition",
"stage5b_salad_component"
```

### Success Criteria
- ✅ Caesar salad triggers Stage 5B instead of stage0_no_candidates
- ✅ Components tagged with alignment_stage='stage5b_salad_component'
- ✅ Flattened foods list returned (not nested structure)

---

## Task 3: Add Cooked Egg/Veg Intent + Produce Guardrails ⏳

**Status**: NOT STARTED
**Priority**: HIGH - Quality improvement
**Time**: 60 minutes

### Files to Modify
1. `configs/variants.yml`
2. `configs/category_allowlist.yml`
3. `configs/negative_vocabulary.yml`
4. `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

### Changes Required

#### variants.yml - Add cooked variants
```yaml
eggs_scrambled:
  - egg scrambled
  - eggs scrambled
  - scrambled eggs
  - omelet

broccoli_cooked:
  - broccoli steamed
  - broccoli cooked

spinach_cooked:
  - spinach steamed
  - spinach cooked

rice_white_cooked:
  - rice white cooked
```

#### category_allowlist.yml - Add egg preferences and blocks
```yaml
eggs:
  prefer_contains:
    - whole
    - cooked
    - scrambled
  hard_block_contains:
    - yolk raw frozen
    - mixture
    - pasteurized
    - frozen

produce:
  hard_block_contains:
    - babyfood
    - pickled
    - canned
    - frozen
    - juice
```

#### negative_vocabulary.yml - Strengthen filters
```yaml
egg:
  - bread egg
  - toast
  - roll
  - bun
  - yolk raw
  - white pasteurized
  - mixture
  - frozen

broccoli:
  - soup
  - cheese

spinach:
  - babyfood
  - canned
  - pickled
  - frozen
```

#### align_convert.py - Add intent-based scoring
In candidate scoring method, add:
```python
# Intent: cooked vs raw
intent_cooked = "scrambled" in pred_name or "cooked" in pred_form
name_l = cand.name.lower()

if intent_cooked:
    if "scrambled" in name_l or ("egg" in name_l and "whole" in name_l and "cooked" in name_l):
        score += 0.25
    if any(x in name_l for x in ["yolk", "white", "pasteurized", "frozen"]):
        score -= 0.25

# Produce guardrails
if any(x in name_l for x in ["babyfood", "pickled", "canned", "frozen", "juice"]):
    score -= 0.3
```

### Success Criteria
- ✅ "scrambled eggs" → "Egg, whole, cooked, scrambled" ≥90%
- ✅ Fresh produce never aligns to pickled/babyfood/frozen unless specified
- ✅ Cooked broccoli finds steamed variants, not soup

---

## Task 4: Improve Salad/Mixed Greens Matching ⏳

**Status**: NOT STARTED
**Priority**: HIGH - Makes Stage 5B trigger correctly
**Time**: 30 minutes

### Files to Modify
1. `configs/proxy_alignment_rules.json` (verify structure)
2. `configs/variants.yml`
3. `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

### Changes Required

#### proxy_alignment_rules.json - Verify structure
Ensure salad_decomposition section has:
```json
{
  "stage5_proxies": { ... },
  "salad_decomposition": {
    "caesar salad": {
      "recipe_name": "caesar salad",
      "components": [
        {"name": "lettuce romaine raw", "ratio": 0.70},
        {"name": "parmesan cheese grated", "ratio": 0.08},
        {"name": "croutons", "ratio": 0.15},
        {"name": "caesar dressing", "ratio": 0.07}
      ]
    },
    "house salad": {...},
    "mixed greens": {...},
    "spring mix": {...},
    "mesclun": {...}
  }
}
```

#### variants.yml - Add comprehensive salad coverage
```yaml
mixed_greens:
  - mixed greens
  - lettuce mixed greens
  - spring mix
  - mesclun

salad:
  - salad
  - green salad
  - garden salad

romaine_lettuce:
  - romaine
  - lettuce romaine
  - romaine lettuce
```

#### align_convert.py - Rewrite _match_salad_key()
```python
def _match_salad_key(self, predicted_name: str):
    toks = [t for t in re.split(r"[^a-z]+", predicted_name.lower()) if t]
    if not toks:
        return None
    s = " ".join(dict.fromkeys(toks))  # de-dupe preserve order

    # Canonical mappings
    if "salad" in s and "caesar" in s:
        return "caesar salad"
    if "salad" in s and "house" in s:
        return "house salad"
    if "spring" in s and "mix" in s:
        return "spring mix"
    if "mesclun" in s:
        return "mesclun"
    if "mixed" in s and "greens" in s:
        return "mixed greens"
    if s in self._external_salad_decomp:
        return s
    if s.endswith(" salad"):
        return "house salad"
    return None
```

### Success Criteria
- ✅ "caesar salad" → decomposes to 4 components
- ✅ "mixed greens", "spring mix", "mesclun" → decompose
- ✅ salads_decomposed > 0 in validator

---

## Task 5: Fix Form Token De-duplication ⏳

**Status**: NOT STARTED
**Priority**: MEDIUM - Quality improvement
**Time**: 15 minutes

### Files to Modify
1. `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

### Changes Required

Add `_normalize_form()` method:
```python
def _normalize_form(self, form: str) -> str:
    """Normalize form string, removing duplicate tokens."""
    if not form:
        return ""
    toks = re.split(r"[()\s,;]+", form.lower())
    toks = [t for t in toks if t]
    return " ".join(dict.fromkeys(toks))
```

Use in form processing:
```python
predicted_form = self._normalize_form(predicted_form)
```

### Success Criteria
- ✅ "spinach (raw) (raw)" → "raw"
- ✅ No duplicate tokens in normalized forms

---

## Task 6: Activate Branded Fallback for Components ⏳

**Status**: NOT STARTED
**Priority**: HIGH - Enables croutons/dressings to work
**Time**: 20 minutes

### Files to Modify
1. `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

### Changes Required

#### In _align_single_component() method
After Foundation/SR query fails, add:
```python
# Try branded fallback
b = self._query_branded_fallback(canonical_name)
if b:
    out = self._build_component_result(b, mass_g)
    out["source"] = "BrandedFallback"
    return out
return None
```

#### Ensure _query_branded_fallback() uses configs
```python
def _query_branded_fallback(self, canonical_name: str):
    fallback_cfg = getattr(self, '_external_branded_fallbacks', {})
    fallback_names = fallback_cfg.get("fallbacks", {}).get(canonical_name, [])
    # ... existing logic
```

### Success Criteria
- ✅ "croutons" finds branded croutons when no Foundation/SR exists
- ✅ "caesar dressing" finds branded dressing
- ✅ Components have source='BrandedFallback'

---

## Task 7: Fix Mass Correctness (Unit→Gram Conversion) ⏳

**Status**: NOT STARTED
**Priority**: CRITICAL - Fixes calorie accuracy
**Time**: 45 minutes

### Files to Modify
1. `configs/unit_to_grams.yml` (NEW)
2. `pipeline/run.py`

### Changes Required

#### Create configs/unit_to_grams.yml
```yaml
# Unit to gram conversions for common foods
egg_whole_large: 50
croutons_tbsp: 7
dressing_caesar_tbsp: 15
romaine_cup_shredded: 47
cucumber_cup_slices: 104
tomato_cup_chopped: 180
```

#### pipeline/run.py - Add unit conversion
```python
def _emit_food(...):
    mass_g = food.get("mass_g")

    # If Stage5B component has unit counts, convert using config
    if not mass_g and food.get("unit_key") and food.get("unit_count"):
        utg = self._unit_to_grams.get(food["unit_key"])
        if utg:
            mass_g = float(food["unit_count"]) * float(utg)
            food["mass_g"] = mass_g
```

#### pipeline/run.py - Propagate parent mass to components
```python
if result["alignment_stage"] == "stage5b_salad_decomposition":
    parent_g = parent_food.get("mass_g")
    for comp in result["expanded_foods"]:
        if not comp.get("mass_g") and comp.get("ratio"):
            if parent_g:
                comp["mass_g"] = float(parent_g) * float(comp["ratio"])
```

### Success Criteria
- ✅ Components have mass_g = parent_mass_g * ratio
- ✅ Unit conversions work (egg count → grams)
- ✅ Item mass MAPE median < 0.5 (from ~1.0)

---

## Task 8: Enhance Telemetry & Validator Reporting ⏳

**Status**: NOT STARTED
**Priority**: MEDIUM - Observability
**Time**: 30 minutes

### Files to Modify
1. `pipeline/schemas.py`
2. `tools/metrics/validate_phase7_3.py`

### Changes Required

#### schemas.py - Add telemetry fields
```python
class TelemetryEvent(BaseModel):
    # ... existing fields
    stage0_term: Optional[str] = None
    confusion_hint: Optional[str] = None
```

#### validate_phase7_3.py - Add reporting sections
```python
# Top 10 stage0_no_candidates
top10_stage0_terms = Counter([
    r["predicted_name"] for r in results
    if r.get("alignment_stage") == "stage0_no_candidates"
]).most_common(10)

# Confusion table
confusions = {
    "eggs(scrambled)": _calc_confusion_rate(results, "scrambled eggs", "Egg, whole, cooked, scrambled"),
    "broccoli(steamed)": _calc_confusion_rate(results, "broccoli steamed", "Broccoli, cooked, steamed"),
    "spinach(raw)": _calc_confusion_rate(results, "spinach raw", "Spinach, raw"),
    "mixed greens": _calc_confusion_rate(results, "mixed greens", "stage5b_salad_component"),
    "caesar salad": _calc_confusion_rate(results, "caesar salad", "stage5b_salad_component")
}

# Skipped items mass count
skipped_mass_items = len([
    item for r in results
    for item in r.get("foods", [])
    if not item.get("mass_g") or item.get("mass_g") <= 0
])

# Add to output JSON
report["Top10_stage0_terms"] = top10_stage0_terms
report["Confusions"] = confusions
report["SkippedItems_Mass"] = skipped_mass_items
```

### Success Criteria
- ✅ Top 10 stage0 terms visible in validator output
- ✅ Confusion rates calculated for sensitive terms
- ✅ Skipped mass items tracked

---

## Task 9: Add Lightweight Class Priors (Tie-Breakers) ⏳

**Status**: NOT STARTED
**Priority**: LOW - Nice to have
**Time**: 30 minutes

### Files to Modify
1. `configs/class_priors.yml` (NEW)
2. `nutritionverse-tests/src/nutrition/alignment/align_convert.py`

### Changes Required

#### Create configs/class_priors.yml
```yaml
# Lightweight nutrient category priors for tie-breaking
eggs: protein_high
leafy_greens: fiber_moderate
starchy_veg: carbs_high
oils: fat_very_high
cured_meat: fat_protein_high
```

#### align_convert.py - Add tie-breaking logic
```python
def _break_ties_with_priors(self, candidates):
    if len(candidates) <= 1:
        return candidates[0]

    gap = candidates[0].score - candidates[1].score
    if gap >= 0.05:
        return candidates[0]

    # Tiny nudge if priors agree with candidate nutrients
    for c in candidates[:2]:
        prior = self._class_prior_for(c)
        if prior and self._candidate_agrees_with_prior(c, prior):
            c.score += 0.03

    candidates.sort(key=lambda x: x.score, reverse=True)
    return candidates[0]
```

### Success Criteria
- ✅ Ties broken by nutrient agreement (+0.03 nudge)
- ✅ Doesn't override hard blocks
- ✅ Only activates when score gap < 0.05

---

## Task 10: Create Comprehensive Documentation ⏳

**Status**: NOT STARTED
**Priority**: HIGH - Knowledge capture
**Time**: 45 minutes

### Files to Create
1. `docs/PHASE7_3_SUMMARY.md`
2. `docs/PIPELINE_STATUS.md`

### Content Required

#### PHASE7_3_SUMMARY.md
- What changed in Phase 7.3
- How to enable configs (ALIGN_CONFIGS env var)
- Salad decomposition examples
- Cooking intent examples
- Guardrails explanation
- Metrics improvements

#### PIPELINE_STATUS.md
- Current pipeline architecture (5 stages + Stage Z)
- Stage flow diagram
- Config loading environment variables
- Run recipes (how to execute tests)
- Known issues and limitations
- Validation checklist:
  - Config banner shows resolved path
  - salads_decomposed > 0
  - Eggs scrambled → whole cooked
  - Mass MAPE < 0.5
  - Calorie MAPE < 0.35

### Success Criteria
- ✅ Both docs created and comprehensive
- ✅ Clear instructions for running tests
- ✅ Validation checklist complete

---

## Smoke Tests (Post-Implementation)

### Test 1: Config Loading
```bash
export ALIGN_CONFIGS=/Users/austinprofenius/snapandtrack-model-testing/configs
python gpt5-context-delivery/entrypoints/run_first_50_by_dish_id.py --configs $ALIGN_CONFIGS
```
**Expect**: `[CONFIG] Using configs at: .../configs` (NO "hardcoded defaults")

### Test 2: Salad Decomposition
```bash
python tools/metrics/validate_phase7_3.py --file nutritionverse-tests/results/gpt_5_212images_*.json
```
**Expect**: `salads_decomposed > 0`

### Test 3: Full Validation
**Expect improvements**:
- DishName_Jaccard≥0.6_rate ↑
- Item_ExactMatch_Precision_mean → 0.65-0.75
- Calories_MAPE_mean ↓ < 0.35-0.45
- Mass_MAPE_median ↓ < 0.5

---

## Overall Progress Tracking

| Task | Status | Time Spent | Notes |
|------|--------|------------|-------|
| 1. Config Loading | ⏳ NOT STARTED | 0/30 min | |
| 2. Stage 5B Wiring | ⏳ NOT STARTED | 0/45 min | |
| 3. Cooking Intent | ⏳ NOT STARTED | 0/60 min | |
| 4. Salad Matching | ⏳ NOT STARTED | 0/30 min | |
| 5. Form Dedup | ⏳ NOT STARTED | 0/15 min | |
| 6. Branded Fallback | ⏳ NOT STARTED | 0/20 min | |
| 7. Mass Conversion | ⏳ NOT STARTED | 0/45 min | |
| 8. Telemetry | ⏳ NOT STARTED | 0/30 min | |
| 9. Class Priors | ⏳ NOT STARTED | 0/30 min | |
| 10. Documentation | ⏳ NOT STARTED | 0/45 min | |
| **TOTAL** | **0%** | **0/350 min** | **~6 hours** |

---

## Notes
- All changes are backward compatible
- Configs required in production, dev mode via DEV_ALLOW_HARDCODED=1
- Stage 5B doesn't break existing flows, only activates when no FDC candidates
- Mass conversion gracefully handles missing units
- Class priors are soft nudges, don't override hard logic

**Next Action**: Begin Task 1 - Force config loading
