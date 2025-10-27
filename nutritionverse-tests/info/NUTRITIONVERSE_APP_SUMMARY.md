# NutritionVerse Evaluator App - Complete Summary

**Status**: ✅ **READY TO USE** - Zero setup required!

---

## What Was Built

A **streamlined Streamlit app** specifically optimized for evaluating OpenAI vision models on your NutritionVerse dataset with comprehensive nutritional analysis.

## 🎯 Key Features

### ✅ Zero Configuration
- Automatically loads from your CSV files at `/Users/austinprofenius/snapandtrack-model-testing/nutritionverse`
- Reads metadata, images, and splits directly
- No schema discovery or setup steps needed

### ✅ OpenAI Model Selection
Choose from:
- **gpt-4o-mini** (fastest, cheapest, recommended)
- **gpt-4o** (best accuracy)
- **gpt-4-turbo** (balanced)

### ✅ Micronutrient Mode Toggle
- **Macro-Only Mode** (default): Calories, mass, protein, carbs, fat
- **Micro+Macro Mode**: Adds 7 micronutrients (calcium, iron, magnesium, potassium, sodium, vitamin D, B12)

### ✅ Comprehensive Results Display

**Comparison Table:**
- Predicted vs Actual values
- Absolute difference
- **Percentage error** (what you requested!)
- Color-coded accuracy (green < 10%, yellow < 25%, red > 25%)

**Per-Food Breakdown:**
- Predicted foods (left column)
- Actual foods (right column)
- Detailed nutrition per food item

**Overall Accuracy Score:**
- Aggregate performance across ALL statistics
- Single number showing total model performance

## 📁 File Structure

```
nutritionverse-tests/
├── nutritionverse_app.py              ← Main Streamlit app
├── run_app.sh                         ← Launch script
├── NUTRITIONVERSE_README.md           ← Full documentation
└── src/core/
    ├── nutritionverse_loader.py       ← CSV dataset loader
    └── nutritionverse_prompts.py      ← Macro & micro prompts
```

## 🚀 How to Use

### 1. Launch the App

```bash
cd nutritionverse-tests
./run_app.sh
```

### 2. Configure in Sidebar

1. **Select Model**: gpt-4o-mini (recommended to start)
2. **Micronutrients**: OFF for faster testing
3. **Filter Split**: Train, Val, or All
4. **Select Dish**: Choose from dropdown

### 3. Run Prediction

1. Click **"Run Prediction"** button
2. Wait 3-10 seconds for model response
3. View comprehensive results

### 4. Analyze Results

**Comparison Table** shows:
- ✅ Total Mass (g) - **predicted, actual, % error**
- ✅ Total Calories (kcal) - **predicted, actual, % error**
- ✅ Total Protein (g) - **predicted, actual, % error**
- ✅ Total Carbs (g) - **predicted, actual, % error**
- ✅ Total Fat (g) - **predicted, actual, % error**

**If micronutrients enabled:**
- ✅ Calcium (mg), Iron (mg), Magnesium (mg), etc.

**Per-Food section** shows:
- What foods the model identified
- Nutrition breakdown per food
- Comparison with ground truth foods

**Overall Accuracy:**
- Single score showing average accuracy across all metrics
- Example: "92.3%" means model is 92.3% accurate on average

## 📊 Example Results Display

### Comparison Table (what you'll see)

| Metric | Predicted | Actual | Difference | Error % |
|--------|-----------|--------|------------|---------|
| Total Calories | 520 kcal | 500 kcal | +20 kcal | **+4.0%** 🟢 |
| Total Protein | 45g | 50g | -5g | **-10.0%** 🟡 |
| Total Carbs | 60g | 55g | +5g | **+9.1%** 🟢 |
| Total Fat | 18g | 15g | +3g | **+20.0%** 🟡 |

**Overall Accuracy**: 91.2%

### Per-Food Breakdown

**Predicted:**
- Grilled chicken breast (150g): 248 kcal, 47g protein, 0g carbs, 5g fat
- Brown rice (200g): 218 kcal, 5g protein, 45g carbs, 2g fat

**Actual (Ground Truth):**
- chicken-wing (153g): 374 kcal, 53g protein, 0g carbs, 15g fat
- corn (79g): 83 kcal, 2g protein, 17g carbs, 2g fat

## 💡 What Makes This Different

### Compared to Original Test Harness:

| Feature | Original Harness | NutritionVerse App |
|---------|------------------|-------------------|
| Setup | Schema discovery required | **Zero setup** |
| Dataset | Generic, needs mapping | **Direct CSV loading** |
| UI | General purpose | **Optimized for nutrition** |
| Results | Basic metrics | **Percentage comparisons** |
| Food Display | Minimal | **Per-food breakdown** |
| Micronutrients | Not supported | **Toggle on/off** |
| Model Selection | Config file | **Live dropdown** |

### Key Improvements:

