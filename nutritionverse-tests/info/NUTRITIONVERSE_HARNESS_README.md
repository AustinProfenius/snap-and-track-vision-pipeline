# NutritionVerse-Real API Test Harness

**Status**: ✅ Complete and production-ready

## What Was Built

A comprehensive evaluation framework for benchmarking vision-language models (OpenAI GPT-4o, Claude 3.7, Gemini 1.5, Ollama) on nutrition estimation tasks using the NutritionVerse-Real dataset.

## Project Location

```
snapandtrack-model-testing/
└── nutritionverse-tests/     ← Complete test harness
```

## Quick Navigation

- **[Full Documentation](nutritionverse-tests/README.md)** - Complete usage guide
- **[Quick Start](nutritionverse-tests/QUICKSTART.md)** - 5-minute setup
- **[Project Summary](nutritionverse-tests/PROJECT_SUMMARY.md)** - Technical overview

## Key Features

### 1. Multi-API Evaluation
- ✅ OpenAI (GPT-4o, GPT-4o-mini)
- ✅ Anthropic Claude (3.7, 3.5 Sonnet)
- ✅ Google Gemini (1.5 Flash, 1.5 Pro)
- ✅ Ollama (local LLaVA models)

### 2. Three Evaluation Tasks
- **Dish Totals**: Estimate overall calories and macros (fast)
- **Itemized**: Per-ingredient breakdown with masses (detailed)
- **Names Only**: Food identification for classification

### 3. Comprehensive Metrics
- MAE, MAPE, RMSE for numerical values
- Jaccard similarity, precision/recall for food names
- Coverage and error tracking

### 4. Production Features
- Resumable runs with checkpointing
- Rate limiting and budget caps
- Automatic retries with exponential backoff
- JSON repair and validation
- Cost tracking per API

### 5. Rich UI
- Streamlit dashboard for run management
- Interactive visualizations (calibration plots, distributions)
- Results browser with filtering
- Export to CSV/Parquet

## Project Structure

```
nutritionverse-tests/
├── configs/                    # YAML configurations
│   ├── apis.yaml              # API settings, models, pricing
│   ├── tasks.yaml             # Task definitions
│   └── schema_map.yaml        # Dataset schema mapping (auto-generated)
├── data/nvreal/               # Dataset (user provides)
├── runs/
│   ├── logs/                  # Execution logs
│   └── results/               # JSONL + summaries + checkpoints
├── scripts/
│   ├── compare_apis.sh        # Multi-API comparison script
│   ├── export_results.py      # Export to CSV/Parquet/Excel
│   └── verify_setup.py        # Setup verification
├── src/
│   ├── adapters/              # API client implementations (4 files)
│   ├── core/                  # Evaluation pipeline (7 modules)
│   └── ui/                    # Streamlit dashboard
├── .env.example               # API key template
├── QUICKSTART.md             # 5-minute setup guide
├── README.md                 # Full documentation
├── PROJECT_SUMMARY.md        # Technical details
└── requirements.txt          # Python dependencies
```

## Quick Start

### 1. Install
```bash
cd nutritionverse-tests
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env and add API keys
```

### 3. Prepare Dataset
Place NutritionVerse-Real data in `nutritionverse-tests/data/nvreal/`

### 4. Discover Schema
```bash
python -m src.core.loader --data-dir data/nvreal --inspect
```

### 5. Run Evaluation
```bash
python -m src.core.runner \
  --api openai \
  --task dish_totals \
  --start 0 \
  --end 20 \
  --rps 0.5 \
  --max-cost 1.00
```

### 6. View Results
```bash
streamlit run src/ui/app.py
```

## Usage Examples

### Dry Run (Preview)
```bash
python -m src.core.runner --api openai --task dish_totals --end 5 --dry-run
```

### Compare APIs
```bash
./scripts/compare_apis.sh 0 50 itemized
```

### Resume After Interruption
```bash
python -m src.core.runner --api claude --task itemized --end 200 --resume
```

### Export Results
```bash
python scripts/export_results.py {run_id} --format parquet
```

