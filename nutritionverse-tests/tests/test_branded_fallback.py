"""
Unit tests for StageZ Branded Fallback stage.

Tests the deterministic branded fallback system for foods that don't exist in Foundation/SR
databases (cherry tomatoes, broccoli florets, scrambled eggs, green beans).
"""
import pytest
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.alignment_adapter import AlignmentEngineAdapter


def test_cherry_tomato_normalization_variants():
    """Test that 'cherry tomatoes' finds 'cherry_tomato' config via key variants."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    prediction = {"foods": [{"name": "cherry tomatoes", "form": "raw", "mass_g": 100.0}]}
    result = adapter.align_prediction_batch(prediction)

    food = result["foods"][0]
    assert food.get("alignment_stage") == "stageZ_branded_fallback", \
        f"Expected stageZ_branded_fallback, got {food.get('alignment_stage')}"
    assert food.get("fdc_id") in [383842, 531259], \
        f"Should match cherry tomato FDC ID, got {food.get('fdc_id')}"

    # Check telemetry
    telemetry = food.get("telemetry", {})
    assert "stageZ_branded_fallback" in telemetry, "Should have stageZ_branded_fallback telemetry"
    assert "canonical_key" in telemetry["stageZ_branded_fallback"], "Should have canonical_key"


def test_scrambled_eggs_reaches_stageZ():
    """Test that scrambled eggs uses Stage Z fallback, NOT fast-food SR entry."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    prediction = {"foods": [{"name": "scrambled eggs", "form": "cooked", "mass_g": 100.0}]}
    result = adapter.align_prediction_batch(prediction)

    food = result["foods"][0]
    assert food.get("alignment_stage") == "stageZ_branded_fallback", \
        f"Scrambled eggs should use Stage Z, got {food.get('alignment_stage')}"
    assert food.get("fdc_id") == 450876, \
        f"Should match generic scrambled eggs (NOT fast food), got {food.get('fdc_id')}"

    fdc_name = food.get("fdc_name", "").lower()
    assert "fast food" not in fdc_name, \
        f"Must NOT be fast food entry, got: {fdc_name}"

    # Check egg exception telemetry
    telemetry = food.get("telemetry", {})
    assert "stageZ_branded_fallback" in telemetry, "Should have stageZ_branded_fallback telemetry"
    # Egg exception should be marked
    assert telemetry.get("egg_cooked_exception") == True, "Should have egg_cooked_exception marker"


def test_grape_tomato_variant():
    """Test grape tomatoes (similar to cherry tomatoes)."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    prediction = {"foods": [{"name": "grape tomatoes", "form": "raw", "mass_g": 100.0}]}
    result = adapter.align_prediction_batch(prediction)

    food = result["foods"][0]
    # Should either match Foundation/SR grape tomatoes or fall back to branded
    assert food.get("alignment_stage") in ["stage1b_raw_foundation_direct", "stageZ_branded_fallback"], \
        f"Unexpected stage: {food.get('alignment_stage')}"

    if food.get("alignment_stage") == "stageZ_branded_fallback":
        assert food.get("fdc_id") in [447986, 523755], \
            f"Should match grape tomato FDC ID, got {food.get('fdc_id')}"


def test_broccoli_florets_regression():
    """Ensure broccoli florets still works via Stage Z (regression test)."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    prediction = {"foods": [{"name": "broccoli florets", "form": "raw", "mass_g": 100.0}]}
    result = adapter.align_prediction_batch(prediction)

    food = result["foods"][0]
    assert food.get("alignment_stage") == "stageZ_branded_fallback", \
        f"Broccoli florets should use Stage Z, got {food.get('alignment_stage')}"
    assert food.get("fdc_id") in [372976, 448529], \
        f"Should match broccoli florets FDC ID, got {food.get('fdc_id')}"


def test_button_mushroom_stageZ():
    """Test button mushrooms use Stage Z fallback with verified FDC IDs."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    prediction = {"foods": [{"name": "button mushrooms", "form": "raw", "mass_g": 100.0}]}
    result = adapter.align_prediction_batch(prediction)

    food = result["foods"][0]
    # Button mushrooms should use Stage Z fallback
    assert food.get("alignment_stage") == "stageZ_branded_fallback", \
        f"Button mushrooms should use Stage Z, got {food.get('alignment_stage')}"

    # Should match verified button mushroom FDC IDs (565950 or 1360945)
    assert food.get("fdc_id") in [565950, 1360945], \
        f"Should match verified button mushroom FDC ID, got {food.get('fdc_id')}"

    # Check telemetry
    telemetry = food.get("telemetry", {})
    assert "stageZ_branded_fallback" in telemetry, "Should have stageZ_branded_fallback telemetry"

    # Verify plausible kcal range (20-35 kcal/100g for mushrooms)
    stageZ_telemetry = telemetry.get("stageZ_branded_fallback", {})
    kcal = stageZ_telemetry.get("kcal_per_100g", 0)
    assert 20 <= kcal <= 35, f"Button mushrooms kcal {kcal} should be in range [20, 35]"


def test_green_beans_handling():
    """Test green beans alignment with all-rejected telemetry (may use Foundation/SR or Stage Z fallback)."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    prediction = {"foods": [{"name": "green beans", "form": "raw", "mass_g": 100.0}]}
    result = adapter.align_prediction_batch(prediction)

    food = result["foods"][0]
    telemetry = food.get("telemetry", {})

    # Green beans may match Foundation/SR "Beans snap green" or use Stage Z
    assert food.get("alignment_stage") in ["stage1b_raw_foundation_direct", "stageZ_branded_fallback"], \
        f"Unexpected stage: {food.get('alignment_stage')}"

    # If using Stage Z, should match green beans branded FDC ID and have rejection telemetry
    if food.get("alignment_stage") == "stageZ_branded_fallback":
        assert food.get("fdc_id") in [359180, 394232], \
            f"Should match green beans branded FDC ID, got {food.get('fdc_id')}"

        # Verify rejection telemetry exists
        assert "stage1_all_rejected" in telemetry, "Should have stage1_all_rejected in telemetry"
        assert "had_candidates_to_score" in telemetry, "Should have had_candidates_to_score in telemetry"
        assert "candidate_pool_size" in telemetry, "Should have candidate_pool_size in telemetry"


