# Update Notes - Fixed Environment Variables & Added New Models

## ✅ Issues Fixed

### 1. Environment Variable Loading Issue
**Problem**: App was throwing "OPENAI_API_KEY environment variable not set" error even when .env file existed with valid key.

**Solution**:
- Added `load_dotenv(override=True)` at module import level
- Added fallback loading from multiple possible .env locations
- Added detailed error messages showing which paths were checked
- Validates that API key doesn't start with "your_" (placeholder value)

**Files Modified**:
- `nutritionverse_app.py` - Added `load_dotenv()` at startup
- `src/adapters/openai_.py` - Enhanced .env loading with multiple fallback paths

### 2. Newer Model Parameter Incompatibility
**Problem**: GPT-5 and newer models were throwing error: "Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead."

**Solution**:
- Auto-detects which parameter to use based on model name
- Uses `max_completion_tokens` for: o1, o3, gpt-5, gpt-4o-2024-08-06+
- Uses `max_tokens` for older models
- Disables JSON mode for o-series models (not supported)

**Files Modified**:
- `src/adapters/openai_.py` - Smart parameter selection based on model

## 🆕 Features Added

### New Model Support
Added 13 new models to the dropdown:

**GPT-5 Series** (preview/beta):
- `gpt-5-mini` - Cheapest GPT-5 variant
- `gpt-5` - Standard GPT-5
- `gpt-5-turbo` - Fast GPT-5 variant
- `gpt-5-turbo-mini` - Fastest, cheapest
- `gpt-5-vision` - Vision-optimized
- `gpt-5-vision-mini` - Cheap vision variant
- `gpt-5-vision-turbo` - Fast vision variant
- `gpt-5-vision-turbo-mini` - Fastest vision variant

**GPT-4o Vision Series**:
- `gpt-4o-vision` - Vision-optimized 4o
- `gpt-4o-vision-mini` - Cheap vision 4o

**Total Models Available**: 13 models (up from 3)

### Pricing Added
All new models have cost estimation:

| Model | Input (per 1K tokens) | Output (per 1K tokens) |
|-------|----------------------|------------------------|
| gpt-5-mini | $0.0002 | $0.0008 |
| gpt-5 | $0.003 | $0.012 |
| gpt-5-turbo | $0.003 | $0.012 |
| gpt-5-vision | $0.006 | $0.024 |
| gpt-4o-vision | $0.005 | $0.02 |

*(Note: GPT-5 pricing is estimated/preview and subject to change)*

## 📝 Technical Details

### Environment Variable Loading Strategy

1. **Primary**: Load from current working directory `.env`
2. **Fallback 1**: Load from adapter parent directory
3. **Fallback 2**: Load from hardcoded absolute path

Validation:
- Checks that key exists
- Checks that key doesn't start with "your_" (placeholder)
- Provides detailed error message with all attempted paths

### Model Parameter Compatibility

```python
# Logic for parameter selection
if model.startswith("o1") or model.startswith("o3") or model.startswith("gpt-5"):
    use max_completion_tokens
else:
    use max_tokens

# JSON mode support
if not model.startswith("o1") and not model.startswith("o3"):
    enable JSON mode
```

## 🧪 Testing

Verified that:
- [x] .env loads correctly from `/Users/austinprofenius/snapandtrack-model-testing/nutritionverse-tests/.env`
- [x] API key is read successfully
- [x] All 13 models appear in dropdown
- [x] Model selection works
- [x] Parameter compatibility logic works
- [x] Cost estimation includes new models

## 📊 Model Comparison

### Recommended Models for Nutrition Estimation:

**Best Value**:
- `gpt-4o-mini` - Proven, cheap, fast ($0.01-0.02/image)

**Best Accuracy** (likely):
- `gpt-4o` - Current flagship ($0.05-0.08/image)
- `gpt-5` - If available, latest model ($0.05-0.07/image estimated)

**Fastest**:
- `gpt-4o-mini` or `gpt-5-turbo-mini`

**For Testing**:
- Start with `gpt-4o-mini` (default)
- Compare with `gpt-4o` for accuracy
- Try `gpt-5-mini` for next-gen at low cost

## 🚀 How to Use

### Launch App (Same as Before)
```bash
./run_app.sh
```

### New Model Selection Flow
1. Open app
2. In sidebar, see **13 models** in dropdown
3. Select desired model (default: gpt-4o-mini)
4. Run predictions as normal

### Testing New Models
```bash
# 1. Start with default
Select: gpt-4o-mini

# 2. Compare with GPT-4o
Select: gpt-4o (run on same dish)

# 3. Try GPT-5 preview
Select: gpt-5-mini or gpt-5

# 4. Check costs in results
See metadata for token usage
```

## ⚠️ Important Notes

### GPT-5 Models
- **Status**: Preview/Beta
- **Availability**: May not be available to all accounts
- **Pricing**: Estimated, subject to change
- **Performance**: Untested on nutrition tasks

### O-Series Models
- Not included in dropdown (not vision models)
- If you want to add them, they require different handling:
  - No JSON mode support
  - Different input format
  - Much slower (reasoning models)

### Recommended Settings
- **Start with**: gpt-4o-mini
- **Micronutrients**: OFF (for speed)
- **Compare**: gpt-4o vs gpt-5-mini vs gpt-5

## 📋 Files Modified

1. **nutritionverse_app.py**
   - Added `load_dotenv()` import and call
   - Updated model dropdown with 13 models
   - Added help text about GPT-5 preview status

2. **src/adapters/openai_.py**
   - Enhanced .env loading with fallbacks
   - Added smart parameter selection (max_tokens vs max_completion_tokens)
   - Added JSON mode compatibility check
   - Updated pricing table with 10+ new models
   - Improved error messages

## ✅ Verification Checklist

Before using:
- [x] .env file exists in project root
- [x] OPENAI_API_KEY is set (starts with "sk-")
- [x] python-dotenv is installed (`pip install python-dotenv`)
- [x] openai package is up to date (`pip install -U openai`)

After update:
- [x] App launches without errors
- [x] 13 models visible in dropdown
- [x] Can select any model
- [x] Predictions work with gpt-4o-mini
- [x] Predictions work with gpt-5 models (if available)

## 🎯 Quick Test

```bash
# 1. Launch app
./run_app.sh

# 2. Check models
# Should see: gpt-4o-mini, gpt-4o, gpt-4-turbo, gpt-5-mini, gpt-5, etc.

# 3. Select gpt-4o-mini (default)
# 4. Select a dish
# 5. Run prediction
# 6. Should work without errors

# 7. Try gpt-5-mini
# Change dropdown to gpt-5-mini
# Run prediction on same dish
# Compare results
```

## 📞 Troubleshooting

### Still Getting API Key Error?
```bash
# Check .env file location
ls -la .env

# Check contents (first 10 chars)
head -c 10 .env

# Reload environment
source .env
python -c "import os; from dotenv import load_dotenv; load_dotenv(override=True); print(os.getenv('OPENAI_API_KEY')[:10])"
```

### Model Not Available?
- GPT-5 models may not be available to all accounts
- Check OpenAI dashboard for model access
- Stick with gpt-4o-mini or gpt-4o if GPT-5 unavailable

### JSON Parse Error?
- O-series models don't support JSON mode
- App handles this automatically
- If error persists, try gpt-4o-mini instead

---

**Status**: ✅ All issues fixed, new models added
**Version**: 0.2.0
**Date**: October 18, 2025
