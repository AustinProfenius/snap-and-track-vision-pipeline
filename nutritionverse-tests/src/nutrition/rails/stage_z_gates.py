"""
Stage Z Gate Validation - Universal Branded Last-Resort Fallback

This module provides strict validation gates for Stage Z, the final fallback
stage that allows branded items only when they meet rigorous quality criteria.

Stage Z exists to fill catalog gaps (e.g., green bell pepper, herbs, uncommon produce)
without reintroducing processing/species misalignments.

Gates Applied (ALL must pass):
1. Token overlap ≥2 (after synonym expansion)
2. Energy band compliance (category-aware fallback bands)
3. Macro plausibility (per-category rules)
4. Ingredient sanity (single-ingredient requires ≤2 components)
5. Processing mismatch detection
6. Sodium/sugar sanity for raw produce
7. Score floor ≥2.4 (higher than Stage 4's 2.0)

"""
from typing import Dict, List, Optional, Tuple
import re

# Generic energy band fallbacks (used when class-specific band not in energy_bands.json)
GENERIC_ENERGY_BANDS = {
    "veg_raw": {"min": 15, "max": 45},  # Raw non-starchy vegetables
    "fruit_raw": {"min": 40, "max": 80},  # Raw fruits
    "starch_cooked": {"min": 110, "max": 170},  # Cooked grains/pasta/rice
    "starch_fried": {"min": 190, "max": 320},  # Fried potatoes/hash browns
    "meat_lean_cooked": {"min": 120, "max": 190},  # Lean poultry/fish
    "meat_red_cooked": {"min": 170, "max": 280},  # Red meat cooked
    "cheese": {"min": 250, "max": 420},  # Cheeses
    "egg_cooked": {"min": 50, "max": 170},  # Egg/egg white cooked
}

# Category mapping for foods not in energy_bands.json
CATEGORY_MAPPING = {
    # Vegetables (raw)
    "bell_pepper": "veg_raw",
    "bell_pepper_green": "veg_raw",
    "bell_pepper_red": "veg_raw",
    "bell_pepper_yellow": "veg_raw",
    "onion": "veg_raw",
    "red_onion": "veg_raw",
    "garlic": "veg_raw",
    "tomato": "veg_raw",
    "cherry_tomatoes": "veg_raw",
    "grape_tomatoes": "veg_raw",
    "plum_tomatoes": "veg_raw",
    "cucumber": "veg_raw",
    "lettuce": "veg_raw",
    "spinach": "veg_raw",
    "broccoli": "veg_raw",
    "cauliflower": "veg_raw",
    "carrot": "veg_raw",
    "celery": "veg_raw",
    "zucchini": "veg_raw",
    "eggplant": "veg_raw",
    "squash_yellow": "veg_raw",
    "bok_choy": "veg_raw",
    "brussels_sprouts": "veg_raw",
    "cabbage": "veg_raw",
    "kale": "veg_raw",
    "asparagus": "veg_raw",
    "herbs_fresh": "veg_raw",

    # Fruits (raw)
    "apple": "fruit_raw",
    "banana": "fruit_raw",
    "orange": "fruit_raw",
    "berries": "fruit_raw",
    "blueberries": "fruit_raw",
    "blackberries": "fruit_raw",
    "raspberries": "fruit_raw",
    "strawberries": "fruit_raw",
    "grapes": "fruit_raw",
    "watermelon": "fruit_raw",
    "cantaloupe": "fruit_raw",
    "pineapple": "fruit_raw",

    # Starches (cooked)
    "rice_white": "starch_cooked",
    "rice_brown": "starch_cooked",
    "pasta_wheat": "starch_cooked",
    "quinoa": "starch_cooked",
    "oats": "starch_cooked",

    # Proteins
    "chicken_breast": "meat_lean_cooked",
    "turkey_breast": "meat_lean_cooked",
    "white_fish": "meat_lean_cooked",
    "salmon_fillet": "meat_lean_cooked",
    "beef_steak": "meat_red_cooked",
    "pork_chop": "meat_red_cooked",
    "bacon": "meat_red_cooked",
}

