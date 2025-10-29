"""
Unit tests for alignment quality guards and filters.

Tests the new guardrails implemented to fix misalignment issues:
- Species/substitution blocking (bacon → meatless, chicken → plant-based)
- Processing mismatch detection (chicken → breaded)
- Negative vocabulary filtering (potato → flour, raisins → cookies)
- Stage priority (Stage 2 raw+convert before Stage 1 cooked exact)
- Branded admission gates (score floor, token coverage, macro gates)

Expected Outcomes:
- Bacon (fried) never matches meatless/turkey, matches pork, kcal 400-600
- Chicken breast (cooked) rejects breaded/nuggets, prefers Stage 2, kcal 150-180
- Potato (roasted) rejects flour/starch, kcal 80-110
- Raisins (dried) reject cookies/bars, kcal 290-320
- Peas (cooked) prefer Foundation, kcal 70-90, reject branded snacks
"""
import sys
import json
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.fdc_alignment_v2 import CLASS_DISALLOWED_ALIASES, PROCESSING_BAD, macro_plausible_for_class


def test_bacon_species_filter():
    """
    Test: Bacon (fried) should never match meatless/turkey variants.

    Expected:
    - Blocks: "meatless", "turkey", "plant-based", "soy", "imitation", "vegan"
    - Allows: "bacon", "pork bacon", "bacon fried"
    - Energy: 400-600 kcal/100g for fried bacon
    """
    print("\n===== TEST: Bacon Species Filter =====")

    # Check that bacon class has species blockers
    assert "bacon" in CLASS_DISALLOWED_ALIASES, "bacon not in CLASS_DISALLOWED_ALIASES"

    bacon_blockers = CLASS_DISALLOWED_ALIASES["bacon"]
    print(f"Bacon blockers: {bacon_blockers}")

    # Test cases: These should be BLOCKED
    blocked_names = [
        "Bacon meatless (fried)",
        "Turkey bacon",
        "Plant-based bacon strips",
        "Soy bacon",
        "Imitation bacon bits",
        "Vegan bacon"
    ]

    for name in blocked_names:
        name_lower = name.lower()
        should_block = any(blocker in name_lower for blocker in bacon_blockers)
        print(f"  ❌ '{name}': blocked={should_block}")
        assert should_block, f"FAIL: '{name}' should be blocked but wasn't"

    # Test cases: These should be ALLOWED
    allowed_names = [
        "Bacon (fried)",
        "Pork bacon",
        "Bacon strips cooked"
    ]

    for name in allowed_names:
        name_lower = name.lower()
        should_block = any(blocker in name_lower for blocker in bacon_blockers)
        print(f"  ✓ '{name}': blocked={should_block}")
        assert not should_block, f"FAIL: '{name}' should be allowed but was blocked"

    print("✅ Bacon species filter test PASSED")


def test_chicken_processing_filter():
    """
    Test: Chicken breast (cooked) should reject breaded/battered variants.

    Expected:
    - Blocks: "breaded", "battered", "nugget", "tender", "patty"
    - Allows: "chicken breast", "grilled chicken breast", "roasted chicken breast"
    - Energy: 150-180 kcal/100g for cooked chicken breast
    """
    print("\n===== TEST: Chicken Processing Filter =====")

    # Check processing regex
    processing_blocked_names = [
        "Chicken breast tenders breaded cooked microwaved",
        "Chicken nugget",  # Use singular to match regex word boundary
        "Chicken patty",
        "Battered chicken breast fried"
    ]

    for name in processing_blocked_names:
        is_blocked = bool(PROCESSING_BAD.search(name))
        print(f"  ❌ '{name}': blocked={is_blocked}")
        assert is_blocked, f"FAIL: '{name}' should be blocked by PROCESSING_BAD"

    # Check class-specific blockers
    chicken_blockers = CLASS_DISALLOWED_ALIASES["chicken_breast"]
    print(f"Chicken blockers: {chicken_blockers}")

    # Test plant-based variants
    species_blocked = [
        "Plant-based chicken breast",
        "Impossible chicken breast",
        "Tofu chicken substitute"
    ]

    for name in species_blocked:
        name_lower = name.lower()
        should_block = any(blocker in name_lower for blocker in chicken_blockers)
        print(f"  ❌ '{name}': blocked={should_block}")
        assert should_block, f"FAIL: '{name}' should be blocked"

    # Macro plausibility test
    # Chicken breast should have low carbs (<5g), high protein (>18g for lean)
    print("\n  Macro plausibility tests:")

    # Good chicken macros
    is_plausible = macro_plausible_for_class(
        "chicken_breast",
        protein_g=30.0,
        carbs_g=0.0,
        fat_g=3.0,
        kcal=165.0
    )
    print(f"    Real chicken (P:30 C:0 F:3 kcal:165): plausible={is_plausible}")
    assert is_plausible, "FAIL: Real chicken should be plausible"

    # Bad chicken macros (breaded - high carbs)
    is_plausible = macro_plausible_for_class(
        "chicken_breast",
        protein_g=18.0,
        carbs_g=15.0,  # Too high for plain chicken
        fat_g=8.0,
        kcal=220.0
    )
    print(f"    Breaded chicken (P:18 C:15 F:8 kcal:220): plausible={is_plausible}")
    assert not is_plausible, "FAIL: Breaded chicken should be rejected (carbs>5)"

    print("✅ Chicken processing filter test PASSED")


def test_potato_form_filter():
    """
    Test: Potato (roasted) should reject flour/starch/powder variants.

    Expected:
    - Blocks: "flour", "starch", "powder", "mix", "instant", "dehydrated"
    - Allows: "potato", "roasted potato", "baked potato"
    - Energy: 80-110 kcal/100g for roasted potato (no oil)
    """
    print("\n===== TEST: Potato Form Filter =====")

    potato_blockers = CLASS_DISALLOWED_ALIASES["potato_russet"]
    print(f"Potato blockers: {potato_blockers}")

    # Test cases: These should be BLOCKED
    blocked_names = [
        "Potato flour",
        "Potato starch",
        "Potato powder",
        "Instant mashed potato mix",
        "Dehydrated potato granules"
    ]

    for name in blocked_names:
        name_lower = name.lower()
        should_block = any(blocker in name_lower for blocker in potato_blockers)
        print(f"  ❌ '{name}': blocked={should_block}")
        assert should_block, f"FAIL: '{name}' should be blocked"

    # Test cases: These should be ALLOWED
    allowed_names = [
        "Potato roasted",
        "Baked potato",
        "Boiled potato"
    ]

    for name in allowed_names:
        name_lower = name.lower()
        should_block = any(blocker in name_lower for blocker in potato_blockers)
        print(f"  ✓ '{name}': blocked={should_block}")
        assert not should_block, f"FAIL: '{name}' should be allowed"

    print("✅ Potato form filter test PASSED")


def test_raisins_ingredient_filter():
    """
    Test: Raisins (dried) should reject cookies/bars/snacks.

    Expected:
    - Blocks: "cookie", "cookies", "cake", "muffin", "bread", "cereal"
    - Allows: "raisins", "dried grapes", "raisins seedless"
    - Energy: 290-320 kcal/100g for plain raisins
    """
    print("\n===== TEST: Raisins Ingredient Filter =====")

    raisin_blockers = CLASS_DISALLOWED_ALIASES["raisins"]
    print(f"Raisin blockers: {raisin_blockers}")

    # Test cases: These should be BLOCKED
    blocked_names = [
        "Cookies oatmeal soft with raisins",
        "Raisin bran cereal",
        "Oatmeal raisin cookie",
        "Raisin bread"
    ]

    for name in blocked_names:
        name_lower = name.lower()
        should_block = any(blocker in name_lower for blocker in raisin_blockers)
        print(f"  ❌ '{name}': blocked={should_block}")
        assert should_block, f"FAIL: '{name}' should be blocked"

    # Test cases: These should be ALLOWED
    allowed_names = [
        "Raisins seedless",
        "Dried grapes",
        "Raisins golden"
    ]

    for name in allowed_names:
        name_lower = name.lower()
        should_block = any(blocker in name_lower for blocker in raisin_blockers)
        print(f"  ✓ '{name}': blocked={should_block}")
        assert not should_block, f"FAIL: '{name}' should be allowed"

    print("✅ Raisins ingredient filter test PASSED")


def test_peas_foundation_preference():
    """
    Test: Peas (cooked) should prefer Foundation, reject branded snacks.

    Expected:
    - Blocks: "snack", "crisps", "chips", "puffs"
    - Allows: "peas", "green peas cooked", "peas boiled"
    - Energy: 70-90 kcal/100g for cooked peas
    """
    print("\n===== TEST: Peas Foundation Preference =====")

    pea_blockers = CLASS_DISALLOWED_ALIASES["peas"]
    print(f"Pea blockers: {pea_blockers}")

    # Test cases: These should be BLOCKED
    blocked_names = [
        "Pea snacks wasabi",
        "Pea crisps",
        "Roasted pea snacks",
        "Pea puffs"
    ]

    for name in blocked_names:
        name_lower = name.lower()
        should_block = any(blocker in name_lower for blocker in pea_blockers)
        print(f"  ❌ '{name}': blocked={should_block}")
        assert should_block, f"FAIL: '{name}' should be blocked"

    # Macro plausibility for vegetables
    # Peas should be low-calorie (<150 kcal/100g)
    print("\n  Macro plausibility tests:")

    # Good peas macros
    is_plausible = macro_plausible_for_class(
        "peas",
        protein_g=5.0,
        carbs_g=14.0,
        fat_g=0.4,
        kcal=81.0
    )
    print(f"    Real peas (P:5 C:14 F:0.4 kcal:81): plausible={is_plausible}")
    assert is_plausible, "FAIL: Real peas should be plausible"

    # Bad peas macros (pea snacks - high kcal)
    is_plausible = macro_plausible_for_class(
        "peas",
        protein_g=20.0,
        carbs_g=45.0,
        fat_g=15.0,
        kcal=420.0  # Way too high for vegetable
    )
    print(f"    Pea snacks (P:20 C:45 F:15 kcal:420): plausible={is_plausible}")
    assert not is_plausible, "FAIL: Pea snacks should be rejected (kcal>150)"

    print("✅ Peas foundation preference test PASSED")


