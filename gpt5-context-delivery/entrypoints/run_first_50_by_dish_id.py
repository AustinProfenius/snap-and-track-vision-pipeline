"""
Run First 50 Images (Sorted by Dish ID) - Batch Harness Test
Matches web app test for direct comparison.

This script:
1. Loads test dataset from food-nutrients/test
2. Sorts images by dish_id
3. Processes first 50 images
4. Outputs results with full telemetry
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add nutritionverse-tests to path (use actual implementation, not copy)
nutritionverse_path = Path(__file__).parent.parent.parent / "nutritionverse-tests"
sys.path.insert(0, str(nutritionverse_path))

from src.adapters.alignment_adapter import AlignmentEngineAdapter

def load_metadata(metadata_path):
    """Load metadata.jsonl with dish information."""
    metadata = {}
    with open(metadata_path, 'r') as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                dish_id = entry['id']  # Field is 'id', not 'dish_id'
                metadata[dish_id] = entry
    return metadata

def get_first_50_dishes_sorted(test_dir):
    """Get first 50 dish IDs sorted alphabetically."""
    # Find all dish images
    dish_images = list(Path(test_dir).glob("dish_*.png"))

    # Extract dish IDs and sort
    dish_ids = sorted([img.stem for img in dish_images])

    # Return first 50
    return dish_ids[:50]

def run_batch_test():
    """Run batch test on first 50 dishes (sorted by ID)."""

    # Load environment from nutritionverse-tests directory
    env_path = Path(__file__).parent.parent.parent / "nutritionverse-tests" / ".env"
    load_dotenv(dotenv_path=env_path, override=True)

    # Paths
    test_dir = Path("/Users/austinprofenius/snapandtrack-model-testing/food-nutrients/test")
    metadata_path = Path("/Users/austinprofenius/snapandtrack-model-testing/food-nutrients/metadata.jsonl")

    # Output directory
    output_dir = Path(__file__).parent.parent / "telemetry"
    output_dir.mkdir(exist_ok=True)

    # Load metadata
    print("Loading metadata...")
    metadata = load_metadata(metadata_path)

    # Get first 50 dishes sorted by ID
    print("Finding first 50 dishes (sorted by dish_id)...")
    dish_ids = get_first_50_dishes_sorted(test_dir)

    print(f"Selected {len(dish_ids)} dishes")
    print(f"First dish: {dish_ids[0]}")
    print(f"Last dish: {dish_ids[-1]}")

    # Initialize alignment adapter
    print("\nInitializing alignment adapter...")
    adapter = AlignmentEngineAdapter()

    if not adapter.db_available:
        print("ERROR: Database not available. Set NEON_CONNECTION_URL.")
        return

    # Process each dish
    results = []

    print(f"\n{'='*70}")
    print(f"BATCH TEST: First 50 Dishes (Sorted by ID)")
    print(f"{'='*70}\n")

    for idx, dish_id in enumerate(dish_ids):
        print(f"[{idx+1}/50] Processing {dish_id}...")

        # Get metadata
        dish_meta = metadata.get(dish_id)
        if not dish_meta:
            print(f"  WARNING: No metadata for {dish_id}")
            continue

        # Convert metadata ingredients to prediction format
        ingredients = dish_meta.get("ingredients", [])
        if not ingredients:
            print(f"  WARNING: No ingredients for {dish_id}")
            continue

        # Convert ingredients to prediction format
        prediction = {
            "foods": [
                {
                    "name": ingr["name"],
                    "form": "raw",  # Default to raw, alignment engine will handle
                    "mass_g": ingr["grams"],
                    "confidence": 0.85  # Default confidence
                }
                for ingr in ingredients
            ]
        }

        # Run alignment
        try:
            aligned = adapter.align_prediction_batch(prediction)

            # Build result with ground truth from metadata
            result = {
                "dish_id": dish_id,
                "image_filename": f"{dish_id}.png",
                "prediction": prediction,
                "database_aligned": aligned,
                "ground_truth": {
                    "ingredients": ingredients,
                    "total_calories": dish_meta.get("total_calories"),
                    "total_mass": dish_meta.get("total_mass"),
                    "total_fat": dish_meta.get("total_fat"),
                    "total_carb": dish_meta.get("total_carb"),
                    "total_protein": dish_meta.get("total_protein")
                }
            }

            results.append(result)

            # Print summary
            foods = aligned.get("foods", [])
            stage_summary = {}
            for food in foods:
                stage = food.get("alignment_stage", "unknown")
                stage_summary[stage] = stage_summary.get(stage, 0) + 1

            print(f"  Foods: {len(foods)}, Stages: {stage_summary}")

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"batch_harness_first50_sorted_{timestamp}.json"

    output = {
        "timestamp": timestamp,
        "test_type": "batch_harness_first_50_sorted_by_dish_id",
        "total_dishes": len(results),
        "dish_ids": dish_ids,
        "results": results
    }

    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*70}")
    print(f"BATCH TEST COMPLETE")
    print(f"{'='*70}")
    print(f"Processed: {len(results)} dishes")
    print(f"Output: {output_file}")

    # Summary statistics
    total_items = sum(len(r["database_aligned"]["foods"]) for r in results)
    stage_dist = {}
    for r in results:
        for food in r["database_aligned"]["foods"]:
            stage = food.get("alignment_stage", "unknown")
            stage_dist[stage] = stage_dist.get(stage, 0) + 1

    print(f"\nTotal food items: {total_items}")
    print(f"Stage distribution:")
    for stage, count in sorted(stage_dist.items()):
        pct = (count / total_items * 100) if total_items > 0 else 0
        print(f"  {stage}: {count} ({pct:.1f}%)")

    return output_file

if __name__ == "__main__":
    run_batch_test()
