"""
Atwater Energy Reconciliation System

Fixes Foundation Foods entries with missing/zero energy by deriving kcal from macros.
Handles energy-macro inconsistencies using Atwater factors.
"""
from typing import Dict, Optional, Any


def atwater_kcal(protein_g: float, carbs_g: float, fat_g: float,
                fiber_g: Optional[float] = None,
                fiber_kcal: float = 2.0,
                use_net_carbs: bool = True) -> float:
    """
    Calculate energy using Atwater factors.

    Standard factors:
    - Protein: 4 kcal/g
    - Fat: 9 kcal/g
    - Carbs: 4 kcal/g (net carbs if fiber provided)
    - Fiber: 2 kcal/g (configurable)

    Args:
        protein_g: Protein in grams
        carbs_g: Carbohydrates in grams
        fat_g: Fat in grams
        fiber_g: Fiber in grams (optional)
        fiber_kcal: Energy per gram of fiber (default: 2.0)
        use_net_carbs: If True, uses net carbs (carbs - fiber)

    Returns:
        Estimated energy in kcal
    """
    if fiber_g is None or not use_net_carbs:
        # Simple Atwater: 4*P + 9*F + 4*C
        return 4.0 * protein_g + 9.0 * fat_g + 4.0 * carbs_g

    # Fiber-aware Atwater
    net_carbs = max(0.0, carbs_g - fiber_g)
    return 4.0 * protein_g + 9.0 * fat_g + 4.0 * net_carbs + fiber_kcal * fiber_g


def reconcile_energy(row: Dict[str, Any],
                    inconsistency_threshold: float = 0.15) -> Dict[str, Any]:
    """
    Reconcile energy with macros using Atwater factors.

    Handles three cases:
    1. Missing/zero energy → derive from macros
    2. Energy-macro inconsistency > threshold → use Atwater
    3. Consistent energy → use database value

    IMPORTANT: Normalizes per-serving values to per-100g if serving_gram_weight is present.

    Args:
        row: FDC database record (may be per-100g or per-serving)
        inconsistency_threshold: Max allowed difference (default: 15%)

    Returns:
        Dict with:
            - kcal_100g: Reconciled energy per 100g
            - protein_g: Protein per 100g
            - carbs_g: Carbs per 100g
            - fat_g: Fat per 100g
            - fiber_g: Fiber per 100g (if available)
            - provenance: Source of energy value
    """
    # CRITICAL: Check if values are per-serving and need normalization to per-100g
    serving_gram_weight = row.get("serving_gram_weight")
    if serving_gram_weight and float(serving_gram_weight) > 0:
        # Values are per-serving, convert to per-100g
        serving_g = float(serving_gram_weight)
        scale_to_100g = 100.0 / serving_g
        print(f"[ATWATER] Normalizing per-serving values (serving={serving_g}g) to per-100g (×{scale_to_100g:.2f})")
    else:
        # Values are already per-100g
        scale_to_100g = 1.0

    # Extract macros (with robust fallbacks) and normalize to per-100g
    protein_g = float(row.get("protein_value") or 0) * scale_to_100g
    fat_g = float(row.get("total_fat_value") or 0) * scale_to_100g

    # Carbs: prefer carbohydrate_by_difference (normalize to per-100g)
    carbs_g = float(row.get("carbohydrate_by_difference_value") or
                   row.get("carbohydrates_value") or 0) * scale_to_100g

    # Fiber (normalize to per-100g)
    fiber_g = row.get("fiber_value") or row.get("fiber_total_dietary_value")
    fiber_g = float(fiber_g) * scale_to_100g if fiber_g else None

    # Extract database energy (with fallbacks) and normalize to per-100g
    kcal_db = row.get("calories_value")
    kcal_db = float(kcal_db) if kcal_db else None

    if not kcal_db or kcal_db <= 0:
        kcal_db = row.get("energy_kcal_value")
        kcal_db = float(kcal_db) if kcal_db else None

    if not kcal_db or kcal_db <= 0:
        # Try converting from kJ
        kj = row.get("energy_kj_value")
        if kj:
            kj = float(kj)
            if kj > 0:
                kcal_db = kj / 4.184

    # Apply per-100g normalization if we have a value
    if kcal_db and kcal_db > 0:
        kcal_db = kcal_db * scale_to_100g
    else:
        kcal_db = None

    # Calculate Atwater energy
    kcal_atwater = atwater_kcal(
        protein_g, carbs_g, fat_g,
        fiber_g=fiber_g,
        fiber_kcal=2.0,
        use_net_carbs=True
    )

    # Decide which energy to use
    provenance = {
        "energy_source": "db_ok",
        "fiber_policy": "net_carbs_2kcal_per_g" if fiber_g else "no_fiber_data",
        "scaling_policy": "calorie_anchored_db_ratio"
    }

    if not kcal_db or kcal_db <= 0:
        # Case 1: Missing/zero energy → use Atwater
        kcal_use = kcal_atwater
        provenance["energy_source"] = "derived_from_macros"
        print(f"[ATWATER] Derived energy: {kcal_use:.1f} kcal/100g from macros (P:{protein_g:.1f}, C:{carbs_g:.1f}, F:{fat_g:.1f})")

    else:
        # Case 2: Check consistency
        diff_ratio = abs(kcal_db - kcal_atwater) / max(kcal_db, 1e-6)

        if diff_ratio > inconsistency_threshold:
            # Inconsistent → use Atwater
            kcal_use = kcal_atwater
            provenance["energy_source"] = "corrected_inconsistent_energy"
            provenance["db_kcal"] = float(kcal_db)
            provenance["atwater_kcal"] = float(kcal_atwater)
            provenance["difference_pct"] = float(diff_ratio * 100)
            print(f"[ATWATER] Corrected inconsistent energy: DB={kcal_db:.1f}, Atwater={kcal_atwater:.1f}, diff={diff_ratio*100:.1f}%")

        else:
            # Case 3: Consistent → use database
            kcal_use = kcal_db
            provenance["energy_source"] = "db_ok"

    return {
        "kcal_100g": max(kcal_use, 0.0),
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "fiber_g": fiber_g if fiber_g else 0.0,
        "provenance": provenance
    }


def validate_macro_energy_consistency(nutrition: Dict[str, float],
                                     tolerance: float = 0.20) -> Dict[str, Any]:
    """
    Validate that calories match macros within tolerance.

    Args:
        nutrition: Dict with kcal_100g, protein_g, carbs_g, fat_g
        tolerance: Max allowed difference (default: 20%)

    Returns:
        Dict with is_consistent flag and details
    """
    kcal_stated = nutrition.get("kcal_100g", 0)
    kcal_from_macros = atwater_kcal(
        nutrition.get("protein_g", 0),
        nutrition.get("carbs_g", 0),
        nutrition.get("fat_g", 0),
        fiber_g=nutrition.get("fiber_g")
    )

    if kcal_stated <= 0:
        return {
            "is_consistent": False,
            "reason": "zero_stated_energy",
            "kcal_stated": kcal_stated,
            "kcal_from_macros": kcal_from_macros
        }

    diff_ratio = abs(kcal_stated - kcal_from_macros) / kcal_stated

    return {
        "is_consistent": diff_ratio <= tolerance,
        "kcal_stated": kcal_stated,
        "kcal_from_macros": kcal_from_macros,
        "difference_pct": diff_ratio * 100,
        "tolerance_pct": tolerance * 100
    }
