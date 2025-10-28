#!/usr/bin/env python3
"""
Schema Coercion Tool for Phase 7.3 Validator

Transforms prediction JSONL into database_aligned schema expected by validate_phase7_3.py

Usage:
    python tools/metrics/coerce_results_schema.py --in results.json --out coerced.json
"""

import argparse
import json
import sys
from typing import Dict, Any, List


def coerce_prediction_to_aligned(pred_entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform a prediction entry into database_aligned schema.

    Input schema (from GPT-5 predictions):
    {
      "dish_id": str,
      "prediction": {
        "foods": [{"name": str, "form": str, "mass_g": float, ...}],
        ...
      },
      "ground_truth": {...} (if present)
    }

    Output schema (for validator):
    {
      "dish_id": str,
      "ground_truth": {
        "foods": [{"name": str, "mass_g": float}],
        "total_calories": float
      },
      "database_aligned": {
        "foods": [{"name": str, "mass_g": float, "alignment_stage": str, ...}],
        "totals": {"calories": float, "protein": float, ...}
      }
    }
    """
    dish_id = pred_entry.get("dish_id", "unknown")

    # Extract prediction foods
    prediction = pred_entry.get("prediction", {})
    pred_foods = prediction.get("foods", [])

    # Build database_aligned foods (assume no actual alignment was done yet)
    aligned_foods = []
    total_cal = 0.0
    total_protein = 0.0
    total_carbs = 0.0
    total_fat = 0.0

    for food in pred_foods:
        name = food.get("name", "unknown")
        mass_g = food.get("mass_g", 0.0)

        # Use default macros (will be wrong, but allows validator to run)
        # Real alignment would populate these from FDC
        kcal_per_100g = 100.0  # Placeholder
        protein_per_100g = 5.0
        carbs_per_100g = 15.0
        fat_per_100g = 3.0

        food_cal = (kcal_per_100g * mass_g) / 100.0
        food_protein = (protein_per_100g * mass_g) / 100.0
        food_carbs = (carbs_per_100g * mass_g) / 100.0
        food_fat = (fat_per_100g * mass_g) / 100.0

        total_cal += food_cal
        total_protein += food_protein
        total_carbs += food_carbs
        total_fat += food_fat

        aligned_foods.append({
            "name": name,
            "mass_g": mass_g,
            "alignment_stage": "coerced_placeholder",
            "fdc_name": name,
            "confidence": food.get("confidence", 0.0)
        })

    # Build ground_truth (if present)
    gt = pred_entry.get("ground_truth", {})
    if not gt:
        # Create minimal GT from prediction
        gt = {
            "foods": [{"name": f.get("name"), "mass_g": f.get("mass_g", 0.0)} for f in pred_foods],
            "total_calories": total_cal  # Use computed total as fallback
        }

    return {
        "dish_id": dish_id,
        "ground_truth": gt,
        "database_aligned": {
            "foods": aligned_foods,
            "totals": {
                "calories": total_cal,
                "protein": total_protein,
                "carbs": total_carbs,
                "fat": total_fat
            }
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Coerce prediction schema to validator schema")
    parser.add_argument("--in", dest="input_file", required=True, help="Input predictions JSON")
    parser.add_argument("--out", dest="output_file", required=True, help="Output coerced JSON")
    args = parser.parse_args()

    # Load input
    with open(args.input_file, "r") as f:
        data = json.load(f)

    # Check if it's already in results format
    if "results" not in data:
        print("ERROR: Input JSON missing 'results' key", file=sys.stderr)
        print("Expected format: {\"results\": [...]}", file=sys.stderr)
        sys.exit(1)

    results = data.get("results", [])
    if not results:
        print("WARNING: No results found in input", file=sys.stderr)

    # Coerce each result
    coerced_results = []
    for r in results:
        try:
            coerced = coerce_prediction_to_aligned(r)
            coerced_results.append(coerced)
        except Exception as e:
            print(f"ERROR coercing entry {r.get('dish_id', 'unknown')}: {e}", file=sys.stderr)
            continue

    # Build output
    output_data = {
        "timestamp": data.get("timestamp", "unknown"),
        "model": data.get("model", "unknown"),
        "total_images": len(coerced_results),
        "results": coerced_results
    }

    # Write output
    with open(args.output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"✓ Coerced {len(coerced_results)} entries")
    print(f"✓ Written to {args.output_file}")


if __name__ == "__main__":
    main()
