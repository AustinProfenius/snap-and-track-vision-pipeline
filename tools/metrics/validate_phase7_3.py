#!/usr/bin/env python3
"""
Phase 7.3 Validation Metrics

Computes batch metrics from a results JSON:
- Dish Name Accuracy (Jaccard >= 0.6)
- Item Exact Match Rate (name canonical equality)
- Calorie MAPE (dish-level)
- Mass MAPE (item-level)
- Salad subgroup metrics (if stage5b present)

Usage:
  python tools/metrics/validate_phase7_3.py --file path/to/batch.json

Pass Criteria:
- DishName_Jaccard>=0.6_rate: >=0.90
- Item_ExactMatch_Precision_mean: >=0.85
- Calories_MAPE_mean: <=0.15
- Mass_MAPE_median: <=0.25
- FruitVeg_Mass_MAPE_median: <=0.15
- Salad_Calories_MAPE_mean: <=0.25
"""

import argparse
import json
import statistics
from typing import List, Dict, Any, Optional


def jaccard(a: set, b: set) -> float:
    """Compute Jaccard similarity between two sets."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


def mape(y_true: float, y_pred: float) -> Optional[float]:
    """Compute Mean Absolute Percentage Error."""
    if y_true == 0:
        return 0.0 if y_pred == 0 else 1.0
    return abs(y_true - y_pred) / abs(y_true)


def canonical_tokens(name: str) -> List[str]:
    """Extract canonical tokens from food name."""
    return [t for t in (name or "").lower().replace(",", " ").split() if t]


def flatten_predicted_items(db_aligned_foods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Flatten predicted foods, handling stage5b expanded_foods.

    Args:
        db_aligned_foods: List of aligned foods from database

    Returns:
        Flattened list with expanded foods unwrapped
    """
    out = []
    for f in db_aligned_foods:
        if "expanded_foods" in f and f["expanded_foods"]:
            out.extend(f["expanded_foods"])
        else:
            out.append(f)
    return out


def main():
    parser = argparse.ArgumentParser(
        description="Validate Phase 7.3 batch results"
    )
    parser.add_argument("--file", required=True, help="Path to batch results JSON")
    args = parser.parse_args()

    # Load results
    with open(args.file, "r") as f:
        data = json.load(f)

    results = data.get("results", [])
    if not results:
        print("No results found in file.")
        return

    # Metrics accumulators
    dish_name_pass = []
    item_exact = []
    cal_mape_vals = []
    mass_mape_vals = []

    salad_cal_mape = []
    fruitveg_mass = []

    # Process each dish
    for r in results:
        gt = r.get("ground_truth", {})
        pred = r.get("database_aligned", {})

        # Dish name Jaccard over token sets (all food names)
        gt_names = [(f.get("name") or "").lower() for f in gt.get("foods", [])]
        pred_foods = flatten_predicted_items(pred.get("foods", []))
        pred_names = [(f.get("name") or "").lower() for f in pred_foods]

        jac = jaccard(set(gt_names), set(pred_names))
        dish_name_pass.append(1 if jac >= 0.6 else 0)

        # Item exact match (precision over predicted)
        exact_hits = sum(1 for f in pred_names if f in gt_names)
        precision = exact_hits / max(1, len(pred_names))
        item_exact.append(precision)

        # Calorie MAPE (dish-level totals)
        gt_cal = gt.get("total_calories", 0.0)
        pred_cal = pred.get("totals", {}).get("calories", 0.0)
        if gt_cal is not None and pred_cal is not None:
            e = mape(gt_cal, pred_cal)
            if e is not None:
                cal_mape_vals.append(e)

        # Mass MAPE (item-level)
        for pf in pred_foods:
            pm = pf.get("mass_g", 0.0)
            # Map to same name in GT by first match
            match = next(
                (g for g in gt.get("foods", [])
                 if (g.get("name") or "").lower() == (pf.get("name") or "").lower()),
                None
            )
            gm = match.get("mass_g", 0.0) if match else 0.0
            if pm is not None and gm is not None:
                e = mape(gm, pm)
                if e is not None:
                    mass_mape_vals.append(e)

                    # Fruit/veg bucket (rough heuristic)
                    name_lower = (pf.get("name") or "").lower()
                    is_produce = any(
                        k in name_lower
                        for k in [
                            "lettuce", "tomato", "cucumber", "spinach",
                            "broccoli", "brussels", "yam", "melon", "berries",
                            "avocado", "cauliflower", "romaine", "greens"
                        ]
                    )
                    if is_produce:
                        fruitveg_mass.append(e)

        # Salad subgroup (if any stage5b)
        has_stage5b = any(
            f.get("alignment_stage") == "stage5b_salad_decomposition"
            for f in pred.get("foods", [])
        )
        if has_stage5b and gt_cal is not None and pred_cal is not None:
            e = mape(gt_cal, pred_cal)
            if e is not None:
                salad_cal_mape.append(e)

    # Compute summary statistics
    report = {
        "DishName_Jaccard>=0.6_rate": (
            sum(dish_name_pass) / max(1, len(dish_name_pass))
        ),
        "Item_ExactMatch_Precision_mean": (
            statistics.mean(item_exact) if item_exact else None
        ),
        "Calories_MAPE_mean": (
            statistics.mean(cal_mape_vals) if cal_mape_vals else None
        ),
        "Mass_MAPE_median": (
            statistics.median(mass_mape_vals) if mass_mape_vals else None
        ),
        "FruitVeg_Mass_MAPE_median": (
            statistics.median(fruitveg_mass) if fruitveg_mass else None
        ),
        "Salad_Calories_MAPE_mean": (
            statistics.mean(salad_cal_mape) if salad_cal_mape else None
        ),
        "Counts": {
            "dishes": len(results),
            "pred_items_total": sum(
                len(flatten_predicted_items(r.get("database_aligned", {}).get("foods", [])))
                for r in results
            ),
            "salads_decomposed": len(salad_cal_mape)
        },
        "PassThresholds": {
            "DishName_Jaccard>=0.6_rate": ">=0.90",
            "Item_ExactMatch_Precision_mean": ">=0.85",
            "Calories_MAPE_mean": "<=0.15",
            "Mass_MAPE_median": "<=0.25",
            "FruitVeg_Mass_MAPE_median": "<=0.15",
            "Salad_Calories_MAPE_mean": "<=0.25"
        }
    }

    # Print JSON report
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
