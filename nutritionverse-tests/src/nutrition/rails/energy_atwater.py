"""
Energy density and Atwater validation rails.

Standalone utilities for:
1. Energy band clamping (method-aware plausible bounds)
2. Atwater factor validation (4P + 4C + 9F consistency)
3. Soft correction when violations occur

Used by both cook_convert.py and align_convert.py to ensure
nutrition values are physically plausible.
"""
from typing import Dict, Tuple, Optional


# Atwater factors (kcal per gram)
ATWATER_PROTEIN = 4.0
ATWATER_CARBS = 4.0
ATWATER_FAT = 9.0
ATWATER_FIBER = 2.0  # Net carbs adjustment


def calculate_atwater_energy(
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    fiber_g: float = 0.0
) -> float:
    """
    Calculate energy using Atwater factors.

    Formula: 4P + 4C + 9F - 2F_fiber
    (Fiber provides ~2 kcal/g instead of 4)

    Args:
        protein_g: Protein in grams
        carbs_g: Total carbs in grams
        fat_g: Fat in grams
        fiber_g: Fiber in grams (optional, default 0)

    Returns:
        Calculated energy in kcal
    """
    net_carbs = carbs_g - fiber_g if fiber_g > 0 else carbs_g
    fiber_energy = fiber_g * ATWATER_FIBER if fiber_g > 0 else 0.0

    return (
        ATWATER_PROTEIN * protein_g +
        ATWATER_CARBS * net_carbs +
        ATWATER_FAT * fat_g +
        fiber_energy
    )


def validate_atwater_consistency(
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    kcal: float,
    fiber_g: float = 0.0,
    tolerance: float = 0.12
) -> Tuple[bool, float, float]:
    """
    Validate energy consistency with Atwater factors.

    Args:
        protein_g: Protein in grams
        carbs_g: Total carbs in grams
        fat_g: Fat in grams
        kcal: Stated energy in kcal
        fiber_g: Fiber in grams (optional)
        tolerance: Acceptable deviation fraction (default 12%)

    Returns:
        (is_valid, calculated_kcal, deviation_pct) tuple
    """
    atwater_kcal = calculate_atwater_energy(protein_g, carbs_g, fat_g, fiber_g)

    if atwater_kcal == 0 or kcal == 0:
        # Cannot validate if either is zero
        return True, atwater_kcal, 0.0

    deviation_pct = abs(kcal - atwater_kcal) / atwater_kcal

    is_valid = deviation_pct <= tolerance

    return is_valid, atwater_kcal, deviation_pct


def soft_atwater_correction(
    kcal_stated: float,
    kcal_atwater: float,
    blend_weight: float = 0.7
) -> float:
    """
    Apply soft correction: blend Atwater with stated value.

    Default: 70% Atwater + 30% stated

    Args:
        kcal_stated: Original/stated energy value
        kcal_atwater: Atwater-calculated energy
        blend_weight: Weight for Atwater (default 0.7)

    Returns:
        Blended energy value
    """
    return blend_weight * kcal_atwater + (1 - blend_weight) * kcal_stated


def clamp_energy_to_band(
    kcal: float,
    band_key: str,
    energy_bands: Dict[str, Dict[str, float]]
) -> Tuple[float, bool]:
    """
    Clamp energy to method-aware plausible bounds.

    Args:
        kcal: Calculated energy density (kcal/100g)
        band_key: Lookup key in format "food_class.method" (e.g., "rice_white.boiled")
        energy_bands: energy_bands.json content

    Returns:
        (clamped_kcal, was_clamped) tuple
    """
    if band_key not in energy_bands:
        # No band defined for this food+method
        return kcal, False

    band = energy_bands[band_key]
    min_kcal = band["min"]
    max_kcal = band["max"]

    if kcal < min_kcal:
        return min_kcal, True
    elif kcal > max_kcal:
        return max_kcal, True
    else:
        return kcal, False


def is_in_energy_band(
    kcal: float,
    core_class: str,
    method: str,
    energy_bands: Dict[str, Dict[str, float]]
) -> bool:
    """
    Check if energy is within plausible bounds for food class + cooking method.

    Args:
        kcal: Energy density to check (kcal/100g)
        core_class: Food class (e.g., "rice_white", "chicken_breast")
        method: Cooking method (e.g., "boiled", "grilled")
        energy_bands: energy_bands.json content

    Returns:
        True if within band (or no band defined), False if outside bounds
    """
    band_key = f"{core_class}.{method}"

    if band_key not in energy_bands:
        # No band defined for this food+method combination
        return True  # Allow - no constraint available

    band = energy_bands[band_key]
    return band["min"] <= kcal <= band["max"]


