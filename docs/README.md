# Repository Census Documentation

**Generated**: 2025-10-29
**Purpose**: Complete repository analysis and consolidation guide

---

## Overview

This directory contains a comprehensive census of the Snap & Track Vision Pipeline repository, identifying active code vs. duplicates/legacy code that needs cleanup.

**Key Finding**: The repository has ~5000+ lines of duplicate code across temporary delivery directories that can be safely removed.

---

## 📁 Documents in This Directory

### 1. **REPO_SNAPSHOT.md** (PRIMARY DOCUMENT)

**Purpose**: Human-readable repository state analysis

**Contents**:
- Executive summary
- Directory-by-directory breakdown (nutritionverse-tests, gpt5-context-delivery, pipeline, configs)
- Active vs. Fluff table (45 active files, ~60 legacy/duplicate files)
- Pipeline stages and entrypoints
- Duplication map
- Telemetry documentation
- **Reassembly Plan** (step-by-step consolidation guide)
- Reproducible commands for analysis

**Read This First** if you need to understand the repository structure.

---

### 2. **UNUSED_OR_DUPLICATE_REPORT.md**

**Purpose**: Detailed list of files to delete or archive

**Contents**:
- Duplicate files by directory
- Superseded files (fdc_alignment.py, fdc_alignment_v2.py)
- Experimental/unused adapters (ollama, claude, gemini)
- Old documentation to move
- Summary by action (DELETE, MOVE, ARCHIVE)
- Verification checklist
- Execution plan with bash commands

**Use This** when executing the cleanup/consolidation.

---

### 3. **ACTIVE_INVENTORY.json** (MACHINE-READABLE)

**Purpose**: Structured data for active files

**Schema**:
```json
{
  "path": "relative/path/to/file.py",
  "language": "Python",
  "purpose_short": "Brief description",
  "last_commit_date": "2025-10-29",
  "active_score": 100,
  "why_active": ["Reason 1", "Reason 2"],
  "deps": ["module1", "module2"],
  "referenced_by_tests": ["test_file.py"],
  "referenced_by_configs": ["config.yml"]
}
```

**Contains**: 45 core/support files with scores ≥ 40

**Use This** for programmatic analysis or dashboard generation.

---

### 4. **DEPENDENCY_GRAPH.dot**

**Purpose**: Visual dependency graph (Graphviz DOT format)

**Generate PNG**:
```bash
dot -Tpng DOCS/DEPENDENCY_GRAPH.dot -o DOCS/dependency_graph.png
```

**Shows**:
- Entrypoints → Pipeline → Engine → Supporting Modules
- Config file dependencies
- Test coverage
- Stage relationships within align_convert.py

**Use This** to visualize how modules connect.

---

### 5. **../tools/scan_repo.py** (SCANNER SCRIPT)

**Purpose**: Automated repository scanner

**Usage**:
```bash
# Generate active inventory JSON
python tools/scan_repo.py > DOCS/ACTIVE_INVENTORY_NEW.json

# Run from any directory
cd /path/to/repo
python tools/scan_repo.py --output DOCS/inventory.json
```

**Features**:
- Scans all Python/YAML/config files
- Calculates active scores (0-100)
- Extracts imports and dependencies
- Categorizes as core/support/nice-to-have/legacy
- Outputs JSON inventory

**Use This** to regenerate inventory after making changes.

---

## 🎯 Quick Start

### If You Want To...

**...Understand the repository structure:**
→ Read `REPO_SNAPSHOT.md` (start with Executive Summary)

**...Clean up duplicate code:**
→ Follow `UNUSED_OR_DUPLICATE_REPORT.md` execution plan

**...Query file metadata programmatically:**
→ Use `ACTIVE_INVENTORY.json`

**...Visualize dependencies:**
→ Generate PNG from `DEPENDENCY_GRAPH.dot`

**...Regenerate inventory:**
→ Run `../tools/scan_repo.py`

---

## 📊 Key Statistics

| Metric | Count |
|--------|-------|
| **Total Code Files** | 179 |
| **Active Core Files** | ~45 (score ≥ 80) |
| **Support Files** | ~30 (score 60-79) |
| **Legacy/Duplicate** | ~60 (score ≤ 39) |
| **Config Files (All Active)** | 10 |
| **Test Files** | 15 |
| **Duplicate Directories** | 3 (gpt5-context-delivery, tempPipeline10-27-811, scattered copies) |
| **Estimated Duplicate Lines** | ~5000+ |