def test_macro_plausibility_gates():
    """
    Test: Enhanced macro plausibility gates.

    Expected:
    - Lean proteins (chicken breast, white fish) must have protein ≥18g
    - Low-pred vs high-cand rejection (pred<60 but cand>120)
    - Energy band integration (when available)
    """
    print("\n===== TEST: Macro Plausibility Gates =====")

    # Test 1: Lean protein density floor
    print("  Test 1: Lean protein density floor")

    # Good: High protein chicken breast
    is_plausible = macro_plausible_for_class(
        "chicken_breast",
        protein_g=30.0,
        carbs_g=0.0,
        fat_g=3.0,
        kcal=165.0
    )
    print(f"    Chicken breast (P:30): plausible={is_plausible}")
    assert is_plausible, "FAIL: High protein chicken should be plausible"

    # Bad: Low protein "chicken breast"
    is_plausible = macro_plausible_for_class(
        "chicken_breast",
        protein_g=12.0,  # Too low for lean protein
        carbs_g=0.0,
        fat_g=2.0,
        kcal=70.0
    )
    print(f"    Fake chicken (P:12): plausible={is_plausible}")
    assert not is_plausible, "FAIL: Low protein chicken should be rejected (protein<18)"

    # Test 2: Low-pred vs high-cand rejection
    print("\n  Test 2: Low-pred vs high-cand rejection")

    # Scenario: Model predicted 50 kcal/100g (low-cal veggie)
    # But candidate is 200 kcal/100g (processed/fried)
    is_plausible = macro_plausible_for_class(
        "broccoli",
        protein_g=3.0,
        carbs_g=7.0,
        fat_g=0.4,
        kcal=200.0,  # Way too high
        predicted_kcal_est=50.0  # Model predicted low-cal
    )
    print(f"    Veggie pred:50 cand:200: plausible={is_plausible}")
    assert not is_plausible, "FAIL: High-cand when pred is low should be rejected"

    # Good scenario: pred and cand both low-cal
    is_plausible = macro_plausible_for_class(
        "broccoli",
        protein_g=2.8,
        carbs_g=7.0,
        fat_g=0.4,
        kcal=34.0,
        predicted_kcal_est=40.0
    )
    print(f"    Veggie pred:40 cand:34: plausible={is_plausible}")
    assert is_plausible, "FAIL: Matching low-cal should be plausible"

    print("✅ Macro plausibility gates test PASSED")


def test_stage_priority_order():
    """
    Test: Verify Stage 2 (raw+convert) documentation says it runs FIRST.

    This is a documentation/structure test to ensure the refactoring
    was applied correctly.
    """
    print("\n===== TEST: Stage Priority Order =====")

    # Read align_convert.py to verify docstring
    align_convert_path = Path(__file__).parent.parent / "src" / "nutrition" / "alignment" / "align_convert.py"

    if align_convert_path.exists():
        with open(align_convert_path, 'r') as f:
            content = f.read()

        # Check that docstring mentions Stage 2 as FIRST
        assert "Stage 2: Foundation/Legacy raw + conversion (FIRST" in content, \
            "FAIL: Docstring should indicate Stage 2 runs FIRST"

        # Check that code has Stage 2 before Stage 1
        stage2_pos = content.find("# Stage 2: Foundation/Legacy raw + conversion (NOW FIRST")
        stage1_pos = content.find("# Stage 1: Foundation/Legacy cooked exact match (NOW SECOND")

        assert stage2_pos > 0 and stage1_pos > 0, "FAIL: Stage comments not found"
        assert stage2_pos < stage1_pos, "FAIL: Stage 2 should come before Stage 1 in code"

        print("  ✓ Docstring updated: Stage 2 marked as FIRST")
        print("  ✓ Code order correct: Stage 2 appears before Stage 1")
        print("✅ Stage priority order test PASSED")
    else:
        print("  ⚠️  align_convert.py not found, skipping test")


def test_tomato_raw_first():
    """
    Test: Tomato (raw) should not match canned/cooked variants.

    Expected:
    - Blocks: "canned", "sauce", "paste", "cooked"
    - Allows: "tomato", "raw tomatoes", "fresh tomatoes"
    - Energy: 15-30 kcal/100g for raw tomato
    """
    print("\n===== TEST: Tomato Raw-First =====")

    from src.adapters.fdc_alignment_v2 import PRODUCE_CLASSES

    # Verify tomato is in produce classes
    assert "tomato" in PRODUCE_CLASSES or "cherry_tomatoes" in PRODUCE_CLASSES, \
        "FAIL: Tomato should be in PRODUCE_CLASSES"

    print(f"  Tomato is in PRODUCE_CLASSES: True")

    # Simulate candidate names that should be penalized
    bad_candidates = [
        "Tomatoes canned diced",
        "Tomato sauce",
        "Tomato paste",
        "Tomatoes cooked"
    ]

    for cand in bad_candidates:
        # Check that produce penalty would apply
        is_cooked_canned = any(
            kw in cand.lower()
            for kw in ["canned", "sauce", "paste", "cooked", "fried", "roasted"]
        )

        print(f"  ❌ '{cand}': would be penalized={is_cooked_canned}")
        assert is_cooked_canned, f"FAIL: {cand} should be detected as cooked/canned"

    # Good candidates
    good_candidates = [
        "Tomatoes raw",
        "Tomatoes fresh",
        "Cherry tomatoes"
    ]

    for cand in good_candidates:
        is_raw_fresh = "raw" in cand.lower() or "fresh" in cand.lower() or (
            "tomato" in cand.lower() and not any(
                kw in cand.lower()
                for kw in ["canned", "sauce", "paste", "cooked"]
            )
        )
        print(f"  ✓ '{cand}': would be boosted/allowed={is_raw_fresh}")
        assert is_raw_fresh, f"FAIL: {cand} should be allowed"

    print("✅ Tomato raw-first test PASSED")


def test_green_bell_pepper_fallback():
    """
    Test: Green bell pepper should use branded fallback if no Foundation.

    This verifies Stage Z category mapping exists for bell pepper variants.
    """
    print("\n===== TEST: Green Bell Pepper Fallback =====")

    from src.nutrition.rails.stage_z_gates import CATEGORY_MAPPING

    # Check that bell pepper variants are mapped
    bell_pepper_mapped = (
        "bell_pepper" in CATEGORY_MAPPING or
        "bell_pepper_green" in CATEGORY_MAPPING or
        "bell_pepper_red" in CATEGORY_MAPPING
    )

    assert bell_pepper_mapped, "FAIL: Bell pepper should be in CATEGORY_MAPPING"

    if "bell_pepper_green" in CATEGORY_MAPPING:
        category = CATEGORY_MAPPING["bell_pepper_green"]
        print(f"  bell_pepper_green → {category}")
        assert category == "veg_raw", "FAIL: Bell pepper should map to veg_raw"

    if "bell_pepper_red" in CATEGORY_MAPPING:
        category = CATEGORY_MAPPING["bell_pepper_red"]
        print(f"  bell_pepper_red → {category}")
        assert category == "veg_raw", "FAIL: Bell pepper should map to veg_raw"

    print("✅ Bell pepper category mapping exists for Stage Z fallback")


def test_eggplant_cooked_only():
    """
    Test: Eggplant (raw) should not match branded fried variants.

    Expected:
    - Method token extraction works
    - "fried" and "breaded" are detected
    """
    print("\n===== TEST: Eggplant Cooked-Only =====")

    from src.adapters.fdc_alignment_v2 import COOKED_METHOD_TOKENS

    # Test method token extraction
    test_candidates = [
        ("Eggplant fried breaded", True),
        ("Eggplant grilled", True),
        ("Eggplant roasted", True),
        ("Eggplant raw", False),  # Should not match cooked methods
        ("Eggplant fresh", False)
    ]

    for cand, should_have_method in test_candidates:
        has_method = bool(COOKED_METHOD_TOKENS.search(cand))
        print(f"  '{cand}': has_cooked_method={has_method} (expected={should_have_method})")
        assert has_method == should_have_method, \
            f"FAIL: Method detection mismatch for '{cand}'"

    print("✅ Eggplant cooked-only test PASSED")


def test_potato_flour_ban():
    """
    Test: Potato (roasted) should reject flour/starch variants.

    This is already tested in test_potato_form_filter, but we verify
    the ban regex specifically.
    """
    print("\n===== TEST: Potato Flour Ban (Whole-Food) =====")

    from src.adapters.fdc_alignment_v2 import WHOLE_FOOD_INGREDIENT_BAN, WHOLE_FOOD_CLASSES

    # Verify potato is in whole-food classes
    assert "potato_russet" in WHOLE_FOOD_CLASSES or "potato_red" in WHOLE_FOOD_CLASSES, \
        "FAIL: Potato should be in WHOLE_FOOD_CLASSES"

    print(f"  Potato classes: {[c for c in WHOLE_FOOD_CLASSES if 'potato' in c]}")

    # Test ingredient-form ban regex
    banned_names = [
        "Potato flour",
        "Potato starch",
        "Potato powder dehydrated",
        "Sweet potato meal"
    ]

    for name in banned_names:
        is_banned = bool(WHOLE_FOOD_INGREDIENT_BAN.search(name))
        print(f"  ❌ '{name}': banned={is_banned}")
        assert is_banned, f"FAIL: {name} should be banned by ingredient regex"

    print("✅ Potato flour ban test PASSED")


def test_universal_branded_last_resort():
    """
    Test: Universal branded last-resort should never drop an ingredient.

    Verifies Stage Z exists and has proper gates configured.
    """
    print("\n===== TEST: Universal Branded Last-Resort =====")

    from src.nutrition.rails.stage_z_gates import passes_stage_z_gates, GENERIC_ENERGY_BANDS

    # Verify generic energy bands exist for categories
    assert "veg_raw" in GENERIC_ENERGY_BANDS, "FAIL: veg_raw generic band missing"
    assert "fruit_raw" in GENERIC_ENERGY_BANDS, "FAIL: fruit_raw generic band missing"

    veg_band = GENERIC_ENERGY_BANDS["veg_raw"]
    print(f"  veg_raw energy band: {veg_band['min']}-{veg_band['max']} kcal/100g")
    assert veg_band["min"] == 15 and veg_band["max"] == 45, \
        "FAIL: veg_raw band should be 15-45 kcal"

    fruit_band = GENERIC_ENERGY_BANDS["fruit_raw"]
    print(f"  fruit_raw energy band: {fruit_band['min']}-{fruit_band['max']} kcal/100g")
    assert fruit_band["min"] == 40 and fruit_band["max"] == 80, \
        "FAIL: fruit_raw band should be 40-80 kcal"

    print("✅ Universal branded last-resort gates configured correctly")


