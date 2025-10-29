"""
StageZ Deterministic Branded Fallback

For foods that don't exist in Foundation/SR databases (cherry tomatoes, broccoli florets,
scrambled eggs, green beans), provide deterministic branded entries as fallback.

Only triggers when:
1. Stage1b/1c/2 fail (empty pool or all rejected)
2. Class-intent matches target classes (produce, eggs, vegetable, fruit, protein)
3. Feature flag allow_branded_when_foundation_missing=true

Uses hardcoded FDC IDs from stageZ_branded_fallbacks.yml with plausibility guards.
"""
import os
from typing import Optional, Tuple, Dict, Any, List
from ..types import FdcEntry


class BrandedFallbackResolver:
    """Resolves foods to deterministic branded entries when Foundation/SR don't exist."""

    def __init__(self, branded_fallbacks_config: Dict[str, Any], fdc_database):
        """
        Initialize resolver with config and database.

        Args:
            branded_fallbacks_config: Loaded stageZ_branded_fallbacks.yml
            fdc_database: FDCDatabase instance for fetching branded entries
        """
        self.config = branded_fallbacks_config
        self.fdc_db = fdc_database
        self.enabled = branded_fallbacks_config.get('enabled', True)

        # Extract config sections
        self.fallbacks = branded_fallbacks_config.get('fallbacks', {})
        self.plausibility_guards = branded_fallbacks_config.get('plausibility_guards', {})
        self.reject_patterns = self.plausibility_guards.get('reject_patterns', [])

    def resolve(
        self,
        normalized_name: str,
        class_intent: str,
        form: str,
        feature_flags: Dict[str, bool]
    ) -> Optional[Tuple[FdcEntry, Dict[str, Any]]]:
        """
        Try to resolve food to a deterministic branded entry.

        Args:
            normalized_name: Normalized food name (from _normalize_for_lookup)
            class_intent: Class intent string (e.g., "produce|vegetable")
            form: Form string (e.g., "raw", "cooked")
            feature_flags: Feature flags dict

        Returns:
            Tuple of (FdcEntry, telemetry_dict) if found, else None
        """
        # Check feature flag
        if not feature_flags.get('allow_branded_when_foundation_missing', False):
            return None

        if not self.enabled:
            return None

        # Generate key variants: singular/plural, space/underscore combinations
        key_candidates = {
            normalized_name,                                    # exact
            normalized_name.rstrip('s'),                        # singular
            normalized_name + 's',                              # plural
            normalized_name.replace(' ', '_'),                  # underscore
            normalized_name.replace('_', ' '),                  # space
            normalized_name.rstrip('s').replace(' ', '_'),      # singular + underscore
            normalized_name.rstrip('s').replace('_', ' '),      # singular + space
        }

        # Try each variant to find a matching config
        fallback_config = None
        canonical_key = None

        for candidate_key in key_candidates:
            if candidate_key in self.fallbacks:
                fallback_config = self.fallbacks[candidate_key]
                canonical_key = candidate_key
                if os.getenv('ALIGN_VERBOSE', '0') == '1':
                    print(f"[BRANDED_FALLBACK] Key match: '{normalized_name}' → '{canonical_key}'")
                break

        if not fallback_config:
            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"[BRANDED_FALLBACK] No fallback config for '{normalized_name}' (tried {len(key_candidates)} variants)")
            return None

        primary = fallback_config.get('primary', {})

        if not primary or 'fdc_id' not in primary:
            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"[BRANDED_FALLBACK] No primary FDC ID for '{normalized_name}'")
            return None

        # Try primary candidate
        fdc_id = primary['fdc_id']
        brand = primary.get('brand', 'Unknown')
        kcal_range = primary.get('kcal_per_100g', [0, 1000])

        if os.getenv('ALIGN_VERBOSE', '0') == '1':
            print(f"[BRANDED_FALLBACK] Trying primary: {brand} FDC {fdc_id} for '{normalized_name}'")

        # Fetch from database
        food_data = self.fdc_db.get_food_by_fdc_id(str(fdc_id))

        if not food_data:
            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"[BRANDED_FALLBACK] ✗ FDC ID {fdc_id} not found in database")
            return None

        # Validate plausibility
        kcal = food_data.get('calories_value', 0) or 0
        if not (kcal_range[0] <= kcal <= kcal_range[1]):
            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"[BRANDED_FALLBACK] ✗ FDC {fdc_id} kcal={kcal:.1f} outside range {kcal_range}")
            return None

        # Check reject patterns
        food_name_lower = food_data.get('name', '').lower()

        # CRITICAL: Explicitly reject fast food entries
        if 'fast food' in food_name_lower:
            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"[BRANDED_FALLBACK] ✗ FDC {fdc_id} rejected: fast food entry")
            return None

        for pattern in self.reject_patterns:
            if pattern.lower() in food_name_lower:
                if os.getenv('ALIGN_VERBOSE', '0') == '1':
                    print(f"[BRANDED_FALLBACK] ✗ FDC {fdc_id} rejected: contains '{pattern}'")
                return None

        # Build FdcEntry
        entry = self._build_fdc_entry(food_data, normalized_name, form)

        # Build telemetry
        telemetry = {
            "reason": "not_in_foundation_sr",
            "queries_tried": [normalized_name],
            "canonical_key": canonical_key,  # NEW: Track which config key matched
            "brand": brand,
            "fdc_id": fdc_id,
            "kcal_per_100g": round(kcal, 1),
            "kcal_range": kcal_range,
            "fallback_key": normalized_name
        }

        if os.getenv('ALIGN_VERBOSE', '0') == '1':
            print(f"[BRANDED_FALLBACK] ✓ Resolved to {food_name} ({brand}, {kcal:.1f} kcal/100g)")

        return (entry, telemetry)

    def _build_fdc_entry(self, food_data: Dict[str, Any], core_class: str, form: str) -> FdcEntry:
        """
        Build FdcEntry from FDC database food data.

        Args:
            food_data: Dict from fdc_database.get_food_by_fdc_id()
            core_class: Core class for entry
            form: Form string

        Returns:
            FdcEntry instance
        """
        return FdcEntry(
            fdc_id=str(food_data.get('fdc_id', '')),
            name=food_data.get('name', ''),
            source="branded_food",
            form=form,
            data_type=food_data.get('data_type', 'branded_food'),
            core_class=core_class,
            method=form,  # Use form as method
            kcal_100g=float(food_data.get('calories_value', 0) or 0),
            protein_100g=float(food_data.get('protein_value', 0) or 0),
            carbs_100g=float(food_data.get('carbohydrates_value', 0) or 0),
            fat_100g=float(food_data.get('total_fat_value', 0) or 0),
            fiber_100g=float(food_data.get('fiber_value', 0) or 0)
        )


def resolve_branded_fallback(
    normalized_name: str,
    class_intent: str,
    form: str,
    branded_fallbacks_config: Dict[str, Any],
    fdc_database,
    feature_flags: Dict[str, bool]
) -> Optional[Tuple[FdcEntry, Dict[str, Any]]]:
    """
    Convenience function to resolve branded fallback.

    Args:
        normalized_name: Normalized food name
        class_intent: Class intent string
        form: Form string
        branded_fallbacks_config: Loaded stageZ_branded_fallbacks.yml
        fdc_database: FDCDatabase instance
        feature_flags: Feature flags dict

    Returns:
        Tuple of (FdcEntry, telemetry_dict) if found, else None
    """
    resolver = BrandedFallbackResolver(branded_fallbacks_config, fdc_database)
    return resolver.resolve(normalized_name, class_intent, form, feature_flags)
