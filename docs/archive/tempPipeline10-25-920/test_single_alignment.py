"""
Quick test of database alignment with a mock prediction.
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment first
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.adapters.fdc_alignment import FDCAlignmentEngine


def main():
    """Test alignment with a mock prediction similar to the apple example."""
    print("=" * 60)
    print("Testing Database Alignment with Apple Prediction")
    print("=" * 60)

    # Mock prediction similar to the apple example from the user
    mock_prediction = {
        "foods": [
            {
                "name": "fresh red apple (medium, with skin)",
                "mass_g": 180.0,
                "calories": 94.0,
                "protein_g": 0.5,
                "carbs_g": 25.0,
                "fat_g": 0.3
            },
            {
                "name": "shredded carrot piece",
                "mass_g": 1.0,
                "calories": 0.4,
                "protein_g": 0.0,
                "carbs_g": 0.1,
                "fat_g": 0.0
            }
        ],
        "totals": {
            "mass_g": 181.0,
            "calories": 94.4,
            "protein_g": 0.5,
            "carbs_g": 25.0,
            "fat_g": 0.3
        }
    }

    print("\nMock Prediction:")
    print(f"  Foods: {len(mock_prediction['foods'])}")
    for food in mock_prediction['foods']:
        print(f"    - {food['name']}: {food['calories']} kcal")

    print("\n" + "=" * 60)
    print("Running Alignment Engine")
    print("=" * 60)

    engine = FDCAlignmentEngine()
    result = engine.align_prediction_batch(mock_prediction)

    print("\n" + "=" * 60)
    print("Alignment Results")
    print("=" * 60)
    print(f"Available: {result.get('available')}")
    print(f"Foods aligned: {len(result.get('foods', []))}")

    if result.get('foods'):
        for food in result['foods']:
            print(f"\n  Predicted: {food['predicted_name']}")
            print(f"  Matched: {food['matched_name']}")
            print(f"  FDC: {food['fdc_id']} ({food['data_type']})")
            nut = food['nutrition']
            print(f"  Nutrition: {nut['mass_g']:.1f}g, {nut['calories']:.1f} kcal")

    print(f"\nTotals:")
    totals = result.get('totals', {})
    print(f"  Mass: {totals.get('mass_g', 0):.1f}g")
    print(f"  Calories: {totals.get('calories', 0):.1f} kcal")
    print(f"  Protein: {totals.get('protein_g', 0):.1f}g")
    print(f"  Carbs: {totals.get('carbs_g', 0):.1f}g")
    print(f"  Fat: {totals.get('fat_g', 0):.1f}g")


if __name__ == "__main__":
    main()