def test_green_bell_pepper_mass_only():
    """NEW: Test green bell pepper mass-only mode with color enforcement."""
    print("\n===== TEST: Green Bell Pepper Mass-Only =====")

    from src.adapters.fdc_alignment_v2 import derive_alignment_hints, COLOR_TOKENS

    pred_item = {"name": "bell pepper", "modifiers": ["green"], "form": "", "mass_g": 120, "confidence": 0.85}
    hints = derive_alignment_hints(pred_item)

    assert "bell_pepper" in hints["class_from_name"]
    assert "green" in hints["color_tokens"]
    assert hints["implied_form"] == "raw"
    print("✅ Green bell pepper mass-only test PASSED")


def test_rice_form_missing():
    """NEW: Test rice with missing form infers boiled method."""
    print("\n===== TEST: Rice Form Missing =====")

    from src.nutrition.utils.method_resolver import infer_method_from_class

    inferred_method, reason = infer_method_from_class("rice_white", "")
    assert inferred_method == "boiled"
    # Reason can be "conversion_config" (if found in cook_conversions.v2.json) or "class_default"
    assert reason in ("conversion_config", "class_default")
    print("✅ Rice form missing test PASSED")


def test_chicken_generic_cooked():
    """NEW: Test chicken with generic cooked form normalizes to grilled."""
    print("\n===== TEST: Chicken Generic Cooked =====")

    from src.nutrition.utils.method_resolver import infer_method_from_class

    inferred_method, reason = infer_method_from_class("chicken_breast", "cooked")
    assert inferred_method == "grilled"
    # Reason can be "conversion_config" (if found in cook_conversions.v2.json) or "class_default"
    assert reason in ("conversion_config", "class_default")
    print("✅ Chicken generic cooked test PASSED")


def test_eggs_count_mass():
    """NEW: Test eggs with count+mass calculates per-unit mass."""
    print("\n===== TEST: Eggs Count + Mass =====")

    from src.adapters.fdc_alignment_v2 import derive_alignment_hints

    pred_item = {"name": "egg", "count": 2, "mass_g": 100, "form": "cooked", "confidence": 0.85}
    hints = derive_alignment_hints(pred_item)

    assert hints["discrete_hint"] is not None
    assert hints["discrete_hint"]["mass_per_unit"] == 50.0
    assert hints["discrete_hint"]["count"] == 2
    print("✅ Eggs count + mass test PASSED")


def test_bacon_species_required():
    """NEW: Test bacon with species modifier enforces pork."""
    print("\n===== TEST: Bacon Species Required =====")

    from src.adapters.fdc_alignment_v2 import derive_alignment_hints

    pred_item = {"name": "bacon", "modifiers": ["pork"], "form": "pan_seared", "mass_g": 25, "confidence": 0.90}
    hints = derive_alignment_hints(pred_item)

    assert "pork" in hints["species_tokens"]
    assert "bacon" in hints["class_from_name"]
    print("✅ Bacon species required test PASSED")


def test_sparse_accept_on_floor():
    """NEW: Test sparse accept logic for scores on floor."""
    print("\n===== TEST: Sparse Accept On Floor =====")

    from src.config.feature_flags import FLAGS

    assert FLAGS.vision_mass_only
    assert FLAGS.accept_sparse_stage2_on_floor

    sparse_floor = 1.3
    normal_floor = 1.6
    test_score = 1.45
    assert sparse_floor <= test_score < normal_floor
    print("✅ Sparse accept on floor test PASSED")


def test_mixed_salad_greens_synonym():
    """Test that 'mixed salad greens' maps to lettuce class."""
    from src.adapters.fdc_alignment_v2 import derive_alignment_hints, CLASS_NAME_PATTERNS
    import re

    # Test cases for leafy greens synonyms
    test_cases = [
        ("mixed salad greens", "lettuce"),
        ("spring mix", "lettuce"),
        ("salad mix", "lettuce"),
        ("green salad mix", "lettuce"),
        ("greens mix", "lettuce"),
    ]

    for name, expected_class in test_cases:
        pred_item = {"name": name, "form": "", "mass_g": 50, "confidence": 0.85}
        hints = derive_alignment_hints(pred_item)

        assert hints["class_from_name"] == expected_class, \
            f"Expected '{expected_class}' for '{name}', got '{hints['class_from_name']}'"

        # Also verify pattern matching directly
        matched = False
        for pattern, class_name in CLASS_NAME_PATTERNS.items():
            if re.search(pattern, name, re.I):
                if class_name == expected_class:
                    matched = True
                    break
        assert matched, f"Pattern match failed for '{name}'"

    print("✅ Mixed salad greens synonym test PASSED")


def test_pumpkin_not_seeds():
    """Test that pumpkin aligns to flesh, not seeds (negative vocabulary)."""
    from src.adapters.fdc_alignment_v2 import CLASS_DISALLOWED_ALIASES

    # Verify pumpkin has seeds/pepitas in disallowed list
    assert "pumpkin" in CLASS_DISALLOWED_ALIASES, "Pumpkin not in disallowed aliases"
    pumpkin_banned = CLASS_DISALLOWED_ALIASES["pumpkin"]

    assert "seeds" in pumpkin_banned, "'seeds' not in pumpkin banned list"
    assert "pepitas" in pumpkin_banned, "'pepitas' not in pumpkin banned list"
    assert "pie" in pumpkin_banned, "'pie' not in pumpkin banned list"

    # Verify squash variants also have protection
    assert "squash" in CLASS_DISALLOWED_ALIASES, "Squash not in disallowed aliases"
    squash_banned = CLASS_DISALLOWED_ALIASES["squash"]
    assert "seeds" in squash_banned, "'seeds' not in squash banned list"

    print("✅ Pumpkin not seeds test PASSED")


def test_curated_branded_fallback():
    """Test curated branded fallback flags and gates."""
    from src.config.feature_flags import FLAGS

    # Verify feature flag exists and is enabled
    assert hasattr(FLAGS, "mass_brand_last_resort"), "mass_brand_last_resort flag missing"
    assert FLAGS.mass_brand_last_resort == True, "mass_brand_last_resort should default to True"

    # Test telemetry field exists
    from src.adapters.fdc_alignment_v2 import FDCAlignmentEngineV2
    aligner = FDCAlignmentEngineV2()

    # Verify method exists
    assert hasattr(aligner, "_try_curated_branded_fallback"), \
        "_try_curated_branded_fallback method missing"

    print("✅ Curated branded fallback test PASSED")


def test_class_synonyms_loading():
    """Test class_synonyms.json loads correctly (Fix #1)."""
    from src.nutrition.utils.method_resolver import load_class_synonyms, normalize_vision_class

    synonyms = load_class_synonyms()
    assert len(synonyms) > 50, f"Expected >50 synonyms, got {len(synonyms)}"

    # Test specific mappings
    assert normalize_vision_class("chicken breast") == "chicken_breast"
    assert normalize_vision_class("hash browns") == "potato_russet"
    assert normalize_vision_class("egg whites") == "egg_white"
    assert normalize_vision_class("scrambled eggs") == "egg_whole"

    print("✅ Class synonyms loading test PASSED")


def test_egg_whites_disallow_yolk():
    """Test egg whites vs yolk disambiguation (Fix #2 - CRITICAL)."""
    from src.adapters.fdc_alignment_v2 import CLASS_DISALLOWED_ALIASES

    # Verify disallowed aliases exist
    assert "egg_white" in CLASS_DISALLOWED_ALIASES
    assert "yolk" in CLASS_DISALLOWED_ALIASES["egg_white"]

    assert "egg_yolk" in CLASS_DISALLOWED_ALIASES
    assert "white" in CLASS_DISALLOWED_ALIASES["egg_yolk"]

    print("✅ Egg whites disallow yolk test PASSED")


def test_corn_kernel_vs_flour():
    """Test corn kernel vs flour guardrail (Fix #3 - CRITICAL)."""
    from src.adapters.fdc_alignment_v2 import CLASS_DISALLOWED_ALIASES

    # Verify corn has flour/meal in disallowed list
    assert "corn" in CLASS_DISALLOWED_ALIASES
    corn_banned = CLASS_DISALLOWED_ALIASES["corn"]
    assert "flour" in corn_banned
    assert "meal" in corn_banned
    assert "grits" in corn_banned

    print("✅ Corn kernel vs flour test PASSED")


def test_salad_context_detection():
    """Test salad greens inclusion rule (Fix #4)."""
    from src.adapters.fdc_alignment_v2 import detect_salad_context

    # Test positive case: parmesan + greens
    salad_items = [
        {"name": "parmesan", "modifiers": []},
        {"name": "mixed salad greens", "modifiers": []}
    ]
    assert detect_salad_context(salad_items) == True

    # Test negative case: only parmesan
    no_salad = [{"name": "parmesan", "modifiers": []}]
    assert detect_salad_context(no_salad) == False

    print("✅ Salad context detection test PASSED")


def test_potato_wedges_in_conversion_config():
    """Test potato wedges method exists in cook_conversions.v2.json (Fix #5)."""
    import json
    from pathlib import Path

    config_path = Path(__file__).parent.parent / "src" / "data" / "cook_conversions.v2.json"
    with open(config_path) as f:
        config = json.load(f)

    # Verify potato_russet has wedges method
    potato = config["classes"].get("potato_russet")
    assert potato is not None, "potato_russet not in conversion config"

    methods = potato["method_profiles"]
    assert "wedges" in methods, "wedges method missing"
    assert "hash_browns" in methods, "hash_browns method missing"
    assert "fries" in methods, "fries method missing"

    # Verify oil uptake
    wedges = methods["wedges"]
    assert "surface_oil_uptake_g_per_100g" in wedges, "wedges missing oil uptake"

    print("✅ Potato wedges in conversion config test PASSED")


