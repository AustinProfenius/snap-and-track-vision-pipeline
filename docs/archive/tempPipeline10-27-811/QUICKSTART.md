# Quick Start Guide

**Goal**: Get the alignment pipeline running in 5 minutes

---

## Step 1: Environment Setup (2 min)

```bash
cd tempPipeline10-27-811

# Copy environment template
cp .env.template .env

# Edit .env and add your credentials:
# - NEON_CONNECTION_URL (required)
# - OPENAI_API_KEY (required)
nano .env  # or vim, VS Code, etc.
```

**Minimum Required in .env**:
```bash
NEON_CONNECTION_URL=postgresql://user:pass@host:5432/database
OPENAI_API_KEY=sk-proj-...
```

---

## Step 2: Install Dependencies (1 min)

```bash
pip install -r requirements.txt

# Or with virtual environment:
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## Step 3: Test Single Item (1 min)

```bash
cd entrypoints
python -c "
import sys
sys.path.insert(0, '../')

from alignment.alignment_adapter import AlignmentEngineAdapter

adapter = AlignmentEngineAdapter()
prediction = {
    'foods': [{
        'name': 'grapes',
        'form': 'raw',
        'mass_g': 100,
        'confidence': 0.85
    }]
}

result = adapter.align_prediction_batch(prediction)
food = result['foods'][0]

print(f'Name: {food[\"name\"]}')
print(f'Stage: {food[\"alignment_stage\"]}')
print(f'FDC Match: {food[\"fdc_name\"]}')
print(f'Variant: {food[\"telemetry\"][\"variant_chosen\"]}')
print(f'Score: {food[\"telemetry\"].get(\"stage1b_score\", \"N/A\")}')
"
```

**Expected Output**:
```
Name: grapes
Stage: stage1b_raw_foundation_direct
FDC Match: Grapes, red or green, raw
Variant: grapes raw
Score: 0.95
```

---

## Step 4: Run Batch Test (OPTIONAL - 10-30 min)

```bash
# Full 459-image evaluation (takes ~30 min)
cd entrypoints
python run_459_batch_evaluation.py

# Results saved to:
# ../telemetry/results/gpt_5_459images_<timestamp>.json
```

---

## Step 5: Verify Fixes (1 min)

Test the critical fixes from 2025-10-27:

```bash
python -c "
import sys
sys.path.insert(0, '../')
from alignment.alignment_adapter import AlignmentEngineAdapter

adapter = AlignmentEngineAdapter()

# Test 1: Grapes (should match, not stage0)
test_items = [
    ('grapes', 'raw'),
    ('almonds', 'raw'),
    ('cantaloupe', 'raw'),
    ('apple', 'raw')
]

for name, form in test_items:
    pred = {'foods': [{'name': name, 'form': form, 'mass_g': 100, 'confidence': 0.85}]}
    result = adapter.align_prediction_batch(pred)
    food = result['foods'][0]

    stage = food['alignment_stage']
    fdc_name = food['fdc_name']

    # Check for issues
    if stage == 'stage0_no_candidates':
        print(f'❌ {name}: NO MATCH (stage0)')
    elif 'strudel' in fdc_name.lower() or 'juice' in fdc_name.lower() or 'oil' in fdc_name.lower():
        print(f'❌ {name}: NEGATIVE LEAK ({fdc_name})')
    else:
        print(f'✅ {name}: {stage} - {fdc_name}')
"
```

**Expected Output**:
```
✅ grapes: stage1b_raw_foundation_direct - Grapes, red or green, raw
✅ almonds: stage1b_raw_foundation_direct - Almonds, raw
✅ cantaloupe: stage1b_raw_foundation_direct - Melons, cantaloupe, raw
✅ apple: stage1b_raw_foundation_direct - Apples, raw, with skin
```

---

## Troubleshooting

### Error: "Database connection URL not provided"

**Fix**: Set `NEON_CONNECTION_URL` in `.env`

```bash
export NEON_CONNECTION_URL="postgresql://..."
```

### Error: "No module named 'alignment'"

**Fix**: Run from correct directory

```bash
cd entrypoints
python -c "import sys; sys.path.insert(0, '../'); from alignment.alignment_adapter import AlignmentEngineAdapter"
```

### Error: "OpenAI API key not found"

**Fix**: Set `OPENAI_API_KEY` in `.env` (only needed for vision model)

```bash
export OPENAI_API_KEY="sk-proj-..."
```

### Grapes still showing stage0_no_candidates

**Check**:
1. Is `NEON_CONNECTION_URL` correct?
2. Run with verbose logging: `export ALIGN_VERBOSE=1`
3. Check FDC database has Foundation entries: `SELECT * FROM foods WHERE name ILIKE '%grape%' LIMIT 5;`

---

## Next Steps

1. ✅ Single-item test passed → **Pipeline is working**
2. ⏭️ Run full 459-image batch test to measure overall accuracy
3. ⏭️ Compare results with baseline (`telemetry/results/gpt_5_50images_20251026_204653.json`)
4. ⏭️ Integrate with web app (see `README.md` section 8)

---

## Key Files

- **Main Engine**: `alignment/align_convert.py`
- **Web Interface**: `alignment/alignment_adapter.py`
- **Config**: `configs/*.yml`
- **Results**: `telemetry/results/*.json`
- **Docs**: `README.md`, `INVENTORY.md`, `MANIFEST.md`

---

## Performance Expectations

| Test Type | Time | Items | Purpose |
|-----------|------|-------|---------|
| Single-item | <1s | 1 | Quick validation |
| 10-image | ~1 min | 30-50 | Smoke test |
| 50-image | ~5 min | 150-200 | Regression test |
| 459-image | ~30 min | 1200-1500 | Full evaluation |

---

## Success Criteria

After running tests, verify:

- [ ] Grapes: **stage1b_raw_foundation_direct** (not stage0)
- [ ] Almonds: **stage1b_raw_foundation_direct** (not stage0)
- [ ] Cantaloupe: **stage1b_raw_foundation_direct** (not stage0)
- [ ] Apple: **No "strudel/pie/juice"** in FDC name
- [ ] Stage-Z produce count: **0** (fruits/nuts/vegetables never use Stage-Z)
- [ ] Overall stage0 rate: **<10%** (down from ~25% baseline)

---

## Getting Help

1. **Check Logs**: Set `ALIGN_VERBOSE=1` for detailed stage decisions
2. **Review Telemetry**: Inspect JSON results for `alignment_stage`, `variant_chosen`, `foundation_pool_count`
3. **Read Docs**: See `README.md` for complete guide
4. **Check Fixes**: See `STAGE1B_FIXES_COMPLETE.md` for what changed

**Issues**: Review `INVENTORY.md` section 10 for known issues and TODOs
