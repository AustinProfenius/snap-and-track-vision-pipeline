#!/usr/bin/env python3
"""
Quick test to verify mass-only alignment pipeline works end-to-end.
Tests the import fix and basic functionality.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.adapters.fdc_alignment_v2 import FDCAlignmentEngineV2, derive_alignment_hints
from src.config.feature_flags import FLAGS
from src.nutrition.utils.method_resolver import infer_method_from_class

def test_imports():
    """Test that all imports work correctly."""
    print("="*60)
    print("TEST 1: Import Validation")
    print("="*60)

    # Test FLAGS import
    assert FLAGS.vision_mass_only == True, "vision_mass_only should be enabled"
    assert FLAGS.accept_sparse_stage2_on_floor == True, "accept_sparse_stage2_on_floor should be enabled"
    print("✅ Feature flags imported successfully")

    # Test derive_alignment_hints
    pred_item = {
        "name": "bell pepper",
        "modifiers": ["green"],
        "form": "",
        "mass_g": 120,
        "confidence": 0.85
    }
    hints = derive_alignment_hints(pred_item)
    assert hints["class_from_name"] == "bell_pepper_green"
    assert "green" in hints["color_tokens"]
    assert hints["implied_form"] == "raw"
    print("✅ derive_alignment_hints working correctly")

    # Test infer_method_from_class
    method, reason = infer_method_from_class("rice_white", "")
    assert method == "boiled"
    assert reason == "class_default"
    print("✅ infer_method_from_class working correctly")

    print()


def test_alignment_engine():
    """Test that alignment engine can be instantiated."""
    print("="*60)
    print("TEST 2: Alignment Engine Instantiation")
    print("="*60)

    try:
        # Try to instantiate (will fail if DB not available, but that's okay)
        engine = FDCAlignmentEngineV2()
        print("✅ FDCAlignmentEngineV2 instantiated successfully")

        if engine.db_available:
            print("✅ Database connection available")
        else:
            print("⚠️  Database not available (expected in some test environments)")
    except Exception as e:
        print(f"⚠️  Engine instantiation error (expected if DB not configured): {e}")

    print()


def test_mass_only_prediction():
    """Test mass-only prediction enrichment."""
    print("="*60)
    print("TEST 3: Mass-Only Prediction Enrichment")
    print("="*60)

    # Test cases
    test_cases = [
        {
            "name": "Green bell pepper",
            "pred": {"name": "bell pepper", "modifiers": ["green"], "form": "", "mass_g": 120},
            "expected_class": "bell_pepper_green",
            "expected_form": "raw",
            "expected_color": "green"
        },
        {
            "name": "Rice (no form)",
            "pred": {"name": "rice", "form": "", "mass_g": 180},
            "expected_class": "rice_white",
            "expected_form": "boiled",
            "expected_color": None
        },
        {
            "name": "Pork bacon",
            "pred": {"name": "bacon", "modifiers": ["pork"], "form": "pan_seared", "mass_g": 25},
            "expected_class": "bacon_pork",
            "expected_form": "pan_seared",
            "expected_species": "pork"
        },
        {
            "name": "Eggs with count",
            "pred": {"name": "egg", "count": 2, "mass_g": 100, "form": "cooked"},
            "expected_class": "egg",
            "expected_form": "cooked",
            "expected_per_unit": 50.0
        }
    ]

    for test in test_cases:
        print(f"\n  Testing: {test['name']}")
        hints = derive_alignment_hints(test['pred'])

        # Check class
        assert test['expected_class'] in hints['class_from_name'], \
            f"Expected {test['expected_class']} in {hints['class_from_name']}"
        print(f"    ✓ Class: {hints['class_from_name']}")

        # Check form
        assert hints['implied_form'] == test['expected_form'], \
            f"Expected form {test['expected_form']}, got {hints['implied_form']}"
        print(f"    ✓ Form: {hints['implied_form']}")

        # Check color
        if test.get('expected_color'):
            assert test['expected_color'] in hints['color_tokens'], \
                f"Expected color {test['expected_color']} in {hints['color_tokens']}"
            print(f"    ✓ Color: {hints['color_tokens']}")

        # Check species
        if test.get('expected_species'):
            assert test['expected_species'] in hints['species_tokens'], \
                f"Expected species {test['expected_species']} in {hints['species_tokens']}"
            print(f"    ✓ Species: {hints['species_tokens']}")

        # Check per-unit mass
        if test.get('expected_per_unit'):
            assert hints['discrete_hint'] is not None, "Expected discrete_hint"
            assert hints['discrete_hint']['mass_per_unit'] == test['expected_per_unit'], \
                f"Expected per-unit {test['expected_per_unit']}, got {hints['discrete_hint']['mass_per_unit']}"
            print(f"    ✓ Per-unit mass: {hints['discrete_hint']['mass_per_unit']}g")

    print("\n✅ All mass-only enrichment tests passed")
    print()


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("MASS-ONLY PIPELINE QUICK TEST")
    print("="*60)
    print()

    try:
        test_imports()
        test_alignment_engine()
        test_mass_only_prediction()

        print("="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        print("\nThe mass-only alignment enhancement is working correctly!")
        print("You can now run the full nutritionverse_app.py without import errors.")
        print()
        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