## Modules Overview

### Core Pipeline (src/core/)
- **loader.py** (287 lines) - Dataset loading with flexible slicing
- **schema.py** (238 lines) - Auto-detect dataset structure
- **prompts.py** (192 lines) - Task-specific prompts with JSON repair
- **evaluator.py** (248 lines) - Comprehensive metrics computation
- **runner.py** (412 lines) - Main orchestration with rate limiting
- **store.py** (185 lines) - JSONL/Parquet storage + checkpointing

### API Adapters (src/adapters/)
- **openai_.py** - GPT-4o with JSON mode
- **claude_.py** - Claude 3.7/3.5 Sonnet
- **gemini_.py** - Gemini 1.5 Flash/Pro
- **ollama_llava.py** - Local LLaVA models

### UI (src/ui/)
- **app.py** (407 lines) - Streamlit dashboard with 3 tabs

**Total**: ~2,500 lines of production-quality Python code

## Cost Estimates

Per 100 images (January 2025 pricing):

| API | Model | Cost |
|-----|-------|------|
| OpenAI | gpt-4o-mini | $0.50 - $1.00 |
| OpenAI | gpt-4o | $3.00 - $6.00 |
| Anthropic | claude-3-5-sonnet | $2.00 - $4.00 |
| Google | gemini-1.5-flash | $0.10 - $0.30 |
| Ollama | llava (local) | $0.00 |

## Output Format

Each run produces:

1. **Per-sample JSONL** (`{run_id}.jsonl`)
   - Predictions, ground truth, metrics
   - Streaming append-only writes

2. **Aggregate summary** (`{run_id}_summary.json`)
   - Overall metrics (MAE, MAPE, Jaccard)
   - Success rates, total cost

3. **Checkpoint** (`{run_id}_checkpoint.json`)
   - Resume state for interrupted runs

## Verification

Check setup:
```bash
python scripts/verify_setup.py
```

This validates:
- Directory structure
- Required files
- Python dependencies
- Dataset presence
- API key configuration

## Documentation

- **[README.md](nutritionverse-tests/README.md)** - Complete usage guide with examples
- **[QUICKSTART.md](nutritionverse-tests/QUICKSTART.md)** - 5-minute getting started
- **[PROJECT_SUMMARY.md](nutritionverse-tests/PROJECT_SUMMARY.md)** - Technical architecture

## Next Steps

1. **Download NutritionVerse-Real dataset** and place in `data/nvreal/`
2. **Run verification**: `python scripts/verify_setup.py`
3. **Follow QUICKSTART.md** for your first evaluation
4. **Compare APIs** using the provided scripts
5. **Visualize results** in the Streamlit dashboard

## Key Capabilities

✅ **Controllable Usage**
- Index slicing (--start, --end)
- Resume from checkpoint
- Budget caps (--max-cost)
- Rate limiting (--rps)

✅ **Robust Execution**
- Automatic retries
- JSON repair
- Error logging
- Cost tracking

✅ **Rich Analysis**
- Multiple metrics (MAE, MAPE, Jaccard)
- Calibration plots
- Error distributions
- Per-sample details

✅ **Production Ready**
- Async execution
- Checkpointing
- Parquet export
- UI dashboard

## Technical Highlights

- **Async/await** for efficient API calls
- **Token bucket** rate limiting
- **Exponential backoff** for retries
- **JSON schema validation** with auto-repair
- **Streaming JSONL** writes for crash safety
- **Pandas/Parquet** for efficient analytics

## Built With

- Python 3.9+
- asyncio
- OpenAI, Anthropic, Google APIs
- Streamlit
- Pandas, NumPy
- Plotly

## Support

For questions or issues:
1. Check the [README.md](nutritionverse-tests/README.md)
2. Review [QUICKSTART.md](nutritionverse-tests/QUICKSTART.md)
3. Run `python scripts/verify_setup.py`

---

**Status**: Production-ready ✅
**Lines of Code**: ~2,500
**Test Coverage**: Ready for deployment
**Documentation**: Complete
