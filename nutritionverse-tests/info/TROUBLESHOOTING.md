# Troubleshooting Guide

Common issues and solutions for the NutritionVerse API Test Harness.

## Streamlit UI Issues

### Error: "The value 0 is greater than the max_value -1"

**Cause**: Dataset directory is empty or schema map doesn't exist.

**Solution**:
1. Ensure NutritionVerse-Real data is in `data/nvreal/`
2. Run schema discovery:
   ```bash
   python -m src.core.loader --data-dir data/nvreal --inspect
   ```
3. Restart Streamlit app

**Workaround**: The UI now handles this gracefully with a setup guide. Refresh the page after fixing.

### UI won't start

**Check dependencies**:
```bash
pip install streamlit plotly pandas
```

**Check if port is in use**:
```bash
# Streamlit defaults to port 8501
lsof -ti:8501  # macOS/Linux
# Kill if needed: kill -9 $(lsof -ti:8501)
```

**Run with explicit port**:
```bash
streamlit run src/ui/app.py --server.port 8502
```

## Dataset Issues

### "No annotation files found"

**Cause**: Dataset not in correct location or wrong file format.

**Solution**:
1. Verify directory structure:
   ```
   data/nvreal/
     ├── images/ (or in same dir as annotations)
     └── annotations/ (or *.json files)
   ```
2. Check file extensions (must be `.json`)
3. Test with sample:
   ```bash
   ls data/nvreal/**/*.json | head -5
   ```

### Schema discovery fails

**Cause**: JSON annotations are malformed or inconsistent.

**Solution**:
1. Validate one annotation manually:
   ```bash
   python -c "import json; print(json.load(open('data/nvreal/annotations/dish_001.json')))"
   ```
2. Check for consistent field names across samples
3. If format is non-standard, manually edit `configs/schema_map.yaml`

### "Schema map not found"

**Cause**: Haven't run schema discovery yet.

**Solution**:
```bash
python -m src.core.loader --data-dir data/nvreal --inspect
```

This creates `configs/schema_map.yaml`.

## API Issues

### "OPENAI_API_KEY environment variable not set"

**Solution**:
1. Create `.env` file:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and add your key:
   ```
   OPENAI_API_KEY=sk-...
   ```
3. Verify:
   ```bash
   cat .env | grep OPENAI_API_KEY
   ```

### Rate limit errors from API

**Symptoms**: "RateLimitError" or 429 status codes

**Solution**:
1. Reduce request rate:
   ```bash
   --rps 0.1  # 1 request every 10 seconds
   ```
2. Check your API tier limits
3. Add delays between runs
4. Use multiple API keys (requires code modification)

### "JSON parse error" or malformed responses

**Cause**: Model returned non-JSON or invalid JSON.

**Built-in fixes**:
- Auto-extracts JSON from markdown code blocks
- Finds JSON object boundaries in text
- Falls back to regex extraction

**Manual fix**:
If errors persist, add `--keep-raw` flag (when implemented) to save raw responses for debugging.

## Runner Issues

### "Checkpoint not found" when resuming

**Cause**: Run ID mismatch or checkpoint was deleted.

**Solution**:
1. List available checkpoints:
   ```bash
   ls runs/results/*_checkpoint.json
   ```
2. Use exact API and task names from original run
3. If checkpoint is corrupt, start fresh without `--resume`

### Budget exceeded before completion

**Expected behavior**: Runner stops gracefully and saves progress.

**To continue**:
1. Increase budget:
   ```bash
   --max-cost 20.00  # Higher limit
   ```
2. Or resume from checkpoint with new budget allocation

### "No items to process"

**Cause**: Index range is invalid or IDs file is empty.

**Solution**:
1. Check dataset size:
   ```bash
   python -m src.core.loader --stats
   ```
2. Verify index range:
   ```bash
   --start 0 --end 10  # Must be < dataset size
   ```
3. If using `--ids-file`, check it's not empty:
   ```bash
   cat ids.txt
   ```

## Import Errors

### "ModuleNotFoundError: No module named 'openai'"

**Solution**:
```bash
pip install -r requirements.txt
```

### "ImportError: cannot import name 'OpenAIAdapter'"

**Cause**: Python path issue or missing `__init__.py`

**Solution**:
1. Run from project root:
   ```bash
   cd nutritionverse-tests
   python -m src.core.runner ...
   ```
2. Verify `__init__.py` files exist:
   ```bash
   ls src/__init__.py src/adapters/__init__.py src/core/__init__.py
   ```

## Performance Issues

### Runner is very slow

**Cause**: Default rate limiting or network latency.

**Solution**:
1. Increase RPS (if API allows):
   ```bash
   --rps 2.0  # 2 requests/second
   ```
2. Use faster/cheaper models:
   - Gemini 1.5 Flash (fastest)
   - GPT-4o-mini (fast, cheap)
3. Reduce retry attempts:
   ```bash
   --max-retries 1
   ```

### Out of memory

**Cause**: Large dataset or keeping too many results in memory.

**Solution**:
1. Process in smaller batches:
   ```bash
   --limit 50
   ```
2. Export results after each run:
   ```bash
   python scripts/export_results.py {run_id} --format parquet
   ```
3. Clean up old results:
   ```bash
   rm runs/results/*.jsonl  # Keep only summaries
   ```

## Export Issues

### Parquet export fails

**Cause**: Missing `pyarrow` dependency.

**Solution**:
```bash
pip install pyarrow
```

### Excel export not working

**Cause**: Missing `openpyxl` dependency.

**Solution**:
```bash
pip install openpyxl
```

Then:
```bash
python scripts/export_results.py {run_id} --format excel
```

## Verification

### Run full verification

```bash
python scripts/verify_setup.py
```

This checks:
- Directory structure
- Configuration files
- Python dependencies
- Dataset presence
- API keys

## Getting Help

1. **Check logs**:
   ```bash
   ls runs/logs/
   ```

2. **Enable verbose output** (add to runner.py if needed):
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

3. **Dry run to test config**:
   ```bash
   python -m src.core.runner --dry-run --api openai --task dish_totals --end 5
   ```

4. **Test single sample manually**:
   ```python
   # test_single.py
   import asyncio
   from pathlib import Path
   from src.adapters import OpenAIAdapter
   from src.core.prompts import build_user_prompt

   async def test():
       adapter = OpenAIAdapter()
       prompt = build_user_prompt("dish_totals")
       result = await adapter.infer(
           Path("data/nvreal/images/dish_001.jpg"),
           prompt
       )
       print(result)

   asyncio.run(test())
   ```

## Still Having Issues?

1. Check if it's a known issue in GitHub
2. Run verification script: `python scripts/verify_setup.py`
3. Try minimal example from QUICKSTART.md
4. Check API status pages (OpenAI, Anthropic, Google)

## Common Warnings (Safe to Ignore)

- `missing ScriptRunContext` - When importing Streamlit outside of `streamlit run`
- `Session state does not function` - Same as above
- `FutureWarning` from pandas - Deprecated API usage (non-breaking)