---

## 🗑️ Cleanup Summary

### DELETE (High Priority)

**Directories** (~8400 lines):
- `/gpt5-context-delivery/alignment/` (duplicates)
- `/gpt5-context-delivery/vision/` (duplicates)
- `/gpt5-context-delivery/configs/` (duplicates)
- `/tempPipeline10-27-811/` (old snapshot)

**Files**:
- `nutritionverse-tests/src/adapters/fdc_alignment.py` (superseded)
- `nutritionverse-tests/src/adapters/fdc_alignment_v2.py` (superseded)

### MOVE (High Priority)

**From** `/gpt5-context-delivery/entrypoints/` **To** `/nutritionverse-tests/entrypoints/`:
- `run_first_50_by_dish_id.py` (active entrypoint)

**From** `nutritionverse-tests/info/` **To** `/docs/archive/`:
- Entire directory (old documentation)

### ARCHIVE (Medium Priority)

**To** `.archived/experimental_adapters/`:
- `ollama_llava.py`, `claude_.py`, `gemini_.py` (unused LLM adapters)

---

## 🔍 Active Pipeline Components

### Core Files (Score 100)

1. **`nutritionverse-tests/src/nutrition/alignment/align_convert.py`**
   - Main alignment engine (2000+ lines)
   - Stages 1b/1c/2/5/Z

2. **`pipeline/run.py`**
   - Unified orchestrator (single source of truth)
   - Calls engine, writes telemetry

3. **`pipeline/schemas.py`**
   - Pydantic type-safe contracts
   - TelemetryEvent with `stage1c_switched`

4. **`configs/negative_vocabulary.yml`**
   - Guardrails + Stage 1c preferences
   - Phase 7.4 updates

### Entrypoints

| File | Purpose | Location |
|------|---------|----------|
| `run_first_50_by_dish_id.py` | First-50 batch test | `gpt5-context-delivery/entrypoints/` → **NEEDS MOVE** |
| `run_459_batch_evaluation.py` | 300-image batch | `nutritionverse-tests/` |
| `nutritionverse_app.py` | Flask web app | `nutritionverse-tests/` |

---

## 🏗️ Post-Cleanup Structure

```
snapandtrack-model-testing/
├── pipeline/                     # Unified orchestrator
│   ├── run.py ⭐
│   ├── schemas.py ⭐
│   ├── config_loader.py
│   ├── fdc_index.py
│   └── tests/
├── nutritionverse-tests/         # Main source code
│   ├── src/
│   │   ├── nutrition/            # Alignment, conversions
│   │   ├── adapters/             # DB, FDC
│   │   └── core/                 # Vision, prompts
│   ├── tests/
│   ├── entrypoints/              # ✅ Consolidated here
│   └── results/
├── configs/                      # Production configs
│   ├── negative_vocabulary.yml ⭐
│   ├── class_thresholds.yml ⭐
│   └── ...
├── tests/                        # Pipeline E2E tests
├── tools/                        # Validation scripts
├── docs/                         # Documentation
│   ├── phases/
│   └── archive/
└── DOCS/                         # This census
    ├── REPO_SNAPSHOT.md ⭐
    ├── UNUSED_OR_DUPLICATE_REPORT.md ⭐
    ├── ACTIVE_INVENTORY.json
    └── DEPENDENCY_GRAPH.dot
```

**Deleted**:
- ❌ `/gpt5-context-delivery`
- ❌ `/tempPipeline10-27-811`

---

## ✅ Execution Checklist

Use this checklist when performing cleanup:

### Phase 1: Backup
- [ ] Create backup: `tar -czf repo_backup_$(date +%Y%m%d).tar.gz gpt5-context-delivery tempPipeline10-27-811`
- [ ] Verify backup: `tar -tzf repo_backup_*.tar.gz | head`

### Phase 2: Move Unique Files
- [ ] Create: `mkdir -p nutritionverse-tests/entrypoints`
- [ ] Move: `mv gpt5-context-delivery/entrypoints/run_first_50_by_dish_id.py nutritionverse-tests/entrypoints/`
- [ ] Update import paths in moved file
- [ ] Test: Run moved script to ensure it works

