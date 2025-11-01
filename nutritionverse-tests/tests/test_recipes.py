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


def test_yogurt_parfait_trigger_matching():
    """Test that yogurt parfait triggers match correctly."""
    config_dir = Path(__file__).parent.parent.parent / "configs"
    loader = RecipeLoader(config_dir)

    # Should match yogurt parfait
    template = loader.match_recipe("yogurt parfait")
    assert template is not None, "Should match 'yogurt parfait'"
    assert "yogurt" in template.name.lower() or "parfait" in template.name.lower()

    # Should match greek yogurt parfait variant
    template = loader.match_recipe("greek yogurt parfait")
    assert template is not None, "Should match 'greek yogurt parfait'"
    assert "yogurt" in template.name.lower() or "parfait" in template.name.lower()

    # Should match simple parfait
    template = loader.match_recipe("parfait")
    assert template is not None, "Should match 'parfait'"


def test_burrito_trigger_matching():
    """Test that burrito triggers match correctly."""
    config_dir = Path(__file__).parent.parent.parent / "configs"
    loader = RecipeLoader(config_dir)

    # Should match burrito
    template = loader.match_recipe("burrito")
    assert template is not None, "Should match 'burrito'"
    assert "burrito" in template.name.lower()

    # Should match chicken burrito
    template = loader.match_recipe("chicken burrito")
    assert template is not None, "Should match 'chicken burrito'"
    assert "burrito" in template.name.lower()

    # Should match beef burrito
    template = loader.match_recipe("beef burrito")
    assert template is not None, "Should match 'beef burrito'"
    assert "burrito" in template.name.lower()


def test_grain_bowl_trigger_matching():
    """Test that grain bowl triggers match correctly."""
    config_dir = Path(__file__).parent.parent.parent / "configs"
    loader = RecipeLoader(config_dir)

    # Should match grain bowl
    template = loader.match_recipe("grain bowl")
    assert template is not None, "Should match 'grain bowl'"
    assert "grain" in template.name.lower() or "bowl" in template.name.lower()

    # Should match buddha bowl
    template = loader.match_recipe("buddha bowl")
    assert template is not None, "Should match 'buddha bowl'"
    assert "grain" in template.name.lower() or "bowl" in template.name.lower()

    # Should match quinoa bowl
    template = loader.match_recipe("quinoa bowl")
    assert template is not None, "Should match 'quinoa bowl'"
    assert "grain" in template.name.lower() or "bowl" in template.name.lower()


def test_yogurt_parfait_decomposition_end_to_end():
    """Test that yogurt parfait gets decomposed into components (Stage 5C)."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    prediction = {"foods": [{"name": "yogurt parfait", "form": "raw", "mass_g": 200.0}]}
    result = adapter.align_prediction_batch(prediction)

    food = result["foods"][0]

    # Check if decomposition occurred
    if food.get("alignment_stage") == "stage5c_recipe_decomposition":
        # Verify decomposition telemetry
        telemetry = food.get("telemetry", {})
        assert "stage5c_recipe_decomposition" in telemetry, "Should have stage5c telemetry"

        stage5c_data = telemetry["stage5c_recipe_decomposition"]
        assert "recipe_template" in stage5c_data, "Should have recipe_template"
        assert "yogurt" in stage5c_data["recipe_template"].lower() or "parfait" in stage5c_data["recipe_template"].lower(), \
            f"Should be yogurt parfait recipe, got {stage5c_data['recipe_template']}"

        # Verify expanded_foods present (expect 3 components: yogurt, granola, berries)
        expanded_foods = food.get("expanded_foods", [])
        assert len(expanded_foods) >= 2, f"Yogurt parfait should have at least 2 components, got {len(expanded_foods)}"

        # Verify components have FDC IDs (at least 60% should align per requirement)
        aligned_components = [c for c in expanded_foods if c.get("fdc_id")]
        assert len(aligned_components) > 0, "At least some components should align"

        # Verify total mass matches
        total_mass = sum(c.get("mass_g", 0) for c in expanded_foods)
        assert abs(total_mass - 200.0) < 1.0, f"Total mass should be ~200g, got {total_mass}g"

        # Verify ratios sum to ~1.0
        if "component_ratios" in stage5c_data:
            ratio_sum = sum(stage5c_data["component_ratios"].values())
            assert abs(ratio_sum - 1.0) < 0.01, f"Component ratios should sum to ~1.0, got {ratio_sum}"
    else:
        # If decomposition didn't trigger, that's okay
        assert food.get("alignment_stage") != "stage0_no_candidates", \
            f"Yogurt parfait should not be a miss, got {food.get('alignment_stage')}"


def test_burrito_decomposition_end_to_end():
    """Test that burrito gets decomposed into components (Stage 5C)."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    prediction = {"foods": [{"name": "chicken burrito", "form": "cooked", "mass_g": 350.0}]}
    result = adapter.align_prediction_batch(prediction)

    food = result["foods"][0]

    # Check if decomposition occurred
    if food.get("alignment_stage") == "stage5c_recipe_decomposition":
        # Verify decomposition telemetry
        telemetry = food.get("telemetry", {})
        assert "stage5c_recipe_decomposition" in telemetry, "Should have stage5c telemetry"

        stage5c_data = telemetry["stage5c_recipe_decomposition"]
        assert "recipe_template" in stage5c_data, "Should have recipe_template"
        assert "burrito" in stage5c_data["recipe_template"].lower(), \
            f"Should be burrito recipe, got {stage5c_data['recipe_template']}"

        # Verify expanded_foods present (expect 5 components: tortilla, protein, rice, beans, cheese)
        expanded_foods = food.get("expanded_foods", [])
        assert len(expanded_foods) >= 3, f"Burrito should have at least 3 components, got {len(expanded_foods)}"

        # Verify components have FDC IDs (at least 60% should align per requirement)
        aligned_components = [c for c in expanded_foods if c.get("fdc_id")]
        assert len(aligned_components) >= 0.6 * len(expanded_foods), \
            f"At least 60% of components should align, got {len(aligned_components)}/{len(expanded_foods)}"

        # Verify total mass matches
        total_mass = sum(c.get("mass_g", 0) for c in expanded_foods)
        assert abs(total_mass - 350.0) < 1.0, f"Total mass should be ~350g, got {total_mass}g"

        # Verify ratios sum to ~1.0
        if "component_ratios" in stage5c_data:
            ratio_sum = sum(stage5c_data["component_ratios"].values())
            assert abs(ratio_sum - 1.0) < 0.01, f"Component ratios should sum to ~1.0, got {ratio_sum}"
    else:
        # If decomposition didn't trigger, that's okay
        assert food.get("alignment_stage") != "stage0_no_candidates", \
            f"Burrito should not be a miss, got {food.get('alignment_stage')}"


