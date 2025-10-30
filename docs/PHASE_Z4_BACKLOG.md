# Phase Z4 Backlog: Complex Dishes & Advanced Alignment

**Status**: Planning
**Target**: TBD
**Owner**: Alignment Team

---

## Overview

Phase Z4 will address complex multi-component dishes and specialty items that were intentionally deferred from Phase Z3 to avoid risky broad fallbacks.

**Key Principle**: Don't guess - decompose or verify

---

## Deferred from Phase Z3

### 1. Pizza & Cheese Pizza (30 instances)

**Problem**:
- "cheese pizza" appears 21 times in 630-image batch
- "pizza" appears 9 times
- Currently: Stage 0 (no match) - 100% miss rate

**Why deferred**:
- Too broad for single Stage Z fallback
- Varies wildly: thin crust vs thick, toppings, cheese amount
- Energy range too large (200-300 kcal/100g)

**Proposed Z4 Approach**:
1. **Multi-component Stage 5B rule**:
   ```yaml
   pizza_cheese:
     components:
       - pizza_dough_thin: 50%  # FDC <validated>
       - mozzarella_cheese: 30%  # FDC <validated>
       - tomato_sauce: 15%  # FDC <validated>
       - olive_oil: 5%  # FDC <validated>
     total_mass_hint: "per slice ~100-120g"
   ```

2. **Validated with fixtures**:
   - Test with known pizza samples
   - Verify energy within ±15% of USDA SR pizza entries
   - Compare with Foundation "Pizza, cheese, thin crust" if exists

3. **Fallback only if decomposition fails**:
   - If "pizza" too vague → use generic Stage Z (FDC <validated>)
   - If "pepperoni pizza" → add pepperoni component (10%)

**Expected Impact**: -30 misses (-1.7%)

---

### 2. Chia Pudding (6 instances)

**Problem**:
- Specialty dessert/snack item
- Not in Foundation/SR
- Wide variation: milk type, sweetener, toppings

**Why deferred**:
- Need verified branded entry, not generic
- Energy range depends on preparation (100-200 kcal/100g)

**Proposed Z4 Approach**:
1. **Look up verified branded entries**:
   - Search FDC for "chia pudding" branded entries
   - Filter by: plain/vanilla, no added toppings
   - Validate energy range plausible

2. **Add to Stage Z with tight guards**:
   ```yaml
   chia_pudding:
     synonyms:
       - chia pudding
       - chia seed pudding
     primary:
       brand: "Generic (Verified)"
       fdc_id: <validated>
       kcal_per_100g: [120, 180]
     alternates:
       - brand: "Specific Brand"
         fdc_id: <validated>
         kcal_per_100g: [110, 160]
   ```

**Expected Impact**: -6 misses (-0.3%)

---

## New Opportunities (Not from Z3 Misses)

### 3. Oatmeal Variations

**Observation**: "oatmeal", "oats cooked", "steel cut oats" may have inconsistent alignment

**Proposed Z4 Approach**:
- Verify Foundation entries exist for all oatmeal types
- If gaps found, add Stage Z verified entries
- Ensure instant vs steel-cut vs rolled differentiation

---

### 4. Yogurt with Toppings

**Observation**: "yogurt with granola", "yogurt with fruit" may trigger decomposition when simple match preferred

**Proposed Z4 Approach**:
- Review Stage 5B decomposition rules for yogurt
- Consider adding common combinations as Stage Z verified entries
- Balance between decomposition (accurate) vs direct match (simpler)

---

### 5. Mixed Nuts & Trail Mix

**Observation**: "mixed nuts", "trail mix" may be ambiguous

**Proposed Z4 Approach**:
- Check if Foundation has generic "mixed nuts" entry
- If not, add Stage Z with conservative macro ranges
- Document assumption (e.g., "almonds 40%, cashews 30%, peanuts 30%")

---

## Z4 Implementation Checklist

For each item added in Z4:

- [ ] **Foundation/SR check**: Verify entry truly doesn't exist
- [ ] **FDC validation**: Confirm FDC ID exists in database
- [ ] **Energy validation**: Check kcal range plausible
- [ ] **Synonym coverage**: Add all reasonable name variations
- [ ] **Fixture testing**: Create targeted test case
- [ ] **630 replay**: Run full replay to verify impact
- [ ] **Documentation**: Add to CHANGELOG with metrics

---

## Acceptance Criteria (Proposed)

**Phase Z4 Targets**:
| Metric | Z3 Target | Z4 Target | Delta |
|--------|-----------|-----------|-------|
| Stage Z usage | 20%+ | 25%+ | +5% |
| Miss rate | ≤25% | ≤20% | -5% |
| Tests | 6+ | 8+ | +2 |

**Additional**:
- ✅ Pizza decomposition working (validated with fixtures)
- ✅ Specialty items covered (chia pudding, etc.)
- ✅ No regression in Foundation/SR precedence
- ✅ Documentation updated

---

## Risks & Mitigations

### Risk: Over-reliance on Stage Z
**Symptom**: Stage Z becomes default instead of last resort
**Mitigation**:
- Maintain precedence: Foundation/SR → Stage 2 → Stage Z
- Add metrics tracking: % of Z matches that could have been Foundation/SR + Stage 2
- Review top Z matches quarterly for Foundation/SR candidates

### Risk: Broad pizza fallback masking bugs
**Symptom**: All pizza variants map to same entry, losing granularity
**Mitigation**:
- Use decomposition FIRST for pizza
- Stage Z fallback ONLY if decomposition fails
- Log when pizza hits Stage Z (should be rare)

### Risk: Energy band too wide
**Symptom**: Implausible matches accepted (e.g., thin crust pizza → deep dish energy)
**Mitigation**:
- Tighten energy bands in Z4 (±20% → ±15%)
- Add macro validation (protein/fat ratio checks)
- Reject if deviation > threshold

---

## Timeline (Tentative)

**Week 1**: Research & FDC lookups
- Validate all proposed FDC IDs
- Document energy ranges
- Create fixture test cases

**Week 2**: Implementation
- Add pizza decomposition to Stage 5B
- Add specialty items to Stage Z
- Update tests (target: 8 total)

**Week 3**: Validation
- Run 630-image replay with Z4 changes
- Analyze results vs Z3 baseline
- Document in Z4_RESULTS.md

**Week 4**: Review & iterate
- Address any regressions
- Fine-tune energy bands
- Update all documentation

---

## See Also

- `docs/PHASE_Z3_PLAN.md` - Current phase (completed)
- `docs/CHANGELOG.md` - Change history
- `docs/EVAL_BASELINES.md` - Baseline tracking
- `docs/RUNBOOK.md` - How to run replays
