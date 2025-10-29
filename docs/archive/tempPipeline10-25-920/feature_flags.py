"""
Feature flags for alignment micro-fixes.

Enable/disable experimental features via environment variables or direct modification.
All flags default to True for production use after validation.

Usage:
    from src.config.feature_flags import FLAGS

    if FLAGS.strict_cooked_exact_gate:
        # Apply stricter Stage 1 admission logic
        ...
"""
import os


class FeatureFlags:
    """
    Feature flags for alignment quality micro-fixes.

    Set via environment variables or modify defaults here.
    Example: export STRICT_COOKED_EXACT_GATE=false
    """

    # Fix 5.1: Stricter Foundation cooked-exact gate
    # Requires method compatibility AND energy within ±20% (instead of ±30%)
    strict_cooked_exact_gate: bool = os.getenv("STRICT_COOKED_EXACT_GATE", "true").lower() == "true"

    # Fix 5.2: Branded two-token coverage bump for meats
    # Raises score floor to 2.5 (from 2.0) when coverage=2 for sensitive classes
    branded_two_token_floor_25: bool = os.getenv("BRANDED_TWO_TOKEN_FLOOR_25", "true").lower() == "true"

    # Fix 5.3: Starch Atwater protein floor
    # Only apply Atwater soft correction when protein ≥12g/100g (skip for starches)
    starch_atwater_protein_floor: bool = os.getenv("STARCH_ATWATER_PROTEIN_FLOOR", "true").lower() == "true"

    # Fix 5.5: Mass soft clamps
    # Apply per-class IQR mass rails when confidence <0.75
    mass_soft_clamps: bool = os.getenv("MASS_SOFT_CLAMPS", "true").lower() == "true"

    # Stage Z: Universal branded last-resort fallback
    # Fills catalog gaps (bell pepper, herbs, etc.) with strict quality gates
    stageZ_branded_fallback: bool = os.getenv("STAGEZ_BRANDED_FALLBACK", "true").lower() == "true"

    # Vision Mass-Only Mode: Vision returns only mass, FDC computes nutrition (PRODUCTION DEFAULT)
    # When enabled, vision model returns {name, form, mass_g, count?, confidence} only
    # Reduces output tokens by 60-70% and improves mass accuracy
    vision_mass_only: bool = os.getenv("VISION_MASS_ONLY", "true").lower() == "true"

    # Vision Debug: Optional energy prior for Stage 4 tie-breaking (DEV ONLY)
    # When enabled, vision model includes optional debug_est_kcal_per_100g field
    # Used only for tie-breaking in Stage 4, never for primary scoring
    vision_debug_energy_prior: bool = os.getenv("VISION_DEBUG_ENERGY_PRIOR", "false").lower() == "true"

    @classmethod
    def print_status(cls):
        """Print current flag status for debugging."""
        print("\n[FLAGS] ===== Feature Flags Status =====")
        print(f"[FLAGS]   strict_cooked_exact_gate: {cls.strict_cooked_exact_gate}")
        print(f"[FLAGS]   branded_two_token_floor_25: {cls.branded_two_token_floor_25}")
        print(f"[FLAGS]   starch_atwater_protein_floor: {cls.starch_atwater_protein_floor}")
        print(f"[FLAGS]   mass_soft_clamps: {cls.mass_soft_clamps}")
        print(f"[FLAGS]   stageZ_branded_fallback: {cls.stageZ_branded_fallback}")
        print(f"[FLAGS]   vision_mass_only: {cls.vision_mass_only}")
        print(f"[FLAGS]   vision_debug_energy_prior: {cls.vision_debug_energy_prior}")
        print(f"[FLAGS] =====================================\n")

    @classmethod
    def disable_all(cls):
        """Disable all experimental features (for A/B testing baseline)."""
        cls.strict_cooked_exact_gate = False
        cls.branded_two_token_floor_25 = False
        cls.starch_atwater_protein_floor = False
        cls.mass_soft_clamps = False
        cls.stageZ_branded_fallback = False
        cls.vision_mass_only = False  # Revert to legacy macro mode
        cls.vision_debug_energy_prior = False

    @classmethod
    def enable_all(cls):
        """Enable all experimental features."""
        cls.strict_cooked_exact_gate = True
        cls.branded_two_token_floor_25 = True
        cls.starch_atwater_protein_floor = True
        cls.mass_soft_clamps = True
        cls.stageZ_branded_fallback = True
        cls.vision_mass_only = True  # Enable mass-only mode
        # Note: vision_debug_energy_prior stays False (dev-only flag)


# Global instance
FLAGS = FeatureFlags()
