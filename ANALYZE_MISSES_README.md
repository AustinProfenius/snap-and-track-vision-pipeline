# First 50 Dishes - Miss Analysis Tool

Comprehensive analysis tool for extracting and analyzing missed food matches from the First 50 Dishes test batch.

## Overview

This tool analyzes log files from the First 50 Dishes batch test to:
- Extract all missed food matches (stage0_no_candidates)
- Load telemetry data from individual run directories
- Identify patterns in missed foods
- Generate a consolidated JSON report with complete telemetry

## Quick Start

```bash
# Analyze the latest log file (default)
python analyze_first_50_misses.py

# Specify custom log file
python analyze_first_50_misses.py --log runs/first_50_custom.log

# Specify custom output file
python analyze_first_50_misses.py --output my_report.json
```

## Output

### Console Output
The script prints:
- Total dishes processed
- Total misses found
- Miss rate percentage
- Most common missed foods
- Misses by form (raw/cooked)
- Detailed list of all misses with telemetry

### JSON Report
Generated file: `first_50_misses_report.json`

Structure:
```json
{
  "metadata": {
    "log_file": "runs/first_50_latest.log",
    "total_dishes": 500,
    "dishes_with_misses": 171,
    "total_missed_foods": 201
  },
  "summary": {
    "miss_rate": "25.7%",
    "dishes_with_all_matches": 329,
    "dishes_with_some_misses": 171
  },
  "patterns": {
    "most_common_foods": {
      "cherry tomatoes": 50,
      "corn on the cob": 42,
      "deprecated": 31,
      ...
    },
    "misses_by_form": {
      "raw": 201
    }
  },
  "dishes_with_misses": [
    {
      "dish_id": "dish_1557861697",
      "runs_dir": "20251029_200049",
      "total_foods": 1,
      "missed_foods": 1,
      "stage_distribution": {...},
      "foods": [...]
    }
  ],
  "all_misses": [
    {
      "dish_id": "dish_1557861697",
      "food_name": "eggplant",
      "food_form": "raw",
      "stage": "stage0_no_candidates",
      "runs_dir": "20251029_200049",
      "telemetry": {
        "candidate_pool_size": 0,
        "foundation_pool_count": 0,
        "search_variants_tried": [],
        "attempted_stages": [...],
        ...
      },
      "full_dish_results": {...}
    }
  ]
}
```

## Report Structure

### metadata
- `log_file`: Path to analyzed log file
- `total_dishes`: Number of dishes processed
- `dishes_with_misses`: Number of dishes that had at least one miss
- `total_missed_foods`: Total count of missed food items

### summary
- `miss_rate`: Percentage of foods that couldn't be matched
- `dishes_with_all_matches`: Dishes with 100% match rate
- `dishes_with_some_misses`: Dishes with at least one miss

### patterns
- `most_common_foods`: Top 10 foods that failed to match
- `misses_by_form`: Breakdown by food form (raw/cooked)
- `patterns`: Common patterns (raw_form_miss, meat_miss, eggplant_miss)

### dishes_with_misses
Array of dishes that had misses, including:
- Dish ID and index
- Runs directory (for looking up telemetry files)
- Total foods and missed count
- Stage distribution
- Full food list with match status

### all_misses
Comprehensive array of every missed food with:
- Food name and form
- Dish context
- Alignment stage attempted
- **Full telemetry data** from JSONL files
- Complete dish results

## Telemetry Available

When telemetry is available (from runs/TIMESTAMP/ directories), each miss includes:

```json
{
  "candidate_pool_size": 0,
  "foundation_pool_count": 0,
  "search_variants_tried": ["cherry_tomato", "cherry tomatoes"],
  "attempted_stages": ["stage1b", "stage2", "stageZ_branded_fallback"],
  "negative_vocab_blocks": [],
  "sodium_gate_blocks": null,
  "atwater_ok": true,
  "method": "raw",
  "method_reason": "no_profile",
  "config_version": "configs@9c1be3db741d",
  "fdc_index_version": "fdc@unknown"
}
```

## Common Miss Patterns Found

From latest analysis:

1. **Cherry Tomatoes** (50 misses)
   - Stage: stage0_no_candidates
   - Issue: No Foundation/SR entries available
   - **Solution**: Add to Stage Z branded fallback config

2. **Corn on the Cob** (42 misses)
   - Stage: stage0_no_candidates
   - Issue: Specific form not in database
   - **Solution**: Add normalization rule or Stage Z entry

3. **Deprecated** (31 misses)
   - Stage: stage0_no_candidates
   - Issue: Invalid food label in ground truth
   - **Solution**: Clean up dataset metadata

4. **Spinach (raw)** (22 misses)
   - Stage: stage0_no_candidates
   - Issue: Duplicate "(raw)" in food name causing search failure
   - **Solution**: Fix name normalization

5. **Potatoes** (20 misses)
   - Stage: stage0_no_candidates
   - Issue: Generic name needs type specification
   - **Solution**: Add disambiguation or proxy rule

## Usage Examples

### Find all cherry tomato misses
```bash
python analyze_first_50_misses.py
cat first_50_misses_report.json | jq '.all_misses[] | select(.food_name == "cherry tomatoes")'
```

### Count misses by food name
```bash
cat first_50_misses_report.json | jq '.patterns.most_common_foods'
```

### Get dishes with multiple misses
```bash
cat first_50_misses_report.json | jq '.dishes_with_misses[] | select(.missed_foods > 2)'
```

### Extract telemetry for specific food
```bash
cat first_50_misses_report.json | jq '.all_misses[] | select(.food_name == "eggplant") | .telemetry'
```

## Integration with Stage Z Config

Use this report to identify candidates for Stage Z branded fallback:

1. **High frequency misses** (>10 occurrences) → Priority for Stage Z
2. **Common foods** (cherry tomatoes, corn) → Add to `stageZ_branded_fallbacks.yml`
3. **Check FDC database** for branded alternatives
4. **Add with plausibility guards** (kcal range validation)

Example workflow:
```bash
# Generate report
python analyze_first_50_misses.py

# Find top misses
cat first_50_misses_report.json | jq '.patterns.most_common_foods | to_entries | .[0:3]'

# Query FDC for cherry tomatoes
# Add to configs/stageZ_branded_fallbacks.yml

# Re-run test to validate
cd gpt5-context-delivery/entrypoints
python run_first_50_by_dish_id.py
```

## Troubleshooting

### "No telemetry available"
- The runs directory doesn't exist or was cleaned up
- Run the First 50 test again to generate fresh artifacts
- Telemetry is in `runs/TIMESTAMP/telemetry.jsonl`

### "Log file not found"
- Ensure you run from the project root
- Default path: `runs/first_50_latest.log`
- Specify custom path with `--log` flag

### KeyError in analysis
- Log format may have changed
- Check regex patterns in `parse_log_file()`
- Ensure log has `[N/50] Processing dish_...` format

## Future Enhancements

- [ ] Add automatic FDC query suggestions for misses
- [ ] Generate Stage Z config snippets from high-frequency misses
- [ ] Compare multiple test runs (before/after fixes)
- [ ] Export miss patterns to CSV for analysis
- [ ] Add visualization dashboard for miss patterns

## See Also

- `stageZ_branded_fallbacks.yml` - Stage Z configuration
- `run_first_50_by_dish_id.py` - Test runner
- `first_50_latest.log` - Latest test log
