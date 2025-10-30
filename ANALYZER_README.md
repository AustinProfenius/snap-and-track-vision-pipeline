# Batch Results Analyzer - Usage Guide

**Script**: [analyze_batch_results.py](analyze_batch_results.py)
**Purpose**: Analyze batch evaluation results to validate Phase Z2 implementation
**Created**: 2025-10-30

---

## Overview

The Batch Results Analyzer processes JSON output from `run_459_batch_evaluation.py` to extract comprehensive metrics about alignment performance, including:

- **Unique misses** - Foods that got `stage0_no_candidates`
- **Total no matches** - Count of items with no FDC alignment
- **Stage distribution** - Breakdown by alignment stage
- **Coverage class** - Distribution by coverage type (Foundation, converted, branded, etc.)
- **Phase Z2 impact** - Metrics specific to Phase Z2 features
- **Special cases** - Validation of Phase Z2 special handling

---

## Quick Start

### Basic Usage
```bash
# Analyze results and print report
python analyze_batch_results.py results/batch_459_results_TIMESTAMP.json

# Save detailed analysis to JSON
python analyze_batch_results.py results/batch_459_results_TIMESTAMP.json -o analysis.json

# Verbose mode (shows more details)
python analyze_batch_results.py results/batch_459_results_TIMESTAMP.json -v

# Compare with baseline
python analyze_batch_results.py results/current.json --compare results/baseline.json
```

### Example Output
```
================================================================================
PHASE Z2 BATCH RESULTS ANALYSIS
================================================================================
Results file: batch_459_results_20251030_114822.json
Timestamp: 20251030_114822
Total items: 459

1. MISS ANALYSIS (stage0_no_candidates)
----------------------------------------
Total misses: 281 items
Unique foods: 23 foods
Miss rate: 61.2%
Pass rate: 38.8%

❌ PHASE Z2 TARGET NOT MET: 23 unique misses > 10

Top 20 unique misses by frequency:
   1. egg                                      ( 26 instances)
   2. potato                                   ( 19 instances)
   3. beef steak                               ( 15 instances)
   ...
```

---

## Report Sections

### 1. Miss Analysis
**What it shows**: Foods that couldn't be aligned (stage0_no_candidates)

**Metrics**:
- Total misses count
- Unique foods count
- Miss rate percentage
- Pass rate percentage
- Top missed foods by frequency

**Phase Z2 Target**: ≤10 unique misses

**Example**:
```
Total misses: 281 items
Unique foods: 23 foods
Miss rate: 61.2%
Pass rate: 38.8%

❌ PHASE Z2 TARGET NOT MET: 23 unique misses > 10
```

**Interpretation**:
- **Without database**: High miss rate expected (Stage Z requires DB)
- **With database**: Should see dramatic reduction in unique misses

---

### 2. Stage Distribution
**What it shows**: Breakdown of items by alignment stage

**Stages**:
- `stage0_no_candidates` - No FDC match found
- `stage1b_raw_foundation_direct` - Raw Foundation match
- `stage1c_cooked_sr_direct` - Cooked SR Legacy match
- `stage2_raw_convert` - Cooked food converted from raw
- `stageZ_branded_fallback` - Stage Z branded fallback (Phase Z2)
- `stage5_proxy_alignment` - Salad decomposition proxy

**Example**:
```
stage0_no_candidates                      281 ( 61.2%)
stage1b_raw_foundation_direct              91 ( 19.8%)
stage2_raw_convert                         60 ( 13.1%)
stageZ_energy_only                         17 (  3.7%)
stage1c_cooked_sr_direct                   10 (  2.2%)
```

**Interpretation**:
- High `stage0` without database is expected
- With database, expect to see `stageZ_branded_fallback` usage

---

### 3. Coverage Class Distribution
**What it shows**: Items grouped by coverage type

**Coverage Classes**:
- `foundation` - Direct Foundation/SR match
- `converted` - Cooked conversion from raw
- `branded_verified_csv` - Stage Z from verified CSV (Phase Z2)
- `branded_generic` - Stage Z from existing config
- `proxy` - Salad decomposition
- `no_match` - No alignment found
- `ignored` - Negative vocabulary match

**Example**:
```
no_match                        281 ( 61.2%)
foundation                      101 ( 22.0%)
converted                        60 ( 13.1%)
branded_verified_csv             45 (  9.8%)  # Phase Z2 CSV entries
branded_generic                  12 (  2.6%)
```

**Interpretation**:
- With Phase Z2, expect to see `branded_verified_csv` category
- This shows CSV-derived entries working

---

### 4. Phase Z2 Impact Metrics
**What it shows**: Phase Z2 specific features and usage