# Stage Z specific processing terms (adds to existing PROCESSING_BAD)
STAGEZ_FORBIDDEN_PROCESSING = re.compile(
    r"\b(prepared|seasoned|marinated|kit|mix|meal|frozen prepared|"
    r"microwaved|convenience|ready-to-eat)\b",
    re.I
)

# Forbidden ingredient terms (multi-ingredient traps)
FORBIDDEN_INGREDIENT_TERMS = {
    "pastry", "cookie", "bar", "drink", "beverage", "smoothie",
    "shake", "sauce", "dressing", "gravy", "soup", "stew"
}


def get_energy_band_for_category(
    core_class: str,
    method: str,
    energy_bands: Dict[str, Dict[str, float]]
) -> Optional[Tuple[float, float]]:
    """
    Get energy band for a food class, with generic fallback.

    Priority:
    1. Exact class.method match in energy_bands.json
    2. Generic category from GENERIC_ENERGY_BANDS
    3. None (no band available)

    Args:
        core_class: Food class (e.g., "bell_pepper", "rice_white")
        method: Cooking method (e.g., "raw", "boiled", "grilled")
        energy_bands: Loaded energy_bands.json content

    Returns:
        (min_kcal, max_kcal) tuple or None if no band available
    """
    # Try exact match first
    band_key = f"{core_class}.{method}"
    if band_key in energy_bands:
        band = energy_bands[band_key]
        return (band["min"], band["max"])

    # Try generic category
    if core_class in CATEGORY_MAPPING:
        category = CATEGORY_MAPPING[core_class]
        if category in GENERIC_ENERGY_BANDS:
            band = GENERIC_ENERGY_BANDS[category]
            return (band["min"], band["max"])

    # No band available
    return None


def check_macro_gates_stage_z(
    core_class: str,
    protein: float,
    carbs: float,
    fat: float,
    method: str
) -> Tuple[bool, str]:
    """
    Check if macros are plausible for food class (Stage Z strict gates).

    Per-category rules:
    - Lean meats: protein ≥18g, carbs ≤5g
    - Starches non-fried: protein ≤8g, carbs ≥20g, fat ≤5g
    - Starches fried: fat ≥8g
    - Raw veg: carbs ≤10g, protein ≤3g, fat ≤1g
    - Fruits raw: carbs 10-20g, fat ≤1g
    - Cheeses: protein 15-30g, fat 15-35g

    Args:
        core_class: Food class
        protein, carbs, fat: Macros per 100g
        method: Cooking method

    Returns:
        (passes, reason) tuple
    """
    # Get category
    category = CATEGORY_MAPPING.get(core_class, "unknown")

    # Lean meats
    if category == "meat_lean_cooked":
        if protein < 18.0:
            return False, f"lean_meat_protein_too_low_{protein:.1f}g"
        if carbs > 5.0:
            return False, f"lean_meat_carbs_too_high_{carbs:.1f}g"

    # Red meats
    elif category == "meat_red_cooked":
        if protein < 15.0:
            return False, f"red_meat_protein_too_low_{protein:.1f}g"
        if carbs > 5.0:
            return False, f"red_meat_carbs_too_high_{carbs:.1f}g"

    # Starches cooked
    elif category == "starch_cooked":
        if protein > 8.0:
            return False, f"starch_protein_too_high_{protein:.1f}g"
        if carbs < 20.0:
            return False, f"starch_carbs_too_low_{carbs:.1f}g"

        # Non-fried should have low fat
        if method not in ("fried", "hash_browns", "fries") and fat > 5.0:
            return False, f"starch_non_fried_fat_too_high_{fat:.1f}g"

    # Fried starches
    elif category == "starch_fried" or method in ("fried", "hash_browns", "fries"):
        if fat < 8.0:
            return False, f"fried_starch_fat_too_low_{fat:.1f}g"

    # Raw vegetables
    elif category == "veg_raw":
        if carbs > 10.0:
            return False, f"raw_veg_carbs_too_high_{carbs:.1f}g"
        if protein > 3.0:
            return False, f"raw_veg_protein_too_high_{protein:.1f}g"
        if fat > 1.0:
            return False, f"raw_veg_fat_too_high_{fat:.1f}g"

    # Raw fruits
    elif category == "fruit_raw":
        if carbs < 10.0 or carbs > 20.0:
            return False, f"raw_fruit_carbs_out_of_range_{carbs:.1f}g"
        if fat > 1.0:
            return False, f"raw_fruit_fat_too_high_{fat:.1f}g"

    # Cheeses
    elif category == "cheese":
        if protein < 15.0 or protein > 30.0:
            return False, f"cheese_protein_out_of_range_{protein:.1f}g"
        if fat < 15.0 or fat > 35.0:
            return False, f"cheese_fat_out_of_range_{fat:.1f}g"

    return True, "pass"


