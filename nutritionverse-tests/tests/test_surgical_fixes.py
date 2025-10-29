"""
Unit tests for surgical fixes: normalization, scrambled eggs bypass, dessert leak guard.

Tests the P0+P1 implementation fixes for:
- Safe normalization with whitelist
- Scrambled eggs SR bypass
- Produce→dessert penalty enforcement
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.nutrition.alignment.align_convert import _normalize_for_lookup
from src.adapters.alignment_adapter import AlignmentEngineAdapter


def test_normalization_preserves_form():
    """
    Test that normalization removes 'florets' but preserves form extraction.

    Requirements:
    - "broccoli florets raw" → normalized name "broccoli"
    - Form extracted as "raw" before modifiers removed
    - Tokens include normalized plurals
    """
    normalized, tokens, form, method = _normalize_for_lookup("broccoli florets raw")

    assert normalized == "broccoli", f"Expected 'broccoli', got '{normalized}'"
    assert form == "raw", f"Expected form='raw', got '{form}'"
    assert "florets" not in normalized, "Florets should be removed from normalized name"

    print(f"✓ test_normalization_preserves_form passed")
    print(f"  Input: 'broccoli florets raw'")
    print(f"  Normalized: '{normalized}'")
    print(f"  Form: '{form}'")


def test_normalization_plural_whitelist():
    """
    Test that plural→singular uses whitelist to avoid bugs like "glass"→"glas".

    Requirements:
    - Whitelisted plurals: tomatoes→tomato, mushrooms→mushroom, eggs→egg
    - Non-whitelisted words unchanged: glass→glass, pass→pass
    """
    # Whitelisted plurals
    norm1, _, _, _ = _normalize_for_lookup("cherry tomatoes")
    assert "tomato" in norm1, f"Expected 'tomato' in '{norm1}'"
    assert "tomatoes" not in norm1, f"'tomatoes' should be singularized"

    norm2, _, _, _ = _normalize_for_lookup("mushrooms")
    assert "mushroom" in norm2, f"Expected 'mushroom' in '{norm2}'"

    norm3, _, _, _ = _normalize_for_lookup("scrambled eggs")
    assert "egg" in norm3, f"Expected 'egg' in '{norm3}'"

    print(f"✓ test_normalization_plural_whitelist passed")
    print(f"  'cherry tomatoes' → '{norm1}'")
    print(f"  'mushrooms' → '{norm2}'")
    print(f"  'scrambled eggs' → '{norm3}'")


def test_scrambled_eggs_not_stage0_with_health_check():
    """
    Test that scrambled eggs matches SR or Stage2, never stage0.

    Requirements:
    - Scrambled eggs finds SR "Egg, scrambled" or Foundation conversion
    - Does NOT match fast food entries
    - Does NOT fall to stage0_no_candidates
    """
    adapter = AlignmentEngineAdapter()

    # Health check
    if not adapter.db_available:
        pytest.skip("DB not available")

    prediction = {
        "foods": [{
            "name": "scrambled eggs",
            "form": "cooked",
            "mass_g": 100.0,
            "confidence": 0.8
        }]
    }

    result = adapter.align_prediction_batch(prediction)

    assert result["available"], "DB should be available"
    assert len(result["foods"]) > 0, "Should have at least one food result"

    food = result["foods"][0]

    # Must not be stage0
    assert food.get("alignment_stage") != "stage0_no_candidates", \
        f"Scrambled eggs should not fall to stage0 (got {food.get('alignment_stage')})"

    # Verify not fast food
    fdc_name = food.get("fdc_name", "").lower()
    assert "fast foods" not in fdc_name and "fast food" not in fdc_name, \
        f"Should not match fast food entry: {food.get('fdc_name')}"

    print(f"✓ test_scrambled_eggs_not_stage0_with_health_check passed")
    print(f"  Matched: {food.get('fdc_name')}")
    print(f"  Stage: {food.get('alignment_stage')}")


def test_dessert_leak_guard():
    """
    Test that produce items don't match desserts due to class-conditional penalties.

    Requirements:
    - Apple → "Apples raw" (NOT "Croissants apple")
    - Strawberry → "Strawberries raw" (NOT ice cream/dessert)
    - Produce gets class_intent="produce" → dessert penalty (-0.35)
    """
    adapter = AlignmentEngineAdapter()

    if not adapter.db_available:
        pytest.skip("DB not available")

    test_cases = [
        ("apple", "raw"),
        ("strawberry", "raw")
    ]

    for food_name, form in test_cases:
        prediction = {
            "foods": [{
                "name": food_name,
                "form": form,
                "mass_g": 100.0,
                "confidence": 0.8
            }]
        }

        result = adapter.align_prediction_batch(prediction)

        assert result["available"], f"DB should be available for {food_name}"
        assert len(result["foods"]) > 0, f"Should have result for {food_name}"

        food = result["foods"][0]

        # Verify produce match (not dessert)
        fdc_name_lower = food.get("fdc_name", "").lower()
        dessert_tokens = ["croissant", "ice cream", "cake", "pastry", "pie", "cookie", "muffin"]

        for token in dessert_tokens:
            assert token not in fdc_name_lower, \
                f"{food_name} matched dessert: {food.get('fdc_name')} (contains '{token}')"

        print(f"✓ {food_name} → {food.get('fdc_name')} (no dessert leak)")


if __name__ == "__main__":
    print("Running surgical fixes unit tests...\n")

    # Test 1: Normalization preserves form
    try:
        test_normalization_preserves_form()
    except AssertionError as e:
        print(f"✗ test_normalization_preserves_form FAILED: {e}\n")
    except Exception as e:
        print(f"✗ test_normalization_preserves_form ERROR: {e}\n")

    # Test 2: Plural whitelist safety
    try:
        test_normalization_plural_whitelist()
    except AssertionError as e:
        print(f"✗ test_normalization_plural_whitelist FAILED: {e}\n")
    except Exception as e:
        print(f"✗ test_normalization_plural_whitelist ERROR: {e}\n")

    # Test 3: Scrambled eggs bypass
    try:
        test_scrambled_eggs_not_stage0_with_health_check()
    except AssertionError as e:
        print(f"✗ test_scrambled_eggs_not_stage0_with_health_check FAILED: {e}\n")
    except Exception as e:
        if "skip" in str(e).lower():
            print(f"⊘ test_scrambled_eggs_not_stage0_with_health_check SKIPPED: {e}\n")
        else:
            print(f"✗ test_scrambled_eggs_not_stage0_with_health_check ERROR: {e}\n")

    # Test 4: Dessert leak guard
    try:
        test_dessert_leak_guard()
    except AssertionError as e:
        print(f"✗ test_dessert_leak_guard FAILED: {e}\n")
    except Exception as e:
        if "skip" in str(e).lower():
            print(f"⊘ test_dessert_leak_guard SKIPPED: {e}\n")
        else:
            print(f"✗ test_dessert_leak_guard ERROR: {e}\n")

    print("\nAll tests complete!")