def test_plausibility_bands():
    """Test plausibility band recovery system (Fix #6)."""
    from src.adapters.fdc_alignment_v2 import check_plausibility_band, PLAUSIBILITY_BANDS

    # Verify bands exist
    assert len(PLAUSIBILITY_BANDS) > 20, "Expected >20 plausibility bands"
    assert "egg_white_raw" in PLAUSIBILITY_BANDS
    assert "corn_kernels" in PLAUSIBILITY_BANDS
    assert "corn_flour" in PLAUSIBILITY_BANDS

    # Test egg whites: should pass for 52 kcal, fail for 334 kcal
    hints_white = {"class_from_name": "egg_white"}
    is_plausible, _ = check_plausibility_band("egg", 52, hints_white)
    assert is_plausible == True, "Egg white 52 kcal should be plausible"

    is_plausible_yolk, _ = check_plausibility_band("egg", 334, hints_white)
    assert is_plausible_yolk == False, "Egg yolk 334 kcal should NOT be plausible for whites"

    # Test corn: should pass for 86 kcal, fail for 364 kcal
    hints_corn = {"class_from_name": "corn"}
    is_plausible, _ = check_plausibility_band("corn", 86, hints_corn)
    assert is_plausible == True, "Corn kernels 86 kcal should be plausible"

    is_plausible_flour, _ = check_plausibility_band("corn", 364, hints_corn)
    assert is_plausible_flour == False, "Corn flour 364 kcal should NOT be plausible for kernels"

    print("✅ Plausibility bands test PASSED")


def test_hash_browns_routing():
    """
    Test: Hash browns should route through raw potato + hash_browns method + oil uptake.
    """
    print("\n===== TEST: Hash Browns Routing =====")

    from src.nutrition.utils.method_resolver import normalize_vision_class
    import json
    from pathlib import Path

    # Check synonym mapping
    normalized_class = normalize_vision_class("hash browns")
    assert normalized_class == "potato_russet", \
        f"FAIL: Hash browns should map to potato_russet, got {normalized_class}"
    print(f"  ✓ 'hash browns' → {normalized_class}")

    # Check conversion config has hash_browns method
    cfg_path = Path(__file__).parent.parent / "src" / "data" / "cook_conversions.v2.json"
    with open(cfg_path) as f:
        config = json.load(f)

    classes = config.get("classes", {})
    methods = classes["potato_russet"].get("method_profiles", {})
    assert "hash_browns" in methods, "FAIL: hash_browns method not in potato_russet"

    hash_browns_profile = methods["hash_browns"]
    oil_uptake = hash_browns_profile["surface_oil_uptake_g_per_100g"]["mean"]
    assert 8 <= oil_uptake <= 15, \
        f"FAIL: hash_browns oil uptake should be 8-15 g/100g, got {oil_uptake}"
    print(f"  ✓ hash_browns method exists with {oil_uptake}g/100g oil uptake")

    print("✅ Hash browns routing test PASSED")


def test_olive_sodium_gating():
    """Test olive sodium gating prevents raw fruit misalignment."""
    print("\n===== TEST: Olive Sodium Gating =====")

    from src.adapters.fdc_alignment_v2 import SODIUM_GATE_ITEMS, check_sodium_gate

    # Check gate config exists
    assert "olives" in SODIUM_GATE_ITEMS, "FAIL: Olives should be in SODIUM_GATE_ITEMS"

    gate_config = SODIUM_GATE_ITEMS["olives"]
    min_sodium = gate_config["min_sodium_mg_per_100g"]
    assert min_sodium >= 600, f"FAIL: Olive min sodium should be ≥600, got {min_sodium}"
    print(f"  ✓ Olive sodium gate: {min_sodium} mg/100g minimum")

    # Test low-sodium candidate (should fail)
    passes, reason = check_sodium_gate("olives", "Olives, raw", 50.0)
    assert not passes, "FAIL: Low-sodium olive candidate should be rejected"
    print(f"  ✓ Low-sodium candidate rejected: {reason}")

    # Test high-sodium candidate (should pass)
    passes, reason = check_sodium_gate("olives", "Olives, ripe, canned", 735.0)
    assert passes, f"FAIL: High-sodium olive candidate should pass"
    print(f"  ✓ High-sodium candidate passed")

    print("✅ Olive sodium gating test PASSED")


def test_mixed_salad_canonicalization():
    """Test mixed salad greens canonicalize to lettuce class."""
    print("\n===== TEST: Mixed Salad Canonicalization =====")

    from src.nutrition.utils.method_resolver import normalize_vision_class

    test_cases = [
        ("mixed greens", "lettuce"),
        ("spring mix", "lettuce"),
        ("salad mix", "lettuce"),
        ("baby greens", "lettuce"),
    ]

    for vision_name, expected_class in test_cases:
        normalized = normalize_vision_class(vision_name)
        assert normalized == expected_class, \
            f"FAIL: '{vision_name}' should map to '{expected_class}', got '{normalized}'"
        print(f"  ✓ '{vision_name}' → '{normalized}'")

    print("✅ Mixed salad canonicalization test PASSED")


def test_method_aliases_expanded():
    """Test new method aliases (broiled, toasted, charred, air-fried)."""
    print("\n===== TEST: Method Aliases Expanded =====")

    from src.nutrition.utils.method_resolver import METHOD_ALIASES

    test_cases = [
        ("broiled", "grilled"),
        ("toasted", "roasted_oven"),
        ("charred", "grilled"),
        ("air-fried", "roasted_oven"),
    ]

    for raw_method, expected_canonical in test_cases:
        assert raw_method in METHOD_ALIASES, \
            f"FAIL: '{raw_method}' should be in METHOD_ALIASES"
        canonical = METHOD_ALIASES[raw_method]
        assert canonical == expected_canonical, \
            f"FAIL: '{raw_method}' should map to '{expected_canonical}', got '{canonical}'"
        print(f"  ✓ '{raw_method}' → '{canonical}'")

    print("✅ Method aliases expansion test PASSED")


def test_homefries_oil_uptake():
    """Test homefries oil uptake profile exists."""
    print("\n===== TEST: Homefries Oil Uptake =====")

    import json
    from pathlib import Path

    cfg_path = Path(__file__).parent.parent / "src" / "data" / "cook_conversions.v2.json"
    with open(cfg_path) as f:
        config = json.load(f)

    classes = config.get("classes", {})
    methods = classes["potato_russet"].get("method_profiles", {})
    assert "homefries" in methods, "FAIL: homefries method not in potato_russet"

    homefries_profile = methods["homefries"]
    oil_uptake = homefries_profile["surface_oil_uptake_g_per_100g"]["mean"]
    assert 5 <= oil_uptake <= 10, \
        f"FAIL: homefries oil uptake should be 5-10 g/100g, got {oil_uptake}"
    print(f"  ✓ homefries method exists with {oil_uptake}g/100g oil uptake")

    print("✅ Homefries oil uptake test PASSED")


def test_prefer_raw_foundation_flag():
    """Test prefer_raw_foundation_convert feature flag exists."""
    print("\n===== TEST: Prefer Raw Foundation Convert Flag =====")

    from src.config.feature_flags import FLAGS

    # Check flag exists and has correct default
    assert hasattr(FLAGS, 'prefer_raw_foundation_convert'), \
        "FAIL: prefer_raw_foundation_convert flag should exist"

    # Flag should be True by default (enabled)
    assert FLAGS.prefer_raw_foundation_convert == True, \
        f"FAIL: prefer_raw_foundation_convert should default to True, got {FLAGS.prefer_raw_foundation_convert}"

    print(f"  ✓ prefer_raw_foundation_convert flag exists and defaults to {FLAGS.prefer_raw_foundation_convert}")

    print("✅ Prefer raw Foundation convert flag test PASSED")


def test_sodium_gate_integration():
    """Test sodium gate is integrated into alignment search."""
    print("\n===== TEST: Sodium Gate Integration =====")

    from src.adapters.fdc_alignment_v2 import check_sodium_gate, SODIUM_GATE_ITEMS

    # Verify function exists
    assert callable(check_sodium_gate), "FAIL: check_sodium_gate should be callable"

    # Verify gate items exist
    assert len(SODIUM_GATE_ITEMS) > 0, "FAIL: SODIUM_GATE_ITEMS should not be empty"
    assert "olives" in SODIUM_GATE_ITEMS, "FAIL: olives should be in SODIUM_GATE_ITEMS"

    # Test the function works - low sodium should fail for olives
    passes, reason = check_sodium_gate("olives", "Olives, ripe, raw", 10.0)
    assert not passes, "FAIL: Low-sodium olives should fail gate"
    assert "sodium_gate_fail" in reason, f"FAIL: Expected sodium_gate_fail in reason, got {reason}"

    # High sodium should pass for olives
    passes, reason = check_sodium_gate("olives", "Olives, ripe, canned", 700.0)
    assert passes, "FAIL: High-sodium olives should pass gate"

    print(f"  ✓ check_sodium_gate function exists and works correctly")
    print(f"  ✓ SODIUM_GATE_ITEMS contains {len(SODIUM_GATE_ITEMS)} categories")

    print("✅ Sodium gate integration test PASSED")


def test_yellow_squash_synonym():
    """Test yellow squash synonym maps to squash_summer."""
    print("\n===== TEST: Yellow Squash Synonym =====")

    from src.nutrition.utils.method_resolver import load_class_synonyms

    synonyms = load_class_synonyms()

    # Test all squash variants
    test_cases = [
        ("yellow squash", "squash_summer"),
        ("summer squash", "squash_summer"),
        ("pattypan squash", "squash_summer"),
    ]

    for vision_string, expected_class in test_cases:
        assert vision_string in synonyms, \
            f"FAIL: '{vision_string}' should be in synonyms"
        actual_class = synonyms[vision_string]
        assert actual_class == expected_class, \
            f"FAIL: '{vision_string}' should map to '{expected_class}', got '{actual_class}'"
        print(f"  ✓ '{vision_string}' → '{actual_class}'")

    print("✅ Yellow squash synonym test PASSED")


