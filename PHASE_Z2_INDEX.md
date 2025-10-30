# Phase Z2: Close Alignment Misses - Documentation Index

**Quick Links**:
- 🚀 [Start Here: Quick Start Script](#quick-start)
- 📖 [User Guide: PHASE_Z2_README.md](PHASE_Z2_README.md)
- 🔧 [Technical Details: Implementation Status](docs/phase_z2_implementation_status.md)
- 📊 [Summary: PHASE_Z2_SUMMARY.md](PHASE_Z2_SUMMARY.md)

---

## 🎯 Mission

Reduce 54 unique alignment misses to ≤10 through:
- **CSV-based verified FDC mappings** (from `missed_food_names.csv`)
- **Normalization fixes** (duplicate parentheticals, sun-dried, peel hints)
- **Systematic ignore rules** (tatsoi, alcohol, deprecated)
- **Enhanced telemetry** (coverage_class, source tracking)

**Current Status**: 40% Complete (2/7 major tasks done)

---

## 🚀 Quick Start

### Option 1: Automated Script (Recommended)
```bash
cd /Users/austinprofenius/snapandtrack-model-testing
./phase_z2_quickstart.sh
```

### Option 2: Manual Execution
```bash
# 1. Run CSV merge
python tools/merge_verified_fallbacks.py \
  --csv ./missed_food_names.csv \
  --out configs/stageZ_branded_fallbacks_verified.yml \
  --merge-into configs/stageZ_branded_fallbacks.yml \
  --report runs/csv_merge_report.json

# 2. Validate merged config
python tools/validate_stageZ_config.py configs/stageZ_branded_fallbacks.yml

# 3. Review merge report
cat runs/csv_merge_report.json
```

---

## 📚 Documentation Structure

### For Users (Start Here)
1. **[PHASE_Z2_README.md](PHASE_Z2_README.md)** - Complete implementation guide
   - Quick start instructions
   - Tool usage examples
   - Step-by-step remaining work
   - Acceptance criteria
   - Common pitfalls

2. **[PHASE_Z2_SUMMARY.md](PHASE_Z2_SUMMARY.md)** - Executive summary
   - Progress tracker
   - Completed deliverables
   - Time estimates
   - Risk mitigation

### For Developers (Technical Details)
3. **[docs/phase_z2_implementation_status.md](docs/phase_z2_implementation_status.md)** - Deep technical dive
   - Complete task breakdown
   - Code snippets for remaining work
   - Integration points
   - Telemetry specifications
   - Test suite details

### For Git/CI (Automation)
4. **[phase_z2_quickstart.sh](phase_z2_quickstart.sh)** - Automated setup script
5. **[PHASE_Z2_COMMIT_MESSAGE.txt](PHASE_Z2_COMMIT_MESSAGE.txt)** - Pre-written commit message

---

## 🛠️ Completed Tools

### 1. CSV Merge Tool
**File**: [tools/merge_verified_fallbacks.py](tools/merge_verified_fallbacks.py)
**Purpose**: Ingest verified FDC mappings from CSV into Stage Z config
**Size**: 636 lines
**Status**: ✅ Complete & Tested

**Features**:
- DB validation with precedence rules
- Kcal inference for all food categories
- Special case handling (cherry tomato, chicken, chilaquiles, orange w/ peel)
- Error handling (skips malformed rows, logs to report)

**Usage**:
```bash
python tools/merge_verified_fallbacks.py --help
```

### 2. Config Validation Tool
**File**: [tools/validate_stageZ_config.py](tools/validate_stageZ_config.py)
**Purpose**: Validate Stage Z config for consistency and correctness
**Size**: 304 lines
**Status**: ✅ Complete & Tested

**Checks**:
- Duplicate keys (critical error)
- Kcal ranges (min < max, no negatives)
- FDC ID existence (warning if missing)
- Synonym conflicts (warning)

**Usage**:
```bash
python tools/validate_stageZ_config.py --help
```

---

## 🔄 Remaining Work

### 3. Normalization Fixes (30 min)
**File**: `nutritionverse-tests/src/nutrition/alignment/align_convert.py`
**Function**: `_normalize_for_lookup()` (line ~276)
**Status**: ❌ Not Started

**Required Changes**:
- Collapse duplicate parentheticals
- Normalize sun-dried → sun_dried
- Extract peel hints (don't block alignment)
- Handle "deprecated" token

**Details**: See [PHASE_Z2_README.md → Step 2](PHASE_Z2_README.md#step-2-normalization-fixes-30-min)

---

### 4. Config Updates (10 min)
**Files**: `configs/stageZ_branded_fallbacks.yml`, `configs/negative_vocabulary.yml`
**Status**: ❌ Not Started

**Required Changes**:
- Add celery root → celery mapping
- Add tatsoi ignore rule
- Add alcohol ignore rules
- Add deprecated ignore rule

**Details**: See [PHASE_Z2_README.md → Step 3](PHASE_Z2_README.md#step-3-config-updates-10-min)

---

### 5. Telemetry Enhancements (30 min)
**Files**: `align_convert.py`, `stageZ_branded_fallback.py`
**Status**: ❌ Not Started

**Required Changes**:
- Add global `coverage_class` field
- Enhance Stage Z telemetry (source, DB validation status)
- Add `form_hint` for peel qualifiers
- Add `ignored_class` for negative vocab
- Enhance Stage 0 miss telemetry

**Details**: See [PHASE_Z2_README.md → Step 4](PHASE_Z2_README.md#step-4-telemetry-enhancements-30-min)

---

### 6. Test Suite (45 min)
**File**: `nutritionverse-tests/tests/test_phaseZ2_verified.py` (new)
**Status**: ❌ Not Started

**Test Categories**:
- CSV merge tests (3)
- Special case tests (4)
- No-result food tests (4)
- Normalization tests (2)

**Details**: See [PHASE_Z2_README.md → Step 5](PHASE_Z2_README.md#step-5-test-suite-45-min)

---

### 7. Integration & Validation (30 min)
**Status**: ❌ Not Started

**Tasks**:
- Run consolidated test on 50+ dishes
- Analyze miss reduction (target: 54 → ≤10)
- Spot-check Stage Z selections
- Verify ignored classes
- Check for regressions

**Details**: See [PHASE_Z2_README.md → Step 6](PHASE_Z2_README.md#step-6-integration--validation-30-min)

---

## 📊 Progress Tracker

```
Phase Z2 Implementation: 40% Complete (2/7 tasks done)

✅✅❌❌❌❌❌  [=========>           ] 40%

Completed:
  ✅ CSV Merge Tool (45 min)
  ✅ Config Validation Tool (30 min)

Remaining:
  ❌ Normalization Fixes (30 min)
  ❌ Config Updates (10 min)
  ❌ Telemetry Enhancements (30 min)
  ❌ Test Suite (45 min)
  ❌ Integration & Validation (30 min)

Time Spent: 1h 45m
Time Remaining: 2h 25m
Total Estimated: 4h 10m
```

---

## 🎯 Success Criteria

Phase Z2 is complete when:

- [ ] **Miss Reduction**: 54 → ≤10 unique misses
- [ ] **No Stage 0** for: cherry/grape tomatoes, spinach, wheat berry, green beans, sun-dried tomatoes, mushrooms, scrambled eggs, eggplant, potatoes, chicken
- [ ] **Special Cases**: Generic chicken doesn't force-map to breast; peel hints work; chilaquiles marked low confidence
- [ ] **Ignore Rules**: tatsoi, alcohol, deprecated return `available=false` with `ignored_class`
- [ ] **Config Valid**: `validate_stageZ_config.py` passes
- [ ] **Tests Pass**: All Phase Z2 tests pass
- [ ] **No Regressions**: Stage 5B, mass propagation, dessert blocking intact

---

## 📂 File Structure

```
snapandtrack-model-testing/
├── 📘 PHASE_Z2_INDEX.md                    ← YOU ARE HERE
├── 📖 PHASE_Z2_README.md                   ← User guide (start here)
├── 📊 PHASE_Z2_SUMMARY.md                  ← Executive summary
├── 📝 PHASE_Z2_COMMIT_MESSAGE.txt          ← Pre-written commit message
├── 🚀 phase_z2_quickstart.sh               ← Quick start script
│
├── docs/
│   └── 📄 phase_z2_implementation_status.md  ← Technical deep-dive
│
├── tools/
│   ├── ✅ merge_verified_fallbacks.py      ← CSV merge tool (COMPLETE)
│   └── ✅ validate_stageZ_config.py        ← Config validator (COMPLETE)
│
├── configs/
│   ├── stageZ_branded_fallbacks.yml        ← Stage Z config (TO UPDATE)
│   ├── stageZ_branded_fallbacks_verified.yml  ← Generated by merge tool
│   └── negative_vocabulary.yml             ← Ignore rules (TO UPDATE)
│
├── nutritionverse-tests/
│   ├── src/nutrition/alignment/
│   │   ├── align_convert.py                ← Normalization + telemetry (TO UPDATE)
│   │   └── stageZ_branded_fallback.py      ← Telemetry (TO UPDATE)
│   └── tests/
│       └── test_phaseZ2_verified.py        ← Test suite (TO CREATE)
│
├── runs/
│   └── csv_merge_report.json               ← Generated by merge tool
│
└── missed_food_names.csv                   ← Input CSV (104 rows)
```

---

## 🔗 Key Concepts

### Precedence Order
```
Foundation/SR (Stage 1)
    ↓
Cooked Conversion (Stage 2)
    ↓
Stage Z (Verified CSV)
    ↓
Stage Z (Generic Branded)
    ↓
Stage 0 (Miss)
```

### Coverage Classes
- `foundation` - Stage 1b/1c match
- `converted` - Stage 2 cooked conversion
- `branded_verified_csv` - Stage Z from CSV
- `branded_generic` - Stage Z pre-existing
- `proxy` - Stage 5 proxy
- `ignored` - Negative vocab match

### Special Cases (From CSV)
1. **Cherry tomato**: Foundation 321360 only if DB-verified
2. **Chicken**: Token constraint for "breast" queries
3. **Chilaquiles**: Low confidence + reject patterns
4. **Orange with peel**: Normalizes to "orange" + peel hint

---

## 💡 Common Commands

```bash
# Run CSV merge
python tools/merge_verified_fallbacks.py \
  --csv ./missed_food_names.csv \
  --merge-into configs/stageZ_branded_fallbacks.yml

# Validate config
python tools/validate_stageZ_config.py configs/stageZ_branded_fallbacks.yml

# Run consolidated test
python nutritionverse-tests/entrypoints/run_first_50_consolidated.py

# Analyze misses
python analyze_consolidated_misses.py

# Run Phase Z2 tests
pytest nutritionverse-tests/tests/test_phaseZ2_verified.py -v

# Check for regressions
pytest nutritionverse-tests/tests/ -v
```

---

## 📞 Getting Help

### By Document Type

**Need to get started?**
→ Read [PHASE_Z2_README.md](PHASE_Z2_README.md)

**Need progress overview?**
→ Read [PHASE_Z2_SUMMARY.md](PHASE_Z2_SUMMARY.md)

**Need technical details?**
→ Read [docs/phase_z2_implementation_status.md](docs/phase_z2_implementation_status.md)

**Need to run tools?**
→ Execute `./phase_z2_quickstart.sh`

**Need tool help?**
→ `python tools/<tool_name>.py --help`

---

## 🚦 Next Actions

### Immediate (5 min)
```bash
./phase_z2_quickstart.sh
```

### Short-term (2.5 hours)
Complete remaining 5 tasks:
1. Normalization fixes
2. Config updates
3. Telemetry enhancements
4. Test suite
5. Integration & validation

### Medium-term (30 min)
- Run consolidated test
- Analyze miss reduction
- Verify acceptance criteria
- Prepare PR for review

---

**Last Updated**: 2025-10-30
**Status**: Ready for continuation
**Next Step**: Run `./phase_z2_quickstart.sh`

---

*This index provides navigation to all Phase Z2 documentation*
*Choose the appropriate document based on your role and needs*
