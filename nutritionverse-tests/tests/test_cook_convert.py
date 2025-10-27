"""
Unit tests for raw→cooked conversion system.

Tests:
- Method resolution (explicit, alias, fallback)
- Conversion kernels (hydration, shrinkage, fat rendering, oil uptake)
- Energy clamping
- Atwater validation
- End-to-end conversion
"""
import json
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.nutrition.types import FdcEntry, ConversionFactors
from src.nutrition.utils.method_resolver import resolve_method, normalize_method
from src.nutrition.conversions.cook_convert import (
    convert_from_raw,
    apply_hydration,
    apply_shrinkage,
    apply_fat_rendering,
    apply_oil_uptake,
    extract_conversion_factors
)
from src.nutrition.rails.energy_atwater import (
    validate_atwater_consistency,
    clamp_energy_to_band,
    calculate_atwater_energy
)


def load_test_fixtures():
    """Load test fixtures."""
    fixtures_path = Path(__file__).parent / "fixtures" / "fdc_stubs.json"
    with open(fixtures_path) as f:
        return json.load(f)


def load_cook_config():
    """Load cook_conversions.v2.json."""
    cfg_path = Path(__file__).parent.parent / "src" / "data" / "cook_conversions.v2.json"
    with open(cfg_path) as f:
        return json.load(f)


def load_energy_bands():
    """Load energy_bands.json."""
    bands_path = Path(__file__).parent.parent / "src" / "data" / "energy_bands.json"
    with open(bands_path) as f:
        return json.load(f)


def test_method_resolution():
    """Test cooking method resolution."""
    cfg = load_cook_config()

    print("\n" + "="*80)
    print("TEST: Method Resolution")
    print("="*80)

    # Test 1: Explicit match
    method, reason = resolve_method("rice_white", "boiled", cfg)
    assert method == "boiled", f"Expected 'boiled', got '{method}'"
    assert reason == "explicit", f"Expected 'explicit', got '{reason}'"
    print(f"✓ Explicit match: rice_white + boiled → {method} ({reason})")

    # Test 2: Alias expansion
    method, reason = resolve_method("chicken_breast", "sauteed", cfg)
    assert method == "pan_seared", f"Expected 'pan_seared', got '{method}'"
    assert reason == "alias", f"Expected 'alias', got '{reason}'"
    print(f"✓ Alias expansion: chicken_breast + sauteed → {method} ({reason})")

    # Test 3: Class fallback
    method, reason = resolve_method("rice_white", "unknown", cfg)
    assert method == "boiled", f"Expected 'boiled' (fallback), got '{method}'"
    assert reason == "class_fallback", f"Expected 'class_fallback', got '{reason}'"
    print(f"✓ Class fallback: rice_white + unknown → {method} ({reason})")

    # Test 4: Category fallback
    method, reason = resolve_method("beef_steak", None, cfg)
    # Should get category fallback (meat_poultry → grilled)
    assert reason in ("class_fallback", "category_fallback", "first_available")
    print(f"✓ Category/class fallback: beef_steak + None → {method} ({reason})")

    print("\n✅ All method resolution tests passed!")


