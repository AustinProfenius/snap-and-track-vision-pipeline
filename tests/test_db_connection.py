#!/usr/bin/env python3
"""
Standalone test to diagnose DB connection and import issues.
Tests each component in isolation.
"""
import sys
from pathlib import Path

print("=" * 70)
print("DIAGNOSTIC TEST: DB Connection & Import Paths")
print("=" * 70)

# Test 1: Environment variable loading
print("\n[1/6] Testing .env loading...")
from dotenv import load_dotenv
import os

repo_root = Path(__file__).parent
env_path = repo_root / ".env"
print(f"  .env path: {env_path}")
print(f"  .env exists: {env_path.exists()}")

load_dotenv(env_path, override=True)
neon_url = os.getenv("NEON_CONNECTION_URL")
print(f"  NEON_CONNECTION_URL loaded: {'✓ YES' if neon_url else '✗ NO'}")
if neon_url:
    # Mask the password
    masked = neon_url.split('@')[0].split(':')[0] + ":***@" + neon_url.split('@')[1] if '@' in neon_url else "***"
    print(f"  Connection string: {masked}")

# Test 2: Python path setup
print("\n[2/6] Testing Python paths...")
nutritionverse_path = repo_root / "nutritionverse-tests"
print(f"  nutritionverse-tests path: {nutritionverse_path}")
print(f"  Exists: {nutritionverse_path.exists()}")

if str(nutritionverse_path) not in sys.path:
    sys.path.insert(0, str(nutritionverse_path))
    print(f"  Added to sys.path: {nutritionverse_path}")

# Test 3: FDCDatabase import
print("\n[3/6] Testing FDCDatabase import...")
try:
    from src.adapters.fdc_database import FDCDatabase
    print("  ✓ FDCDatabase imported successfully")
except ImportError as e:
    print(f"  ✗ FDCDatabase import failed: {e}")
    sys.exit(1)

# Test 4: FDCDatabase connection
print("\n[4/6] Testing FDCDatabase connection...")
try:
    db = FDCDatabase()
    print("  ✓ FDCDatabase instantiated")

    # Try a simple query
    results = db.search_foods("apple", limit=5)
    print(f"  ✓ Search query succeeded: found {len(results)} results")
    if results:
        print(f"    Sample: {results[0].get('description', 'N/A')}")
except Exception as e:
    print(f"  ✗ FDCDatabase connection failed: {e}")
    import traceback
    traceback.print_exc()

# Test 5: config_loader import
print("\n[5/6] Testing config_loader import...")
pipeline_path = repo_root / "pipeline"
print(f"  pipeline path: {pipeline_path}")
print(f"  Exists: {pipeline_path.exists()}")

if str(pipeline_path) not in sys.path:
    sys.path.insert(0, str(pipeline_path))
    print(f"  Added to sys.path: {pipeline_path}")

try:
    from config_loader import load_pipeline_config
    print("  ✓ config_loader imported successfully")

    # Try loading configs
    configs_path = repo_root / "configs"
    cfg = load_pipeline_config(root=str(configs_path))
    print(f"  ✓ Configs loaded: {cfg.config_version}")
except ImportError as e:
    print(f"  ✗ config_loader import failed: {e}")
except Exception as e:
    print(f"  ✗ Config loading failed: {e}")

# Test 6: AlignmentEngineAdapter import and initialization
print("\n[6/6] Testing AlignmentEngineAdapter...")
try:
    from src.adapters.alignment_adapter import AlignmentEngineAdapter
    print("  ✓ AlignmentEngineAdapter imported successfully")

    adapter = AlignmentEngineAdapter()
    print("  ✓ AlignmentEngineAdapter instantiated")

    # Try a simple alignment
    prediction = {"foods": [{"name": "apple", "form": "raw", "mass_g": 100.0, "confidence": 0.8}]}
    result = adapter.align_prediction_batch(prediction)

    if result["available"]:
        print(f"  ✓ Alignment succeeded")
        if result["foods"]:
            food = result["foods"][0]
            print(f"    Matched: {food.get('fdc_name', 'NO_MATCH')} (stage={food.get('alignment_stage')})")
    else:
        print(f"  ✗ Alignment failed: {result.get('error', 'Unknown error')}")

except Exception as e:
    print(f"  ✗ AlignmentEngineAdapter test failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("DIAGNOSTIC TEST COMPLETE")
print("=" * 70)
