"""
P0+P1 Unit Tests: Produce Alignment & Safety Rails

Tests for:
- Produce variants (cherry/grape tomatoes, mushrooms, green beans)
- Produce → dessert/pastry leakage prevention
- Stage2 seed guardrail
- Stage1c telemetry IDs
"""
import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.alignment_adapter import AlignmentEngineAdapter


@pytest.mark.parametrize("food_name,form,expected_not_stage0", [
    ("cherry tomatoes", "raw", True),
    ("grape tomatoes", "raw", True),
    ("button mushrooms", "raw", True),
    ("green beans", "raw", True),
    ("broccoli florets", "raw", True),
])
def test_produce_alignment_not_stage0(food_name, form, expected_not_stage0):
    """Test that produce items don't fall to stage0."""
    adapter = AlignmentEngineAdapter()
    prediction = {"foods": [{"name": food_name, "form": form, "mass_g": 100.0, "confidence": 0.8}]}
    result = adapter.align_prediction_batch(prediction)

    assert result["available"], f"{food_name}: DB not available"

    if expected_not_stage0 and result["foods"]:
        food = result["foods"][0]
        assert food.get("alignment_stage") != "stage0_no_candidates", \
            f"{food_name}: Still stage0 (no match found)"


@pytest.mark.parametrize("food_name,bad_tokens", [
    ("apple", ["croissant", "pastry", "ice cream"]),
    ("strawberry", ["ice cream", "cake"]),
    ("cherry", ["pie"]),
])
def test_produce_no_dessert_leakage(food_name, bad_tokens):
    """Test that produce doesn't match desserts/pastries."""
    adapter = AlignmentEngineAdapter()
    prediction = {"foods": [{"name": food_name, "form": "raw", "mass_g": 100.0, "confidence": 0.8}]}
    result = adapter.align_prediction_batch(prediction)

    assert result["available"], f"{food_name}: DB not available"

    if result["foods"]:
        food = result["foods"][0]
        fdc_name = food.get("fdc_name", "").lower()

        for bad_token in bad_tokens:
            assert bad_token.lower() not in fdc_name, \
                f"{food_name}: Incorrectly matched '{bad_token}' FDC"


def test_stage2_seed_guardrail():
    """Test that Stage2 conversions only use Foundation raw seeds."""
    adapter = AlignmentEngineAdapter()

    # Test with cooked egg (should use Foundation raw → convert, not SR cooked)
    prediction = {"foods": [{"name": "scrambled eggs", "form": "cooked", "mass_g": 100.0, "confidence": 0.8}]}
    result = adapter.align_prediction_batch(prediction)

    assert result["available"], "DB not available"

    for food in result.get("foods", []):
        if food.get("alignment_stage") == "stage2_raw_convert":
            tel = food.get("telemetry", {})
            guardrail = tel.get("stage2_seed_guardrail", {})

            # If guardrail exists, must be passed
            if guardrail:
                assert guardrail.get("status") == "passed", \
                    f"Stage2 seed guardrail failed: {guardrail.get('reason')}"


def test_stage1c_telemetry_ids():
    """Test that stage1c switches include from_id and to_id."""
    adapter = AlignmentEngineAdapter()

    # Use foods that might trigger stage1c (processed → raw switches)
    test_foods = [
        {"name": "frozen broccoli", "form": "raw", "mass_g": 100.0, "confidence": 0.8},
        {"name": "canned tomatoes", "form": "raw", "mass_g": 100.0, "confidence": 0.8},
    ]

    for test_food in test_foods:
        prediction = {"foods": [test_food]}
        result = adapter.align_prediction_batch(prediction)

        if not result["available"]:
            continue

        for food in result.get("foods", []):
            tel = food.get("telemetry", {})
            if "stage1c_switched" in tel:
                switch = tel["stage1c_switched"]
                assert switch.get("from_id") is not None, \
                    f"{test_food['name']}: stage1c switch missing from_id"
                assert switch.get("to_id") is not None, \
                    f"{test_food['name']}: stage1c switch missing to_id"


def test_config_version_stamped():
    """Test that config version is stamped in telemetry."""
    adapter = AlignmentEngineAdapter()
    prediction = {"foods": [{"name": "apple", "form": "raw", "mass_g": 100.0, "confidence": 0.8}]}
    result = adapter.align_prediction_batch(prediction)

    assert result["available"], "DB not available"

    telemetry = result.get("telemetry", {})
    assert telemetry.get("config_version") is not None, "config_version missing from telemetry"
    assert telemetry.get("config_fingerprint") is not None, "config_fingerprint missing from telemetry"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