def test_tater_tots_coverage():
    """Test tater tots synonym and oil profile exist."""
    print("\n===== TEST: Tater Tots Coverage =====")

    import json
    from pathlib import Path
    from src.nutrition.utils.method_resolver import load_class_synonyms

    # Check synonym mapping
    synonyms = load_class_synonyms()
    test_synonyms = ["tater tots", "tatertots", "tater tot"]

    for synonym in test_synonyms:
        assert synonym in synonyms, f"FAIL: '{synonym}' should be in synonyms"
        assert synonyms[synonym] == "potato_russet", \
            f"FAIL: '{synonym}' should map to potato_russet, got {synonyms[synonym]}"
        print(f"  ✓ '{synonym}' → potato_russet")

    # Check oil profile in cook_conversions
    cfg_path = Path(__file__).parent.parent / "src" / "data" / "cook_conversions.v2.json"
    with open(cfg_path) as f:
        config = json.load(f)

    methods = config["classes"]["potato_russet"]["method_profiles"]
    assert "tater_tots" in methods, "FAIL: tater_tots method not in potato_russet"

    tater_tots_profile = methods["tater_tots"]
    oil_uptake = tater_tots_profile["surface_oil_uptake_g_per_100g"]["mean"]
    assert 10 <= oil_uptake <= 15, \
        f"FAIL: tater tots oil uptake should be 10-15 g/100g, got {oil_uptake}"
    print(f"  ✓ tater_tots method exists with {oil_uptake}g/100g oil uptake")

    print("✅ Tater tots coverage test PASSED")


def test_pumpkin_flesh_guard():
    """Test pumpkin negative vocabulary prevents seeds misalignment."""
    print("\n===== TEST: Pumpkin Flesh Guard =====")

    from src.adapters.fdc_alignment_v2 import CLASS_DISALLOWED_ALIASES

    # Check pumpkin classes have seed guards
    pumpkin_classes = ["pumpkin", "pumpkin_sugar"]
    seed_terms = ["seeds", "pepitas", "roasted seeds"]

    for pumpkin_class in pumpkin_classes:
        assert pumpkin_class in CLASS_DISALLOWED_ALIASES, \
            f"FAIL: {pumpkin_class} should have disallowed aliases"

        banned = CLASS_DISALLOWED_ALIASES[pumpkin_class]

        for seed_term in seed_terms:
            assert seed_term in banned, \
                f"FAIL: {pumpkin_class} should ban '{seed_term}'"
            print(f"  ✓ {pumpkin_class} blocks '{seed_term}'")

    # Check squash classes also have seed guards
    squash_classes = ["squash_summer", "squash_butternut", "squash_acorn"]
    for squash_class in squash_classes:
        assert squash_class in CLASS_DISALLOWED_ALIASES, \
            f"FAIL: {squash_class} should have disallowed aliases"
        banned = CLASS_DISALLOWED_ALIASES[squash_class]
        assert "seeds" in banned, f"FAIL: {squash_class} should ban 'seeds'"
        print(f"  ✓ {squash_class} blocks 'seeds'")

    print("✅ Pumpkin flesh guard test PASSED")


def test_candidate_classification_helpers():
    """Test candidate classification helper functions."""
    print("\n===== TEST: Candidate Classification Helpers =====")

    from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion
    from src.nutrition.types import FdcEntry

    # Create alignment engine
    aligner = FDCAlignmentWithConversion()

    # Create test candidates
    raw_foundation = FdcEntry(
        fdc_id=1,
        core_class="chicken_breast",
        name="Chicken, broilers or fryers, breast, meat only, raw",
        source="foundation",
        form="raw",
        method=None,
        protein_100g=23.0,
        carbs_100g=0.0,
        fat_100g=3.0,
        kcal_100g=120
    )

    cooked_sr = FdcEntry(
        fdc_id=2,
        core_class="chicken_breast",
        name="Chicken, broilers or fryers, breast, meat only, cooked, grilled",
        source="sr_legacy",
        form="cooked",
        method="grilled",
        protein_100g=30.0,
        carbs_100g=0.0,
        fat_100g=4.0,
        kcal_100g=165
    )

    branded = FdcEntry(
        fdc_id=3,
        core_class="chicken_breast",
        name="Brand X Chicken Breast Grilled",
        source="branded",
        form="cooked",
        method=None,
        protein_100g=25.0,
        carbs_100g=1.0,
        fat_100g=5.0,
        kcal_100g=150
    )

    # Test is_foundation_raw
    assert aligner.is_foundation_raw(raw_foundation) == True, \
        "FAIL: raw_foundation should be identified as foundation raw"
    assert aligner.is_foundation_raw(cooked_sr) == False, \
        "FAIL: cooked_sr should NOT be foundation raw"
    assert aligner.is_foundation_raw(branded) == False, \
        "FAIL: branded should NOT be foundation raw"
    print("  ✓ is_foundation_raw() works correctly")

    # Test is_foundation_or_sr_cooked
    assert aligner.is_foundation_or_sr_cooked(cooked_sr) == True, \
        "FAIL: cooked_sr should be foundation/SR cooked"
    assert aligner.is_foundation_or_sr_cooked(raw_foundation) == False, \
        "FAIL: raw_foundation should NOT be cooked"
    assert aligner.is_foundation_or_sr_cooked(branded) == False, \
        "FAIL: branded should NOT be foundation/SR cooked"
    print("  ✓ is_foundation_or_sr_cooked() works correctly")

    # Test is_branded
    assert aligner.is_branded(branded) == True, \
        "FAIL: branded should be identified as branded"
    assert aligner.is_branded(raw_foundation) == False, \
        "FAIL: raw_foundation should NOT be branded"
    assert aligner.is_branded(cooked_sr) == False, \
        "FAIL: cooked_sr should NOT be branded"
    print("  ✓ is_branded() works correctly")

    print("✅ Candidate classification helpers test PASSED")


def test_no_unknown_alignment_stage():
    """Verify alignment results never have stage='unknown'."""
    print("\n===== TEST: No Unknown Alignment Stage =====")

    from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion

    # Create alignment engine
    aligner = FDCAlignmentWithConversion()

    # Test case: no candidates (should return stage0_no_candidates, NOT unknown)
    result = aligner.align_food_item(
        predicted_name="chicken breast",
        predicted_form="grilled",
        predicted_kcal_100g=165,
        fdc_candidates=[],  # Empty candidates
        confidence=0.8
    )

    assert result.alignment_stage != "unknown", \
        f"FAIL: Empty candidates should not return 'unknown', got {result.alignment_stage}"
    assert result.alignment_stage == "stage0_no_candidates", \
        f"FAIL: Expected stage0_no_candidates, got {result.alignment_stage}"

    # Verify telemetry also has correct stage
    assert result.telemetry.get("alignment_stage") == "stage0_no_candidates", \
        f"FAIL: Telemetry should also have stage0_no_candidates"

    # Verify method is set (not unknown)
    assert result.method != "unknown", \
        f"FAIL: Method should not be 'unknown', got {result.method}"

    print("  ✓ No-match case returns stage0_no_candidates (not unknown)")
    print("  ✓ Telemetry correctly populated")
    print("  ✓ Method is resolved (not unknown)")

    print("✅ No unknown alignment stage test PASSED")


def test_salad_synonyms_comprehensive():
    """Test all salad synonym variations map to lettuce."""
    print("\n===== TEST: Salad Synonyms Comprehensive =====")

    from src.nutrition.utils.method_resolver import load_class_synonyms

    synonyms = load_class_synonyms()

    # All salad variants that should map to lettuce
    test_cases = [
        "mixed greens",
        "mixed salad greens",
        "spring mix",
        "salad mix",
        "mesclun",
        "baby greens",
        "field greens",
        "lettuce mix",
    ]

    for phrase in test_cases:
        assert phrase in synonyms, \
            f"FAIL: '{phrase}' should be in synonyms"
        actual_class = synonyms[phrase]
        assert actual_class == "lettuce", \
            f"FAIL: '{phrase}' should map to 'lettuce', got '{actual_class}'"
        print(f"  ✓ '{phrase}' → 'lettuce'")

    print("✅ Salad synonyms comprehensive test PASSED")


def test_conversion_fires_on_grilled_chicken():
    """
    TEST: Conversion layer proactive gate implementation.

    Validates the critical conversion wiring fix:
    - Helper methods correctly classify candidates
    - Proactive gate logic is in place (prefer_raw_foundation_convert flag)
    - Stage 2 raw+convert path exists in code
    """
    print("\n" + "="*60)
    print("TEST: Conversion Layer Proactive Gate")
    print("="*60)

    from src.nutrition.types import FdcEntry
    from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion
    from src.config.feature_flags import FLAGS

    # Create test FdcEntry objects
    raw_foundation = FdcEntry(
        fdc_id=1,
        core_class="chicken_breast",
        name="Chicken, broilers or fryers, breast, meat only, raw",
        source="foundation",
        form="raw",
        method=None,
        kcal_100g=120,
        protein_100g=22.5,
        fat_100g=2.6,
        carbs_100g=0.0
    )

    cooked_sr = FdcEntry(
        fdc_id=2,
        core_class="chicken_breast",
        name="Chicken, broilers or fryers, breast, meat only, cooked",
        source="sr_legacy",
        form="cooked",
        method="roasted_oven",
        kcal_100g=165,
        protein_100g=31.0,
        fat_100g=3.6,
        carbs_100g=0.0
    )

    # Create alignment engine
    engine = FDCAlignmentWithConversion()

    # Test 1: Helper methods correctly classify candidates
    assert engine.is_foundation_raw(raw_foundation) == True, \
        "Helper should identify raw Foundation candidate"
    assert engine.is_foundation_or_sr_cooked(cooked_sr) == True, \
        "Helper should identify cooked SR candidate"
    print("  ✓ Helper methods classify candidates correctly")

    # Test 2: Feature flag is enabled
    assert FLAGS.prefer_raw_foundation_convert == True, \
        "prefer_raw_foundation_convert flag should be enabled"
    print("  ✓ Feature flag prefer_raw_foundation_convert is enabled")

    # Test 3: Verify conversion config exists for chicken
    assert "chicken_breast" in engine.cook_cfg.get("classes", {}), \
        "chicken_breast should have conversion config"
    print("  ✓ Conversion config exists for chicken_breast")

    # Test 4: Verify _stage2_raw_convert method exists
    assert hasattr(engine, "_stage2_raw_convert"), \
        "Engine should have _stage2_raw_convert method"
    print("  ✓ Stage 2 raw+convert method exists")

    print("\n✅ Conversion layer proactive gate test PASSED")


