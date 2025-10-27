# NutritionVerse-Real API Test Harness

A comprehensive evaluation framework for testing vision-language models on nutrition estimation tasks using the NutritionVerse-Real dataset.

## Features

- **Multi-API Support**: OpenAI GPT-4o, Claude 3.7, Gemini 1.5, and local Ollama models
- **Flexible Evaluation**: Three task modes (totals, itemized, names)
- **Controllable Usage**: Index slicing, resumable runs, rate limiting, and budget caps
- **Comprehensive Metrics**: MAE, MAPE, Jaccard similarity, precision/recall
- **Rich UI**: Streamlit dashboard for run management and visualization
- **Production-Ready**: Checkpointing, retry logic, cost tracking

## Quick Start

### 1. Installation

```bash
cd nutritionverse-tests
pip install -r requirements.txt
```

### 2. Dataset Setup

Place the NutritionVerse-Real dataset in `data/nvreal/`:

```
data/nvreal/
  images/
    dish_001.jpg
    dish_002.jpg
    ...
  annotations/
    dish_001.json
    dish_002.json
    ...
```

### 3. Configuration

Copy `.env.example` to `.env` and add your API keys:

```bash
cp .env.example .env
# Edit .env and add your keys
```

### 4. Schema Discovery

Run schema discovery to map the dataset format:

```bash
python -m src.core.loader --data-dir data/nvreal --inspect
```

This generates `configs/schema_map.yaml`. Review and adjust if needed.

### 5. Verify Setup

Check dataset statistics:

```bash
python -m src.core.loader --data-dir data/nvreal --stats
```

## Usage

### Command-Line Interface

#### Basic Run (First 20 samples)

```bash
python -m src.core.runner \
  --api openai \
  --task dish_totals \
  --start 0 \
  --end 20 \
  --rps 0.5 \
  --max-cost 1.00
```

#### Dry Run (Preview)

```bash
python -m src.core.runner \
  --api openai \
  --task itemized \
  --start 0 \
  --end 100 \
  --dry-run
```

#### Resume from Checkpoint

```bash
python -m src.core.runner \
  --api claude \
  --task itemized \
  --start 0 \
  --end 200 \
  --resume \
  --rps 0.2
```

#### Use Specific IDs

Create a file `ids.txt` with dish IDs (one per line):

```
dish_001
dish_042
dish_123
```

Then run:

```bash
python -m src.core.runner \
  --api gemini \
  --task names_only \
  --ids-file ids.txt \
  --rps 1.0
```

### Streamlit UI

Launch the interactive dashboard:

```bash
streamlit run src/ui/app.py
```

Features:
- Configure and launch runs
- Browse results
- Interactive visualizations (calibration plots, error distributions)
- Export results to CSV

## Configuration

### APIs (`configs/apis.yaml`)

Enable/disable APIs and configure model settings:

```yaml
apis:
  openai:
    enabled: true
    default_model: gpt-4o-mini
    models:
      gpt-4o-mini:
        temperature: 0.0
        max_tokens: 2048
        supports_json_mode: true
```

### Tasks (`configs/tasks.yaml`)

Define evaluation tasks:

```yaml
tasks:
  dish_totals:
    description: "Estimate overall calories and macros"
    prompt_template: dish_totals
    evaluate_fields:
      - totals.calories_kcal
      - totals.macros_g.protein
```

### Schema Map (`configs/schema_map.yaml`)

Auto-generated mapping from dataset to uniform schema. Review after running `--inspect`.

## Evaluation Metrics

### Numerical Metrics
- **MAE** (Mean Absolute Error): Average absolute difference
- **MAPE** (Mean Absolute Percentage Error): Error as % of true value
- **RMSE** (Root Mean Squared Error): Penalizes large errors

### Categorical Metrics
- **Jaccard Similarity**: Overlap between predicted and true food names
- **Precision/Recall**: Classification performance for food identification

### Coverage
- Success rate (% samples with valid predictions)
- Error rate

## Project Structure