def validate_ingredients_stage_z(
    core_class: str,
    ingredients: Optional[List[str]],
    predicted_name: str,
    cand_name: str
) -> Tuple[bool, str]:
    """
    Validate ingredient list for Stage Z.

    Rules:
    - Single-ingredient predictions: require ≤2 ingredients (food + water/salt)
    - Multi-ingredient: require core food first in list
    - Reject if any forbidden terms present

    Args:
        core_class: Food class
        ingredients: Ingredient list from branded entry (None if not available)
        predicted_name: User's predicted food name
        cand_name: Candidate food name

    Returns:
        (passes, reason) tuple
    """
    # If no ingredients available, allow only if candidate name is simple/exact match
    if not ingredients or len(ingredients) == 0:
        # Check if candidate name is suspiciously complex
        cand_tokens = cand_name.lower().split()
        if len(cand_tokens) > 3:
            return False, "missing_ingredients_complex_name"

        # Allow simple branded entries without ingredient data
        return True, "missing_ingredients_allowed_simple_name"

    # Check for forbidden terms
    ingredients_str = " ".join(ingredients).lower()
    for forbidden in FORBIDDEN_INGREDIENT_TERMS:
        if forbidden in ingredients_str:
            return False, f"forbidden_ingredient_term_{forbidden}"

    # Single-ingredient check
    # Heuristic: if predicted_name is 1-2 words and doesn't contain "salad/mix/blend"
    pred_tokens = predicted_name.lower().split()
    is_single_ingredient = (
        len(pred_tokens) <= 2 and
        not any(term in predicted_name.lower() for term in ("salad", "mix", "blend", "medley"))
    )

    if is_single_ingredient:
        # Require ≤2 ingredients (food + water/salt)
        if len(ingredients) > 2:
            # Check if extra ingredients are just water/salt
            normalized_ingredients = [ing.lower().strip() for ing in ingredients]
            acceptable = {"water", "salt", "sea salt"}
            extra_ingredients = [ing for ing in normalized_ingredients if ing not in acceptable]

            if len(extra_ingredients) > 1:
                return False, f"single_ingredient_too_many_components_{len(ingredients)}"

    # Multi-ingredient: check core food is first
    else:
        first_ingredient = ingredients[0].lower().strip() if ingredients else ""
        # Core food name should be in first ingredient
        core_base = core_class.split("_")[0]  # e.g., "chicken" from "chicken_breast"
        if core_base not in first_ingredient:
            return False, f"multi_ingredient_core_not_first_{first_ingredient}"

    return True, "pass"


def check_sodium_sugar_sanity(
    core_class: str,
    sodium_mg: Optional[float],
    sugar_g: Optional[float]
) -> Tuple[bool, str]:
    """
    Check sodium and sugar levels for raw produce.

    Rules (TIGHTENED for mass-only mode):
    - Raw produce: sodium ≤50mg/100g (lowered from 80mg to block canned/pickled)
    - Raw veg: sugar ≤6g/100g

    Args:
        core_class: Food class
        sodium_mg: Sodium per 100g (None if not available)
        sugar_g: Sugar per 100g (None if not available)

    Returns:
        (passes, reason) tuple
    """
    category = CATEGORY_MAPPING.get(core_class, "unknown")

    # Raw produce sodium check (TIGHTENED: 30mg floor to block canned/pickled)
    if category in ("veg_raw", "fruit_raw"):
        if sodium_mg is not None and sodium_mg > 30.0:
            return False, f"raw_produce_sodium_too_high_{sodium_mg:.0f}mg"

    # Raw veg sugar check (blocks pickled/sweetened)
    if category == "veg_raw":
        if sugar_g is not None and sugar_g > 6.0:
            return False, f"raw_veg_sugar_too_high_{sugar_g:.1f}g"

    return True, "pass"