**Metrics**:
- Stage Z usage (total, CSV verified, existing config)
- Normalization hints (peel qualifiers)
- Ignored foods (negative vocabulary)

**Example**:
```
Stage Z branded fallback usage: 57 items
  - CSV verified entries: 45 items
  - Existing config entries: 12 items

Normalization hints (peel): 3 items

Ignored foods (negative vocab): 8 items
  - leafy_unavailable: 2 items
  - alcoholic_beverage: 5 items
  - deprecated: 1 item
```

**Interpretation**:
- CSV verified entries show Phase Z2 working
- Normalization hints show peel detection working
- Ignored foods show negative vocabulary working

---

### 5. Special Cases Validation
**What it shows**: Validation of Phase Z2 special handling

**Special Cases Tracked**:
- **Chicken breast** - Should have token constraint
- **Cherry tomato** - Should prefer Foundation
- **Celery** - Should map celery root → celery
- **Tatsoi** - Should be ignored (leafy_unavailable)
- **Alcohol** - Should be ignored (alcoholic_beverage)
- **Deprecated** - Should be ignored (deprecated)

**Example**:
```
Chicken breast items: 44
  - All using Foundation or Stage Z with token constraint

Cherry/grape tomato items: 12
  ✅ 12 using Foundation (preferred)

Tatsoi items: 2 (should be ignored)
  ✅ All 2 correctly ignored

Alcohol items: 5 (should be ignored)
  ✅ All 5 correctly ignored
```

**Interpretation**:
- ✅ indicates special handling is working correctly
- Shows Phase Z2 features (ignore rules, token constraints) in action

---

## Output Files

### Terminal Report
Human-readable report printed to stdout showing all metrics and validation results.

### JSON Analysis File (-o option)
Detailed JSON file with complete analysis data:

```json
{
  "metadata": {
    "source_file": "batch_459_results_20251030_114822.json",
    "timestamp": "20251030_114822",
    "total_items": 459
  },
  "miss_analysis": {
    "total_misses": 281,
    "unique_foods": 23,
    "miss_rate": 0.612,
    "unique_misses": [
      ["egg", 26],
      ["potato", 19],
      ...
    ]
  },
  "stage_distribution": {...},
  "coverage_distribution": {...},
  "phase_z2_impact": {...},
  "special_cases": {...}
}
```

---

## Use Cases

### 1. Phase Z2 Validation
**Goal**: Verify Phase Z2 reduces unique misses to ≤10

**Steps**:
```bash
# 1. Run batch evaluation WITH database
export NEON_CONNECTION_URL="postgresql://..."
cd nutritionverse-tests
PYTHONPATH=$(pwd):$PYTHONPATH python entrypoints/run_459_batch_evaluation.py

# 2. Analyze results
python analyze_batch_results.py nutritionverse-tests/entrypoints/results/batch_459_phase1/batch_459_results_TIMESTAMP.json

# 3. Check report for:
#    - Unique misses ≤ 10 ✅
#    - Stage Z usage > 0
#    - CSV verified entries > 0
```

**Expected Outcome**:
```
✅ PHASE Z2 TARGET MET: 8 unique misses ≤ 10

Stage Z branded fallback usage: 98 items
  - CSV verified entries: 87 items
  - Existing config entries: 11 items
```

---

### 2. Baseline Comparison
**Goal**: Compare current results with pre-Phase-Z2 baseline

**Steps**:
```bash
# Compare current vs baseline
python analyze_batch_results.py current_results.json --compare baseline_results.json
```

**Expected Output**:
```
================================================================================
COMPARISON WITH BASELINE
================================================================================
Baseline unique misses: 54
Current unique misses: 8
Reduction: 46 (85.2%)

✅ PHASE Z2 TARGET ACHIEVED!
```

---

### 3. Debug Missing Foods
**Goal**: Identify which foods are still missing after Phase Z2

**Steps**:
```bash
# Run with verbose mode
python analyze_batch_results.py results.json -v

# Check "Top 20 unique misses" section
# These are foods that may need:
# - Additional CSV entries
# - Config adjustments
# - Feature flag changes
```

**Example**:
```
Top 20 unique misses by frequency:
   1. obscure_food_A                           (  5 instances)
   2. regional_dish_B                          (  3 instances)
   ...
```

**Action**: Add these to `missed_food_names.csv` and re-run CSV merge

---

### 4. Monitor Special Cases
**Goal**: Ensure Phase Z2 special handling is working

**Steps**:
```bash
# Run analysis
python analyze_batch_results.py results.json

# Check section 5 for special cases
# Verify:
# - Chicken breast using token constraint
# - Cherry tomato preferring Foundation
# - Ignored foods (tatsoi, alcohol) being ignored
```

**Validation**:
- All special cases should show ✅
- Any ❌ indicates configuration issue

