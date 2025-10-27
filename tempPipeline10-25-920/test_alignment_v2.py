"""
Test the improved FDC alignment system (V2) with real-world examples.
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from src.adapters.fdc_alignment_v2 import FDCAlignmentEngineV2


def test_problematic_cases():
    """Test cases that were failing in V1."""
    print("=" * 70)
    print("TESTING V2 ALIGNMENT ENGINE - PROBLEMATIC CASES")
    print("=" * 70)

    engine = FDCAlignmentEngineV2()

    if not engine.db_available:
        print("❌ Database not available")
        return

    # Test cases from user feedback
    test_cases = [
        {
            "name": "cooked white rice",
            "calories": 156,
            "mass_g": 120,
            "expected_class": "rice",
            "should_not_match": ["onion", "pineapple"]
        },
        {
            "name": "grape tomatoes",
            "calories": 27,
            "mass_g": 90,
            "expected_class": "tomatoes",
            "should_not_match": []  # "Tomatoes grape raw" is correct - grape is valid within tomato class
        },
        {
            "name": "fresh baby spinach",
            "calories": 6,
            "mass_g": 25,
            "expected_class": "spinach",
            "should_not_match": ["carrot"]
        },
        {
            "name": "raw almonds",
            "calories": 164,
            "mass_g": 28,
            "expected_class": "almonds",
            "should_not_match": []
        },
        {
            "name": "fresh red apple (medium, with skin)",
            "calories": 94,
            "mass_g": 180,
            "expected_class": "apple",
            "should_not_match": ["pineapple"]
        },
    ]

    results = []

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'=' * 70}")
        print(f"TEST {i}: {test['name']}")
        print(f"  Predicted: {test['mass_g']}g, {test['calories']} kcal")
        print(f"  Expected class: {test['expected_class']}")
        print("=" * 70)

        # Build predicted food dict
        predicted_food = {
            "mass_g": test["mass_g"],
            "calories": test["calories"]
        }

        # Run alignment
        alignment = engine.align_predicted_food(test["name"], predicted_food)

        if alignment:
            matched_name = alignment["matched_name"]
            nutrition = alignment["nutrition"]

            print(f"\n✅ MATCHED: {matched_name}")
            print(f"   FDC ID: {alignment['fdc_id']}")
            print(f"   Data Type: {alignment['data_type']}")
            print(f"   Confidence: {alignment['confidence']:.2f}")
            print(f"   Score: {alignment['score']:.2f}")
            print(f"\n   Computed Nutrition:")
            print(f"     Mass: {nutrition['mass_g']:.1f}g")
            print(f"     Calories: {nutrition['calories']:.1f} kcal")
            print(f"     Protein: {nutrition['protein_g']:.1f}g")
            print(f"     Carbs: {nutrition['carbs_g']:.1f}g")
            print(f"     Fat: {nutrition['fat_g']:.1f}g")

            # Check if we avoided bad matches
            matched_lower = matched_name.lower()
            bad_matches = [word for word in test["should_not_match"] if word in matched_lower]

            if bad_matches:
                print(f"\n   ⚠️  WARNING: Matched contains unwanted words: {bad_matches}")
                results.append(("WARN", test["name"], matched_name))
            else:
                print(f"\n   ✓ Good: Avoided unwanted matches")
                results.append(("PASS", test["name"], matched_name))

            # Check mass sanity
            mass_ratio = nutrition['mass_g'] / test['mass_g']
            if mass_ratio < 0.5 or mass_ratio > 2.0:
                print(f"   ⚠️  WARNING: Mass ratio {mass_ratio:.2f}x seems wrong")

            # Check calorie sanity
            cal_ratio = nutrition['calories'] / test['calories']
            if abs(cal_ratio - 1.0) > 0.01:
                print(f"   ⚠️  WARNING: Calorie mismatch (got {nutrition['calories']:.1f}, expected {test['calories']})")

        else:
            print(f"\n❌ FAILED: No match found")
            results.append(("FAIL", test["name"], "No match"))

    # Summary
    print(f"\n\n{'=' * 70}")
    print("SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in results if r[0] == "PASS")
    warned = sum(1 for r in results if r[0] == "WARN")
    failed = sum(1 for r in results if r[0] == "FAIL")

    print(f"Total: {len(results)} tests")
    print(f"  ✓ Passed: {passed}")
    print(f"  ⚠  Warnings: {warned}")
    print(f"  ✗ Failed: {failed}")

    if passed == len(results):
        print("\n🎉 ALL TESTS PASSED!")
    elif passed + warned == len(results):
        print("\n✓ All tests completed (some warnings)")
    else:
        print("\n❌ Some tests failed")

    print("\nDetailed Results:")
    for status, name, match in results:
        symbol = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}[status]
        print(f"  {symbol} {name} → {match}")


if __name__ == "__main__":
    test_problematic_cases()
