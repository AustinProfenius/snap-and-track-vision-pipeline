# Snap & Track Vision Pipeline

Unified nutrition alignment pipeline for the Snap & Track mobile application.

## Quick Start

```bash
# Install dependencies
pip install -r nutritionverse-tests/requirements.txt

# Set up environment (requires NEON_CONNECTION_URL)
cp .env.example .env
# Edit .env and add your credentials

# Run first-50 test
bash scripts/run_first_50.sh

# Check stage1c telemetry
bash scripts/grep_stage1c.sh
```

## Repository Structure

```
/
├─ nutritionverse-tests/          # Canonical source (engine + tests)
│  ├─ src/
│  │  ├─ nutrition/              # Alignment stages (1b/1c/5B/Z)
│  │  ├─ adapters/               # Pipeline adapters
│  │  └─ core/                   # Vision detection
│  ├─ entrypoints/               # Batch runners (first-50, 459-batch)
│  └─ tests/                     # Unit & integration tests
│
├─ pipeline/                      # Unified orchestrator
│  ├─ run.py                     # Main pipeline entry point
│  ├─ config_loader.py           # Config management
│  ├─ schemas.py                 # Pydantic schemas
│  └─ fdc_index.py               # FDC database loader
│
├─ configs/                       # Production configs (single source of truth)
│  ├─ negative_vocabulary.yml
│  ├─ class_thresholds.yml
│  ├─ variants.yml
│  └─ ... (see pipeline.md for full list)
│
├─ scripts/                       # Utility scripts
│  ├─ run_first_50.sh            # Run first-50 batch test
│  └─ grep_stage1c.sh            # Search stage1c telemetry
│
├─ runs/                          # Per-run artifacts (ignored by git)
│  └─ <timestamp>/
│     ├─ results.jsonl
│     └─ telemetry.jsonl
│
├─ docs/                          # Documentation
│  ├─ REPO_SNAPSHOT.md           # Repository census
│  ├─ ACTIVE_INVENTORY.json      # Machine-readable manifest
│  ├─ pipeline.md                # Pipeline stages & configs
│  └─ archive/                   # Archived legacy code
│
└─ tools/                         # Analysis tools
   └─ scan_repo.py               # Repository scanner
```

## Key Components

### Pipeline Stages

- **Stage 1b**: Raw foundation food direct match
- **Stage 1c**: Raw-first preference (with guardrails)
- **Stage 2**: Simple semantic → Foundation
- **Stage 5B**: Proxy alignment fallback
- **Stage Z**: Branded fallback (disabled in evaluations)

See [docs/pipeline.md](docs/pipeline.md) for detailed stage documentation.

### Entrypoints

All batch runners live in `nutritionverse-tests/entrypoints/`:

- `run_first_50_by_dish_id.py` - First 50 dishes sorted by ID
- `run_459_batch_evaluation.py` - Full 459-dish evaluation

### Telemetry

Per-food telemetry is written to `runs/<timestamp>/telemetry.jsonl` with:

- Alignment stage used
- FDC match details
- Stage 1c switch events (`stage1c_switched` field)
- Conversion details
- Guardrail blocks

## Common Tasks

### Run First-50 Test

```bash
cd nutritionverse-tests/entrypoints
python run_first_50_by_dish_id.py
```

### Check Stage 1c Telemetry

```bash
bash scripts/grep_stage1c.sh
```

### Run Tests

```bash
pytest nutritionverse-tests/tests/
pytest pipeline/tests/
```

### Regenerate Repository Census

```bash
python tools/scan_repo.py > docs/ACTIVE_INVENTORY_NEW.json
```

## Configuration

All configs live in `/configs`:

- `negative_vocabulary.yml` - Blocked search terms
- `class_thresholds.yml` - Per-class confidence thresholds
- `variants.yml` - Search variants & normalization
- `unit_to_grams.yml` - Unit conversion factors
- `branded_fallbacks.yml` - Stage-Z fallbacks
- `category_allowlist.yml` - Allowed FDC categories
- `cook_conversions.v2.json` - Raw→cooked conversions

See [pipeline/config_loader.py](pipeline/config_loader.py) for schema details.

## Environment Variables

Required:

- `NEON_CONNECTION_URL` - Neon PostgreSQL connection string (contains FDC database)

Optional:

- `OPENAI_API_KEY` - For vision detection (if running end-to-end)

## Development

### Code Layout

- **Canonical engine**: `nutritionverse-tests/src/nutrition/alignment/`
- **Orchestrator**: `pipeline/run.py`
- **Adapters**: `nutritionverse-tests/src/adapters/`
- **Tests**: `nutritionverse-tests/tests/`, `pipeline/tests/`

### Testing Strategy

1. **Unit tests**: Test individual modules (no DB required)
2. **Integration tests**: Test full pipeline with FDC database
3. **Batch evaluation**: Run 459-dish ground truth evaluation

### Adding a New Stage

1. Implement logic in `nutritionverse-tests/src/nutrition/alignment/align_convert.py`
2. Update `TelemetryEvent` schema in `pipeline/schemas.py`
3. Extract telemetry in `pipeline/run.py`
4. Add unit tests in `nutritionverse-tests/tests/`
5. Document in `docs/pipeline.md`

## Documentation

- [REPO_SNAPSHOT.md](docs/REPO_SNAPSHOT.md) - Full repository analysis
- [UNUSED_OR_DUPLICATE_REPORT.md](docs/UNUSED_OR_DUPLICATE_REPORT.md) - Cleanup report
- [pipeline.md](docs/pipeline.md) - Pipeline stages & architecture
- [ACTIVE_INVENTORY.json](docs/ACTIVE_INVENTORY.json) - Machine-readable manifest

## Maintenance

### Cleanup Completed (2025-10-29)

- Removed ~5000+ lines of duplicate code
- Archived legacy snapshots (tempPipeline10-27-811, tempPipeline10-25-920)
- Consolidated entrypoints to `nutritionverse-tests/entrypoints/`
- Unified configs at `/configs` (single source of truth)
- Removed gpt5-context-delivery (temporary delivery directory)

### Active File Count

- **Core files**: ~45 (score ≥ 80)
- **Support files**: ~30 (score 60-79)
- **Total active**: ~75 files

See [docs/REPO_SNAPSHOT.md](docs/REPO_SNAPSHOT.md) for full analysis.

## License

Proprietary - Snap & Track / NuVola
