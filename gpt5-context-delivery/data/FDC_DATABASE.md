# FDC Database Structure and Rebuild Instructions

## Overview

The FDC (FoodData Central) database is a **Neon PostgreSQL database** containing USDA food nutrition data. Both the web app and batch harness query this database for food alignment.

## Connection

**Environment Variable**: `NEON_CONNECTION_URL`

Format: `postgresql://user:password@host/database?sslmode=require`

The connection URL must be set in `.env` file for both pipelines to access the same database.

## Database Schema

### Table: `foods`

Primary table containing all USDA FoodData Central entries.

**Key Columns**:
- `fdc_id` (INTEGER, PRIMARY KEY): Unique FDC identifier
- `name` (TEXT): Food name/description
- `data_type` (TEXT): Entry type (see Data Types below)
- `food_category_id` (TEXT): FDC food category
- `publication_date` (DATE): When entry was published

**Nutrition Columns** (per 100g):
- `energy_kcal` (REAL): Calories
- `protein_g` (REAL): Protein in grams
- `fat_g` (REAL): Total fat in grams
- `carb_g` (REAL): Total carbohydrates in grams
- `fiber_g` (REAL): Dietary fiber in grams
- `sugar_g` (REAL): Total sugars in grams

**Micronutrients** (optional, per 100g):
- `sodium_mg`, `calcium_mg`, `iron_mg`, `vitamin_c_mg`, etc.

## Data Types

The `data_type` field categorizes entries into FDC data collections:

1. **`foundation_food`**: High-quality minimally processed foods (priority for alignment)
2. **`sr_legacy_food`**: USDA Standard Reference Legacy foods
3. **`branded_food`**: Commercial branded products
4. **`survey_fndds_food`**: USDA Food and Nutrient Database for Dietary Studies
5. **`experimental_food`**: Research foods

**Alignment Priority** (from align_convert.py):
- **Stage 1b**: Foundation + SR Legacy raw foods
- **Stage 1c**: SR Legacy cooked foods (whitelist only)
- **Stage 2**: Foundation + SR Legacy raw with conversion
- **Stage 3**: Branded cooked exact match
- **Stage 4**: Branded closest energy density
- **Stage Z**: Branded universal fallback (tightest gates)

## Database Access Patterns

### Search Query (from fdc_database.py)

```sql
SELECT
    fdc_id, name, data_type, food_category_id,
    energy_kcal, protein_g, fat_g, carb_g
FROM foods
WHERE UPPER(name) LIKE UPPER(%query%)
  AND data_type = ANY(%data_types%)
ORDER BY LENGTH(name) ASC
LIMIT %limit%;
```

**Notes**:
- Case-insensitive search using `UPPER()`
- Shorter names ranked first (more specific)
- Data type filter for Foundation/SR Legacy

### Get by FDC ID

```sql
SELECT * FROM foods WHERE fdc_id = %fdc_id%;
```

## Deterministic Rebuild Instructions

To ensure both pipelines query the **same candidate pools**, the database must be rebuilt from a consistent source.

### Prerequisites

1. **USDA FDC Data Export**: Download from https://fdc.nal.usda.gov/download-datasets.html
   - Select: **Full Download** (all data types)
   - Version: **October 2024** (or specify exact version)
   - File: `FoodData_Central_csv_2024-10-31.zip` (example)

2. **Neon PostgreSQL Account**: Create database at https://neon.tech
   - Free tier sufficient for testing
   - Note connection string for `.env`

### Rebuild Steps

#### 1. Download and Extract FDC Data

```bash
wget https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_csv_2024-10-31.zip
unzip FoodData_Central_csv_2024-10-31.zip -d fdc_data/
```

#### 2. Create Database Schema

```sql
CREATE TABLE foods (
    fdc_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    data_type TEXT,
    food_category_id TEXT,
    publication_date DATE,

    -- Macronutrients (per 100g)
    energy_kcal REAL,
    protein_g REAL,
    fat_g REAL,
    carb_g REAL,
    fiber_g REAL,
    sugar_g REAL,

    -- Micronutrients (per 100g, optional)
    sodium_mg REAL,
    calcium_mg REAL,
    iron_mg REAL,
    vitamin_c_mg REAL
);

CREATE INDEX idx_foods_name ON foods USING gin(to_tsvector('english', name));
CREATE INDEX idx_foods_data_type ON foods(data_type);
CREATE INDEX idx_foods_category ON foods(food_category_id);
```

#### 3. Import FDC CSV Data

**Option A: Using Python script** (recommended for nutritionverse-tests):