### Phase 3: Delete Duplicates
- [ ] Delete: `rm -rf gpt5-context-delivery/alignment`
- [ ] Delete: `rm -rf gpt5-context-delivery/vision`
- [ ] Delete: `rm -rf gpt5-context-delivery/configs`
- [ ] Delete entire: `rm -rf gpt5-context-delivery`
- [ ] Delete snapshot: `rm -rf tempPipeline10-27-811`

### Phase 4: Delete Superseded
- [ ] Delete: `rm -f nutritionverse-tests/src/adapters/fdc_alignment.py`
- [ ] Delete: `rm -f nutritionverse-tests/src/adapters/fdc_alignment_v2.py`

### Phase 5: Archive Experimental
- [ ] Create: `mkdir -p .archived/experimental_adapters`
- [ ] Move: `mv nutritionverse-tests/src/adapters/{ollama_llava.py,claude_.py,gemini_.py} .archived/experimental_adapters/`

### Phase 6: Verify
- [ ] Run tests: `python -m pytest nutritionverse-tests/tests/ -v`
- [ ] Run pipeline test: `python test_stage1c_telemetry.py`
- [ ] Verify no broken imports: `python tools/scan_repo.py`

### Phase 7: Commit
- [ ] Stage changes: `git add -A`
- [ ] Commit with message from `UNUSED_OR_DUPLICATE_REPORT.md`
- [ ] Push: `git push`

---

## 📝 Verification Commands

### Check for Broken Imports
```bash
# Search for imports that might break
grep -r "from.*fdc_alignment\|from.*ollama_llava\|from.*claude_\|from.*gemini_" \
  nutritionverse-tests pipeline gpt5-context-delivery 2>/dev/null
# Expected: No results
```

### Verify Duplicate Detection
```bash
# Find duplicate file names
find nutritionverse-tests gpt5-context-delivery tempPipeline10-27-811 \
  -type f -name "*.py" 2>/dev/null | \
  xargs -n1 basename | sort | uniq -d
```

### Check Directory Sizes
```bash
du -h -d 2 nutritionverse-tests gpt5-context-delivery pipeline configs | sort -h
```

---

## 🔗 Related Documentation

- **[../PHASE7_4_COMPLETION_SUMMARY.md](../PHASE7_4_COMPLETION_SUMMARY.md)** - Stage 1c implementation
- **[../STAGE1C_TELEMETRY_FIX.md](../STAGE1C_TELEMETRY_FIX.md)** - Telemetry persistence fix
- **[../PR_STAGE1C_VERIFICATION.md](../PR_STAGE1C_VERIFICATION.md)** - Stage 1c verification
- **[../docs/](../docs/)** - Phase 7.3 documentation

---

## ❓ FAQ

**Q: Is it safe to delete `/gpt5-context-delivery`?**
A: Yes, after moving `run_first_50_by_dish_id.py` to `nutritionverse-tests/entrypoints/`. All other files are exact duplicates.

**Q: Why keep experimental adapters instead of deleting?**
A: They're small (~500 lines total) and may be useful for future LLM comparisons. Archiving preserves them without cluttering the main tree.

**Q: What if tests fail after cleanup?**
A: Restore from backup: `tar -xzf repo_backup_*.tar.gz`. Then investigate which file deletion caused the issue.

**Q: How do I regenerate this census after changes?**
A: Run `python tools/scan_repo.py > DOCS/ACTIVE_INVENTORY_NEW.json` and compare with the original.

---

## 🚀 Post-Cleanup Benefits

1. **~5000+ fewer lines** of duplicate code
2. **Single source of truth** (no confusion about which copy is canonical)
3. **Faster searches** (grep, IDE indexing)
4. **Clearer onboarding** for new developers
5. **Easier maintenance** (no need to keep copies in sync)
6. **Reduced storage** and faster git operations

---

**Estimated Cleanup Time**: 2-4 hours (mostly verification and testing)
**Risk Level**: LOW (exact duplicates with clear canonical sources)

---

## 📧 Questions?

Refer to:
- `REPO_SNAPSHOT.md` for detailed analysis
- `UNUSED_OR_DUPLICATE_REPORT.md` for execution steps
- `ACTIVE_INVENTORY.json` for programmatic queries

**Last Updated**: 2025-10-29
