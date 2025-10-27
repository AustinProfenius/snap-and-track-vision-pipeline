"""
Test script for FDC database alignment functionality.
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment first
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.adapters.fdc_alignment import FDCAlignmentEngine


def test_basic_alignment():
    """Test basic food alignment functionality."""
    print("=" * 60)
    print("TEST: Basic Food Alignment")
    print("=" * 60)

    engine = FDCAlignmentEngine()

    if not engine.db_available:
        print("⚠️  Database not available. Skipping test.")
        return

    # Test 1: Search for chicken breast
    print("\n1. Searching for 'chicken breast'...")
    match = engine.search_best_match("chicken breast")

    if match:
        print(f"   ✅ Found match:")
        print(f"      FDC ID: {match['fdc_id']}")
        print(f"      Name: {match['name']}")
        print(f"      Type: {match['data_type']}")
        print(f"      Confidence: {match['confidence']:.2f}")
        print(f"      Base nutrition (per 100g):")
        base = match['base_nutrition_per_100g']
        print(f"         Calories: {base['calories']:.1f} kcal")
        print(f"         Protein: {base['protein_g']:.1f}g")
        print(f"         Carbs: {base['carbs_g']:.1f}g")
        print(f"         Fat: {base['fat_g']:.1f}g")
    else:
        print("   ❌ No match found")

    # Test 2: Compute nutrition from predicted calories
    print("\n2. Computing nutrition for 150 kcal of chicken breast...")
    if match:
        nutrition = engine.compute_nutrition_from_calories(
            match['base_nutrition_per_100g'],
            target_calories=150
        )
        print(f"   ✅ Computed nutrition:")
        print(f"      Mass: {nutrition['mass_g']:.1f}g")
        print(f"      Calories: {nutrition['calories']:.1f} kcal")
        print(f"      Protein: {nutrition['protein_g']:.1f}g")
        print(f"      Carbs: {nutrition['carbs_g']:.1f}g")
        print(f"      Fat: {nutrition['fat_g']:.1f}g")

    # Test 3: Full alignment of a predicted food
    print("\n3. Full alignment of 'grilled chicken' with 200 kcal...")
    alignment = engine.align_predicted_food("grilled chicken", 200)

    if alignment:
        print(f"   ✅ Alignment successful:")
        print(f"      Matched: {alignment['matched_name']}")
        print(f"      FDC ID: {alignment['fdc_id']}")
        print(f"      Type: {alignment['data_type']}")
        print(f"      Confidence: {alignment['confidence']:.2f}")
        print(f"      Nutrition:")
        nut = alignment['nutrition']
        print(f"         Mass: {nut['mass_g']:.1f}g")
        print(f"         Calories: {nut['calories']:.1f} kcal")
        print(f"         Protein: {nut['protein_g']:.1f}g")
        print(f"         Carbs: {nut['carbs_g']:.1f}g")
        print(f"         Fat: {nut['fat_g']:.1f}g")
    else:
        print("   ❌ Alignment failed")


def test_batch_alignment():
    """Test batch prediction alignment."""
    print("\n" + "=" * 60)
    print("TEST: Batch Prediction Alignment")
    print("=" * 60)

    engine = FDCAlignmentEngine()

    if not engine.db_available:
        print("⚠️  Database not available. Skipping test.")
        return

    # Mock prediction
    mock_prediction = {
        "foods": [
            {"name": "chicken breast", "calories": 150, "mass_g": 100},
            {"name": "brown rice", "calories": 200, "mass_g": 150},
            {"name": "broccoli", "calories": 50, "mass_g": 200}
        ],
        "totals": {
            "calories": 400,
            "mass_g": 450,
            "protein_g": 35,
            "carbs_g": 50,
            "fat_g": 8
        }
    }

    print("\nAligning mock prediction with 3 foods...")
    result = engine.align_prediction_batch(mock_prediction)

    if result['available']:
        print(f"✅ Batch alignment complete:")
        print(f"   Matched {len(result['foods'])} foods")

        for i, food in enumerate(result['foods'], 1):
            print(f"\n   {i}. {food['predicted_name']}")
            print(f"      → {food['matched_name']}")
            print(f"      FDC: {food['fdc_id']} | Type: {food['data_type']}")
            nut = food['nutrition']
            print(f"      {nut['mass_g']:.1f}g, {nut['calories']:.1f} kcal")

        print(f"\n   Totals (Database-Aligned):")
        totals = result['totals']
        print(f"      Mass: {totals['mass_g']:.1f}g")
        print(f"      Calories: {totals['calories']:.1f} kcal")
        print(f"      Protein: {totals['protein_g']:.1f}g")
        print(f"      Carbs: {totals['carbs_g']:.1f}g")
        print(f"      Fat: {totals['fat_g']:.1f}g")
    else:
        print("❌ Batch alignment not available")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("FDC DATABASE ALIGNMENT TEST SUITE")
    print("=" * 60)

    try:
        test_basic_alignment()
        test_batch_alignment()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETE")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