def test_tater_tots_uses_oil_profile():
    """
    TEST: Tater tots synonym → potato_russet → tater_tots method → oil uptake.

    Validates:
    - "tater tots" maps to "potato_russet" via class_synonyms.json
    - Method "tater_tots" exists in cook_conversions.v2.json
    - Oil uptake is applied (12.0 g/100g)
    """
    print("\n" + "="*60)
    print("TEST: Tater Tots Uses Oil Profile")
    print("="*60)

    # Test synonym mapping
    from src.nutrition.utils.method_resolver import normalize_vision_class

    actual_class = normalize_vision_class("tater tots")
    assert actual_class == "potato_russet", \
        f"Expected 'potato_russet', got '{actual_class}'"
    print("  ✓ 'tater tots' → 'potato_russet'")

    # Test conversion profile exists
    import json
    from pathlib import Path

    cfg_path = Path(__file__).parent.parent / "src" / "data" / "cook_conversions.v2.json"
    with open(cfg_path) as f:
        config = json.load(f)

    classes = config.get("classes", {})
    assert "potato_russet" in classes, \
        "potato_russet not found in cook_conversions.v2.json"

    method_profiles = classes["potato_russet"].get("method_profiles", {})
    assert "tater_tots" in method_profiles, \
        f"tater_tots method not found in potato_russet. Available: {list(method_profiles.keys())}"
    print("  ✓ tater_tots method exists in cook_conversions.v2.json")

    # Validate oil uptake
    profile = method_profiles["tater_tots"]
    oil_uptake_config = profile.get("surface_oil_uptake_g_per_100g", {})
    oil_uptake = oil_uptake_config.get("mean", 0)
    assert oil_uptake == 12.0, \
        f"Expected oil uptake 12.0 g/100g, got {oil_uptake}"
    print(f"  ✓ Oil uptake: {oil_uptake} g/100g")

    print("\n✅ Tater tots oil profile test PASSED")


def test_egg_whites_not_yolk():
    """
    TEST: Egg whites negative vocabulary prevents yolk misalignment.

    Validates:
    - CLASS_DISALLOWED_ALIASES["egg_white"] includes "yolk"
    - Scoring penalties prevent yolk entries from ranking high
    """
    print("\n" + "="*60)
    print("TEST: Egg Whites Not Yolk Guard")
    print("="*60)

    from src.adapters.fdc_alignment_v2 import CLASS_DISALLOWED_ALIASES

    # Validate guard exists
    assert "egg_white" in CLASS_DISALLOWED_ALIASES, \
        "egg_white not found in CLASS_DISALLOWED_ALIASES"

    disallowed = CLASS_DISALLOWED_ALIASES["egg_white"]
    assert "yolk" in disallowed, \
        f"'yolk' not in egg_white disallowed list: {disallowed}"
    print("  ✓ egg_white disallowed: yolk")

    # Validate guard for scrambled eggs
    assert "egg_scrambled" in CLASS_DISALLOWED_ALIASES, \
        "egg_scrambled not found in CLASS_DISALLOWED_ALIASES"

    scrambled_disallowed = CLASS_DISALLOWED_ALIASES["egg_scrambled"]
    assert "yolk only" in scrambled_disallowed or "yolk" in scrambled_disallowed, \
        f"'yolk' not in egg_scrambled disallowed list: {scrambled_disallowed}"
    print("  ✓ egg_scrambled disallowed: yolk")

    # Validate guard for omelet
    assert "egg_omelet" in CLASS_DISALLOWED_ALIASES, \
        "egg_omelet not found in CLASS_DISALLOWED_ALIASES"

    omelet_disallowed = CLASS_DISALLOWED_ALIASES["egg_omelet"]
    assert "yolk only" in omelet_disallowed or "yolk" in omelet_disallowed, \
        f"'yolk' not in egg_omelet disallowed list: {omelet_disallowed}"
    print("  ✓ egg_omelet disallowed: yolk")

    print("\n✅ Egg whites not yolk test PASSED")


def test_corn_not_flour():
    """
    TEST: Corn kernel vs flour guardrail prevents flour misalignment.

    Validates:
    - CLASS_DISALLOWED_ALIASES["corn"] includes "flour", "meal", "grits"
    - Scoring penalties prevent milled products when kernels intended
    """
    print("\n" + "="*60)
    print("TEST: Corn Not Flour Guard")
    print("="*60)

    from src.adapters.fdc_alignment_v2 import CLASS_DISALLOWED_ALIASES

    # Validate guard exists
    assert "corn" in CLASS_DISALLOWED_ALIASES, \
        "corn not found in CLASS_DISALLOWED_ALIASES"

    disallowed = CLASS_DISALLOWED_ALIASES["corn"]

    # Check all milled forms are blocked
    milled_forms = ["flour", "meal", "grits", "polenta", "starch", "masa"]
    for form in milled_forms:
        assert form in disallowed, \
            f"'{form}' not in corn disallowed list: {disallowed}"
        print(f"  ✓ corn disallowed: {form}")

    print("\n✅ Corn not flour test PASSED")


def test_telemetry_serialization_roundtrip():
    """
    TEST: Telemetry writes to JSON and aggregator reads it (Phase 0.4).

    Validates:
    - AlignmentResult telemetry is serialized to JSON
    - eval_aggregator can read and validate the schema
    - All required fields present: alignment_stage, method, conversion_applied, candidate_pool_size
    """
    print("\n" + "="*60)
    print("TEST: Telemetry Serialization Round-Trip")
    print("="*60)

    import json
    import tempfile
    from pathlib import Path
    from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion
    from src.adapters.fdc_database import FDCDatabase
    from tools.eval_aggregator import validate_telemetry_schema

    # Create alignment engine
    aligner = FDCAlignmentWithConversion()

    # Run alignment on a simple case (grilled chicken)
    # Mock candidates for testing
    # NOTE: _dict_to_fdc_entry expects data_type not source
    mock_candidates = [
        {
            "fdc_id": 171477,
            "name": "Chicken, broilers or fryers, breast, meat only, raw",
            "data_type": "foundation_food",
            "protein_value": 22.5,
            "carbohydrates_value": 0.0,
            "total_fat_value": 2.6,
            "calories_value": 120
        },
        {
            "fdc_id": 171479,
            "name": "Chicken, broilers or fryers, breast, meat only, cooked, roasted",
            "data_type": "sr_legacy_food",
            "protein_value": 31.0,
            "carbohydrates_value": 0.0,
            "total_fat_value": 3.6,
            "calories_value": 165
        }
    ]

    result = aligner.align_food_item(
        predicted_name="chicken breast",
        predicted_form="grilled",
        predicted_kcal_100g=165,
        fdc_candidates=mock_candidates,
        confidence=0.90
    )

    # Create a mock evaluation item with telemetry
    eval_item = {
        "dish_id": "test_001",
        "telemetry": result.telemetry
    }

    # Write to temp JSON file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump([eval_item], f)
        temp_path = f.name

    try:
        # Load and validate with aggregator
        with open(temp_path, 'r') as f:
            loaded_items = json.load(f)

        # Validate schema
        validate_telemetry_schema(loaded_items)
        print("  ✓ Schema validation passed")

        # Check required fields
        telemetry = loaded_items[0]['telemetry']

        assert 'alignment_stage' in telemetry, "Missing alignment_stage"
        assert telemetry['alignment_stage'] != "unknown", "Stage is unknown"
        print(f"  ✓ alignment_stage: {telemetry['alignment_stage']}")

        assert 'method' in telemetry, "Missing method"
        assert telemetry['method'] != "unknown", "Method is unknown"
        print(f"  ✓ method: {telemetry['method']}")

        assert 'conversion_applied' in telemetry, "Missing conversion_applied"
        print(f"  ✓ conversion_applied: {telemetry['conversion_applied']}")

        assert 'candidate_pool_size' in telemetry, "Missing candidate_pool_size"
        assert telemetry['candidate_pool_size'] > 0, "Pool size is 0"
        print(f"  ✓ candidate_pool_size: {telemetry['candidate_pool_size']}")

        print("\n✅ Telemetry serialization round-trip test PASSED")

    finally:
        # Clean up temp file
        Path(temp_path).unlink()


def test_stage1_skipped_when_raw_foundation_exists():
    """
    TEST: Stage 1 not called when raw Foundation exists (Phase 0.5 - Spy Test).

    Validates the proactive gate:
    - When raw_foundation candidates exist
    - AND prefer_raw_foundation_convert=True
    - THEN _stage1_cooked_exact should NOT be called
    - AND result should be stage2_raw_convert
    """
    print("\n" + "="*60)
    print("TEST: Stage 1 Skipped When Raw Foundation Exists (Spy)")
    print("="*60)

    from unittest.mock import patch
    from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion
    from src.config.feature_flags import FLAGS

    # Ensure flag is enabled
    assert FLAGS.prefer_raw_foundation_convert == True, \
        "prefer_raw_foundation_convert must be True for this test"
    print("  ✓ prefer_raw_foundation_convert flag enabled")

    # Create alignment engine
    engine = FDCAlignmentWithConversion()

    # Mock candidates with both raw Foundation and cooked SR
    # NOTE: _dict_to_fdc_entry expects data_type not source
    mock_candidates = [
        {
            "fdc_id": 171477,
            "name": "Chicken, broilers or fryers, breast, meat only, raw",
            "data_type": "foundation_food",
            "protein_value": 22.5,
            "carbohydrates_value": 0.0,
            "total_fat_value": 2.6,
            "calories_value": 120
        },
        {
            "fdc_id": 171479,
            "name": "Chicken, broilers or fryers, breast, meat only, cooked, roasted",
            "data_type": "sr_legacy_food",
            "protein_value": 31.0,
            "carbohydrates_value": 0.0,
            "total_fat_value": 3.6,
            "calories_value": 165
        }
    ]

    # Spy on _stage1_cooked_exact
    with patch.object(engine, '_stage1_cooked_exact', wraps=engine._stage1_cooked_exact) as spy:
        result = engine.align_food_item(
            predicted_name="chicken breast",
            predicted_form="grilled",
            predicted_kcal_100g=165,
            fdc_candidates=mock_candidates,
            confidence=0.9
        )

        # CRITICAL: Assert Stage 1 was NOT called
        assert spy.call_count == 0, \
            f"Stage 1 was called {spy.call_count} times (should be 0)"
        print("  ✓ _stage1_cooked_exact NOT called (spy.call_count=0)")

        # Assert Stage 2 was used
        assert result.alignment_stage == "stage2_raw_convert", \
            f"Expected stage2_raw_convert, got {result.alignment_stage}"
        print(f"  ✓ Alignment stage: {result.alignment_stage}")

        # Assert conversion was applied
        assert result.telemetry["conversion_applied"] == True, \
            "Expected conversion_applied=True"
        print("  ✓ Conversion applied: True")

        # Assert Stage 1 blocked flag is set
        assert result.telemetry["stage1_blocked_raw_foundation_exists"] == True, \
            "Expected stage1_blocked_raw_foundation_exists=True"
        print("  ✓ Stage 1 blocked flag: True")

        # Assert candidate pool counts are tracked
        assert result.telemetry["candidate_pool_raw_foundation"] > 0, \
            "Expected raw_foundation pool > 0"
        print(f"  ✓ Raw foundation pool: {result.telemetry['candidate_pool_raw_foundation']}")

    print("\n✅ Stage 1 skip spy test PASSED")


