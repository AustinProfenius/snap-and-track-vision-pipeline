"""
Stage-Z Energy-Only Last Resort Guards (Option C).

CRITICAL: Stage-Z is a strict last resort when all other stages fail (1, 1b, 2, 3, 4, 5).
It provides ENERGY-ONLY proxies (macros=None) with plausibility clamping.

Eligibility Requirements:
1. All prior stages failed
2. NO raw Foundation candidates exist (or all were guard-blocked)
3. Category is in ALLOWED list
4. Category NOT in NEVER list

This prevents Stage-Z from masking alignment bugs (e.g., fruits/nuts MUST have Foundation entries).
"""

from typing import Dict, Tuple, Optional


def infer_category_from_class(core_class: str) -> str:
    """Infer food category from core_class for Stage-Z eligibility."""
    class_lower = core_class.lower()

    # Fruits
    if any(x in class_lower for x in ["apple", "grape", "berry", "melon", "banana", "orange", "pear"]):
        return "fruit"

    # Nuts/seeds
    if any(x in class_lower for x in ["almond", "walnut", "peanut", "cashew", "seed"]):
        return "nuts_seeds"

    # Vegetables
    if any(x in class_lower for x in ["tomato", "lettuce", "spinach", "carrot", "celery", "broccoli", "pepper", "onion", "cucumber"]):
        return "vegetable"

    # Meat/poultry
    if any(x in class_lower for x in ["chicken", "beef", "pork", "bacon", "sausage", "turkey"]):
        return "meat_poultry"

    # Fish/seafood
    if any(x in class_lower for x in ["fish", "salmon", "tuna", "shrimp", "seafood"]):
        return "fish_seafood"

    # Starch/grain
    if any(x in class_lower for x in ["rice", "pasta", "bread", "potato", "quinoa", "oats"]):
        return "starch_grain"

    # Egg
    if "egg" in class_lower:
        return "egg"

    # Default to vegetable (conservative - will block Stage-Z)
    return "vegetable"


# ALLOWED categories (only when NO raw Foundation candidates exist)
ALLOWED_STAGEZ_CATEGORIES = {
    "meat_poultry",  # bacon, sausage, deli meats
    "fish_seafood",  # uncommon fish species
    "starch_grain",  # rare grain varieties
    "egg",  # egg preparations without SR entries
}

# NEVER allow Stage-Z for these (Foundation must exist)
NEVER_PROXY_CATEGORIES = {
    "fruit",  # apples, grapes, berries → Foundation MUST exist
    "nuts_seeds",  # almonds, walnuts → Foundation MUST exist
    "vegetable",  # common vegetables → Foundation MUST exist
    "legume",  # beans, lentils → Foundation MUST exist
}

# Energy bands by category (kcal/100g) - Conservative ranges
ENERGY_BANDS: Dict[str, Tuple[int, int]] = {
    "starch_grain": (70, 200),  # rice, quinoa, couscous
    "meat_poultry": (90, 280),  # lean chicken to fatty bacon
    "fish_seafood": (70, 230),  # cod to salmon
    "egg": (120, 190),  # whole eggs to omelets
}

# Default band for categories without specific ranges
DEFAULT_ENERGY_BAND = (50, 300)

# Meatlike categories where Stage-Z is allowed even if raw Foundation exists
# (because cooked proteins may not have good SR entries, and raw→cooked conversion may not work)
MEATLIKE = {"meat_poultry", "pork", "beef", "sausage", "bacon", "fish_seafood"}


def can_use_stageZ(
    core_class: str,
    category: str,
    candidate_pool_raw_foundation: int,
    candidate_pool_total: int
) -> bool:
    """
    Stage-Z eligibility check (STRICT with meat exception).

    Only allow when:
    - All prior stages failed (1, 1b, 1c, 2, 3, 4, 5)
    - NO raw Foundation candidates exist (or all were guard-blocked)
      EXCEPT for meats/proteins (allowed even with raw Foundation)
    - Category is in ALLOWED list
    - Category NOT in NEVER list

    Args:
        core_class: Normalized food class (e.g., "bacon", "apple")
        category: Food category (e.g., "meat_poultry", "fruit")
        candidate_pool_raw_foundation: Count of raw Foundation candidates
        candidate_pool_total: Total candidate count

    Returns:
        True if Stage-Z is allowed, False otherwise
    """
    # Hard block for fruit/nuts/veggies (Foundation must exist, Stage-Z never allowed)
    if category in NEVER_PROXY_CATEGORIES:
        return False

    # Only allow if category is whitelisted OR is meatlike
    if category not in ALLOWED_STAGEZ_CATEGORIES and category not in MEATLIKE:
        return False

    # MEAT EXCEPTION: Allow Stage-Z for meats even if raw Foundation exists
    # (cooked proteins may lack good SR entries, raw→cooked conversion may fail)
    if category in MEATLIKE:
        return True

    # For non-meat categories: Do NOT use Stage-Z if we have raw Foundation candidates
    # (even if they failed - indicates alignment bug, not missing data)
    if candidate_pool_raw_foundation > 0:
        return False

    # If we have NO candidates at all, OR only branded/guard-blocked,
    # Stage-Z is allowed for whitelisted categories
    return True


def build_energy_only_proxy(
    core_class: str,
    category: str,
    predicted_kcal_100g: float
) -> Dict:
    """
    Build energy-only proxy with plausibility clamping.

    Returns dict with:
    - kcal_100g: Clamped energy value
    - protein_100g, carbs_100g, fat_100g: None (energy-only, no false precision)
    - source: "stageZ_energy_only"
    - plausibility_adjusted: True if clamping was applied

    Args:
        core_class: Normalized food class
        category: Food category
        predicted_kcal_100g: Predicted energy density (kcal/100g)

    Returns:
        Proxy dict with clamped energy and metadata
    """
    # Get category-specific energy band
    lo, hi = ENERGY_BANDS.get(category, DEFAULT_ENERGY_BAND)

    # Clamp predicted energy to plausibility band
    kcal_clamped = max(lo, min(hi, predicted_kcal_100g or lo))

    plausibility_adjusted = (kcal_clamped != predicted_kcal_100g)

    return {
        "name": f"StageZ energy proxy ({core_class})",
        "kcal_100g": kcal_clamped,
        "protein_100g": None,  # Energy-only, no false precision
        "carbs_100g": None,
        "fat_100g": None,
        "fiber_100g": None,
        "source": "stageZ_energy_only",
        "plausibility_adjusted": plausibility_adjusted,
        "energy_band": (lo, hi),
        "predicted_kcal": predicted_kcal_100g,
        "clamped_kcal": kcal_clamped,
    }


def get_stagez_telemetry_fields(proxy: Dict, category: str) -> Dict:
    """
    Generate telemetry fields for Stage-Z usage.

    Args:
        proxy: Proxy dict from build_energy_only_proxy()
        category: Food category

    Returns:
        Telemetry dict with Stage-Z metadata
    """
    return {
        "stageZ_used": True,
        "stageZ_reason": "energy_only_proxy_all_stages_failed",
        "plausibility_adjustment": proxy["plausibility_adjusted"],
        "category": category,
        "energy_band_min": proxy["energy_band"][0],
        "energy_band_max": proxy["energy_band"][1],
        "predicted_kcal_100g": proxy["predicted_kcal"],
        "clamped_kcal_100g": proxy["clamped_kcal"],
    }
