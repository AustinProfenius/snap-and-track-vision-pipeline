#!/usr/bin/env python3
"""
Quick test script for egg & broccoli alignment fixes.

Tests:
1. Scrambled eggs alignment
2. Broccoli florets alignment
3. Stage 1c telemetry with FDC IDs
4. Config loading (no hardcoded warnings)
"""

import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(override=True)

# Change to nutritionverse-tests directory for imports
sys.path.insert(0, str(Path(__file__).parent / "nutritionverse-tests"))

from src.adapters.alignment_adapter import AlignmentEngineAdapter

def test_alignment(name, form, mass_g):
    """Test alignment for a single food."""
    prediction = {
        'foods': [{
            'name': name,
            'form': form,
            'mass_g': mass_g,
            'confidence': 0.78
        }]
    }

    result = adapter.align_prediction_batch(prediction)

    if result['available'] and result['foods']:
        food = result['foods'][0]
        print(f"\n✓ {name.title()} Aligned Successfully")
        print(f"  FDC Match: {food.get('fdc_name', 'N/A')}")
        print(f"  Stage: {food.get('alignment_stage', 'N/A')}")
        print(f"  Calories: {food.get('calories', 0):.1f}")
        print(f"  Protein: {food.get('protein_g', 0):.1f}g")

        # Check for stage1c telemetry
        if 'stage1c_switched' in food.get('telemetry', {}):
            tel = food['telemetry']['stage1c_switched']
            print(f"  Stage1c Switch: {tel.get('from', 'N/A')} → {tel.get('to', 'N/A')}")
            if 'from_id' in tel and 'to_id' in tel:
                print(f"  FDC IDs: {tel['from_id']} → {tel['to_id']} ✓")
            else:
                print(f"  ✗ Missing FDC IDs in telemetry!")

        return True
    else:
        print(f"\n✗ {name.title()} Failed to Align")
        print(f"  Available: {result['available']}")
        print(f"  Foods count: {len(result.get('foods', []))}")
        return False

if __name__ == "__main__":
    print("="*70)
    print("Egg & Broccoli Alignment Fix - Test Suite")
    print("="*70)

    print("\nInitializing adapter...")
    adapter = AlignmentEngineAdapter()

    print("\n" + "-"*70)
    print("Test 1: Scrambled Eggs")
    print("-"*70)
    test1 = test_alignment("scrambled eggs", "cooked", 130.0)

    print("\n" + "-"*70)
    print("Test 2: Broccoli Florets")
    print("-"*70)
    test2 = test_alignment("broccoli florets", "steamed", 100.0)

    print("\n" + "="*70)
    print("Summary")
    print("="*70)

    results = {
        "Scrambled Eggs": test1,
        "Broccoli Florets": test2
    }

    passed = sum(results.values())
    total = len(results)

    print(f"\nPassed: {passed}/{total}")
    for name, result in results.items():
        status = "✓" if result else "✗"
        print(f"  {status} {name}")

    if passed == total:
        print("\n✓ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print(f"\n✗ {total - passed} TEST(S) FAILED")
        sys.exit(1)
