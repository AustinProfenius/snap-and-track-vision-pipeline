"""
Quick validation test for surgical fixes A-E2.

Tests:
1. Grapes - Should match via Stage 1b with variant "grapes raw"
2. Honeydew - Should match via variant "melons honeydew raw"
3. Cantaloupe - Should match via variant "melons cantaloupe raw"
4. Brussels sprouts (roasted) - Should match via Stage 2, NOT "leaves"
5. Bacon (fried) - Should match via Stage 1c OR Stage-Z (meat whitelist)
6. Sweet potato (roasted) - Should match via Stage 2, NOT "leaves"
7. Apple (raw) - Should NOT match "strudel/pie/juice" (negatives working)
"""

import os
import sys
from pathlib import Path

# Add parent to path for proper package imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set PYTHONPATH for relative imports to work
os.chdir(Path(__file__).parent)

from src.adapters.alignment_adapter import AlignmentEngineAdapter

def test_item(adapter, name, form, expected_stage=None, forbidden_words=None):
    """Test single food item alignment."""
    print(f"\n{'='*70}")
    print(f"TEST: {name} ({form})")
    print('='*70)

    prediction = {
        "foods": [{
            "name": name,
            "form": form,
            "mass_g": 100,
            "calories_per_100g": 100,
            "confidence": 0.85
        }]
    }

    result = adapter.align_prediction_batch(prediction)

    if not result["available"]:
        print("❌ Database not available")
        return False

    food = result["foods"][0]
    telemetry = food.get("telemetry", {})

    # Print results
    print(f"\nAlignment Stage: {food['alignment_stage']}")
    print(f"FDC Match: {food['fdc_name']}")
    print(f"Variant Chosen: {telemetry.get('variant_chosen', 'N/A')}")
    print(f"Variants Tried: {telemetry.get('search_variants_tried', 0)}")
    print(f"Foundation Pool: {telemetry.get('foundation_pool_count', 0)}")

    if food['alignment_stage'] == 'stage1b_raw_foundation_direct':
        print(f"Stage1b Score: {telemetry.get('stage1b_score', 'N/A')}")

    # Validation
    success = True

    # Check expected stage
    if expected_stage and food['alignment_stage'] != expected_stage:
        print(f"⚠️  WARNING: Expected {expected_stage}, got {food['alignment_stage']}")
        success = False

    # Check forbidden words in FDC name
    if forbidden_words:
        fdc_name_lower = food['fdc_name'].lower()
        for word in forbidden_words:
            if word in fdc_name_lower:
                print(f"❌ FORBIDDEN WORD FOUND: '{word}' in '{food['fdc_name']}'")
                success = False

    # Check if match found
    if food['alignment_stage'] == 'stage0_no_candidates':
        print(f"❌ NO MATCH (stage0_no_candidates)")
        success = False

    if success:
        print("✅ PASS")

    return success


def main():
    """Run all validation tests."""
    print("\n" + "="*70)
    print("SURGICAL FIXES VALIDATION TEST (A-E2)")
    print("="*70)

    # Initialize adapter
    adapter = AlignmentEngineAdapter()

    if not adapter.db_available:
        print("\n❌ Database not available. Set NEON_CONNECTION_URL.")
        return

    # Run tests
    results = []

    # Test 1: Grapes (raw) - Stage 1b with plural variant
    results.append(test_item(
        adapter, "grapes", "raw",
        expected_stage="stage1b_raw_foundation_direct"
    ))

    # Test 2: Honeydew (raw) - Should match via melon variant
    results.append(test_item(
        adapter, "honeydew", "raw",
        expected_stage="stage1b_raw_foundation_direct"
    ))

    # Test 3: Cantaloupe (raw) - Should match via melon variant
    results.append(test_item(
        adapter, "cantaloupe", "raw",
        expected_stage="stage1b_raw_foundation_direct"
    ))

    # Test 4: Brussels sprouts (roasted) - Stage 2, NOT leaves
    results.append(test_item(
        adapter, "brussels sprouts", "roasted",
        expected_stage="stage2_raw_convert",
        forbidden_words=["leaves", "leaf"]
    ))

    # Test 5: Bacon (fried) - Stage 1c OR Stage-Z (either is acceptable)
    results.append(test_item(
        adapter, "bacon", "fried"
        # No expected_stage - either stage1c_cooked_sr_direct or stageZ_energy_only is OK
    ))

    # Test 6: Sweet potato (roasted) - Stage 2, NOT leaves
    results.append(test_item(
        adapter, "sweet potato", "roasted",
        expected_stage="stage2_raw_convert",
        forbidden_words=["leaves", "leaf"]
    ))

    # Test 7: Apple (raw) - Should NOT match strudel/pie/juice
    results.append(test_item(
        adapter, "apple", "raw",
        forbidden_words=["strudel", "pie", "juice", "sauce", "chips", "dried"]
    ))

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✅ ALL TESTS PASSED")
    else:
        print(f"❌ {total - passed} TEST(S) FAILED")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
