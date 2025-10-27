#!/usr/bin/env python3
"""
Fit per-class calibration coefficients from validation results.

Usage:
    python scripts/fit_calibration.py results/validation_results.json

This will:
1. Load validation results
2. Fit per-class calibration: true_kcal = a * predicted_kcal + b
3. Save coefficients to calibration_coefficients.json
4. Display calibration statistics
"""
import sys
import json
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.calibration import FoodCalibrator


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/fit_calibration.py <results_json_file>")
        print("\nExample:")
        print("  python scripts/fit_calibration.py results/gpt_5_100images_20251020_203848.json")
        sys.exit(1)

    results_file = Path(sys.argv[1])

    if not results_file.exists():
        print(f"Error: Results file not found: {results_file}")
        sys.exit(1)

    print(f"Loading results from: {results_file}")

    # Load results
    with open(results_file, "r") as f:
        data = json.load(f)

    results = data.get("results", [])
    print(f"Loaded {len(results)} results")

    # Fit calibration
    print("\nFitting calibration coefficients...")
    calibrator = FoodCalibrator()
    calibrator.fit_from_results(results, min_samples=3)

    # Save calibration
    output_file = Path("calibration_coefficients.json")
    calibrator.save(output_file)

    print(f"\n✅ Calibration complete! Saved to {output_file}")
    print(f"\nTo use calibration, load it in your inference pipeline:")
    print(f"  from src.core.calibration import FoodCalibrator")
    print(f"  calibrator = FoodCalibrator.load('calibration_coefficients.json')")
    print(f"  calibrated_pred = calibrator.calibrate(prediction)")


if __name__ == "__main__":
    main()
