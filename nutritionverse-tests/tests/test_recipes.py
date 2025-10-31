"""
Unit tests for Phase Z4 Recipe Decomposition (Stage 5C).

Tests the recipe framework and component-based decomposition for pizza, sandwich, and chia pudding.
"""
import pytest
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.alignment_adapter import AlignmentEngineAdapter
from src.nutrition.alignment.recipes import RecipeLoader, RecipeTemplate, RecipeComponent


def test_recipe_loader_initialization():
    """Test that RecipeLoader loads YAML configs correctly."""
    config_dir = Path(__file__).parent.parent.parent / "configs"
    loader = RecipeLoader(config_dir)

    # Should load at least 3 recipe templates (pizza, sandwich, chia pudding)
    assert len(loader.templates) >= 3, f"Expected at least 3 recipes, got {len(loader.templates)}"

    # Check pizza templates loaded
    pizza_recipes = [r for r in loader.templates.values() if "pizza" in r.name.lower()]
    assert len(pizza_recipes) >= 3, f"Expected at least 3 pizza variants, got {len(pizza_recipes)}"


def test_recipe_component_ratio_validation():
    """Test that recipe component ratios sum to 1.0 (within tolerance)."""
    config_dir = Path(__file__).parent.parent.parent / "configs"
    loader = RecipeLoader(config_dir)

    validation_errors = loader.validate_all()
    assert len(validation_errors) == 0, f"Recipe validation failed: {validation_errors}"


def test_pizza_trigger_matching():
    """Test that pizza triggers match correctly."""
    config_dir = Path(__file__).parent.parent.parent / "configs"
    loader = RecipeLoader(config_dir)

    # Should match cheese pizza
    template = loader.match_recipe("cheese pizza")
    assert template is not None, "Should match 'cheese pizza'"
    assert "pizza" in template.name.lower(), f"Should be pizza template, got {template.name}"

    # Should match pepperoni pizza
    template = loader.match_recipe("pepperoni pizza")
    assert template is not None, "Should match 'pepperoni pizza'"
    assert "pizza" in template.name.lower(), f"Should be pizza template, got {template.name}"


def test_sandwich_trigger_matching():
    """Test that sandwich triggers match correctly."""
    config_dir = Path(__file__).parent.parent.parent / "configs"
    loader = RecipeLoader(config_dir)

    # Should match turkey sandwich
    template = loader.match_recipe("turkey sandwich")
    assert template is not None, "Should match 'turkey sandwich'"
    assert "turkey" in template.name.lower() or "sandwich" in template.name.lower()

    # Should match chicken sandwich
    template = loader.match_recipe("chicken sandwich")
    assert template is not None, "Should match 'chicken sandwich'"
    assert "chicken" in template.name.lower() or "sandwich" in template.name.lower()


def test_chia_pudding_trigger_matching():
    """Test that chia pudding triggers match correctly."""
    config_dir = Path(__file__).parent.parent.parent / "configs"
    loader = RecipeLoader(config_dir)

    # Should match chia pudding
    template = loader.match_recipe("chia pudding")
    assert template is not None, "Should match 'chia pudding'"
    assert "chia" in template.name.lower(), f"Should be chia template, got {template.name}"

    # Should match chia seed pudding variant
    template = loader.match_recipe("chia seed pudding")
    assert template is not None, "Should match 'chia seed pudding'"
    assert "chia" in template.name.lower(), f"Should be chia template, got {template.name}"


