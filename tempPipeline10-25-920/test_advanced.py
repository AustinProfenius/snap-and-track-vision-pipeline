"""
Test script for advanced prompt engineering with FDC database integration.
"""
import asyncio
from pathlib import Path
import json

from src.adapters.openai_advanced import OpenAIAdvancedAdapter
from src.core.nutritionverse_loader import NutritionVerseDataset


async def test_single_pass():
    """Test single-pass workflow."""
    print("=" * 80)
    print("SINGLE-PASS WORKFLOW TEST")
    print("=" * 80)

    # Load dataset
    dataset = NutritionVerseDataset(Path("/Users/austinprofenius/snapandtrack-model-testing/nutritionverse"))
    dish = dataset.dishes[0]  # First dish

    print(f"\nTesting with: {dish.image_filename}")
    print(f"Ground truth: {[f.name for f in dish.foods]}")
    print(f"Ground truth calories: {dish.total_calories:.1f} kcal")

    # Initialize adapter (single-pass mode)
    adapter = OpenAIAdvancedAdapter(
        model="gpt-5-mini",  # Use GPT-5 mini for testing
        use_two_pass=False
    )

    # Run inference
    result = await adapter.infer(dish.image_path)

    print("\n" + "-" * 80)
    print("RESULTS:")
    print("-" * 80)
    print(json.dumps(result, indent=2))


async def test_two_pass():
    """Test two-pass workflow with FDC database."""
    print("\n" + "=" * 80)
    print("TWO-PASS WORKFLOW TEST (with FDC Database)")
    print("=" * 80)

    # Load dataset
    dataset = NutritionVerseDataset(Path("/Users/austinprofenius/snapandtrack-model-testing/nutritionverse"))
    dish = dataset.dishes[0]

    print(f"\nTesting with: {dish.image_filename}")
    print(f"Ground truth: {[f.name for f in dish.foods]}")
    print(f"Ground truth calories: {dish.total_calories:.1f} kcal")

    # Initialize adapter (two-pass mode)
    adapter = OpenAIAdvancedAdapter(
        model="gpt-5-mini",
        use_two_pass=True
    )

    # Run inference
    result = await adapter.infer(dish.image_path)

    print("\n" + "-" * 80)
    print("RESULTS:")
    print("-" * 80)
    print(f"Detected {len(result['items'])} items:")
    for item in result['items']:
        print(f"\n  - {item['name']}: {item['portion_estimate_g']:.1f}g")
        print(f"    Calories: {item['calories_kcal']:.1f} kcal")
        print(f"    Macros: P:{item['macros']['protein_g']:.1f}g "
              f"C:{item['macros']['carbs_g']:.1f}g "
              f"F:{item['macros']['fat_g']:.1f}g")
        print(f"    Confidence: {item['confidence']:.2f}")
        if item['fdc_candidates']:
            print(f"    FDC Match: {item['fdc_candidates'][0]['match_name']}")

    print(f"\nTOTALS:")
    print(f"  Mass: {result['totals']['mass_g']:.1f}g")
    calories_key = 'calories' if 'calories' in result['totals'] else 'calories_kcal'
    print(f"  Calories: {result['totals'][calories_key]:.1f} kcal "
          f"(uncertainty: {result['uncertainty']['kcal_low']:.0f}-{result['uncertainty']['kcal_high']:.0f})")
    print(f"  Protein: {result['totals']['protein_g']:.1f}g")
    print(f"  Carbs: {result['totals']['carbs_g']:.1f}g")
    print(f"  Fat: {result['totals']['fat_g']:.1f}g")

    print(f"\nGROUND TRUTH COMPARISON:")
    print(f"  Predicted: {result['totals'][calories_key]:.1f} kcal")
    print(f"  Actual: {dish.total_calories:.1f} kcal")
    error_pct = abs(result['totals'][calories_key] - dish.total_calories) / dish.total_calories * 100
    print(f"  Error: {error_pct:.1f}%")


async def test_database_search():
    """Test FDC database search functionality."""
    print("\n" + "=" * 80)
    print("FDC DATABASE SEARCH TEST")
    print("=" * 80)

    from src.adapters.fdc_database import FDCDatabase

    with FDCDatabase() as db:
        # Test search
        print("\nSearching for 'chicken breast grilled'...")
        results = db.search_foods("chicken breast grilled", limit=5)

        print(f"\nFound {len(results)} results:")
        for i, food in enumerate(results, 1):
            print(f"\n{i}. {food['name']}")
            print(f"   FDC ID: {food['fdc_id']}")
            print(f"   Type: {food['data_type']}")
            print(f"   Category: {food.get('food_category_description', 'N/A')}")
            if food.get('serving_gram_weight'):
                print(f"   Serving: {food['serving_description']} ({food['serving_gram_weight']}g)")
            print(f"   Per 100g: {food.get('calories_value', 0):.0f} kcal, "
                  f"P:{food.get('protein_value', 0):.1f}g "
                  f"C:{food.get('carbohydrates_value', 0):.1f}g "
                  f"F:{food.get('total_fat_value', 0):.1f}g")

        # Test nutrition computation
        if results:
            print("\n" + "-" * 80)
            print(f"Computing nutrition for 150g of '{results[0]['name']}':")
            nutrition = db.compute_nutrition(str(results[0]['fdc_id']), 150)
            print(f"  Calories: {nutrition['calories']:.1f} kcal")
            print(f"  Protein: {nutrition['protein_g']:.1f}g")
            print(f"  Carbs: {nutrition['carbs_g']:.1f}g")
            print(f"  Fat: {nutrition['fat_g']:.1f}g")


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("ADVANCED NUTRITION ESTIMATION SYSTEM - TEST SUITE")
    print("=" * 80)

    # Test 1: Database search
    try:
        await test_database_search()
    except Exception as e:
        print(f"\n[ERROR] Database test failed: {e}")
        print("Make sure NEON_CONNECTION_URL is set in .env file")

    # Test 2: Single-pass workflow
    try:
        await test_single_pass()
    except Exception as e:
        print(f"\n[ERROR] Single-pass test failed: {e}")

    # Test 3: Two-pass workflow
    try:
        await test_two_pass()
    except Exception as e:
        print(f"\n[ERROR] Two-pass test failed: {e}")
        print("Make sure FDC database is configured")

    print("\n" + "=" * 80)
    print("TESTS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