def get_energy_band_center(
    band_key: str,
    energy_bands: Dict[str, Dict[str, float]]
) -> Optional[float]:
    """
    Get center of energy band for a food+method.

    Args:
        band_key: Lookup key "food_class.method"
        energy_bands: energy_bands.json content

    Returns:
        Center energy (midpoint of min/max) or None if not found
    """
    if band_key not in energy_bands:
        return None

    band = energy_bands[band_key]
    return (band["min"] + band["max"]) / 2


def compute_energy_similarity_score(
    predicted_kcal: float,
    candidate_kcal: float,
    tolerance_15pct: float = 1.0,
    tolerance_30pct: float = 0.5
) -> float:
    """
    Compute similarity score based on energy density difference.

    Args:
        predicted_kcal: Model's predicted energy density
        candidate_kcal: Candidate's energy density
        tolerance_15pct: Score bonus if within 15% (default 1.0)
        tolerance_30pct: Score bonus if within 30% (default 0.5)

    Returns:
        Similarity score (0.0 to tolerance_15pct)
    """
    if predicted_kcal <= 0 or candidate_kcal <= 0:
        return 0.0

    energy_diff_pct = abs(predicted_kcal - candidate_kcal) / predicted_kcal

    if energy_diff_pct < 0.15:
        return tolerance_15pct  # Strong match
    elif energy_diff_pct < 0.30:
        return tolerance_30pct  # Moderate match
    else:
        return 0.0  # Poor match


def diagnose_atwater_violation(
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    kcal: float,
    fiber_g: float = 0.0
) -> Dict[str, any]:
    """
    Diagnose why an Atwater violation occurred.

    Returns detailed breakdown for debugging.

    Args:
        protein_g, carbs_g, fat_g, kcal, fiber_g: Nutrition values

    Returns:
        Dict with diagnosis details
    """
    atwater_kcal = calculate_atwater_energy(protein_g, carbs_g, fat_g, fiber_g)

    protein_kcal = ATWATER_PROTEIN * protein_g
    net_carbs = carbs_g - fiber_g if fiber_g > 0 else carbs_g
    carbs_kcal = ATWATER_CARBS * net_carbs
    fiber_kcal = ATWATER_FIBER * fiber_g if fiber_g > 0 else 0.0
    fat_kcal = ATWATER_FAT * fat_g

    deviation = kcal - atwater_kcal
    deviation_pct = abs(deviation) / atwater_kcal if atwater_kcal > 0 else 0.0

    return {
        "stated_kcal": kcal,
        "atwater_kcal": atwater_kcal,
        "deviation": deviation,
        "deviation_pct": deviation_pct,
        "breakdown": {
            "protein": {"g": protein_g, "kcal": protein_kcal},
            "carbs_net": {"g": net_carbs, "kcal": carbs_kcal},
            "fiber": {"g": fiber_g, "kcal": fiber_kcal},
            "fat": {"g": fat_g, "kcal": fat_kcal},
        },
        "likely_cause": _infer_violation_cause(protein_g, carbs_g, fat_g, kcal, atwater_kcal)
    }


def _infer_violation_cause(
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    kcal_stated: float,
    kcal_atwater: float
) -> str:
    """
    Infer likely cause of Atwater violation.

    Returns:
        Human-readable cause description
    """
    deviation = kcal_stated - kcal_atwater
    deviation_pct = abs(deviation) / kcal_atwater if kcal_atwater > 0 else 0.0

    # Check if macros sum to near-zero (incomplete data)
    total_macros = protein_g + carbs_g + fat_g
    if total_macros < 5:
        return "incomplete_macro_data"

    # Check if stated kcal is much higher (missing fat?)
    if deviation > 50 and deviation_pct > 0.20:
        return "stated_kcal_too_high_missing_fat_data"

    # Check if stated kcal is much lower (fiber not accounted?)
    if deviation < -50 and deviation_pct > 0.20:
        return "stated_kcal_too_low_fiber_miscalculation"

    # Check if kcal is close to 4*(P+C+F) (no fat adjustment)
    simple_atwater = 4 * (protein_g + carbs_g + fat_g)
    if abs(kcal_stated - simple_atwater) / simple_atwater < 0.05:
        return "simple_4kcal_per_gram_used_fat_undercounted"

    # Default
    if deviation > 0:
        return "stated_kcal_exceeds_atwater_unknown_cause"
    else:
        return "stated_kcal_below_atwater_unknown_cause"