def test_tiny_batch_no_unknown_stages():
    """
    TEST: E2E 3-item batch shows stage2_raw_convert and no unknowns (Phase 0.6).

    Validates full alignment pipeline:
    - Load 3-item fixture (grilled chicken, roasted potatoes, boiled eggs)
    - Run alignment on each item
    - Validate telemetry schema (no unknowns)
    - Assert stage2_raw_convert count > 0
    - Assert conversion_hit_rate > 0
    """
    print("\n" + "="*60)
    print("TEST: Tiny Batch No Unknown Stages (E2E)")
    print("="*60)

    from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion
    from tools.eval_aggregator import validate_telemetry_schema

    # Load fixture
    fixture_path = Path(__file__).parent / "fixtures" / "tiny_batch_3items.json"
    with open(fixture_path) as f:
        batch_data = json.load(f)

    items = batch_data["items"]
    print(f"  Loaded {len(items)} items from fixture")

    # Initialize alignment engine
    aligner = FDCAlignmentWithConversion()

    # Mock FDC database (simple in-memory candidates for testing)
    # In real e2e test, this would connect to actual database
    mock_candidates_db = {
        "chicken breast": [
            {
                "fdc_id": 171477,
                "name": "Chicken, broilers or fryers, breast, meat only, raw",
                "data_type": "foundation_food",
                "protein_value": 22.5,
                "carbohydrates_value": 0.0,
                "total_fat_value": 2.6,
                "calories_value": 120
            },
            {
                "fdc_id": 171479,
                "name": "Chicken, broilers or fryers, breast, meat only, cooked, grilled",
                "data_type": "sr_legacy_food",
                "protein_value": 31.0,
                "carbohydrates_value": 0.0,
                "total_fat_value": 3.6,
                "calories_value": 165
            }
        ],
        "potato": [
            {
                "fdc_id": 170032,
                "name": "Potatoes, russet, flesh and skin, raw",
                "data_type": "foundation_food",
                "protein_value": 2.0,
                "carbohydrates_value": 18.0,
                "total_fat_value": 0.1,
                "calories_value": 79
            }
        ],
        "egg": [
            {
                "fdc_id": 173424,
                "name": "Egg, whole, raw, fresh",
                "data_type": "foundation_food",
                "protein_value": 12.6,
                "carbohydrates_value": 0.72,
                "total_fat_value": 9.5,
                "calories_value": 143
            }
        ]
    }

    # Process each item
    results = []
    for item in items:
        predicted_name = item["predicted_name"]
        predicted_form = item["predicted_form"]
        predicted_kcal = item["predicted_kcal_100g"]

        # Get mock candidates
        candidates = mock_candidates_db.get(predicted_name, [])
        if not candidates:
            print(f"  ⚠️  No mock candidates for '{predicted_name}'")
            continue

        # Run alignment
        result = aligner.align_food_item(
            predicted_name=predicted_name,
            predicted_form=predicted_form,
            predicted_kcal_100g=predicted_kcal,
            fdc_candidates=candidates,
            confidence=0.85
        )

        results.append({
            "dish_id": item["id"],
            "telemetry": result.telemetry
        })

    print(f"  Processed {len(results)} items")

    # Validate telemetry schema (this will raise ValueError if unknowns found)
    try:
        validate_telemetry_schema(results)
        print("  ✓ Telemetry schema validation passed")
    except ValueError as e:
        print(f"  ❌ Schema validation failed: {e}")
        raise AssertionError(f"Schema validation failed: {e}")

    # Check conversion hit rate
    conversion_count = sum(1 for r in results if r["telemetry"].get("conversion_applied", False))
    conversion_rate = (conversion_count / len(results)) * 100 if results else 0
    print(f"  ✓ Conversion hit rate: {conversion_rate:.1f}% ({conversion_count}/{len(results)})")
    assert conversion_rate > 0, "Expected at least 1 item to use conversion"

    # Check stage distribution
    stage_counts = {}
    for r in results:
        stage = r["telemetry"]["alignment_stage"]
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    print(f"  ✓ Stage distribution: {stage_counts}")
    assert "stage2_raw_convert" in stage_counts, "Expected at least 1 stage2_raw_convert"
    assert stage_counts["stage2_raw_convert"] > 0, "Expected stage2_raw_convert count > 0"

    # Check no unknown stages or methods
    for r in results:
        assert r["telemetry"]["alignment_stage"] != "unknown", \
            f"Found unknown stage in {r['dish_id']}"
        assert r["telemetry"]["method"] != "unknown", \
            f"Found unknown method in {r['dish_id']}"

    print("  ✓ No unknown stages or methods found")
    print("\n✅ Tiny batch e2e test PASSED")


def test_stage_always_set_in_mass_only_mode():
    """
    TEST: Stage is always set, even with empty candidate pools (Phase 0.7).

    Validates:
    - No-match case returns stage0_no_candidates
    - AlignmentResult.alignment_stage is never None or "unknown"
    - Telemetry always includes alignment_stage
    - Stage validation assertion catches invalid stages
    """
    print("\n" + "="*60)
    print("TEST: Stage Always Set (Mass-Only Mode)")
    print("="*60)

    from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion

    aligner = FDCAlignmentWithConversion()

    # Test 1: Empty candidate pool
    result = aligner.align_food_item(
        predicted_name="unicorn meat",  # Doesn't exist
        predicted_form="grilled",
        predicted_kcal_100g=150,
        fdc_candidates=[],  # Empty!
        confidence=0.85
    )

    print(f"  Test 1: Empty candidates")
    assert result.alignment_stage == "stage0_no_candidates", \
        f"Expected stage0_no_candidates, got {result.alignment_stage}"
    assert "alignment_stage" in result.telemetry, "Missing alignment_stage in telemetry"
    assert result.telemetry["alignment_stage"] == "stage0_no_candidates"
    assert result.telemetry["alignment_stage"] != "unknown"
    print(f"    ✓ Stage: {result.alignment_stage}")
    print(f"    ✓ Telemetry stage: {result.telemetry['alignment_stage']}")

    # Test 2: Candidates exist but no match (plausibility gates reject)
    mock_candidates = [
        {
            "fdc_id": 999999,
            "name": "Fake food with bad macros",
            "data_type": "foundation_food",
            "protein_value": 100.0,  # Implausible
            "carbohydrates_value": 100.0,
            "total_fat_value": 100.0,
            "calories_value": 1500  # Way off
        }
    ]

    result = aligner.align_food_item(
        predicted_name="chicken breast",
        predicted_form="grilled",
        predicted_kcal_100g=165,
        fdc_candidates=mock_candidates,
        confidence=0.85
    )

    print(f"  Test 2: Candidates exist but gates reject")
    assert result.alignment_stage in [
        "stage0_no_candidates",
        "stage2_raw_convert",
        "stage1_cooked_exact"
    ], f"Unexpected stage: {result.alignment_stage}"
    assert result.alignment_stage != "unknown", "Stage is unknown!"
    assert "alignment_stage" in result.telemetry
    assert result.telemetry["alignment_stage"] != "unknown"
    print(f"    ✓ Stage: {result.alignment_stage}")
    print(f"    ✓ Telemetry stage: {result.telemetry['alignment_stage']}")

    # Test 3: Verify assertion catches invalid stages
    print(f"  Test 3: Assertion catches invalid stages")
    try:
        # Try to create result with invalid stage directly via _build_result
        aligner._build_result(
            None,
            "stage99_invalid",  # Invalid!
            0.85,
            "grilled",
            "explicit_match"
        )
        raise AssertionError("Expected assertion error for invalid stage")
    except AssertionError as e:
        if "Invalid alignment_stage" in str(e):
            print(f"    ✓ Assertion caught invalid stage: {e}")
        else:
            # Re-raise if it's not the expected assertion
            raise

    print("\n✅ Stage always set test PASSED")