def test_stageZ_telemetry_structure():
    """Test that Stage Z telemetry has all required fields."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    prediction = {"foods": [{"name": "broccoli florets", "form": "raw", "mass_g": 100.0}]}
    result = adapter.align_prediction_batch(prediction)

    food = result["foods"][0]
    telemetry = food.get("telemetry", {})
    stageZ_telemetry = telemetry.get("stageZ_branded_fallback", {})

    assert "brand" in stageZ_telemetry, "Should have brand in telemetry"
    assert "fdc_id" in stageZ_telemetry, "Should have fdc_id in telemetry"
    assert "reason" in stageZ_telemetry, "Should have reason in telemetry"
    assert "canonical_key" in stageZ_telemetry, "Should have canonical_key in telemetry"
    assert "kcal_per_100g" in stageZ_telemetry, "Should have kcal_per_100g in telemetry"
    assert "kcal_range" in stageZ_telemetry, "Should have kcal_range in telemetry"


def test_rejection_telemetry():
    """Test that stage1_all_rejected and candidate_pool_size are in telemetry."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    # Use cherry tomatoes which has no candidates
    prediction = {"foods": [{"name": "cherry tomatoes", "form": "raw", "mass_g": 100.0}]}
    result = adapter.align_prediction_batch(prediction)

    food = result["foods"][0]
    telemetry = food.get("telemetry", {})

    # Should have candidate pool telemetry
    assert "candidate_pool_size" in telemetry, "Should have candidate_pool_size in telemetry"
    assert "stage1_all_rejected" in telemetry, "Should have stage1_all_rejected in telemetry"


def test_no_fast_food_eggs():
    """Verify that scrambled eggs never matches fast food entries."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    # Test various egg preparations
    egg_names = ["scrambled eggs", "fried eggs", "eggs scrambled"]

    for egg_name in egg_names:
        prediction = {"foods": [{"name": egg_name, "form": "cooked", "mass_g": 100.0}]}
        result = adapter.align_prediction_batch(prediction)

        food = result["foods"][0]
        fdc_name = food.get("fdc_name", "").lower()

        # CRITICAL: Must never match fast food entries
        assert "fast food" not in fdc_name, \
            f"Egg '{egg_name}' matched fast food entry: {fdc_name}"


def test_key_variant_matching():
    """Test that different forms of the same food (singular/plural, underscore/space) match."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    # Test cases: (input_name, expected_stage)
    test_cases = [
        ("cherry tomato", "stageZ_branded_fallback"),   # Singular
        ("cherry tomatoes", "stageZ_branded_fallback"),  # Plural
        ("broccoli floret", "stageZ_branded_fallback"),  # Singular
        ("broccoli florets", "stageZ_branded_fallback"), # Plural
    ]

    for food_name, expected_stage in test_cases:
        prediction = {"foods": [{"name": food_name, "form": "raw", "mass_g": 100.0}]}
        result = adapter.align_prediction_batch(prediction)

        food = result["foods"][0]
        assert food.get("alignment_stage") == expected_stage, \
            f"'{food_name}' should use {expected_stage}, got {food.get('alignment_stage')}"


def test_plausibility_guards():
    """Test that plausibility guards (kcal range) are enforced."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    # Cherry tomatoes should have kcal in range [15, 35]
    prediction = {"foods": [{"name": "cherry tomatoes", "form": "raw", "mass_g": 100.0}]}
    result = adapter.align_prediction_batch(prediction)

    food = result["foods"][0]
    if food.get("alignment_stage") == "stageZ_branded_fallback":
        telemetry = food.get("telemetry", {}).get("stageZ_branded_fallback", {})
        kcal = telemetry.get("kcal_per_100g", 0)
        kcal_range = telemetry.get("kcal_range", [0, 1000])

        assert kcal_range[0] <= kcal <= kcal_range[1], \
            f"Kcal {kcal} outside expected range {kcal_range}"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
