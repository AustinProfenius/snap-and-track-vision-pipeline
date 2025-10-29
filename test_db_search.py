#!/usr/bin/env python3
"""Quick script to search FDC database for specific entries."""
import sys
import os
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent / "nutritionverse-tests"))
sys.path.insert(0, str(Path(__file__).parent / "pipeline"))

from dotenv import load_dotenv
load_dotenv()

from src.adapters.fdc_database import FDCDatabase

db = FDCDatabase(os.getenv('NEON_CONNECTION_URL'))

# Search for BRANDED entries for foods that don't exist in Foundation/SR

print('=== Cherry Tomatoes - Branded ===')
results = db.search_foods('cherry tomatoes', limit=30, data_types=['branded_food'])
for r in results[:10]:
    kcal = r.get('calories_value', 0) or 0
    print(f'{r["fdc_id"]}: {r["name"][:80]} (kcal/100g={kcal:.1f})')

print('\n=== Grape Tomatoes - Branded ===')
results = db.search_foods('grape tomatoes', limit=30, data_types=['branded_food'])
for r in results[:10]:
    kcal = r.get('calories_value', 0) or 0
    print(f'{r["fdc_id"]}: {r["name"][:80]} (kcal/100g={kcal:.1f})')

print('\n=== Broccoli Florets - Branded ===')
results = db.search_foods('broccoli florets', limit=30, data_types=['branded_food'])
for r in results[:10]:
    kcal = r.get('calories_value', 0) or 0
    print(f'{r["fdc_id"]}: {r["name"][:80]} (kcal/100g={kcal:.1f})')

print('\n=== Scrambled Eggs - Branded ===')
results = db.search_foods('scrambled eggs', limit=30, data_types=['branded_food'])
for r in results[:10]:
    kcal = r.get('calories_value', 0) or 0
    print(f'{r["fdc_id"]}: {r["name"][:80]} (kcal/100g={kcal:.1f})')

print('\n=== Green Beans - Branded (raw/plain) ===')
results = db.search_foods('green beans', limit=50, data_types=['branded_food'])
# Filter for raw/plain, avoid baby food
plain_results = [r for r in results if 'baby' not in r['name'].lower()
                 and 'seasoned' not in r['name'].lower()
                 and 'sauce' not in r['name'].lower()]
for r in plain_results[:10]:
    kcal = r.get('calories_value', 0) or 0
    print(f'{r["fdc_id"]}: {r["name"][:80]} (kcal/100g={kcal:.1f})')