```python
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

# Load FDC CSV files
foods_df = pd.read_csv('fdc_data/food.csv')
nutrients_df = pd.read_csv('fdc_data/food_nutrient.csv')
nutrient_defs_df = pd.read_csv('fdc_data/nutrient.csv')

# Pivot nutrients to wide format (one row per food)
nutrients_wide = nutrients_df.pivot_table(
    index='fdc_id',
    columns='nutrient_id',
    values='amount',
    aggfunc='first'
)

# Map nutrient IDs to column names
nutrient_map = {
    1008: 'energy_kcal',
    1003: 'protein_g',
    1004: 'fat_g',
    1005: 'carb_g',
    1079: 'fiber_g',
    2000: 'sugar_g',
    1093: 'sodium_mg',
    1087: 'calcium_mg',
    1089: 'iron_mg',
    1162: 'vitamin_c_mg'
}

# Rename columns
nutrients_wide = nutrients_wide.rename(columns=nutrient_map)

# Merge with foods
final_df = foods_df.merge(nutrients_wide, on='fdc_id', how='left')

# Insert into database
conn = psycopg2.connect(os.getenv('NEON_CONNECTION_URL'))
cursor = conn.cursor()

insert_query = """
INSERT INTO foods (fdc_id, name, data_type, food_category_id, publication_date,
                   energy_kcal, protein_g, fat_g, carb_g, fiber_g, sugar_g)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (fdc_id) DO UPDATE SET
    name = EXCLUDED.name,
    data_type = EXCLUDED.data_type,
    -- ... (update other fields)
"""

execute_batch(cursor, insert_query, final_df.to_records(index=False))
conn.commit()
```

**Option B: Using PostgreSQL COPY** (faster for large datasets):

```bash
psql $NEON_CONNECTION_URL -c "\COPY foods FROM 'fdc_data/foods_processed.csv' CSV HEADER"
```

#### 4. Verify Data Integrity

```sql
-- Check total entries
SELECT data_type, COUNT(*) FROM foods GROUP BY data_type;

-- Expected counts (October 2024 release):
-- foundation_food:      ~1,200
-- sr_legacy_food:     ~7,800
-- branded_food:      ~800,000+
-- survey_fndds_food:  ~8,000

-- Verify key foods exist
SELECT fdc_id, name, data_type FROM foods
WHERE name ILIKE '%chicken breast%'
  AND data_type IN ('foundation_food', 'sr_legacy_food')
LIMIT 5;
```

## Data Snapshot (Alternative to Rebuild)

For **exact reproducibility**, export a database dump:

### Export Current Database

```bash
pg_dump $NEON_CONNECTION_URL > fdc_snapshot_2024-10-27.sql
```

### Restore from Snapshot

```bash
psql $NEW_NEON_CONNECTION_URL < fdc_snapshot_2024-10-27.sql
```

**Advantages**:
- Guarantees identical candidate pools
- Faster than CSV import
- Includes indexes and constraints

**Storage**: Snapshot size ~2-3GB (full FDC database)

## Validation Checklist

After rebuilding or restoring the database, validate alignment behavior:

### 1. Query Test Foods

```python
from src.adapters.fdc_database import FDCDatabase

db = FDCDatabase()
db.connect()

# Test Foundation pool for common foods
test_queries = ['chicken', 'grape', 'almond', 'cantaloupe', 'honeydew']
for query in test_queries:
    results = db.search_foods(query, data_types=['foundation_food', 'sr_legacy_food'])
    print(f"{query}: {len(results)} candidates")
    if results:
        print(f"  Top: {results[0]['name']} (FDC {results[0]['fdc_id']})")
```

Expected output:
```
chicken: 50 candidates
  Top: Chicken broilers or fryers meat and skin raw (FDC 171477)
grape: 30 candidates
  Top: Grapes red or green (European type such as Thompson seedless) raw (FDC 174682)
almond: 15 candidates
  Top: Nuts almonds (FDC 170567)
cantaloupe: 3 candidates
  Top: Melons cantaloupe raw (FDC 169092)
honeydew: 2 candidates
  Top: Melons honeydew raw (FDC 169093)
```

### 2. Run Alignment Test

```bash
cd nutritionverse-tests
python test_surgical_fixes.py
```

Expected: All 7 surgical fixes pass (grapes/almonds/melons match successfully)

### 3. Compare with Baseline

Run first 50 dishes and compare stage distribution:

```bash
cd gpt5-context-delivery/entrypoints
python run_first_50_by_dish_id.py
```

Expected stage distribution:
- stage1b_raw_foundation_direct: ~85%
- stage0_no_candidates: ~8%
- stageZ_energy_only: ~5%

## Troubleshooting

### "No candidates found" for common foods

**Cause**: Database missing Foundation/SR Legacy entries
**Fix**: Re-import FDC data, verify data_type filter in search query

### Different results between web app and batch harness

**Possible causes**:
1. Different NEON_CONNECTION_URL (pointing to different databases)
2. Database updated between runs (different publication dates)
3. Search query differences (check variant generation in search_normalizer.py)

**Fix**: Use same `.env` file for both pipelines, verify with query test above

### Connection timeouts

**Cause**: Neon free tier connection limits
**Fix**: Add connection pooling or use Neon Pro tier

## Contact

For database access issues, contact Neon support or the NutritionVerse team.