def test_conversion_kernels():
    """Test individual conversion kernels."""
    print("\n" + "="*80)
    print("TEST: Conversion Kernels")
    print("="*80)

    # Test hydration kernel (rice example)
    protein, carbs, fat, kcal = apply_hydration(
        protein_100g=7.13,
        carbs_100g=79.95,
        fat_100g=0.66,
        kcal_100g=365.0,
        hydration_factor=2.8
    )
    expected_kcal = 365.0 / 2.8  # ≈130 kcal/100g
    assert abs(kcal - expected_kcal) < 5, f"Hydration: expected ~130 kcal, got {kcal:.1f}"
    print(f"✓ Hydration: 365 kcal/100g ÷ 2.8 → {kcal:.1f} kcal/100g")

    # Test shrinkage kernel (meat example)
    protein, carbs, fat, kcal = apply_shrinkage(
        protein_100g=22.5,
        carbs_100g=0.0,
        fat_100g=2.6,
        kcal_100g=120.0,
        shrinkage_fraction=0.29  # 29% shrinkage
    )
    expected_kcal = 120.0 / 0.71  # ≈169 kcal/100g
    assert abs(kcal - expected_kcal) < 5, f"Shrinkage: expected ~169 kcal, got {kcal:.1f}"
    print(f"✓ Shrinkage: 120 kcal/100g ÷ 0.71 → {kcal:.1f} kcal/100g")

    # Test fat rendering
    fat, kcal = apply_fat_rendering(
        fat_100g=10.0,
        kcal_100g=200.0,
        fat_render_fraction=0.25  # 25% fat lost
    )
    expected_fat = 10.0 * 0.75  # 7.5g
    expected_kcal = 200.0 - (2.5 * 9)  # 200 - 22.5 = 177.5
    assert abs(fat - expected_fat) < 0.5, f"Fat rendering: expected 7.5g fat, got {fat:.1f}g"
    assert abs(kcal - expected_kcal) < 5, f"Fat rendering: expected ~177.5 kcal, got {kcal:.1f}"
    print(f"✓ Fat rendering: 10g fat → {fat:.1f}g, 200 kcal → {kcal:.1f} kcal")

    # Test oil uptake
    fat, kcal = apply_oil_uptake(
        fat_100g=0.5,
        kcal_100g=100.0,
        oil_uptake_g=4.0  # 4g oil absorbed per 100g
    )
    expected_fat = 0.5 + 4.0  # 4.5g
    expected_kcal = 100.0 + (4.0 * 9)  # 100 + 36 = 136
    assert abs(fat - expected_fat) < 0.1, f"Oil uptake: expected 4.5g fat, got {fat:.1f}g"
    assert abs(kcal - expected_kcal) < 1, f"Oil uptake: expected 136 kcal, got {kcal:.1f}"
    print(f"✓ Oil uptake: 0.5g fat → {fat:.1f}g, 100 kcal → {kcal:.1f} kcal")

    print("\n✅ All conversion kernel tests passed!")


def test_energy_clamping():
    """Test energy density clamping."""
    print("\n" + "="*80)
    print("TEST: Energy Clamping")
    print("="*80)

    energy_bands = load_energy_bands()

    # Test 1: Within band (no clamp)
    kcal, clamped = clamp_energy_to_band(135.0, "rice_white.boiled", energy_bands)
    assert not clamped, "Should not clamp value within band"
    assert kcal == 135.0, f"Should preserve value, got {kcal}"
    print(f"✓ Within band: 135 kcal → {kcal} kcal (not clamped)")

    # Test 2: Above band (clamp to max)
    kcal, clamped = clamp_energy_to_band(200.0, "rice_white.boiled", energy_bands)
    assert clamped, "Should clamp value above band"
    assert kcal == 150.0, f"Should clamp to max (150), got {kcal}"
    print(f"✓ Above band: 200 kcal → {kcal} kcal (clamped to max)")

    # Test 3: Below band (clamp to min)
    kcal, clamped = clamp_energy_to_band(80.0, "rice_white.boiled", energy_bands)
    assert clamped, "Should clamp value below band"
    assert kcal == 110.0, f"Should clamp to min (110), got {kcal}"
    print(f"✓ Below band: 80 kcal → {kcal} kcal (clamped to min)")

    # Test 4: No band defined (no clamp)
    kcal, clamped = clamp_energy_to_band(500.0, "unknown_food.unknown", energy_bands)
    assert not clamped, "Should not clamp when no band defined"
    assert kcal == 500.0, f"Should preserve value, got {kcal}"
    print(f"✓ No band: 500 kcal → {kcal} kcal (not clamped)")

    print("\n✅ All energy clamping tests passed!")


