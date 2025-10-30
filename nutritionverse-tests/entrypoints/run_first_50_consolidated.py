"""
Run First 50 Images (Sorted by Dish ID) - Consolidated Batch Output

This script processes 50 dishes and saves ALL results to a SINGLE JSON file
instead of creating separate directories for each dish.

Output: runs/first_50_batch_<timestamp>.json with:
- metadata: batch info, versions
- results: array of all result objects
- telemetry: array of all telemetry events
- summary: aggregated statistics
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from decimal import Decimal

# Add parent directory to path for pipeline imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import unified pipeline components
from pipeline.config_loader import load_pipeline_config, get_code_git_sha
from pipeline.fdc_index import load_fdc_index
from pipeline.schemas import AlignmentRequest, DetectedFood

# Import alignment adapter directly
from src.adapters.alignment_adapter import AlignmentEngineAdapter
from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def load_metadata(metadata_path):
    """Load metadata.jsonl with dish information."""
    metadata = {}
    with open(metadata_path, 'r') as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                dish_id = entry['id']
                metadata[dish_id] = entry
    return metadata


def get_first_50_dishes_sorted(test_dir):
    """Get first 50 dish IDs sorted alphabetically."""
    dish_images = list(Path(test_dir).glob("dish_*.png"))
    dish_ids = sorted([img.stem for img in dish_images])
    return dish_ids[:3000]  # Return exactly 50


def run_batch_test():
    """Run batch test with consolidated single-file output."""

    # Load environment
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

    # Get first 50 dishes
    print("Finding first 50 dishes (sorted by dish_id)...")
    dish_ids = get_first_50_dishes_sorted(test_dir)

    print(f"Selected {len(dish_ids)} dishes")
    print(f"First dish: {dish_ids[0]}")
    print(f"Last dish: {dish_ids[-1]}")

    # Create alignment adapter (reuse for all dishes)
    adapter = AlignmentEngineAdapter(enable_conversion=True)
    adapter.fdc_db = FDC.adapter

    # Create alignment engine with external configs
    alignment_engine = FDCAlignmentWithConversion(
        class_thresholds=CONFIG.thresholds,
        negative_vocab=CONFIG.neg_vocab,
        feature_flags={**CONFIG.feature_flags, "stageZ_branded_fallback": False},
        variants=CONFIG.variants,
        proxy_rules=CONFIG.proxy_rules,
        category_allowlist=CONFIG.category_allowlist,
        branded_fallbacks=CONFIG.branded_fallbacks,
        unit_to_grams=CONFIG.unit_to_grams,
        fdc_db=adapter.fdc_db
    )

    adapter.alignment_engine = alignment_engine
    adapter.db_available = True
    adapter.config_version = CONFIG.config_version
    adapter.config_fingerprint = CONFIG.config_fingerprint

    # Collect all results and telemetry
    all_results = []
    all_telemetry = []
    stage_summary = {}
    failed_dishes = []

    # Process each dish
    print(f"\n{'='*70}")
    print(f"BATCH TEST: First 50 Dishes (Sorted by ID)")
    print(f"{'='*70}\n")

    for idx, dish_id in enumerate(dish_ids, 1):
        print(f"[{idx}/50] Processing {dish_id}...")

        # Get metadata
        dish_meta = metadata.get(dish_id)
        if not dish_meta:
            print(f"  WARNING: No metadata for {dish_id}")
            failed_dishes.append({"dish_id": dish_id, "error": "No metadata"})
            continue

        # Convert metadata ingredients to prediction format
        ingredients = dish_meta.get("ingredients", [])
        if not ingredients:
            print(f"  WARNING: No ingredients for {dish_id}")
            failed_dishes.append({"dish_id": dish_id, "error": "No ingredients"})
            continue

        prediction = {
            "foods": [
                {
                    "name": ingr["name"],
                    "form": "raw",
                    "mass_g": ingr["grams"],
                    "confidence": 0.85,
                    "modifiers": []
                }
                for ingr in ingredients
            ]
        }

        # Run alignment
        try:
            aligned_result = adapter.align_prediction_batch(prediction)

            # Build result object
            result_obj = {
                "image_id": dish_id,
                "foods": aligned_result.get("foods", []),
                "totals": aligned_result.get("totals", {}),
                "telemetry_summary": aligned_result.get("telemetry_summary", {}),
                "code_git_sha": CODE_SHA,
                "config_version": CONFIG.config_version,
                "fdc_index_version": FDC.version
            }

            all_results.append(result_obj)

            # Extract telemetry from each food
            for food_idx, food in enumerate(aligned_result.get("foods", [])):
                telemetry = food.get("telemetry", {})
                if telemetry:
                    # Add context
                    telemetry["image_id"] = dish_id
                    telemetry["food_idx"] = food_idx
                    telemetry["query"] = food.get("name", "")
                    all_telemetry.append(telemetry)

                    # Aggregate stage counts from telemetry
                    stage = telemetry.get("alignment_stage")
                    if stage:
                        stage_summary[stage] = stage_summary.get(stage, 0) + 1

            print(f"  Foods: {len(aligned_result.get('foods', []))}")

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed_dishes.append({"dish_id": dish_id, "error": str(e)})

    # Build consolidated report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    total_items = sum(stage_summary.values())

    report = {
        "metadata": {
            "timestamp": timestamp,
            "batch_name": "first_50_dishes",
            "total_dishes": len(dish_ids),
            "successful_dishes": len(all_results),
            "failed_dishes": len(failed_dishes),
            "code_git_sha": CODE_SHA,
            "config_version": CONFIG.config_version,
            "fdc_index_version": FDC.version
        },
        "results": all_results,
        "telemetry": all_telemetry,
        "summary": {
            "stage_counts": stage_summary,
            "total_food_items": total_items,
            "conversion_rate": (
                sum(1 for t in all_telemetry if t.get("conversion_applied")) / max(total_items, 1)
            ),
            "stage5_proxy_count": stage_summary.get("stage5_proxy_alignment", 0),
            "stage0_no_candidates_count": stage_summary.get("stage0_no_candidates", 0)
        },
        "failed_dishes": failed_dishes
    }

    # Save to single JSON file
    runs_dir = Path("runs")
    runs_dir.mkdir(exist_ok=True)

    output_file = runs_dir / f"first_50_batch_{timestamp}.json"
    print(f"\nSaving consolidated results to: {output_file}")

    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2, cls=DecimalEncoder)

    # Print final summary
    print(f"\n{'='*70}")
    print(f"BATCH TEST COMPLETE")
    print(f"{'='*70}")
    print(f"Processed: {len(dish_ids)} dishes")
    print(f"Successful: {len(all_results)}")
    print(f"Failed: {len(failed_dishes)}")
    print(f"Total food items: {total_items}")
    print(f"\nStage distribution:")
    for stage, count in sorted(stage_summary.items()):
        pct = (count / total_items * 100) if total_items > 0 else 0
        print(f"  {stage}: {count} ({pct:.1f}%)")

    print(f"\n✓ Results saved to: {output_file}")
    print(f"  - {len(all_results)} result objects")
    print(f"  - {len(all_telemetry)} telemetry events")
    print()


if __name__ == "__main__":
    run_batch_test()
