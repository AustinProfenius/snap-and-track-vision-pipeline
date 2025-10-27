"""
Test legacy food fallback for foods not in foundation dataset.
Tests watermelon and honeydew melon which are commonly missing from foundation foods.
"""
from dotenv import load_dotenv
load_dotenv()

from src.adapters.fdc_alignment_v2 import FDCAlignmentEngineV2


def test_legacy_fallback():
    """Test that legacy fallback works for watermelon and honeydew."""
    print("\n" + "=" * 80)
    print("TESTING LEGACY FOOD FALLBACK")
    print("=" * 80)

    engine = FDCAlignmentEngineV2()

    if not engine.db_available:
        print("❌ Database not available, cannot test")
        return

    # Test foods that may not be in foundation foods
    test_foods = [
        {"name": "watermelon", "expected_calories": 30},  # ~30 kcal/100g
        {"name": "honeydew melon", "expected_calories": 36},  # ~36 kcal/100g
        {"name": "cantaloupe", "expected_calories": 34},  # ~34 kcal/100g
    ]

    results = []

    for food in test_foods:
        print(f"\n{'='*80}")
        print(f"Testing: {food['name']}")
        print(f"Expected: ~{food['expected_calories']} kcal/100g")
        print(f"{'='*80}")

        match = engine.search_best_match(food['name'])

        if match:
            print(f"\n✅ FOUND: {match['name']}")
            print(f"   FDC ID: {match['fdc_id']}")
            print(f"   Data Type: {match['data_type']}")
            print(f"   Calories: {match['base_nutrition_per_100g']['calories']:.1f} kcal/100g")
            print(f"   Protein: {match['base_nutrition_per_100g']['protein_g']:.1f}g")
            print(f"   Carbs: {match['base_nutrition_per_100g']['carbs_g']:.1f}g")
            print(f"   Fat: {match['base_nutrition_per_100g']['fat_g']:.1f}g")

            # Check if from legacy
            if match['data_type'] == 'sr_legacy_food':
                print(f"   📦 Source: LEGACY FOOD (fallback worked!)")
            else:
                print(f"   📦 Source: FOUNDATION FOOD")

            results.append({
                "food": food['name'],
                "found": True,
                "source": match['data_type'],
                "calories": match['base_nutrition_per_100g']['calories']
            })
        else:
            print(f"\n❌ NOT FOUND: {food['name']}")
            results.append({
                "food": food['name'],
                "found": False,
                "source": None,
                "calories": 0
            })

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    found_count = sum(1 for r in results if r['found'])
    legacy_count = sum(1 for r in results if r['source'] == 'sr_legacy_food')

    print(f"Total tested: {len(test_foods)}")
    print(f"Found: {found_count}/{len(test_foods)}")
    print(f"From legacy fallback: {legacy_count}")

    print("\nDetailed Results:")
    for r in results:
        status = "✅" if r['found'] else "❌"
        source = f" ({r['source']})" if r['found'] else ""
        cals = f" - {r['calories']:.1f} kcal/100g" if r['found'] else ""
        print(f"  {status} {r['food']}{source}{cals}")

    if found_count == len(test_foods):
        print("\n🎉 All foods found!")
        if legacy_count > 0:
            print(f"   Legacy fallback successfully used for {legacy_count} items")
    elif found_count > 0:
        print(f"\n⚠️  {len(test_foods) - found_count} foods still missing")
    else:
        print("\n❌ No foods found - check database connection")


if __name__ == "__main__":
    test_legacy_fallback()
