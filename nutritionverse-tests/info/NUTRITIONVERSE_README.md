# NutritionVerse Evaluator

**Zero-setup evaluation app for testing OpenAI vision models on the NutritionVerse dataset**

## Features

✅ **Automatic Dataset Loading** - Directly loads from your CSV files, no configuration needed
✅ **OpenAI Model Selection** - Choose between GPT-4o, GPT-4o-mini, or GPT-4-turbo
✅ **Micronutrient Mode** - Toggle between macro-only or full micronutrient analysis
✅ **Comprehensive Comparisons** - See predicted vs actual with percentage differences
✅ **Per-Food Breakdown** - Compare individual food item predictions
✅ **Overall Accuracy Score** - Aggregate performance across all metrics
✅ **Color-Coded Results** - Visual indicators for accuracy (green < 10%, yellow < 25%, red > 25%)

## Quick Start

### 1. Ensure you have your API key in .env

```bash
# Make sure .env exists with OPENAI_API_KEY
cat .env | grep OPENAI_API_KEY
```

### 2. Launch the app

```bash
./run_app.sh
```

Or manually:
```bash
streamlit run nutritionverse_app.py
```

### 3. Use the app

1. **Select Model** - Choose your OpenAI model in the sidebar
2. **Enable/Disable Micros** - Toggle micronutrient mode
3. **Navigate Dataset** - Filter by split (Train/Val/Test) and select a dish
4. **Run Prediction** - Click "Run Prediction" button
5. **View Results** - See comprehensive comparison with percentage differences

## Dataset Information

**Location**: `/Users/austinprofenius/snapandtrack-model-testing/nutritionverse`

**Loaded Data:**
- Metadata CSV: `nutritionverse_dish_metadata3.csv`
- Images: `nutritionverse-manual/nutritionverse-manual/images/`
- Splits: `nutritionverse-manual/nutritionverse-manual/updated-manual-dataset-splits.csv`

**Dataset Size:**
- Total dishes: 225
- Train: 158 dishes
- Val: 67 dishes
- Food items: 1-7 per dish

## Measured Statistics

### Macro Mode (Default)
- **Total Mass** (grams)
- **Total Calories** (kcal)
- **Total Protein** (grams)
- **Total Carbohydrates** (grams)
- **Total Fat** (grams)

### Micronutrient Mode (Optional)
All of the above PLUS:
- **Calcium** (mg)
- **Iron** (mg)
- **Magnesium** (mg)
- **Potassium** (mg)
- **Sodium** (mg)
- **Vitamin D** (µg)
- **Vitamin B12** (µg)

## Results Display

### Comparison Table
Shows side-by-side comparison with:
- **Predicted** value
- **Actual** value (ground truth)
- **Difference** (predicted - actual)
- **Error %** (percentage difference)

Color coding:
- 🟢 Green: < 10% error (excellent)
- 🟡 Yellow: 10-25% error (good)
- 🔴 Red: > 25% error (needs improvement)

### Per-Food Breakdown
- **Predicted Foods** (left column) - What the model identified
- **Actual Foods** (right column) - Ground truth from dataset
- Expandable cards show all nutritional details

### Overall Accuracy
Aggregate score showing average accuracy across ALL measured statistics.

Formula: `100% - average(|percentage_error| for all fields)`

## Model Selection

Available models:
- **gpt-4o-mini** (default) - Faster, cheaper, good accuracy
- **gpt-4o** - Best accuracy, more expensive
- **gpt-4-turbo** - Balance of speed and accuracy

## Prompts

### Macro-Only Prompt
Asks the model to identify foods and estimate:
- Name, mass, calories, protein, carbs, fat for each food
- Totals across all foods

### Micro+Macro Prompt
Extended version that additionally estimates 7 micronutrients:
- All macro fields PLUS
- Calcium, iron, magnesium, potassium, sodium, vitamin D, vitamin B12

## Cost Estimates

Per image (approximate, January 2025 pricing):

| Model | Macro Mode | Micro Mode |
|-------|-----------|------------|
| gpt-4o-mini | $0.01-0.02 | $0.02-0.03 |
| gpt-4o | $0.05-0.08 | $0.08-0.12 |
| gpt-4-turbo | $0.03-0.05 | $0.05-0.08 |

## Example Workflow

1. Launch app: `./run_app.sh`
2. Select **gpt-4o-mini** model
3. Keep **micronutrients OFF** for first test
4. Filter to **Train** split
5. Select first dish
6. Click **Run Prediction**
7. Review results:
   - Check overall accuracy score
   - Review comparison table for errors
   - Expand per-food cards to see individual items
8. Try **micronutrients ON** to see extended analysis
9. Compare different models on same dish

## Troubleshooting

### Dataset Not Loading
- Check path: `/Users/austinprofenius/snapandtrack-model-testing/nutritionverse`
- Ensure CSV files exist
- Verify images directory has .jpg files

### API Errors
- Verify OPENAI_API_KEY in `.env`
- Check API key has credits
- Try gpt-4o-mini for lower costs

### JSON Parse Errors
- Model sometimes returns invalid JSON
- App automatically attempts repair
- If persistent, try a different model

### Performance Issues
- gpt-4o-mini is fastest
- Disable micronutrients for speed
- Each prediction takes 3-10 seconds

## Technical Details

### Architecture
- **Dataset Loader**: `src/core/nutritionverse_loader.py`
- **Prompts**: `src/core/nutritionverse_prompts.py`
- **OpenAI Adapter**: `src/adapters/openai_.py`
- **UI**: `nutritionverse_app.py`

### Data Flow
1. Load CSV metadata → Parse foods per dish
2. Load image splits → Match images to dishes
3. User selects dish → Display image + ground truth
4. Run prediction → Send image + prompt to OpenAI
5. Parse response → Extract JSON, validate schema
6. Compare → Calculate differences and percentages
7. Display → Show comprehensive results

## Future Enhancements

Potential additions:
- [ ] Batch evaluation mode (run multiple dishes)
- [ ] Export results to CSV
- [ ] Visualizations (calibration plots, error distributions)
- [ ] Multi-model comparison (run all 3 models at once)
- [ ] Cost tracking across runs
- [ ] Food name matching (fuzzy match predicted vs actual names)

---

**Status**: ✅ Ready to use
**Setup Required**: None (just ensure .env has OPENAI_API_KEY)
**Dataset**: Auto-loads from `/Users/austinprofenius/snapandtrack-model-testing/nutritionverse`
