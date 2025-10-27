# Quick Start Guide

Get up and running with the NutritionVerse API Test Harness in 5 minutes.

## Prerequisites

- Python 3.9+
- At least one API key (OpenAI, Anthropic, or Google)
- NutritionVerse-Real dataset

## Step 1: Install Dependencies

```bash
cd nutritionverse-tests
pip install -r requirements.txt
```

## Step 2: Set Up Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your API keys
nano .env  # or use your preferred editor
```

Add your keys:
```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
```

## Step 3: Prepare Dataset

Place your NutritionVerse-Real data in `data/nvreal/`:

```
data/nvreal/
  ├── images/
  │   ├── dish_001.jpg
  │   └── ...
  └── annotations/
      ├── dish_001.json
      └── ...
```

## Step 4: Run Schema Discovery

```bash
python -m src.core.loader --data-dir data/nvreal --inspect
```

This creates `configs/schema_map.yaml`. The tool will automatically detect field names like:
- Image paths
- Food ingredient lists
- Nutritional values (calories, protein, carbs, fat)

Review the generated file to ensure correct mapping.

## Step 5: Verify Setup

Check that the dataset loaded correctly:

```bash
python -m src.core.loader --data-dir data/nvreal --stats
```

You should see statistics like:
```
Dataset Statistics (data/nvreal):
Total samples: 245

Calories (kcal):
  Mean: 520.3
  Median: 485.0
  Range: [120.0, 1250.0]
...
```

## Step 6: Run Your First Evaluation

**Dry run** (preview without API calls):
```bash
python -m src.core.runner \
  --api openai \
  --task dish_totals \
  --start 0 \
  --end 5 \
  --dry-run
```

**Real run** (first 5 samples):
```bash
python -m src.core.runner \
  --api openai \
  --task dish_totals \
  --start 0 \
  --end 5 \
  --rps 0.5 \
  --max-cost 0.50
```

Expected output:
```
Evaluation Configuration:
  API: openai
  Task: dish_totals
  Samples: 5
  Range: 0 to 4
  Rate limit: 0.5 req/s
  Budget cap: $0.50

Processing 5 items...

[1/5] Processing dish_001 (index 0)
  Image: dish_001.jpg
  Success! Cost: $0.0234, Total: $0.0234
  Calories MAE: 45.2 kcal
...
```

## Step 7: View Results

### Option A: Command-line

Results are saved to:
- `runs/results/{run_id}.jsonl` - Per-sample results
- `runs/results/{run_id}_summary.json` - Aggregate metrics

View summary:
```bash
cat runs/results/*_summary.json | jq
```

### Option B: Streamlit UI

Launch the dashboard:
```bash
streamlit run src/ui/app.py
```

Navigate to http://localhost:8501 and:
1. Select your run from the "Results" tab
2. View metrics and per-sample results
3. Create visualizations in the "Analysis" tab

## Next Steps

### Compare Multiple APIs

```bash
# OpenAI
python -m src.core.runner --api openai --task itemized --start 0 --end 20

# Claude
python -m src.core.runner --api claude --task itemized --start 0 --end 20

# Gemini
python -m src.core.runner --api gemini --task itemized --start 0 --end 20
```

Then compare results in the UI.

### Try Different Tasks

```bash
# Dish totals only (faster, cheaper)
python -m src.core.runner --api openai --task dish_totals --start 0 --end 50

# Itemized (per-ingredient breakdown)
python -m src.core.runner --api openai --task itemized --start 0 --end 50

# Names only (food identification)
python -m src.core.runner --api openai --task names_only --start 0 --end 50
```

### Process Larger Batches

```bash
# 100 samples with resume support
python -m src.core.runner \
  --api openai \
  --task itemized \
  --start 0 \
  --end 100 \
  --rps 0.5 \
  --max-cost 10.00 \
  --resume
```

If interrupted, re-run with `--resume` to continue from last checkpoint.

## Common Issues

### "OPENAI_API_KEY environment variable not set"
- Ensure `.env` file exists in the project root
- Check that keys are on the right lines (no extra spaces)

### "No annotation files found"
- Verify dataset path is correct (`data/nvreal/`)
- Annotations should be JSON files (`.json`)

### "Schema map not found"
- Run schema discovery first: `python -m src.core.loader --inspect`

### Rate limit errors
- Reduce `--rps` (e.g., `--rps 0.2` for 1 request every 5 seconds)
- Check your API tier limits

## Tips

1. **Start small**: Use `--end 5` for initial testing
2. **Set budget caps**: Always use `--max-cost` to avoid surprises
3. **Use dry runs**: Test configuration with `--dry-run` first
4. **Enable resume**: Add `--resume` for runs over 50 samples
5. **Monitor costs**: Check `_summary.json` after each run

## Example Workflows

### Quick validation (5 samples, <$0.50)
```bash
python -m src.core.runner --api openai --task dish_totals --end 5 --max-cost 0.50
```

### Production run (500 samples, resume support)
```bash
python -m src.core.runner \
  --api openai \
  --task itemized \
  --start 0 \
  --end 500 \
  --rps 0.5 \
  --max-cost 50.00 \
  --resume \
  --max-retries 3
```

### Custom subset (specific dish IDs)
```bash
# Create ids.txt with dish IDs
echo "dish_001\ndish_015\ndish_042" > ids.txt

python -m src.core.runner --api gemini --task itemized --ids-file ids.txt
```

Ready to evaluate! See [README.md](README.md) for full documentation.