def test_atwater_validation():
    """Test Atwater factor validation."""
    print("\n" + "="*80)
    print("TEST: Atwater Validation")
    print("="*80)

    # Test 1: Valid Atwater (within tolerance)
    protein, carbs, fat = 25.0, 30.0, 10.0
    kcal_calculated = calculate_atwater_energy(protein, carbs, fat)
    # 4*25 + 4*30 + 9*10 = 100 + 120 + 90 = 310 kcal

    is_valid, atwater_kcal, deviation = validate_atwater_consistency(
        protein, carbs, fat, kcal_calculated
    )
    assert is_valid, "Should be valid when exact match"
    assert abs(atwater_kcal - 310) < 1, f"Expected 310 kcal, got {atwater_kcal:.1f}"
    print(f"✓ Valid Atwater: P={protein}g, C={carbs}g, F={fat}g → {atwater_kcal:.0f} kcal (deviation: {deviation:.2%})")

    # Test 2: Minor deviation (within 12% tolerance)
    is_valid, atwater_kcal, deviation = validate_atwater_consistency(
        protein, carbs, fat, kcal=320  # Slightly off
    )
    assert is_valid, "Should be valid within 12% tolerance"
    print(f"✓ Minor deviation: stated 320 kcal vs calculated {atwater_kcal:.0f} kcal (deviation: {deviation:.2%})")

    # Test 3: Large deviation (exceeds tolerance)
    is_valid, atwater_kcal, deviation = validate_atwater_consistency(
        protein, carbs, fat, kcal=400  # Way off
    )
    assert not is_valid, "Should be invalid when exceeds 12% tolerance"
    print(f"✓ Large deviation: stated 400 kcal vs calculated {atwater_kcal:.0f} kcal (deviation: {deviation:.2%}) - INVALID")

    print("\n✅ All Atwater validation tests passed!")


def test_end_to_end_conversion():
    """Test complete conversion flow."""
    print("\n" + "="*80)
    print("TEST: End-to-End Conversion")
    print("="*80)

    fixtures = load_test_fixtures()
    cfg = load_cook_config()
    energy_bands = load_energy_bands()

    for test_case in fixtures["conversion_test_cases"]:
        print(f"\nTest: {test_case['test_name']}")
        print(f"  Description: {test_case['description']}")

        # Find raw FDC entry
        raw_entry_dict = next(
            (e for e in fixtures["foundation_foods_raw"] if e["fdc_id"] == test_case["raw_fdc_id"]),
            None
        )
        assert raw_entry_dict, f"Could not find raw entry {test_case['raw_fdc_id']}"

        # Convert to FdcEntry
        raw_entry = FdcEntry(
            fdc_id=raw_entry_dict["fdc_id"],
            core_class=test_case["test_name"].split("_")[0],  # Extract core class from test name
            name=raw_entry_dict["name"],
            source="foundation",
            form="raw",
            method=None,
            protein_100g=raw_entry_dict["protein_value"],
            carbs_100g=raw_entry_dict["carbohydrates_value"],
            fat_100g=raw_entry_dict["total_fat_value"],
            kcal_100g=raw_entry_dict["calories_value"]
        )

        # Perform conversion
        converted = convert_from_raw(
            raw_entry,
            core_class=test_case["test_name"].rsplit("_", 1)[0],  # e.g., "rice_white"
            method=test_case["method"],
            cfg=cfg,
            energy_bands=energy_bands
        )

        # Check result
        expected_kcal = test_case["expected_cooked_kcal_100g"]
        tolerance = test_case.get("tolerance", 0.15)
        deviation = abs(converted.kcal_100g - expected_kcal) / expected_kcal

        print(f"  Raw: {raw_entry.kcal_100g:.1f} kcal/100g")
        print(f"  Converted: {converted.kcal_100g:.1f} kcal/100g")
        print(f"  Expected: {expected_kcal:.1f} kcal/100g")
        print(f"  Deviation: {deviation:.2%} (tolerance: {tolerance:.0%})")
        print(f"  Atwater OK: {converted.atwater_ok}")
        print(f"  Energy clamped: {converted.energy_clamped}")
        print(f"  Provenance: {' → '.join(converted.provenance['conversion_steps'])}")

        assert deviation <= tolerance, f"Deviation {deviation:.2%} exceeds tolerance {tolerance:.0%}"
        assert converted.atwater_ok, "Atwater validation should pass"

        print(f"  ✓ PASS")

    print("\n✅ All end-to-end conversion tests passed!")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*80)
    print("RUNNING ALL CONVERSION UNIT TESTS")
    print("="*80)

    try:
        test_method_resolution()
        test_conversion_kernels()
        test_energy_clamping()
        test_atwater_validation()
        test_end_to_end_conversion()

        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED!")
        print("="*80)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    run_all_tests()
