"""
Run First 50 Images (Sorted by Dish ID) - Batch Harness Test
Uses unified pipeline for reproducibility.

This script:
1. Loads test dataset from food-nutrients/test
2. Sorts images by dish_id
3. Processes first 50 images using pipeline.run_once()
4. Outputs results to runs/<timestamp>/ with version tracking
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path for pipeline imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import unified pipeline
from pipeline.run import run_once
from pipeline.config_loader import load_pipeline_config, get_code_git_sha
from pipeline.fdc_index import load_fdc_index
from pipeline.schemas import AlignmentRequest, DetectedFood

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
    return dish_ids[:2000]

def run_batch_test():
    """Run batch test on first 50 dishes using unified pipeline."""

    # Load environment from repo root
    repo_root = Path(__file__).parent.parent.parent
    env_path = repo_root / ".env"
    load_dotenv(dotenv_path=env_path, override=True)

    # Paths
    test_dir = Path("/Users/austinprofenius/snapandtrack-model-testing/food-nutrients/test")
    metadata_path = Path("/Users/austinprofenius/snapandtrack-model-testing/food-nutrients/metadata.jsonl")

    # Load pipeline components ONCE
    print("Loading pipeline configuration...")
    configs_path = repo_root / "configs"
    CONFIG = load_pipeline_config(root=str(configs_path))
    print(f"  Config version: {CONFIG.config_version}")

    print("Loading FDC index...")
    FDC = load_fdc_index()
    print(f"  FDC version: {FDC.version}")

    CODE_SHA = get_code_git_sha()
    print(f"  Code SHA: {CODE_SHA}")

    # Load metadata
    print("\nLoading metadata...")
    metadata = load_metadata(metadata_path)

    # Get first 50 dishes sorted by ID
    print("Finding first 50 dishes (sorted by dish_id)...")
    dish_ids = get_first_50_dishes_sorted(test_dir)

    print(f"Selected {len(dish_ids)} dishes")
    print(f"First dish: {dish_ids[0]}")
    print(f"Last dish: {dish_ids[-1]}")

    # Process each dish
    print(f"\n{'='*70}")
    print(f"BATCH TEST: First 50 Dishes (Sorted by ID)")
    print(f"{'='*70}\n")

    stage_summary = {}

    for idx, dish_id in enumerate(dish_ids):
        print(f"[{idx+1}/50] Processing {dish_id}...")

        # Get metadata
        dish_meta = metadata.get(dish_id)
        if not dish_meta:
            print(f"  WARNING: No metadata for {dish_id}")
            continue

        # Convert metadata ingredients to DetectedFood objects
        ingredients = dish_meta.get("ingredients", [])
        if not ingredients:
            print(f"  WARNING: No ingredients for {dish_id}")
            continue

        detected_foods = [
            DetectedFood(
                name=ingr["name"],
                form="raw",  # Default to raw
                mass_g=ingr["grams"],
                confidence=0.85
            )
            for ingr in ingredients
        ]

        # Create alignment request
        request = AlignmentRequest(
            image_id=dish_id,
            foods=detected_foods,
            config_version=CONFIG.config_version
        )

        # Run unified pipeline
        try:
            result = run_once(
                request=request,
                cfg=CONFIG,
                fdc_index=FDC,
                allow_stage_z=False,  # Never allow Stage-Z in evaluations
                code_git_sha=CODE_SHA
            )

            # Print summary
            print(f"  Foods: {len(result.foods)}, Stages: {result.telemetry_summary['stage_counts']}")

            # Aggregate stage counts
            for stage, count in result.telemetry_summary['stage_counts'].items():
                stage_summary[stage] = stage_summary.get(stage, 0) + count

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    # Print final summary
    print(f"\n{'='*70}")
    print(f"BATCH TEST COMPLETE")
    print(f"{'='*70}")
    print(f"Processed: {len(dish_ids)} dishes")
    print(f"\nStage distribution:")
    total_items = sum(stage_summary.values())
    for stage, count in sorted(stage_summary.items()):
        pct = (count / total_items * 100) if total_items > 0 else 0
        print(f"  {stage}: {count} ({pct:.1f}%)")

    print(f"\nResults saved to: runs/<timestamp>/results.jsonl")
    print(f"Telemetry saved to: runs/<timestamp>/telemetry.jsonl")

if __name__ == "__main__":
    run_batch_test()