def check_processing_mismatch_stage_z(
    predicted_form: str,
    cand_name: str
) -> Tuple[bool, str]:
    """
    Check for processing mismatch in Stage Z.

    Rejects candidates with forbidden processing terms unless predicted form matches.

    Args:
        predicted_form: User's predicted form/method
        cand_name: Candidate name

    Returns:
        (passes, reason) tuple
    """
    # Check if candidate has forbidden processing
    match = STAGEZ_FORBIDDEN_PROCESSING.search(cand_name)
    if match:
        forbidden_term = match.group(0)
        # Allow only if predicted form explicitly mentions it
        if forbidden_term.lower() not in predicted_form.lower():
            return False, f"processing_mismatch_{forbidden_term}"

    return True, "pass"


def passes_stage_z_gates(
    predicted_name: str,
    predicted_form: str,
    candidate: 'FdcEntry',  # Type hint as string to avoid circular import
    core_class: str,
    method: str,
    energy_bands: Dict[str, Dict[str, float]]
) -> Tuple[bool, Dict[str, any]]:
    """
    Check if a branded candidate passes all Stage Z gates.

    ALL gates must pass for candidate to be accepted.

    Args:
        predicted_name: User's predicted food name
        predicted_form: User's predicted form/method
        candidate: FDC branded entry to validate
        core_class: Normalized food class
        method: Cooking method
        energy_bands: Loaded energy_bands.json

    Returns:
        (passes, gate_results) tuple where gate_results contains:
        {
            "energy_band": bool,
            "macro_gates": bool,
            "ingredients": bool,
            "sodium_sugar": bool,
            "processing": bool,
            "rejection_reason": str (if failed)
        }
    """
    gate_results = {
        "energy_band": False,
        "macro_gates": False,
        "ingredients": False,
        "sodium_sugar": False,
        "processing": False,
        "rejection_reason": ""
    }

    # Gate 1: Energy band
    energy_band = get_energy_band_for_category(core_class, method, energy_bands)
    if energy_band:
        min_kcal, max_kcal = energy_band
        if not (min_kcal <= candidate.kcal_100g <= max_kcal):
            gate_results["rejection_reason"] = f"energy_band_{candidate.kcal_100g:.0f}_outside_{min_kcal}-{max_kcal}"
            return False, gate_results
    gate_results["energy_band"] = True

    # Gate 2: Macro gates
    macro_pass, macro_reason = check_macro_gates_stage_z(
        core_class,
        candidate.protein_100g,
        candidate.carbs_100g,
        candidate.fat_100g,
        method
    )
    if not macro_pass:
        gate_results["rejection_reason"] = macro_reason
        return False, gate_results
    gate_results["macro_gates"] = True

    # Gate 3: Ingredients (if available)
    ingredients = getattr(candidate, 'ingredients', None)
    ing_pass, ing_reason = validate_ingredients_stage_z(
        core_class, ingredients, predicted_name, candidate.name
    )
    if not ing_pass:
        gate_results["rejection_reason"] = ing_reason
        return False, gate_results
    gate_results["ingredients"] = True

    # Gate 4: Sodium/sugar sanity
    sodium_mg = getattr(candidate, 'sodium_mg_100g', None)
    sugar_g = getattr(candidate, 'sugar_g_100g', None)
    sodium_pass, sodium_reason = check_sodium_sugar_sanity(core_class, sodium_mg, sugar_g)
    if not sodium_pass:
        gate_results["rejection_reason"] = sodium_reason
        return False, gate_results
    gate_results["sodium_sugar"] = True

    # Gate 5: Processing mismatch
    proc_pass, proc_reason = check_processing_mismatch_stage_z(predicted_form, candidate.name)
    if not proc_pass:
        gate_results["rejection_reason"] = proc_reason
        return False, gate_results
    gate_results["processing"] = True

    # All gates passed
    return True, gate_results