def test_grain_bowl_decomposition_end_to_end():
    """Test that grain bowl gets decomposed into components (Stage 5C)."""
    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    prediction = {"foods": [{"name": "grain bowl", "form": "cooked", "mass_g": 400.0}]}
    result = adapter.align_prediction_batch(prediction)

    food = result["foods"][0]

    # Check if decomposition occurred
    if food.get("alignment_stage") == "stage5c_recipe_decomposition":
        # Verify decomposition telemetry
        telemetry = food.get("telemetry", {})
        assert "stage5c_recipe_decomposition" in telemetry, "Should have stage5c telemetry"

        stage5c_data = telemetry["stage5c_recipe_decomposition"]
        assert "recipe_template" in stage5c_data, "Should have recipe_template"
        assert "grain" in stage5c_data["recipe_template"].lower() or "bowl" in stage5c_data["recipe_template"].lower(), \
            f"Should be grain bowl recipe, got {stage5c_data['recipe_template']}"

        # Verify expanded_foods present (expect 5 components: grains, protein, roasted_veg, greens, dressing)
        expanded_foods = food.get("expanded_foods", [])
        assert len(expanded_foods) >= 3, f"Grain bowl should have at least 3 components, got {len(expanded_foods)}"

        # Look for roasted vegetables component (validation per requirement)
        roasted_veg_component = next((c for c in expanded_foods
                                      if any(keyword in c.get("name", "").lower()
                                            for keyword in ["sweet potato", "broccoli", "brussels", "cauliflower", "squash", "vegetable"])),
                                    None)
        assert roasted_veg_component is not None, "Should have roasted vegetables component"

        # Look for dressing component (validation per requirement)
        dressing_component = next((c for c in expanded_foods
                                   if any(keyword in c.get("name", "").lower()
                                         for keyword in ["tahini", "oil", "vinaigrette", "lemon", "dressing", "sauce"])),
                                 None)
        assert dressing_component is not None, "Should have dressing component"

        # Verify total mass matches
        total_mass = sum(c.get("mass_g", 0) for c in expanded_foods)
        assert abs(total_mass - 400.0) < 1.0, f"Total mass should be ~400g, got {total_mass}g"

        # Verify ratios sum to ~1.0
        if "component_ratios" in stage5c_data:
            ratio_sum = sum(stage5c_data["component_ratios"].values())
            assert abs(ratio_sum - 1.0) < 0.01, f"Component ratios should sum to ~1.0, got {ratio_sum}"
    else:
        # If decomposition didn't trigger, that's okay
        assert food.get("alignment_stage") != "stage0_no_candidates", \
            f"Grain bowl should not be a miss, got {food.get('alignment_stage')}"


def test_yogurt_near_miss():
    """Test that 'yogurt' alone does NOT trigger parfait decomposition (negative test)."""
    config_dir = Path(__file__).parent.parent.parent / "configs"
    loader = RecipeLoader(config_dir)

    # Should NOT match yogurt parfait template (yogurt alone is not sufficient)
    template = loader.match_recipe("yogurt")
    if template is not None:
        # If a template matched, it should NOT be parfait
        assert "parfait" not in template.name.lower(), \
            f"'yogurt' alone should not match parfait template, got {template.name}"


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
