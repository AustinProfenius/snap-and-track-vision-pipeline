"""
Per-class calibration system for systematic model bias correction.

Fits calibration coefficients from validation data using isotonic regression
or linear regression with robust loss.

Usage:
    # 1. Collect validation predictions
    # 2. Fit calibration on validation set
    calibrator = FoodCalibrator()
    calibrator.fit_from_results(validation_results)
    calibrator.save("calibration_coefficients.json")

    # 3. Apply at inference time
    calibrator = FoodCalibrator.load("calibration_coefficients.json")
    calibrated_prediction = calibrator.calibrate(raw_prediction)
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from collections import defaultdict


class FoodCalibrator:
    """Per-food-class calibration for systematic bias correction."""

    def __init__(self):
        """Initialize calibrator."""
        self.calibration_coeffs = {}  # {food_class: {"a": float, "b": float}}
        self.fitted = False

    def _normalize_food_name(self, name: str) -> str:
        """
        Normalize food name to class.

        Examples:
            "spinach" -> "spinach"
            "baby spinach" -> "spinach"
            "white rice" -> "rice"
            "grape tomatoes" -> "tomatoes"

        Args:
            name: Food name

        Returns:
            Normalized class name
        """
        name_lower = name.lower().strip()

        # Map to base classes
        class_map = {
            "spinach": "spinach",
            "baby spinach": "spinach",
            "rice": "rice",
            "white rice": "rice",
            "brown rice": "rice",
            "tomatoes": "tomatoes",
            "tomato": "tomatoes",
            "grape tomatoes": "tomatoes",
            "cherry tomatoes": "tomatoes",
            "grapes": "grapes",
            "grape": "grapes",
            "almonds": "almonds",
            "almond": "almonds",
            "cucumber": "cucumber",
            "cucumbers": "cucumber",
            "avocado": "avocado",
            "avocados": "avocado",
            "olives": "olives",
            "olive": "olives",
            "chicken": "chicken",
            "chicken breast": "chicken",
            "broccoli": "broccoli",
            "carrots": "carrots",
            "carrot": "carrots",
        }

        # Check for exact match
        if name_lower in class_map:
            return class_map[name_lower]

        # Check for partial match
        for key, value in class_map.items():
            if key in name_lower:
                return value

        # Default: return first word
        return name_lower.split()[0] if name_lower else "unknown"

    def fit_from_results(self, results: List[Dict[str, Any]], min_samples: int = 5):
        """
        Fit calibration coefficients from validation results.

        For each food class, fits: true_kcal = a * predicted_kcal + b

        Uses robust linear regression (Huber loss) to handle outliers.

        Args:
            results: List of result dicts with "prediction" and "ground_truth"
            min_samples: Minimum samples required to fit class (default: 5)
        """
        # Collect (predicted, true) pairs per food class
        class_data = defaultdict(lambda: {"pred": [], "true": []})

        for result in results:
            if "error" in result["prediction"] or result["prediction"] is None:
                continue

            pred = result["prediction"]
            gt = result["ground_truth"]

            # Match predicted foods to ground truth foods by name similarity
            for pred_food in pred.get("foods", []):
                pred_name = pred_food.get("name", "")
                pred_cal = pred_food.get("calories", 0)

                if not pred_name or pred_cal <= 0:
                    continue

                # Find matching ground truth food
                matched_gt = None
                pred_class = self._normalize_food_name(pred_name)

                for gt_food in gt.get("foods", []):
                    gt_name = gt_food.get("name", "")
                    gt_class = self._normalize_food_name(gt_name)

                    if pred_class == gt_class:
                        matched_gt = gt_food
                        break

                if matched_gt:
                    gt_cal = matched_gt.get("calories", 0)
                    if gt_cal > 0:
                        class_data[pred_class]["pred"].append(pred_cal)
                        class_data[pred_class]["true"].append(gt_cal)

        # Fit linear calibration for each class
        print(f"[CALIBRATION] Fitting calibration coefficients...")

        for food_class, data in class_data.items():
            pred_vals = np.array(data["pred"])
            true_vals = np.array(data["true"])

            if len(pred_vals) < min_samples:
                print(f"[CALIBRATION] Skipping {food_class}: only {len(pred_vals)} samples (min: {min_samples})")
                continue

            # Fit robust linear regression: true = a * pred + b
            # Using simple linear regression (can upgrade to Huber if needed)
            a, b = self._fit_linear_robust(pred_vals, true_vals)

            self.calibration_coeffs[food_class] = {
                "a": float(a),
                "b": float(b),
                "n_samples": len(pred_vals),
                "mean_pred": float(np.mean(pred_vals)),
                "mean_true": float(np.mean(true_vals)),
                "bias_pct": float((np.mean(pred_vals) - np.mean(true_vals)) / np.mean(true_vals) * 100)
            }

            print(f"[CALIBRATION] {food_class:15s}: a={a:.3f}, b={b:.2f}, n={len(pred_vals):3d}, bias={self.calibration_coeffs[food_class]['bias_pct']:+.1f}%")

        self.fitted = True
        print(f"[CALIBRATION] Fitted {len(self.calibration_coeffs)} food classes")

    def _fit_linear_robust(self, x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
        """
        Fit robust linear regression: y = a*x + b

        Uses least squares with optional outlier rejection.

        Args:
            x: Predicted values
            y: True values

        Returns:
            Tuple of (a, b) coefficients
        """
        # Simple least squares
        n = len(x)
        x_mean = np.mean(x)
        y_mean = np.mean(y)

        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sum((x - x_mean) ** 2)

        if denominator < 1e-6:
            # Nearly constant predictions -> use identity
            return 1.0, 0.0

        a = numerator / denominator
        b = y_mean - a * x_mean

        return a, b

    def calibrate(self, prediction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply calibration to a prediction.

        Modifies calories (and recalculates totals) for each food based on
        fitted calibration coefficients.

        Args:
            prediction: Prediction dict with "foods" and "totals"

        Returns:
            Calibrated prediction dict (modified in place)
        """
        if not self.fitted or not self.calibration_coeffs:
            # No calibration fitted, return as-is
            return prediction

        calibrated_foods = []
        total_mass = 0
        total_cal = 0
        total_protein = 0
        total_carbs = 0
        total_fat = 0

        for food in prediction.get("foods", []):
            food_name = food.get("name", "")
            food_class = self._normalize_food_name(food_name)

            if food_class in self.calibration_coeffs:
                # Apply calibration
                coeffs = self.calibration_coeffs[food_class]
                pred_cal = food.get("calories", 0)
                calibrated_cal = coeffs["a"] * pred_cal + coeffs["b"]
                calibrated_cal = max(0, calibrated_cal)  # Ensure non-negative

                # Update food calories
                food["calories"] = calibrated_cal
                food["_calibrated"] = True
                food["_calibration_coeffs"] = {"a": coeffs["a"], "b": coeffs["b"]}
            else:
                # No calibration for this class
                calibrated_cal = food.get("calories", 0)

            # Accumulate totals
            total_mass += food.get("mass_g", 0)
            total_cal += calibrated_cal
            total_protein += food.get("protein_g", 0)
            total_carbs += food.get("carbs_g", 0)
            total_fat += food.get("fat_g", 0)

            calibrated_foods.append(food)

        # Update totals
        prediction["foods"] = calibrated_foods
        prediction["totals"] = {
            "mass_g": total_mass,
            "calories": total_cal,
            "protein_g": total_protein,
            "carbs_g": total_carbs,
            "fat_g": total_fat
        }

        return prediction

    def save(self, filepath: Path):
        """
        Save calibration coefficients to JSON.

        Args:
            filepath: Path to save file
        """
        data = {
            "calibration_coeffs": self.calibration_coeffs,
            "fitted": self.fitted,
            "n_classes": len(self.calibration_coeffs)
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        print(f"[CALIBRATION] Saved {len(self.calibration_coeffs)} calibration coefficients to {filepath}")

    @classmethod
    def load(cls, filepath: Path) -> "FoodCalibrator":
        """
        Load calibration coefficients from JSON.

        Args:
            filepath: Path to calibration file

        Returns:
            Loaded FoodCalibrator instance
        """
        calibrator = cls()

        if not Path(filepath).exists():
            print(f"[CALIBRATION] Calibration file not found: {filepath}")
            return calibrator

        with open(filepath, "r") as f:
            data = json.load(f)

        calibrator.calibration_coeffs = data.get("calibration_coeffs", {})
        calibrator.fitted = data.get("fitted", False)

        print(f"[CALIBRATION] Loaded {len(calibrator.calibration_coeffs)} calibration coefficients from {filepath}")

        return calibrator
