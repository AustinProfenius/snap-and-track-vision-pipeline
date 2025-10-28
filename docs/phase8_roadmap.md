# Phase 8 — Protein/Fiber/Mineral Confidence Tuning

## Overview
Enhance alignment confidence scoring using nutrient-profile agreement to penalize mismatches where nutrient density diverges from class priors (e.g., "egg yolk" vs "egg whole"). Surface per-dish Micronutrient Confidence Score (MCS) for downstream UI.

## Objectives
1. Improve **macro/micro confidence** per aligned item using nutrient-profile agreement (USDA vs visual prior)
2. Penalize mismatches where nutrient density diverges from class priors
3. Surface a per-dish **Micronutrient Confidence Score (MCS)** for downstream UI
4. Reduce calorie MAPE by 10-15% for meats and eggs through better variant selection

## Plan

### A. Class Priors (Nutrient Density Bands)
Define per-class expected nutrient density bands (per 100g) for key food categories.

**Implementation**:
- Create `configs/nutrient_priors.yml` with mean ± tolerance bands for:
  - **Proteins**: chicken_breast, beef_steak, salmon, pork_chop, lamb
  - **Vegetables**:
    - Leafy: spinach, romaine, kale, mixed greens
    - Cruciferous: broccoli, cauliflower, brussels sprouts
  - **Fruits/Berries**: strawberry, blueberry, banana, apple, orange
  - **Eggs**: whole, yolk, white (distinct profiles)

**Fields per class**:
```yaml
chicken_breast:
  protein_g_100g: {mean: 31.0, tolerance: 5.0}
  fat_g_100g: {mean: 3.6, tolerance: 2.0}
  carbs_g_100g: {mean: 0.0, tolerance: 1.0}
  fiber_g_100g: {mean: 0.0, tolerance: 0.1}
  sodium_mg_100g: {mean: 74, tolerance: 50}
```

### B. Confidence Scoring
For each aligned candidate, compute deltas from class priors and score nutrient agreement.

**Implementation**:
- Add method `_compute_nutrient_confidence(entry, class_priors)` to align_convert.py
- Compute deltas: Δprotein_g_100g, Δfiber_g_100g, Δminerals (Na/K/Ca/Mg) vs prior band
- Score formula:
  ```python
  delta_vector = [
      abs(entry.protein_g_100g - prior.protein.mean) / prior.protein.tolerance,
      abs(entry.fiber_g_100g - prior.fiber.mean) / prior.fiber.tolerance,
      # ... other nutrients
  ]
  raw_score = 1 - min(1, mean(delta_vector))
  confidence = max(0, raw_score)
  ```
- Apply soft demotions (-0.05 to -0.15) when candidate lies **outside** tolerance band
- Boost (+0.03 to +0.10) when candidate is within **tight** prior band and matches predicted form (raw/fresh/whole)

### C. Selection Integration
Integrate nutrient confidence into Stage 1b scoring as an additive term.

**Implementation**:
- In `_stage1b_raw_foundation_direct`, compute nutrient confidence for each candidate
- Add weighted confidence term to score:
  ```python
  base_score = 0.7 * jaccard + 0.3 * energy_sim
  nutrient_confidence = _compute_nutrient_confidence(entry, priors)
  final_score = base_score + (0.05 * nutrient_confidence)  # +0 to +0.05 boost
  ```
- When two candidates tie (score diff < 0.02), prefer higher MCS
- For StageZ (energy-only), compute **energy-only confidence** and expose as telemetry

### D. Telemetry & Metrics
Track nutrient confidence in telemetry for downstream analysis.

**Implementation**:
- Add to `TelemetryEvent` schema:
  - `macro_confidence: Optional[float]`  # 0-1 score for protein/carbs/fat match
  - `micro_confidence: Optional[float]`  # 0-1 score for minerals/fiber match
  - `mcs_overall: Optional[float]`  # Combined micronutrient confidence score

- Extend `tools/metrics/validate_phase8.py` to report:
  - Correlation between MCS and correctness (name Jaccard)
  - Error reduction by MCS deciles (high-MCS items should have lower MAPE)
  - Breakdown of MCS distribution across food categories

### E. Acceptance Criteria
Phase 8 is considered successful if metrics improve on validation batches:

**Primary Metrics**:
- **+2-4%** improvement in dish-level name Jaccard≥0.6 rate
- **−10-15%** relative reduction in calorie MAPE for meats and eggs
- High-MCS deciles (MCS ≥ 0.8) show **statistically lower errors** (t-test p < 0.05)

**Secondary Metrics**:
- MCS correlates negatively with error (Pearson r < -0.3)
- No regression on produce/vegetables accuracy

### F. Stretch Goals
If primary goals achieved ahead of schedule:

1. **Learn Per-Class Weights from Validation Batches**:
   - Use logistic regression over correctness to learn optimal nutrient weights
   - Replace hand-tuned tolerance bands with learned thresholds

2. **Auto-Flip Egg Variants**:
   - Add rule to automatically flip "egg yolk" ↔ "egg whole" if:
     - Predicted form/visual priors contradict MCS
     - Alternate variant has MCS > 0.8 and current MCS < 0.5
   - Log auto-flip events in telemetry for auditability

3. **Extend to Dairy & Grains**:
   - Add nutrient priors for milk (whole/skim), cheese (hard/soft), rice (white/brown)
   - Test MCS improvements on mixed-category dishes

## Implementation Timeline
- **Week 1**: Define nutrient priors config, implement confidence scoring logic
- **Week 2**: Integrate into Stage 1b, add telemetry fields, test on 50-dish smoke set
- **Week 3**: Run full 405-image validation, analyze MCS correlation with errors
- **Week 4**: Iterate on tolerance bands, implement stretch goals if time permits

## Success Metrics Summary
```
Phase 8 Pass Criteria:
✓ Dish Name Jaccard≥0.6: +2-4% improvement
✓ Calorie MAPE (meats/eggs): -10-15% reduction
✓ High-MCS deciles: statistically lower errors (p < 0.05)
✓ No regression on produce accuracy
```

## Notes
- Nutrient confidence is **additive**, not replacing existing Jaccard/energy scoring
- MCS exposed to UI for transparency (users can see why certain foods flagged)
- Phase 8 builds on Phase 7.3's decomposition work - salads benefit from component-level MCS
- If MCS proves effective, can extend to Stage 3/4 (branded) selection in Phase 9