1. **Immediate Use**: No configuration, just run
2. **Nutrition-Focused**: Prompts optimized for food recognition
3. **Detailed Comparisons**: Percentage errors for every metric
4. **Visual Feedback**: Color-coded accuracy indicators
5. **Flexible Analysis**: Toggle micronutrients as needed
6. **Model Comparison**: Easily switch between OpenAI models

## 📈 Dataset Information

**Auto-loaded from**: `/Users/austinprofenius/snapandtrack-model-testing/nutritionverse`

**Data:**
- **225 total dishes**
- **158 Train** images
- **67 Val** images
- **1-7 food items** per dish

**Nutrition Data:**
- Full macro breakdown per food
- 7 micronutrients per food
- Accurate ground truth totals

## 💰 Cost Estimates

### Per Image

| Model | Macro-Only | With Micros |
|-------|-----------|-------------|
| **gpt-4o-mini** (recommended) | $0.01-0.02 | $0.02-0.03 |
| gpt-4o | $0.05-0.08 | $0.08-0.12 |
| gpt-4-turbo | $0.03-0.05 | $0.05-0.08 |

### Full Dataset (225 images)

| Model | Macro-Only | With Micros |
|-------|-----------|-------------|
| **gpt-4o-mini** | **$2.25-4.50** | $4.50-6.75 |
| gpt-4o | $11.25-18.00 | $18.00-27.00 |
| gpt-4-turbo | $6.75-11.25 | $11.25-18.00 |

**Recommendation**: Start with gpt-4o-mini, macro-only mode

## 🎯 Prompts

### Macro-Only Prompt
Instructs the model to:
1. Identify each food item by name
2. Estimate mass in grams
3. Calculate calories, protein, carbs, fat
4. Sum totals across all foods

**Output schema:**
```json
{
  "foods": [
    {"name": "...", "mass_g": 150, "calories": 248, ...}
  ],
  "totals": {
    "mass_g": 250, "calories": 282, ...
  }
}
```

### Micro+Macro Prompt
Extended version that adds:
- Calcium, Iron, Magnesium (minerals)
- Potassium, Sodium (electrolytes)
- Vitamin D, Vitamin B12 (vitamins)

## 🔧 Technical Details

### Architecture
- **Frontend**: Streamlit with real-time updates
- **Backend**: OpenAI Vision API (async calls)
- **Data**: Pandas for CSV loading
- **Validation**: JSON schema checking
- **Error Handling**: Automatic JSON repair

### Error Recovery
- Extracts JSON from markdown code blocks
- Finds JSON boundaries in text responses
- Validates schema before display
- Shows helpful error messages

## 📝 Usage Tips

### For Best Results:

1. **Start Simple**
   - Use gpt-4o-mini
   - Keep micronutrients OFF
   - Test on Train split first

2. **Evaluate Accuracy**
   - Check Overall Accuracy score
   - Look for patterns in errors
   - Note which foods are misidentified

3. **Compare Models**
   - Run same dish on different models
   - Compare error percentages
   - Note cost vs accuracy tradeoff

4. **Enable Micros Selectively**
   - Only when needed for detailed analysis
   - Increases cost and response time
   - May reduce overall accuracy

5. **Iterate**
   - Test multiple dishes
   - Look for systematic errors
   - Consider prompt refinements

## 🎬 Quick Demo Flow

```bash
# 1. Launch
./run_app.sh

# 2. In sidebar:
#    - Model: gpt-4o-mini
#    - Micronutrients: OFF
#    - Split: Train
#    - Select: First dish

# 3. Click "Run Prediction"

# 4. View results:
#    - Comparison table with % errors
#    - Per-food breakdown
#    - Overall accuracy score

# 5. Try different model:
#    - Change to gpt-4o
#    - Run on same dish
#    - Compare accuracy vs gpt-4o-mini

# 6. Enable micronutrients:
#    - Toggle ON
#    - Run prediction
#    - See extended nutrition data
```

## 📋 Checklist for First Use

- [x] Dataset auto-loads (no setup needed)
- [x] OPENAI_API_KEY in .env file
- [ ] Run `./run_app.sh`
- [ ] Select gpt-4o-mini model
- [ ] Keep micronutrients OFF
- [ ] Choose a dish from Train split
- [ ] Click "Run Prediction"
- [ ] Review comparison table
- [ ] Check overall accuracy
- [ ] Expand per-food items
- [ ] Try micronutrients ON
- [ ] Compare different models

## 🏆 Ready to Use!

Everything is configured and optimized for your exact use case:

✅ **Dataset**: Automatically loads from your NutritionVerse folder
✅ **Prompts**: Optimized for food identification and nutrition estimation
✅ **Models**: Easy OpenAI model selection
✅ **Results**: Comprehensive comparisons with percentage errors
✅ **UI**: Clean, intuitive interface
✅ **Documentation**: Complete guide in NUTRITIONVERSE_README.md

**Just run** `./run_app.sh` **and start evaluating!**

---

**Location**: `nutritionverse-tests/nutritionverse_app.py`
**Launch**: `./run_app.sh`
**Docs**: `NUTRITIONVERSE_README.md`
**Status**: ✅ Production ready
