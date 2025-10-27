# Changelog

All notable changes to the NutritionVerse API Test Harness.

## [0.1.1] - 2025-10-18

### Fixed
- **Streamlit UI crash when dataset not loaded**: Fixed `StreamlitValueAboveMaxError` that occurred when dataset directory is empty or schema map doesn't exist
  - Added graceful error handling with helpful messages
  - Set safe default dataset_size to prevent negative max_value
  - Added dataset status indicator in configuration summary
  - Disabled run button when dataset not loaded (unless dry-run mode)
  - Added expandable setup guide in UI when dataset missing

### Added
- **TROUBLESHOOTING.md**: Comprehensive troubleshooting guide for common issues
- **Setup instructions in UI**: Expandable guide shown when dataset not detected
- **Dataset status indicator**: Shows "✓ Loaded" or "⚠️ Not loaded" in config summary
- Better error messages with specific FileNotFoundError handling

## [0.1.0] - 2025-10-18

### Added
- Initial release of NutritionVerse API Test Harness
- Multi-API support (OpenAI, Claude, Gemini, Ollama)
- Three evaluation tasks (dish_totals, itemized, names_only)
- Comprehensive metrics (MAE, MAPE, Jaccard, precision/recall)
- Resumable runs with checkpointing
- Rate limiting and budget caps
- Streamlit UI dashboard
- Schema auto-discovery
- JSON repair and validation
- Cost tracking
- JSONL/Parquet export
- Complete documentation (README, QUICKSTART, PROJECT_SUMMARY)
- Utility scripts (verify_setup, compare_apis, export_results)

### Modules
- `src/core/loader.py` - Dataset loading with flexible slicing
- `src/core/schema.py` - Schema discovery and mapping
- `src/core/prompts.py` - Task-specific prompt templates
- `src/core/evaluator.py` - Metrics computation
- `src/core/runner.py` - Main evaluation orchestration
- `src/core/store.py` - Result storage and checkpointing
- `src/adapters/openai_.py` - OpenAI GPT-4o adapter
- `src/adapters/claude_.py` - Anthropic Claude adapter
- `src/adapters/gemini_.py` - Google Gemini adapter
- `src/adapters/ollama_llava.py` - Ollama local models adapter
- `src/ui/app.py` - Streamlit dashboard

### Documentation
- README.md - Full usage guide
- QUICKSTART.md - 5-minute setup
- PROJECT_SUMMARY.md - Technical overview
- NUTRITIONVERSE_HARNESS_README.md - Parent directory guide

### Configuration
- `configs/apis.yaml` - API settings and pricing
- `configs/tasks.yaml` - Task definitions
- `configs/schema_map.yaml` - Dataset schema mapping (auto-generated)

### Scripts
- `scripts/verify_setup.py` - Setup verification
- `scripts/compare_apis.sh` - Multi-API comparison
- `scripts/export_results.py` - Export to CSV/Parquet/Excel