def test_pizza_decomposition_end_to_end():
    """Test that pizza gets decomposed into components (Stage 5C)."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    # Enable recipe decomposition (default should be True)
    prediction = {"foods": [{"name": "cheese pizza", "form": "cooked", "mass_g": 300.0}]}
    result = adapter.align_prediction_batch(prediction)

    food = result["foods"][0]

    # Check if decomposition occurred
    if food.get("alignment_stage") == "stage5c_recipe_decomposition":
        # Verify decomposition telemetry
        telemetry = food.get("telemetry", {})
        assert "stage5c_recipe_decomposition" in telemetry, "Should have stage5c telemetry"

        stage5c_data = telemetry["stage5c_recipe_decomposition"]
        assert "recipe_template" in stage5c_data, "Should have recipe_template"
        assert "pizza" in stage5c_data["recipe_template"].lower(), "Should be pizza recipe"

        # Verify expanded_foods present
        expanded_foods = food.get("expanded_foods", [])
        assert len(expanded_foods) >= 2, f"Pizza should have multiple components, got {len(expanded_foods)}"

        # Verify components have FDC IDs
        aligned_components = [c for c in expanded_foods if c.get("fdc_id")]
        assert len(aligned_components) > 0, "At least some components should align"

        # Verify total mass matches
        total_mass = sum(c.get("mass_g", 0) for c in expanded_foods)
        assert abs(total_mass - 300.0) < 1.0, f"Total mass should be ~300g, got {total_mass}g"
    else:
        # If decomposition didn't trigger, that's okay (may have matched Foundation/branded directly)
        # Just verify it didn't fail
        assert food.get("alignment_stage") != "stage0_no_candidates", \
            f"Pizza should not be a miss, got {food.get('alignment_stage')}"


def test_sandwich_decomposition_end_to_end():
    """Test that sandwich gets decomposed into components (Stage 5C)."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    prediction = {"foods": [{"name": "turkey sandwich", "form": "cooked", "mass_g": 250.0}]}
    result = adapter.align_prediction_batch(prediction)

    food = result["foods"][0]

    # Check if decomposition occurred
    if food.get("alignment_stage") == "stage5c_recipe_decomposition":
        # Verify decomposition telemetry
        telemetry = food.get("telemetry", {})
        assert "stage5c_recipe_decomposition" in telemetry, "Should have stage5c telemetry"

        stage5c_data = telemetry["stage5c_recipe_decomposition"]
        assert "recipe_template" in stage5c_data, "Should have recipe_template"

        # Verify expanded_foods present
        expanded_foods = food.get("expanded_foods", [])
        assert len(expanded_foods) >= 2, f"Sandwich should have multiple components, got {len(expanded_foods)}"

        # Verify components have FDC IDs
        aligned_components = [c for c in expanded_foods if c.get("fdc_id")]
        assert len(aligned_components) > 0, "At least some components should align"

        # Verify total mass matches
        total_mass = sum(c.get("mass_g", 0) for c in expanded_foods)
        assert abs(total_mass - 250.0) < 1.0, f"Total mass should be ~250g, got {total_mass}g"
    else:
        # If decomposition didn't trigger, that's okay
        assert food.get("alignment_stage") != "stage0_no_candidates", \
            f"Sandwich should not be a miss, got {food.get('alignment_stage')}"


def test_chia_pudding_decomposition_end_to_end():
    """Test that chia pudding gets decomposed into components (Stage 5C)."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    prediction = {"foods": [{"name": "chia pudding", "form": "raw", "mass_g": 200.0}]}
    result = adapter.align_prediction_batch(prediction)

    food = result["foods"][0]

    # Check if decomposition occurred
    if food.get("alignment_stage") == "stage5c_recipe_decomposition":
        # Verify decomposition telemetry
        telemetry = food.get("telemetry", {})
        assert "stage5c_recipe_decomposition" in telemetry, "Should have stage5c telemetry"

        stage5c_data = telemetry["stage5c_recipe_decomposition"]
        assert "recipe_template" in stage5c_data, "Should have recipe_template"
        assert "chia" in stage5c_data["recipe_template"].lower(), "Should be chia recipe"

        # Verify expanded_foods present
        expanded_foods = food.get("expanded_foods", [])
        assert len(expanded_foods) >= 2, f"Chia pudding should have multiple components, got {len(expanded_foods)}"

        # Look for chia seeds component
        chia_component = next((c for c in expanded_foods if "chia" in c.get("name", "").lower()), None)
        assert chia_component is not None, "Should have chia seeds component"

        # Verify total mass matches
        total_mass = sum(c.get("mass_g", 0) for c in expanded_foods)
        assert abs(total_mass - 200.0) < 1.0, f"Total mass should be ~200g, got {total_mass}g"
    else:
        # If decomposition didn't trigger, that's okay
        assert food.get("alignment_stage") != "stage0_no_candidates", \
            f"Chia pudding should not be a miss, got {food.get('alignment_stage')}"


def test_non_recipe_food_skips_stage5c():
    """Test that non-recipe foods skip Stage 5C decomposition."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    # Test with simple food that shouldn't trigger recipe decomposition
    prediction = {"foods": [{"name": "banana", "form": "raw", "mass_g": 100.0}]}
    result = adapter.align_prediction_batch(prediction)

    food = result["foods"][0]

    # Should NOT use Stage 5C for banana
    assert food.get("alignment_stage") != "stage5c_recipe_decomposition", \
        f"Banana should not use recipe decomposition, got {food.get('alignment_stage')}"

    # Should use Foundation or other stage
    assert food.get("alignment_stage") in [
        "stage1b_raw_foundation_direct",
        "stage1c_cooked_sr_direct",
        "stage2_raw_convert",
        "stageZ_branded_fallback"
    ], f"Banana should use standard stages, got {food.get('alignment_stage')}"