---

## Interpreting Results

### Without Database Connection
```
Stage Z branded fallback usage: 0 items
  - CSV verified entries: 0 items

❌ PHASE Z2 TARGET NOT MET: 23 unique misses > 10
```

**This is EXPECTED** - Stage Z requires database to resolve FDC entries

**Action**: Set `NEON_CONNECTION_URL` and re-run test

---

### With Database Connection (Expected Phase Z2 Success)
```
Stage Z branded fallback usage: 98 items
  - CSV verified entries: 87 items
  - Existing config entries: 11 items

✅ PHASE Z2 TARGET MET: 8 unique misses ≤ 10
```

**This indicates success** - Phase Z2 is working as expected

**Breakdown**:
- 87 foods from CSV now resolving via Stage Z
- Only 8 unique foods still missing (target: ≤10)
- 98 total Stage Z usages across batch

---

## Troubleshooting

### Issue: "FileNotFoundError"
**Cause**: Results file path incorrect

**Solution**:
```bash
# Find results files
find . -name "batch_459_results_*.json"

# Use full or relative path
python analyze_batch_results.py ./path/to/results.json
```

---

### Issue: "Stage Z usage: 0 items"
**Cause**: No database connection OR Stage Z feature flag disabled

**Solution**:
```bash
# Check database connection
echo $NEON_CONNECTION_URL

# If empty, set it:
export NEON_CONNECTION_URL="postgresql://..."

# Re-run batch evaluation
cd nutritionverse-tests
PYTHONPATH=$(pwd):$PYTHONPATH python entrypoints/run_459_batch_evaluation.py
```

---

### Issue: "High miss rate (>50%)"
**Cause**: Database not available OR configs not loaded

**Solution**:
1. Verify database connection
2. Check config files exist:
   ```bash
   ls -la configs/stageZ_branded_fallbacks.yml
   ls -la configs/negative_vocabulary.yml
   ```
3. Ensure configs loaded in alignment engine

---

## Command Reference

### Basic Commands
```bash
# Simple analysis
python analyze_batch_results.py results.json

# Verbose mode
python analyze_batch_results.py results.json -v

# Save JSON
python analyze_batch_results.py results.json -o analysis.json

# Compare with baseline
python analyze_batch_results.py current.json --compare baseline.json

# All options
python analyze_batch_results.py results.json -v -o detailed.json --compare old.json
```

### Finding Results Files
```bash
# Find all batch results
find . -name "batch_459_results_*.json"

# Find most recent
ls -lt nutritionverse-tests/entrypoints/results/batch_459_phase1/*.json | head -1

# Analyze most recent
python analyze_batch_results.py $(ls -t nutritionverse-tests/entrypoints/results/batch_459_phase1/*.json | head -1)
```

---

## Integration with Phase Z2 Workflow

### Step 1: Run Batch Evaluation
```bash
export NEON_CONNECTION_URL="postgresql://..."
cd nutritionverse-tests
PYTHONPATH=$(pwd):$PYTHONPATH python entrypoints/run_459_batch_evaluation.py
```

### Step 2: Analyze Results
```bash
cd ..
python analyze_batch_results.py nutritionverse-tests/entrypoints/results/batch_459_phase1/batch_459_results_TIMESTAMP.json -o phase_z2_validation.json
```

### Step 3: Validate Success
Check for:
- ✅ Unique misses ≤ 10
- ✅ Stage Z usage > 0
- ✅ CSV verified entries match expected count (~87)
- ✅ Special cases all passing

### Step 4: Create PR
If validation passes, proceed with PR using metrics from analysis.

---

## Related Documentation

- **[PHASE_Z2_IMPLEMENTATION_COMPLETE.md](PHASE_Z2_IMPLEMENTATION_COMPLETE.md)** - Implementation summary
- **[PHASE_Z2_VALIDATION_REPORT.md](PHASE_Z2_VALIDATION_REPORT.md)** - Standalone validation
- **[CONTINUE_HERE.md](CONTINUE_HERE.md)** - Quick reference guide

---

## Metrics Glossary

| Metric | Definition | Phase Z2 Target |
|--------|------------|-----------------|
| **Total misses** | Items with stage0_no_candidates | N/A |
| **Unique foods** | Distinct food names that missed | ≤10 |
| **Miss rate** | % of items that got no match | <1% (with DB) |
| **Pass rate** | % of items successfully aligned | >99% (with DB) |
| **Stage Z usage** | Items using Stage Z fallback | >0 (with DB) |
| **CSV verified** | Items from manual_verified_csv | ~87 (expected) |

---

**Created**: 2025-10-30
**For**: Phase Z2 validation
**Analyzer Version**: 1.0
