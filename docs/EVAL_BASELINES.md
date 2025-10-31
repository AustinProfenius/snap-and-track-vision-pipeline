# Evaluation Baselines

**Purpose**: Track baseline prediction replay runs for regression comparison

**Last Updated**: 2025-10-30

---

## Current Baseline: Phase Z3.3 - Starches & Leafy Normalization

**Date**: 2025-10-30
**Path**: `runs/replay_z3_3_fixed_20251030/`
**Description**: Phase Z3.3 with feature flag fix - starch normalization and leafy mix support

**Metrics**:
| Metric | Value |
|--------|-------|
| Total foods | 2,032 |
| **Stage Z usage** | **409 (20.1%)** ✅ |
| **Miss rate (Stage 0)** | **491 (24.2%)** ✅ |
| stageZ_branded_fallback | 348 (17.1%) |
| stageZ_energy_only | 61 (3.0%) |
| Config version | configs@9d8b57dfbc1f |
| Fallbacks loaded | 123 |
| Feature flags | `allow_stageZ_for_partial_pools=True` |

**Why this baseline**:
- ✅ **Targets met**: Stage Z 20.1% (≥19%), miss rate 24.2% (≤25%)
- Phase Z3.3 features: Starch normalization, compound terms, egg white cooked support
- Feature flag fix applied (tri-state `db_verified` logic)
- Enhanced telemetry: Per-stage timing, rejection reasons, category breakdown
- All 630 predictions processed successfully
- Zero vision API calls ($0 cost)
- Validated against Z3.2.1 baseline (metrics identical)

**Phase Z3.3 Features**:
- Compound term preservation (sweet potato vs potato)
- Starch routing helper for potato variants
- 12+ Stage Z entries extended with synonyms
- Egg white form inference and cooked trigger
- +0.03 scoring bonus for starch-like produce
- Category breakdown analyzer

**File locations**:
```
runs/replay_z3_3_fixed_20251030/
├── results.jsonl        # 2.9MB, 630 predictions → 2,032 foods
├── telemetry.jsonl      # 2.2MB, detailed per-food telemetry
├── replay_manifest.json # 258B, run metadata
└── Z3_3_FIXED_RESULTS.md # Comprehensive analysis
```

**Documentation**:
- `PHASE_Z3_3_COMPLETE.md` - Implementation details
- `runs/replay_z3_3_20251030/Z3_3_RESULTS.md` - Initial regression analysis
- `runs/replay_z3_3_fixed_20251030/Z3_3_FIXED_RESULTS.md` - Fix validation

---

## Previous Baselines

### Phase Z3.2.1 - Surgical Stage Z Improvements
**Date**: 2025-10-30
**Path**: `runs/replay_z3_2_1_20251030/`
**Metrics**:
- Total foods: 2,032
- Stage Z usage: 409 (20.1%)
- Miss rate: 491 (24.2%)
- Config version: configs@9d8b57dfbc1f

**Note**: Metrics identical to Z3.3 (Z3.3 maintained improvements without regression)

### 630-Image Replay with Configs (Pre-Z3)

**Date**: 2025-10-30
**Path**: `runs/replay_630_withconfigs/`
**Description**: First replay with explicit config loading and feature flag validation

**Metrics**:
| Metric | Value |
|--------|-------|
| Total foods | 1,818 |
| Stage Z usage | 264 (14.5%) |
| Miss rate (Stage 0) | 539 (29.6%) |
| Config version | configs@cfdca3a7f351 |
| Fallbacks loaded | 107 |
| Feature flags | `allow_stageZ_for_partial_pools=True` |

**Why this baseline**:
- First run with configs explicitly wired through replay
- Comprehensive telemetry with source tracking
- Hard assertions for Stage Z activation
- All 630 predictions processed successfully
- Zero vision API calls ($0 cost)

**File locations**:
```
runs/replay_630_withconfigs/
├── results.jsonl        # 2.5MB, 630 predictions → 1,818 foods
├── telemetry.jsonl      # 1.8MB, detailed per-food telemetry
└── replay_manifest.json # 256B, run metadata
```

### Initial Replay (Pre-Config Wiring)
**Date**: 2025-10-30
**Path**: `runs/replay_630_fixed/`
**Metrics**:
- Total foods: 2,140
- Stage Z usage: 300 (14.0%)
- Miss rate: 600 (28.0%)

**Note**: Different food count due to salad decomposition handling differences

---

## How to Add New Baselines

### 1. Run Full Replay
```bash
python nutritionverse-tests/entrypoints/replay_from_predictions.py \
  --in nutritionverse-tests/results/gpt_5_630images_20251027_151930.json \
  --out runs/baseline_<name>_<date> \
  --config-dir configs/ \
  --schema auto
```

### 2. Validate Smoke Tests
```bash
# Check Stage Z > 0
grep "Stage Z usage" runs/baseline_*/*.log

# Verify files created
ls -lh runs/baseline_*/

# Check exit code (should be 0)
echo $?
```

### 3. Extract Key Metrics
```bash
python -c "
import json

# Load telemetry
data = []
with open('runs/baseline_<name>_<date>/telemetry.jsonl') as f:
    for line in f:
        if line.strip():
            data.append(json.loads(line))

# Calculate metrics
total = len(data)
stage_z = sum(1 for d in data if 'stageZ' in d.get('alignment_stage', ''))
misses = sum(1 for d in data if d.get('alignment_stage') == 'stage0_no_candidates')

print(f'Total: {total}')
print(f'Stage Z: {stage_z} ({stage_z/total*100:.1f}%)')
print(f'Misses: {misses} ({misses/total*100:.1f}%)')
"
```

### 4. Add Entry to This File
```markdown
### <Baseline Name> (<Date>)
**Path**: `runs/baseline_<name>_<date>/`
**Metrics**:
- Total foods: <total>
- Stage Z usage: <count> (<percent>%)
- Miss rate: <count> (<percent>%)
**Why this baseline**: <reason>
```

### 5. Update `CONTINUE_HERE.md`
Point to the new baseline for future comparisons.

---

## Baseline Selection Criteria

A good baseline should have:

✅ **Completeness**: All 630 predictions processed successfully
✅ **Reproducibility**: Fixed config version, deterministic results
✅ **Smoke tests passed**: Stage Z > 0, no assertion failures
✅ **Comprehensive telemetry**: Source tracking, full alignment stages
✅ **Documented**: Clear description of what changed vs previous baseline

---

## Future Baseline Candidates

### Phase Z4 Baseline (Planned)
**Changes from Z3**:
- Multi-component decomposition for pizza
- Verified entries for specialty items (chia pudding)
- Intent boosts integrated into scoring

**Expected Targets**:
- Stage Z usage: 25%+
- Miss rate: 20% or less

---

## See Also

- `docs/PHASE_Z3_PLAN.md` - Current phase goals
- `docs/RUNBOOK.md` - How to run replays
- `docs/CHANGELOG.md` - Change history
- `CONTINUE_HERE.md` - Latest run pointer
