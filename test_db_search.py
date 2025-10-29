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

print('=== Searching for broccoli entries ===')
results = db.search_foods('broccoli', limit=10)
for r in results:
    print(f'{r["fdc_id"]}: {r["name"]} (source={r["data_type"]})')

print('\n=== Searching for scrambled egg entries ===')
results = db.search_foods('egg scrambled', limit=10)
for r in results:
    print(f'{r["fdc_id"]}: {r["name"]} (source={r["data_type"]})')

print('\n=== Searching for cherry tomato entries ===')
results = db.search_foods('tomato cherry', limit=10)
for r in results:
    print(f'{r["fdc_id"]}: {r["name"]} (source={r["data_type"]})')

print('\n=== Searching for cherry tomatoes entries ===')
results = db.search_foods('cherry tomatoes', limit=10)
for r in results:
    print(f'{r["fdc_id"]}: {r["name"]} (source={r["data_type"]})')

print('\n=== Searching for green bean entries ===')
results = db.search_foods('green bean', limit=10)
for r in results:
    print(f'{r["fdc_id"]}: {r["name"]} (source={r["data_type"]})')