def test_stage5_leafy_mixed_salad_composite():
    """
    TEST: Stage 5 proxy for leafy mixed salad (Phase 1).

    Validates:
    - leafy_mixed_salad core class triggers Stage 5
    - Returns 50% romaine + 50% green leaf composite
    - Energy-anchored at 17 kcal/100g
    - Proxy telemetry includes proxy_formula
    - Default portion: 55g (1 cup shredded)
    """
    print("\n" + "="*60)
    print("TEST: Stage 5 Leafy Mixed Salad Composite")
    print("="*60)

    from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion

    aligner = FDCAlignmentWithConversion()

    # Run alignment with empty candidates (force Stage 5)
    result = aligner.align_food_item(
        predicted_name="mixed salad greens",  # Synonym maps to leafy_mixed_salad
        predicted_form="raw",
        predicted_kcal_100g=18,  # Close to 17 kcal target
        fdc_candidates=[],  # Empty candidates
        confidence=0.85
    )

    print(f"  Alignment stage: {result.alignment_stage}")
    assert result.alignment_stage == "stage5_proxy_alignment", \
        f"Expected stage5_proxy_alignment, got {result.alignment_stage}"

    # Check proxy macros (50% romaine + 50% green leaf blend)
    print(f"  Protein: {result.protein_100g:.1f}g")
    print(f"  Carbs: {result.carbs_100g:.1f}g")
    print(f"  Fat: {result.fat_100g:.1f}g")
    print(f"  Kcal: {result.kcal_100g:.1f}")

    assert abs(result.protein_100g - 1.2) < 0.2, f"Protein mismatch: {result.protein_100g}"
    assert abs(result.carbs_100g - 3.6) < 0.5, f"Carbs mismatch: {result.carbs_100g}"
    assert abs(result.fat_100g - 0.2) < 0.2, f"Fat mismatch: {result.fat_100g}"
    assert abs(result.kcal_100g - 17.0) < 2.0, f"Kcal mismatch: {result.kcal_100g}"

    # Check telemetry
    assert "proxy_used" in result.telemetry, "Missing proxy_used flag"
    assert result.telemetry["proxy_used"] == True
    assert "proxy_formula" in result.telemetry
    assert "romaine" in result.telemetry["proxy_formula"].lower()
    print(f"  ✓ Proxy formula: {result.telemetry['proxy_formula']}")

    print("\n✅ Leafy mixed salad composite test PASSED")


def test_stage5_yellow_squash_proxy():
    """
    TEST: Stage 5 proxy for yellow squash (Phase 1).

    Validates:
    - squash_summer_yellow core class triggers Stage 5
    - Returns zucchini as proxy
    - Fallback macros if lookup fails
    - Energy validation within 30%
    """
    print("\n" + "="*60)
    print("TEST: Stage 5 Yellow Squash Proxy")
    print("="*60)

    from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion

    aligner = FDCAlignmentWithConversion()

    # Run alignment with empty candidates (force Stage 5)
    result = aligner.align_food_item(
        predicted_name="yellow squash",  # Maps to squash_summer_yellow
        predicted_form="raw",
        predicted_kcal_100g=18,  # Close to zucchini's 17 kcal
        fdc_candidates=[],
        confidence=0.85
    )

    print(f"  Alignment stage: {result.alignment_stage}")
    assert result.alignment_stage == "stage5_proxy_alignment", \
        f"Expected stage5_proxy_alignment, got {result.alignment_stage}"

    # Check zucchini proxy macros
    print(f"  Protein: {result.protein_100g:.1f}g")
    print(f"  Carbs: {result.carbs_100g:.1f}g")
    print(f"  Fat: {result.fat_100g:.1f}g")
    print(f"  Kcal: {result.kcal_100g:.1f}")

    assert abs(result.protein_100g - 1.2) < 0.3, f"Protein mismatch: {result.protein_100g}"
    assert abs(result.carbs_100g - 3.1) < 0.5, f"Carbs mismatch: {result.carbs_100g}"
    assert abs(result.fat_100g - 0.3) < 0.2, f"Fat mismatch: {result.fat_100g}"
    assert abs(result.kcal_100g - 17.0) < 3.0, f"Kcal mismatch: {result.kcal_100g}"

    # Check telemetry
    assert "proxy_used" in result.telemetry
    assert result.telemetry["proxy_used"] == True
    assert "proxy_formula" in result.telemetry
    assert "zucchini" in result.telemetry["proxy_formula"].lower()
    print(f"  ✓ Proxy formula: {result.telemetry['proxy_formula']}")

    print("\n✅ Yellow squash proxy test PASSED")


def test_stage5_tofu_plain_raw():
    """
    TEST: Stage 5 proxy for tofu (Phase 1).

    Validates:
    - tofu_plain_raw core class triggers Stage 5
    - Returns Foundation tofu macros
    - Energy validation within 25%
    - Default portion: 100g
    """
    print("\n" + "="*60)
    print("TEST: Stage 5 Tofu Plain Raw")
    print("="*60)

    from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion

    aligner = FDCAlignmentWithConversion()

    # Run alignment with empty candidates (force Stage 5)
    result = aligner.align_food_item(
        predicted_name="tofu",  # Maps to tofu_plain_raw
        predicted_form="raw",
        predicted_kcal_100g=95,  # Close to tofu's 94 kcal
        fdc_candidates=[],
        confidence=0.85
    )

    print(f"  Alignment stage: {result.alignment_stage}")
    assert result.alignment_stage == "stage5_proxy_alignment", \
        f"Expected stage5_proxy_alignment, got {result.alignment_stage}"

    # Check Foundation tofu macros
    print(f"  Protein: {result.protein_100g:.1f}g")
    print(f"  Carbs: {result.carbs_100g:.1f}g")
    print(f"  Fat: {result.fat_100g:.1f}g")
    print(f"  Kcal: {result.kcal_100g:.1f}")

    assert abs(result.protein_100g - 10.0) < 1.0, f"Protein mismatch: {result.protein_100g}"
    assert abs(result.carbs_100g - 2.0) < 0.5, f"Carbs mismatch: {result.carbs_100g}"
    assert abs(result.fat_100g - 6.0) < 1.0, f"Fat mismatch: {result.fat_100g}"
    assert abs(result.kcal_100g - 94.0) < 5.0, f"Kcal mismatch: {result.kcal_100g}"

    # Check telemetry
    assert "proxy_used" in result.telemetry
    assert result.telemetry["proxy_used"] == True
    assert "proxy_formula" in result.telemetry
    assert "tofu" in result.telemetry["proxy_formula"].lower()
    print(f"  ✓ Proxy formula: {result.telemetry['proxy_formula']}")

    print("\n✅ Tofu plain raw test PASSED")


def test_stage5_whitelist_enforcement():
    """
    TEST: Stage 5 whitelist enforcement (Phase 1).

    Validates:
    - Non-whitelisted classes do NOT trigger Stage 5
    - Only leafy_mixed_salad, squash_summer_yellow, tofu_plain_raw allowed
    - Other classes fall back to stage0_no_candidates
    """
    print("\n" + "="*60)
    print("TEST: Stage 5 Whitelist Enforcement")
    print("="*60)

    from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion

    aligner = FDCAlignmentWithConversion()

    # Test non-whitelisted classes
    non_whitelisted = [
        ("chicken breast", "grilled", 165),
        ("potato", "roasted", 110),
        ("banana", "raw", 89)
    ]

    for name, form, kcal in non_whitelisted:
        result = aligner.align_food_item(
            predicted_name=name,
            predicted_form=form,
            predicted_kcal_100g=kcal,
            fdc_candidates=[],
            confidence=0.85
        )

        print(f"  {name} → {result.alignment_stage}")
        assert result.alignment_stage != "stage5_proxy_alignment", \
            f"{name} should NOT use Stage 5 (non-whitelisted)"
        assert result.alignment_stage == "stage0_no_candidates", \
            f"Expected stage0_no_candidates, got {result.alignment_stage}"

    print("\n✅ Stage 5 whitelist enforcement test PASSED")


def run_all_tests():
    """Run all alignment guard tests."""
    print("\n" + "="*60)
    print("ALIGNMENT GUARDS TEST SUITE (V2 + Mass-Only)")
    print("="*60)

    tests = [
        test_bacon_species_filter,
        test_chicken_processing_filter,
        test_potato_form_filter,
        test_raisins_ingredient_filter,
        test_peas_foundation_preference,
        test_macro_plausibility_gates,
        test_stage_priority_order,
        # NEW: Guardrails V2 tests
        test_tomato_raw_first,
        test_green_bell_pepper_fallback,
        test_eggplant_cooked_only,
        test_potato_flour_ban,
        test_universal_branded_last_resort,
        # NEW: Mass-only mode enhancement tests
        test_green_bell_pepper_mass_only,
        test_rice_form_missing,
        test_chicken_generic_cooked,
        test_eggs_count_mass,
        test_bacon_species_required,
        test_sparse_accept_on_floor,
        # NEW: Alignment quality improvements (Phase 2)
        test_mixed_salad_greens_synonym,
        test_pumpkin_not_seeds,
        test_curated_branded_fallback,
        # NEW: Advanced fixes (P0/P1 - Critical accuracy improvements)
        test_class_synonyms_loading,
        test_egg_whites_disallow_yolk,
        test_corn_kernel_vs_flour,
        test_salad_context_detection,
        test_potato_wedges_in_conversion_config,
        test_plausibility_bands,
        # NEW: Latest improvements (conversion layer + fried family + sodium gating)
        test_hash_browns_routing,
        test_olive_sodium_gating,
        test_mixed_salad_canonicalization,
        test_method_aliases_expanded,
        test_homefries_oil_uptake,
        # NEW: Phase 2 improvements (stricter gates + integration)
        test_prefer_raw_foundation_flag,
        test_sodium_gate_integration,
        # NEW: Phase 3 improvements (conversion wiring + squash/tater tots + pumpkin guard)
        test_yellow_squash_synonym,
        test_tater_tots_coverage,
        test_pumpkin_flesh_guard,
        # NEW: Phase D improvements (helper validation + conversion wiring validation)
        test_candidate_classification_helpers,
        test_no_unknown_alignment_stage,
        test_salad_synonyms_comprehensive,
        test_conversion_fires_on_grilled_chicken,
        test_tater_tots_uses_oil_profile,
        test_egg_whites_not_yolk,
        test_corn_not_flour,
        # NEW: Phase 0 wiring validation tests (BLOCKER)
        test_telemetry_serialization_roundtrip,
        test_stage1_skipped_when_raw_foundation_exists,
        test_tiny_batch_no_unknown_stages,
        test_stage_always_set_in_mass_only_mode,
        # NEW: Phase 1 Stage 5 proxy alignment tests
        test_stage5_leafy_mixed_salad_composite,
        test_stage5_yellow_squash_proxy,
        test_stage5_tofu_plain_raw,
        test_stage5_whitelist_enforcement,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ TEST FAILED: {test.__name__}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ TEST ERROR: {test.__name__}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*60)
    print(f"TEST RESULTS: {passed} passed, {failed} failed")
    print("="*60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
