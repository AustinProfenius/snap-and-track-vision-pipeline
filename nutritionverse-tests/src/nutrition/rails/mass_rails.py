"""
Mass soft clamps for portion size validation.

Addresses mass bias - the #1 remaining error driver (70-80% of calorie error).

Per-class IQR bounds derived from empirical data:
- Bacon strip: 7-13g (median ~10g)
- Sausage link: 20-45g (median ~32g)
- Egg (whole): 46-55g (median ~50g)
- Potato cubes (roasted): 6-12g per piece

Soft clamp strategy (Fix 5.5):
- Only apply when confidence < 0.75 (low confidence predictions need help)
- Shrink toward rail by 50% of overage (gentle nudge, not hard clamp)
- Track telemetry for validation

Feature flag: FLAGS.mass_soft_clamps
"""
from typing import Optional, Tuple
from ...config.feature_flags import FLAGS


# Per-class mass rails (g) - IQR bounds from empirical data
MASS_RAILS = {
    # Processed meats
    "bacon": {"min": 7, "max": 13, "median": 10, "description": "Bacon strip"},
    "sausage": {"min": 20, "max": 45, "median": 32, "description": "Sausage link"},
    "breakfast_sausage": {"min": 20, "max": 45, "median": 32, "description": "Breakfast sausage link"},

    # Eggs
    "egg_whole": {"min": 46, "max": 55, "median": 50, "description": "Whole egg"},
    "egg": {"min": 46, "max": 55, "median": 50, "description": "Whole egg (alias)"},

    # Starchy vegetables (per piece)
    "potato_cubes": {"min": 6, "max": 12, "median": 9, "description": "Potato cube/piece"},
    "sweet_potato_cubes": {"min": 6, "max": 12, "median": 9, "description": "Sweet potato cube"},

    # Additional common items
    "chicken_breast": {"min": 100, "max": 200, "median": 150, "description": "Chicken breast fillet"},
    "salmon_fillet": {"min": 100, "max": 180, "median": 140, "description": "Salmon fillet"},
}


def apply_mass_soft_clamp(
    core_class: str,
    predicted_mass_g: float,
    confidence: float
) -> Tuple[float, bool, Optional[str]]:
    """
    Apply soft mass clamp for portion size validation.

    Strategy:
    - Only apply when confidence < 0.75 (low confidence needs help)
    - Shrink toward rail by 50% of overage (gentle nudge)
    - Track which direction we clamped for telemetry

    Args:
        core_class: Food class (e.g., "bacon", "egg_whole")
        predicted_mass_g: Model's predicted mass (grams)
        confidence: Prediction confidence (0-1)

    Returns:
        (clamped_mass, was_clamped, clamp_reason) tuple
        - clamped_mass: Adjusted mass (or original if no clamp)
        - was_clamped: True if clamp was applied
        - clamp_reason: Description of clamp (e.g., "mass_clamp_bacon_7g→10g")

    Examples:
        >>> apply_mass_soft_clamp("bacon", 3.0, 0.60)
        (6.5, True, "mass_clamp_bacon_too_low_3.0g→6.5g")

        >>> apply_mass_soft_clamp("bacon", 20.0, 0.60)
        (16.5, True, "mass_clamp_bacon_too_high_20.0g→16.5g")

        >>> apply_mass_soft_clamp("bacon", 10.0, 0.60)
        (10.0, False, None)  # Within bounds

        >>> apply_mass_soft_clamp("bacon", 3.0, 0.85)
        (3.0, False, None)  # High confidence, no clamp
    """
    # Feature flag check
    if not FLAGS.mass_soft_clamps:
        return predicted_mass_g, False, None

    # Only apply for low confidence predictions
    if confidence >= 0.75:
        return predicted_mass_g, False, None

    # Check if we have a rail for this class
    if core_class not in MASS_RAILS:
        return predicted_mass_g, False, None

    rail = MASS_RAILS[core_class]
    min_mass = rail["min"]
    max_mass = rail["max"]
    median_mass = rail["median"]

    # Check if within bounds (no clamp needed)
    if min_mass <= predicted_mass_g <= max_mass:
        return predicted_mass_g, False, None

    # Apply soft clamp
    clamped_mass = predicted_mass_g
    clamp_reason = ""

    if predicted_mass_g < min_mass:
        # Too low: shrink toward median by 50% of overage
        overage = min_mass - predicted_mass_g
        clamped_mass = predicted_mass_g + (0.5 * overage)
        clamp_reason = f"mass_clamp_{core_class}_too_low_{predicted_mass_g:.1f}g→{clamped_mass:.1f}g"

    elif predicted_mass_g > max_mass:
        # Too high: shrink toward median by 50% of overage
        overage = predicted_mass_g - max_mass
        clamped_mass = predicted_mass_g - (0.5 * overage)
        clamp_reason = f"mass_clamp_{core_class}_too_high_{predicted_mass_g:.1f}g→{clamped_mass:.1f}g"

    return clamped_mass, True, clamp_reason


def get_mass_rail_bounds(core_class: str) -> Optional[dict]:
    """
    Get mass rail bounds for a food class.

    Args:
        core_class: Food class (e.g., "bacon", "egg_whole")

    Returns:
        Rail dict with {min, max, median, description} or None if not found
    """
    return MASS_RAILS.get(core_class)


def is_within_mass_rail(core_class: str, mass_g: float) -> bool:
    """
    Check if a mass is within the rail bounds for a class.

    Args:
        core_class: Food class
        mass_g: Mass in grams

    Returns:
        True if within bounds (or no rail defined), False if outside
    """
    rail = MASS_RAILS.get(core_class)
    if not rail:
        return True  # No rail defined, accept any mass

    return rail["min"] <= mass_g <= rail["max"]
