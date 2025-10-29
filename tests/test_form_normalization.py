"""
Comprehensive tests for form normalization and validation.

Tests the auto-fix behavior of normalize_form() to ensure it never fails
and always returns a valid enum value.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.nutritionverse_prompts import (
    normalize_form,
    validate_mass_only_response,
    VALID_FORMS,
    FORM_ALIASES
)


def test_valid_forms_passthrough():
    """Test that valid forms pass through unchanged."""
    for form in VALID_FORMS:
        result = normalize_form(form)
        assert result == form, f"Valid form '{form}' should pass through unchanged, got '{result}'"
        assert result in VALID_FORMS, f"Result '{result}' not in VALID_FORMS"


def test_exact_alias_mapping():
    """Test that exact aliases map correctly."""
    # Observed failures from gpt_5_10images_20251024_084418.json
    test_cases = {
        "whole": "raw",
        "salad": "raw",
        "cooked strips": "cooked",
        "toasted": "baked",
        "fresh": "raw",
        "pieces": "cooked",
        "strips": "cooked",
        "halved, toasted": "baked",

        # Original aliases
        "sauteed": "pan_seared",
        "sautéed": "pan_seared",
        "microwaved": "steamed",
        "air_fried": "baked",

        # Additional common variants
        "deep-fried": "fried",
        "stir-fried": "pan_seared",
        "oven-baked": "baked",
    }

    for input_form, expected in test_cases.items():
        result = normalize_form(input_form)
        assert result == expected, f"'{input_form}' should map to '{expected}', got '{result}'"
        assert result in VALID_FORMS, f"Result '{result}' not in VALID_FORMS"


def test_heuristic_keyword_matching():
    """Test that heuristic keyword matching works for non-exact matches."""
    test_cases = {
        # Grilling keywords
        "grilled chicken": "grilled",
        "char-grilled": "grilled",

        # Frying keywords
        "deep fried": "fried",
        "pan fried onions": "fried",

        # Baking keywords
        "oven toasted": "baked",
        "air fried wings": "baked",

        # Searing keywords
        "seared salmon": "pan_seared",
        "sautéed vegetables": "pan_seared",

        # Breading keywords
        "breaded cutlet": "breaded",
        "battered fish": "breaded",
        "crusted chicken": "breaded",

        # Roasting keywords
        "oven roasted": "roasted",
        "broiled fish": "roasted",

        # Steaming keywords
        "steamed broccoli": "steamed",
        "microwaved rice": "steamed",

        # Raw keywords
        "raw vegetables": "raw",
        "fresh lettuce": "raw",
        "whole tomato": "raw",
        "uncooked fish": "raw",

        # Cut descriptors (no cooking method → raw)
        "sliced cucumber": "raw",
        "chopped onion": "raw",
        "diced tomatoes": "raw",
        "shredded carrots": "raw",
    }

    for input_form, expected in test_cases.items():
        result = normalize_form(input_form)
        assert result == expected, f"'{input_form}' should map to '{expected}', got '{result}'"
        assert result in VALID_FORMS, f"Result '{result}' not in VALID_FORMS"


def test_edge_cases():
    """Test edge cases and boundary conditions."""
    test_cases = {
        # Empty/None
        "": "cooked",
        "   ": "cooked",

        # Case insensitivity
        "RAW": "raw",
        "GRILLED": "grilled",
        "Toasted": "baked",
        "CoOkEd": "cooked",

        # Whitespace handling
        "  raw  ": "raw",
        " grilled ": "grilled",
        "\tsteamed\n": "steamed",

        # Unknown terms (fallback to cooked)
        "mysterious": "cooked",
        "xyz123": "cooked",
        "unknown method": "cooked",
    }

    for input_form, expected in test_cases.items():
        result = normalize_form(input_form)
        assert result == expected, f"'{input_form}' should map to '{expected}', got '{result}'"
        assert result in VALID_FORMS, f"Result '{result}' not in VALID_FORMS"


def test_never_returns_invalid():
    """Test that normalize_form() NEVER returns invalid value."""
    # All observed failures from real data
    invalid_forms = [
        "whole", "salad", "cooked strips", "fresh", "pieces", "strips",
        "toasted", "halved, toasted", "sliced", "chopped", "diced",
        "mysterious_cooking_method_xyz", "???", "12345"
    ]

    for form in invalid_forms:
        result = normalize_form(form)
        assert result in VALID_FORMS, f"normalize_form('{form}') returned invalid '{result}'"


def test_validation_auto_fix():
    """Test that validation auto-fixes invalid forms instead of failing."""
    # Valid response with invalid forms (should auto-fix)
    response = {
        "foods": [
            {"name": "lettuce", "form": "whole", "mass_g": 50, "confidence": 0.8},
            {"name": "chicken", "form": "cooked strips", "mass_g": 120, "confidence": 0.85},
            {"name": "bagel", "form": "toasted", "mass_g": 85, "confidence": 0.9},
        ]
    }

    # Should NOT raise - should auto-fix
    try:
        validate_mass_only_response(response)

        # Verify forms were auto-fixed
        assert response["foods"][0]["form"] == "raw", "whole should be auto-fixed to raw"
        assert response["foods"][1]["form"] == "cooked", "cooked strips should be auto-fixed to cooked"
        assert response["foods"][2]["form"] == "baked", "toasted should be auto-fixed to baked"

        print("✅ Validation auto-fix working correctly!")

    except ValueError as e:
        raise AssertionError(f"Validation should auto-fix, not raise. Error: {e}")


def test_validation_still_catches_real_errors():
    """Test that validation still catches genuinely invalid responses."""
    # Missing required field
    response_missing_name = {
        "foods": [
            {"form": "raw", "mass_g": 50, "confidence": 0.8}  # Missing 'name'
        ]
    }

    try:
        validate_mass_only_response(response_missing_name)
        raise AssertionError("Should have raised ValueError for missing name")
    except ValueError as e:
        assert "missing required field: name" in str(e)

    # Invalid mass
    response_invalid_mass = {
        "foods": [
            {"name": "lettuce", "form": "raw", "mass_g": -10, "confidence": 0.8}
        ]
    }

    try:
        validate_mass_only_response(response_invalid_mass)
        raise AssertionError("Should have raised ValueError for negative mass")
    except ValueError as e:
        assert "invalid mass_g" in str(e)

    # Forbidden fields
    response_forbidden = {
        "foods": [
            {"name": "lettuce", "form": "raw", "mass_g": 50, "calories": 12, "confidence": 0.8}
        ]
    }

    try:
        validate_mass_only_response(response_forbidden)
        raise AssertionError("Should have raised ValueError for forbidden field")
    except ValueError as e:
        assert "forbidden field" in str(e)


def test_form_aliases_coverage():
    """Verify all observed failures are in FORM_ALIASES."""
    # From gpt_5_10images_20251024_084418.json
    observed_failures = [
        "whole",
        "salad",
        "cooked strips",
        "toasted",
        "halved, toasted",
    ]

    for form in observed_failures:
        assert form in FORM_ALIASES, f"Observed failure '{form}' missing from FORM_ALIASES"

    print(f"✅ All {len(observed_failures)} observed failures covered in FORM_ALIASES")


def test_comprehensive_normalization():
    """Comprehensive test of all normalization paths."""
    # Test every path in normalize_form()

    # Path 1: Already valid
    assert normalize_form("raw") == "raw"
    assert normalize_form("grilled") == "grilled"

    # Path 2: Exact alias
    assert normalize_form("whole") == "raw"
    assert normalize_form("sautéed") == "pan_seared"

    # Path 3a: Breaded keywords
    assert normalize_form("breaded chicken") == "breaded"
    assert normalize_form("battered fish") == "breaded"

    # Path 3b: Grilling keywords
    assert normalize_form("char-grilled") == "grilled"

    # Path 3c: Searing keywords
    assert normalize_form("seared steak") == "pan_seared"

    # Path 3d: Frying keywords
    assert normalize_form("deep fried") == "fried"

    # Path 3e: Poaching keywords
    assert normalize_form("poached egg") == "poached"

    # Path 3f: Stewing keywords
    assert normalize_form("stewed beef") == "stewed"

    # Path 3g: Simmering keywords
    assert normalize_form("simmered sauce") == "simmered"

    # Path 3h: Baking keywords
    assert normalize_form("oven toasted") == "baked"

    # Path 3i: Roasting keywords
    assert normalize_form("broiled salmon") == "roasted"

    # Path 3j: Boiling keywords
    assert normalize_form("boiled egg") == "boiled"

    # Path 3k: Steaming keywords
    assert normalize_form("steamed veggies") == "steamed"

    # Path 3l: Raw keywords
    assert normalize_form("fresh salad") == "raw"

    # Path 3m: Cooked keywords
    assert normalize_form("cooked chicken") == "cooked"

    # Path 3n: Cut descriptors
    assert normalize_form("sliced tomato") == "raw"

    # Path 4: Fallback
    assert normalize_form("mysterious method") == "cooked"

    print("✅ All normalization paths tested")


if __name__ == "__main__":
    print("=" * 80)
    print("FORM NORMALIZATION TEST SUITE")
    print("=" * 80)
    print()

    tests = [
        ("Valid forms passthrough", test_valid_forms_passthrough),
        ("Exact alias mapping", test_exact_alias_mapping),
        ("Heuristic keyword matching", test_heuristic_keyword_matching),
        ("Edge cases", test_edge_cases),
        ("Never returns invalid", test_never_returns_invalid),
        ("Validation auto-fix", test_validation_auto_fix),
        ("Validation catches real errors", test_validation_still_catches_real_errors),
        ("Form aliases coverage", test_form_aliases_coverage),
        ("Comprehensive normalization", test_comprehensive_normalization),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            print(f"Running: {name}...")
            test_func()
            print(f"  ✅ PASSED\n")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"  ⚠️  ERROR: {e}\n")
            failed += 1

    print("=" * 80)
    print(f"RESULTS: {passed}/{len(tests)} passed, {failed}/{len(tests)} failed")
    print("=" * 80)

    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print(f"❌ {failed} tests failed")
        sys.exit(1)