```
nutritionverse-tests/
├── data/nvreal/              # Dataset (not included)
├── configs/
│   ├── apis.yaml            # API configurations
│   ├── tasks.yaml           # Task definitions
│   └── schema_map.yaml      # Dataset schema mapping (auto-generated)
├── runs/
│   ├── logs/                # Per-run logs
│   └── results/             # JSONL/Parquet results + summaries
├── src/
│   ├── adapters/            # API backend adapters
│   │   ├── openai_.py
│   │   ├── claude_.py
│   │   ├── gemini_.py
│   │   └── ollama_llava.py
│   ├── core/
│   │   ├── loader.py        # Dataset loading + slicing
│   │   ├── schema.py        # Schema discovery + mapping
│   │   ├── prompts.py       # Prompt templates
│   │   ├── evaluator.py     # Metrics computation
│   │   ├── runner.py        # Main evaluation loop
│   │   └── store.py         # Result storage + checkpointing
│   └── ui/
│       └── app.py           # Streamlit dashboard
├── .env.example             # Template for API keys
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Output Files

Each run produces:

1. **Results JSONL** (`runs/results/{run_id}.jsonl`)
   - Per-sample predictions, ground truth, and metrics
   - Append-only for streaming writes

2. **Summary JSON** (`runs/results/{run_id}_summary.json`)
   - Aggregate metrics across all samples
   - Total cost, success rate, etc.

3. **Checkpoint JSON** (`runs/results/{run_id}_checkpoint.json`)
   - Last completed index
   - Cost tracker state
   - For resumable runs

## Advanced Features

### Rate Limiting

Control API request rate to avoid throttling:

```bash
--rps 0.5  # 1 request every 2 seconds
```

### Budget Caps

Stop automatically when reaching a cost limit:

```bash
--max-cost 10.00  # Stop after $10
```

### Retry Logic

Automatic retries with exponential backoff:

```bash
--max-retries 3  # Try up to 3 times per sample
```

### Index Slicing

Process any subset:

```bash
--start 100 --end 200  # Indices 100-199
--limit 50             # First 50 samples in range
```

### JSON Repair

Automatically attempts to fix malformed JSON responses:
- Extracts from markdown code blocks
- Finds JSON object boundaries
- Re-parses with lenient settings

## Example Workflows

### Smoke Test (Quick validation)

```bash
python -m src.core.runner \
  --api openai \
  --task dish_totals \
  --start 0 \
  --end 5 \
  --rps 1.0 \
  --max-cost 0.50
```

### Full Evaluation (Compare APIs)

Run three APIs on same data:

```bash
# OpenAI
python -m src.core.runner --api openai --task itemized --start 0 --end 100 --rps 0.5

# Claude
python -m src.core.runner --api claude --task itemized --start 0 --end 100 --rps 0.2

# Gemini
python -m src.core.runner --api gemini --task itemized --start 0 --end 100 --rps 1.0
```

Then compare in the UI.

### Long-Running Evaluation (Resumable)

```bash
# Start
python -m src.core.runner \
  --api openai \
  --task itemized \
  --start 0 \
  --end 1000 \
  --rps 0.5 \
  --max-cost 50.00

# If interrupted, resume:
python -m src.core.runner \
  --api openai \
  --task itemized \
  --start 0 \
  --end 1000 \
  --resume
```

## Cost Estimation

Approximate costs per 100 images (as of Jan 2025):

| API | Model | Cost (100 images) |
|-----|-------|-------------------|
| OpenAI | gpt-4o-mini | $0.50 - $1.00 |
| OpenAI | gpt-4o | $3.00 - $6.00 |
| Claude | claude-3-5-sonnet | $2.00 - $4.00 |
| Gemini | gemini-1.5-flash | $0.10 - $0.30 |
| Ollama | llava (local) | $0.00 |

*Estimates vary based on prompt length and response verbosity.*

## Troubleshooting

### Schema Discovery Fails

Ensure annotations are valid JSON and follow a consistent structure. Check a few manually first.

### API Key Errors

Verify `.env` file exists and contains valid keys:

```bash
cat .env
```

### Out of Memory

Process in smaller batches:

```bash
--limit 50
```

Or use Parquet export for large results:

```python
from src.core.store import ResultStore
store = ResultStore(Path("runs/results"))
store.jsonl_path = Path("runs/results/{run_id}.jsonl")
store.to_parquet()
```

### Rate Limit Errors

Reduce RPS:

```bash
--rps 0.1  # 1 request every 10 seconds
```

## Future Enhancements

- [ ] Stratified sampling by calorie range or dish type
- [ ] USDA food database integration for synonym mapping
- [ ] Ensemble voting across multiple APIs
- [ ] GPU-accelerated local baselines (LLaVA-Next, etc.)
- [ ] IoU metrics for segmentation tasks
- [ ] Multi-language support for food names

## License

MIT License - see LICENSE file

## Citation

If you use this test harness in your research, please cite:

```bibtex
@software{nutritionverse_harness,
  title={NutritionVerse-Real API Test Harness},
  author={Your Name},
  year={2025},
  url={https://github.com/yourusername/nutritionverse-tests}
}
```

## Contributing

Contributions welcome! Please open an issue or PR.
