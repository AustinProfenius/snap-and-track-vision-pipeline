# PR: P0+P1 Safety Rails & Produce Alignment Gaps

## Summary

Implements **P0 (safety rails)** and **P1 (produce gap fixes)** from the 50-image batch analysis, addressing critical accuracy regressions for eggs, broccoli, and produce classes while adding observability for deterministic debugging.

## P0: Safety & Observability

### Config Load Contract
- **Fail-fast in pipeline mode** (raises FileNotFoundError if configs missing)
- **Graceful error in web app** (returns `{"available": false, "error": "config_load_failed"}`)
- **Config version stamping** in all telemetry (e.g., `configs@a65cd030a277`)

### Stage2 Seed Guardrail
- **Validates seeds are Foundation raw only** (never cooked/processed)
- **Blocks bad seeds**: fast foods, pancakes, crackers, ice cream, pastry, soup, babyfood
- **Telemetry**: `stage2_seed_guardrail: {status, reason}`

### Stage1b Transparency
- **Returns telemetry**: candidate_pool_size, best_candidate_name, best_candidate_id, best_score, threshold
- **Sentinel flag**: `stage1b_dropped_despite_pool` detects logic bugs (pool>0 but stage0)

### Stage1c Telemetry IDs
- **Ensures from_id and to_id** populated in all stage1c switches
- **Full FDC traceability** for raw-first preference swaps

## P1: Produce Alignment Gaps

### Variants Added (38 new variants)
- **Cherry tomatoes**: 5 variants
- **Grape tomatoes**: 5 variants
- **Mushrooms**: 8 variants
- **Green beans**: 7 variants

### Category Allowlist Enhanced
- **Added rules** for tomatoes_cherry, mushrooms, green_beans
- **Prefer fresh/Foundation** entries
- **Penalize processed** (canned, soup, baby food)

### Class-Conditional Penalties
- **-0.35 penalty for dessert/pastry in produce queries**
- **Kills leakage**: apple→croissant, strawberry→ice cream, cherry→pie

## Testing & Tools

### Unit Tests (130 lines)
- test_produce_alignment_not_stage0
- test_produce_no_dessert_leakage
- test_stage2_seed_guardrail
- test_stage1c_telemetry_ids
- test_config_version_stamped

### Batch Diagnostics Script (60 lines)
- One-command diagnostics: `./scripts/diagnose_batch.sh <batch_json>`

## Files Changed

| File | Lines |
|------|-------|
| `nutritionverse-tests/src/adapters/alignment_adapter.py` | +50 |
| `nutritionverse-tests/src/nutrition/alignment/align_convert.py` | +80 |
| `configs/variants.yml` | +38 |
| `configs/category_allowlist.yml` | +38 |
| `nutritionverse-tests/tests/test_produce_alignment.py` | +130 |
| `scripts/diagnose_batch.sh` | +60 |

**Total:** 6 files, 396 lines

## Validation Commands

```bash
# Run unit tests
cd nutritionverse-tests
pytest tests/test_produce_alignment.py -v

# Run 50-batch test
cd gpt5-context-delivery/entrypoints
export PIPELINE_MODE=true
python run_first_50_by_dish_id.py

# Run diagnostics
./scripts/diagnose_batch.sh runs/<timestamp>/telemetry.jsonl
```

---

**Ready for review and validation testing.**
