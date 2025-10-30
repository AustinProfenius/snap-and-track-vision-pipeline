# Evaluation Baselines

**Purpose**: Track baseline prediction replay runs for regression comparison

**Last Updated**: 2025-10-30

---

## Current Baseline: 630-Image Replay with Configs (Pre-Z3)

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

---

## Previous Baselines

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
