"""
Core raw→cooked conversion engine.

Applies conversion kernels to transform Foundation/Legacy raw food entries
to cooked equivalents using method-specific factors.

Conversion kernels (stackable):
1. Hydration: grains/pasta absorb water → divide macros/kcal by factor
2. Shrinkage: meats lose water → divide by (1 - shrinkage) to concentrate
3. Fat rendering: meats lose fat during cooking
4. Oil uptake: surface oil absorption during frying
5. Macro retention: cooking losses for P/C/F
6. Energy clamping: constrain to method-aware plausible bounds
7. Atwater validation: ensure kcal ≈ 4P + 4C + 9F (±12%)

Output: ConvertedEntry with full provenance metadata
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from ..types import FdcEntry, ConversionFactors, ConvertedEntry
from ...config.feature_flags import FLAGS


def load_energy_bands(bands_path: Optional[Path] = None) -> Dict[str, Dict[str, float]]:
    """
    Load method-aware energy density bands.

    Args:
        bands_path: Path to energy_bands.json

    Returns:
        Dict mapping "food_class.method" → {"min": x, "max": y}
    """
    if bands_path is None:
        bands_path = Path(__file__).parent.parent.parent / "data" / "energy_bands.json"

    if not bands_path.exists():
        return {}

    with open(bands_path, 'r') as f:
        return json.load(f)


def extract_conversion_factors(
    core_class: str,
    method: str,
    cfg: Dict[str, Any]
) -> ConversionFactors:
    """
    Extract conversion factors from cook_conversions.v2.json.

    Args:
        core_class: Food class (e.g., "rice_white", "beef_steak")
        method: Cooking method (e.g., "boiled", "grilled")
        cfg: cook_conversions.v2.json content

    Returns:
        ConversionFactors dataclass with hydration, shrinkage, etc.
    """
    # Handle nested structure: cfg["classes"]["rice_white"]
    classes = cfg.get("classes", cfg)  # Support both old and new structure

    if core_class not in classes:
        return ConversionFactors()

    class_cfg = classes[core_class]
    method_profiles = class_cfg.get("method_profiles", {})

    if method not in method_profiles:
        return ConversionFactors()

    profile = method_profiles[method]

    # Extract mass change
    mass_change = profile.get("mass_change", {})
    mass_type = mass_change.get("type")

    hydration_factor = None
    shrinkage_fraction = None

    if mass_type == "hydration":
        hydration_factor = mass_change.get("factor_mean")
    elif mass_type == "shrinkage":
        shrinkage_fraction = mass_change.get("mean")

    # Extract fat rendering
    fat_render = profile.get("fat_render_fraction", {})
    fat_render_fraction = fat_render.get("mean") if fat_render else None

    # Extract oil uptake
    oil_uptake = profile.get("surface_oil_uptake_g_per_100g", {})
    oil_uptake_g = oil_uptake.get("mean") if oil_uptake else None

    # Extract macro retention (default 1.0 if not specified)
    macro_retention = profile.get("macro_retention", {})
    protein_retention = macro_retention.get("protein", 1.0)
    carbs_retention = macro_retention.get("carbs", 1.0)
    fat_retention = macro_retention.get("fat", 1.0)

    return ConversionFactors(
        hydration_factor=hydration_factor,
        shrinkage_fraction=shrinkage_fraction,
        fat_render_fraction=fat_render_fraction,
        oil_uptake_g_per_100g=oil_uptake_g,
        protein_retention=protein_retention,
        carbs_retention=carbs_retention,
        fat_retention=fat_retention
    )


def apply_hydration(
    protein_100g: float,
    carbs_100g: float,
    fat_100g: float,
    kcal_100g: float,
    hydration_factor: float
) -> Tuple[float, float, float, float]:
    """
    Apply hydration kernel: divide by hydration factor.

    When grains/pasta absorb water, the mass increases but nutrients
    are diluted per 100g.

    Example: Raw rice (365 kcal/100g) → Boiled rice (365 / 2.8 = 130 kcal/100g)

    Args:
        protein_100g, carbs_100g, fat_100g, kcal_100g: Raw per-100g values
        hydration_factor: Hydration multiplier (e.g., 2.8 for rice)

    Returns:
        (protein, carbs, fat, kcal) after hydration
    """
    if hydration_factor <= 1.0:
        return protein_100g, carbs_100g, fat_100g, kcal_100g

    return (
        protein_100g / hydration_factor,
        carbs_100g / hydration_factor,
        fat_100g / hydration_factor,
        kcal_100g / hydration_factor
    )


def apply_shrinkage(
    protein_100g: float,
    carbs_100g: float,
    fat_100g: float,
    kcal_100g: float,
    shrinkage_fraction: float
) -> Tuple[float, float, float, float]:
    """
    Apply shrinkage kernel: divide by (1 - shrinkage).

    When meats lose water, the mass decreases but nutrients concentrate
    per 100g of the cooked product.

    Example: Raw beef (250 kcal/100g) → Grilled beef (250 / 0.71 = 352 kcal/100g)
    with 29% shrinkage

    Args:
        protein_100g, carbs_100g, fat_100g, kcal_100g: Raw per-100g values
        shrinkage_fraction: Fraction lost (e.g., 0.29 for 29% shrinkage)

    Returns:
        (protein, carbs, fat, kcal) after shrinkage concentration
    """
    if shrinkage_fraction <= 0 or shrinkage_fraction >= 1.0:
        return protein_100g, carbs_100g, fat_100g, kcal_100g

    concentration_factor = 1.0 / (1.0 - shrinkage_fraction)

    return (
        protein_100g * concentration_factor,
        carbs_100g * concentration_factor,
        fat_100g * concentration_factor,
        kcal_100g * concentration_factor
    )


def apply_fat_rendering(
    fat_100g: float,
    kcal_100g: float,
    fat_render_fraction: float
) -> Tuple[float, float]:
    """
    Apply fat rendering kernel: reduce fat and calories.

    When meats are cooked, fat melts and drips away.

    Args:
        fat_100g: Fat content after shrinkage
        kcal_100g: Calories after shrinkage
        fat_render_fraction: Fraction of fat lost (e.g., 0.25 for 25%)

    Returns:
        (fat, kcal) after fat rendering
    """
    if fat_render_fraction <= 0 or fat_render_fraction >= 1.0:
        return fat_100g, kcal_100g

    fat_lost_g = fat_100g * fat_render_fraction
    kcal_lost = fat_lost_g * 9  # 9 kcal per gram of fat

    return (
        fat_100g - fat_lost_g,
        kcal_100g - kcal_lost
    )


def apply_oil_uptake(
    fat_100g: float,
    kcal_100g: float,
    oil_uptake_g: float
) -> Tuple[float, float]:
    """
    Apply oil uptake kernel: add fat and calories.

    When foods are fried, they absorb surface oil.

    Args:
        fat_100g: Fat content before oil
        kcal_100g: Calories before oil
        oil_uptake_g: Grams of oil absorbed per 100g

    Returns:
        (fat, kcal) after oil uptake
    """
    if oil_uptake_g <= 0:
        return fat_100g, kcal_100g

    kcal_added = oil_uptake_g * 9  # 9 kcal per gram of oil

    return (
        fat_100g + oil_uptake_g,
        kcal_100g + kcal_added
    )


def apply_macro_retention(
    protein_100g: float,
    carbs_100g: float,
    fat_100g: float,
    factors: ConversionFactors
) -> Tuple[float, float, float]:
    """
    Apply macro retention kernel: multiply by retention rates.

    Some macros are lost during cooking (e.g., fat dripping, starch loss).

    Args:
        protein_100g, carbs_100g, fat_100g: Macro values
        factors: ConversionFactors with retention rates

    Returns:
        (protein, carbs, fat) after retention adjustment
    """
    return (
        protein_100g * factors.protein_retention,
        carbs_100g * factors.carbs_retention,
        fat_100g * factors.fat_retention
    )


def clamp_to_energy_band(
    kcal_100g: float,
    core_class: str,
    method: str,
    energy_bands: Dict[str, Dict[str, float]]
) -> Tuple[float, bool]:
    """
    Clamp energy density to method-aware plausible bounds.

    Args:
        kcal_100g: Calculated energy density
        core_class: Food class (e.g., "rice_white")
        method: Cooking method (e.g., "boiled")
        energy_bands: energy_bands.json content

    Returns:
        (clamped_kcal, was_clamped) tuple
    """
    band_key = f"{core_class}.{method}"

    if band_key not in energy_bands:
        return kcal_100g, False

    band = energy_bands[band_key]
    min_kcal = band["min"]
    max_kcal = band["max"]

    if kcal_100g < min_kcal:
        return min_kcal, True
    elif kcal_100g > max_kcal:
        return max_kcal, True
    else:
        return kcal_100g, False


def validate_atwater(
    protein_100g: float,
    carbs_100g: float,
    fat_100g: float,
    kcal_100g: float,
    tolerance: float = 0.12
) -> Tuple[bool, float, float]:
    """
    Validate Atwater consistency: kcal ≈ 4P + 4C + 9F.

    Args:
        protein_100g, carbs_100g, fat_100g, kcal_100g: Nutrition values
        tolerance: Acceptable deviation fraction (default 12%)

    Returns:
        (is_valid, calculated_kcal, deviation_pct) tuple
    """
    atwater_kcal = 4 * protein_100g + 4 * carbs_100g + 9 * fat_100g

    if atwater_kcal == 0:
        return True, 0.0, 0.0

    deviation_pct = abs(kcal_100g - atwater_kcal) / atwater_kcal

    is_valid = deviation_pct <= tolerance

    return is_valid, atwater_kcal, deviation_pct


def soft_atwater_correction(
    protein_100g: float,
    carbs_100g: float,
    fat_100g: float,
    kcal_100g: float,
    atwater_kcal: float
) -> float:
    """
    Apply soft Atwater correction: blend 70% Atwater + 30% original.

    Used when Atwater validation fails but we want to gently adjust
    rather than hard override.

    Args:
        protein_100g, carbs_100g, fat_100g: Macro values
        kcal_100g: Original calculated calories
        atwater_kcal: Atwater-calculated calories

    Returns:
        Blended calories
    """
    return 0.7 * atwater_kcal + 0.3 * kcal_100g


def convert_from_raw(
    raw_entry: FdcEntry,
    core_class: str,
    method: str,
    cfg: Dict[str, Any],
    energy_bands: Optional[Dict[str, Dict[str, float]]] = None
) -> ConvertedEntry:
    """
    Convert a raw FDC entry to cooked equivalent using method-specific factors.

    Applies conversion kernels in sequence:
    1. Hydration (grains/pasta)
    2. Shrinkage (meats)
    3. Fat rendering (meats)
    4. Oil uptake (fried foods)
    5. Macro retention
    6. Atwater validation (only if deviation >20%)
    7. Energy clamping (final authority - method-aware bounds)

    NEW: Kernel order optimized to prevent Atwater vs energy band conflicts.
    Energy clamp happens LAST to ensure method-aware bounds are respected.

    Args:
        raw_entry: FdcEntry with raw nutrition data
        core_class: Food class (e.g., "rice_white", "beef_steak")
        method: Cooking method (e.g., "boiled", "grilled")
        cfg: cook_conversions.v2.json content
        energy_bands: energy_bands.json content (optional)

    Returns:
        ConvertedEntry with cooked nutrition and provenance metadata
    """
    if energy_bands is None:
        energy_bands = load_energy_bands()

    # Extract conversion factors
    factors = extract_conversion_factors(core_class, method, cfg)

    # Start with raw values
    protein = raw_entry.protein_100g
    carbs = raw_entry.carbs_100g
    fat = raw_entry.fat_100g
    kcal = raw_entry.kcal_100g
    fiber = raw_entry.fiber_100g

    provenance_steps = []

    # Kernel 1: Hydration (grains/pasta)
    if factors.hydration_factor:
        protein, carbs, fat, kcal = apply_hydration(
            protein, carbs, fat, kcal, factors.hydration_factor
        )
        provenance_steps.append(f"hydration_×{factors.hydration_factor:.2f}")

    # Kernel 2: Shrinkage (meats)
    if factors.shrinkage_fraction:
        protein, carbs, fat, kcal = apply_shrinkage(
            protein, carbs, fat, kcal, factors.shrinkage_fraction
        )
        provenance_steps.append(f"shrinkage_{factors.shrinkage_fraction:.2%}")

    # Kernel 3: Fat rendering (meats)
    if factors.fat_render_fraction:
        fat, kcal = apply_fat_rendering(fat, kcal, factors.fat_render_fraction)
        provenance_steps.append(f"fat_render_{factors.fat_render_fraction:.2%}")

    # Kernel 4: Oil uptake (fried)
    if factors.oil_uptake_g_per_100g:
        fat, kcal = apply_oil_uptake(fat, kcal, factors.oil_uptake_g_per_100g)
        provenance_steps.append(f"oil_uptake_{factors.oil_uptake_g_per_100g:.1f}g")

    # Kernel 5: Macro retention
    if (factors.protein_retention != 1.0 or
        factors.carbs_retention != 1.0 or
        factors.fat_retention != 1.0):
        protein, carbs, fat = apply_macro_retention(protein, carbs, fat, factors)
        provenance_steps.append("macro_retention")

    # Kernel 6: Atwater validation (MOVED BEFORE energy clamp to avoid fighting)
    # Only apply soft correction if deviation is large (>20%)
    atwater_ok, atwater_kcal, deviation_pct = validate_atwater(protein, carbs, fat, kcal, tolerance=0.20)

    # Fix 5.3: Only apply Atwater soft correction for protein-dense foods
    # For starches (low protein), trust energy band instead to avoid fighting
    if not atwater_ok:
        should_apply_correction = True

        if FLAGS.starch_atwater_protein_floor:
            # Only apply Atwater correction if protein >= 12g/100g
            # This prevents Atwater from fighting with energy bands for starches
            if protein < 12.0:
                should_apply_correction = False
                provenance_steps.append(f"atwater_skip_starch_P{protein:.1f}g")

        if should_apply_correction:
            # Apply soft correction only if deviation is significant
            kcal_before_correction = kcal
            kcal = soft_atwater_correction(protein, carbs, fat, kcal, atwater_kcal)
            provenance_steps.append(f"atwater_soft_{kcal_before_correction:.0f}→{kcal:.0f}")

    # Kernel 7: Energy clamping (MOVED AFTER Atwater to be final authority)
    # Energy bands are method-aware empirical bounds, should have final say
    energy_clamped = False
    if energy_bands:
        kcal_before_clamp = kcal
        kcal, energy_clamped = clamp_to_energy_band(kcal, core_class, method, energy_bands)
        if energy_clamped:
            provenance_steps.append(f"energy_clamp_{kcal_before_clamp:.0f}→{kcal:.0f}")

    # Final check: Is result still outside energy band? (Should not happen if clamping worked)
    energy_band_outlier = False
    if energy_bands:
        band_key = f"{core_class}.{method}"
        if band_key in energy_bands:
            band = energy_bands[band_key]
            if not (band["min"] <= kcal <= band["max"]):
                energy_band_outlier = True
                provenance_steps.append(f"OUTLIER_band_{band['min']}-{band['max']}_actual_{kcal:.0f}")

    # Calculate confidence
    confidence = 0.85  # Base confidence for Foundation/Legacy conversion

    # Reduce confidence if energy was clamped (indicates large deviation)
    if energy_clamped:
        confidence -= 0.10

    # Reduce confidence if Atwater failed
    if not atwater_ok:
        confidence -= 0.05

    # Reduce confidence if energy band outlier detected
    if energy_band_outlier:
        confidence -= 0.05

    # Build provenance metadata
    provenance = {
        "raw_fdc_id": raw_entry.fdc_id,
        "raw_source": raw_entry.source,
        "raw_name": raw_entry.name,
        "conversion_steps": provenance_steps,
        "atwater_deviation_pct": deviation_pct,
        "energy_clamped": energy_clamped,
        "energy_band_outlier": energy_band_outlier,
    }

    return ConvertedEntry(
        original=raw_entry,
        protein_100g=protein,
        carbs_100g=carbs,
        fat_100g=fat,
        kcal_100g=kcal,
        fiber_100g=fiber,
        conversion_factors=factors,
        method=method,
        provenance=provenance,
        atwater_ok=atwater_ok,
        energy_clamped=energy_clamped,
        confidence=confidence
    )
