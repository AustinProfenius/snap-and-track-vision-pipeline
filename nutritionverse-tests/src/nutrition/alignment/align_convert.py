"""
5-Stage FDC Alignment with Raw→Cooked Conversion Priority + Universal Fallback.

PRIORITY ORDER (Stage 2 runs FIRST for cleaner matches):

Stage 2: Foundation/Legacy raw + conversion (FIRST - PREFERRED - cleanest, no processing variants)
Stage 1: Foundation/Legacy cooked exact match (SECOND - high quality, but may have processing noise)
Stage 3: Branded cooked exact match (THIRD - branded, but at least cooked)
Stage 4: Branded closest energy density (FOURTH - branded + energy match)
Stage 5: Proxy alignment (NEW - for classes lacking Foundation/Legacy entries)
Stage Z: Branded universal fallback (FIFTH - TIGHTEST GATES - catalog gap filler)

Rationale for Stage 2 first:
- Raw Foundation entries have no processing variants (no breaded/battered/fried noise)
- Conversion is controlled and predictable via cook_conversions.v2.json
- Stage 1 (cooked exact) can match noisy processed variants
- This prioritization increases Stage 2 usage from ~30% to target ≥60%

Stage 5 Rationale:
- Handles classes without Foundation/Legacy entries (e.g., mixed salad greens, yellow squash, tofu)
- Uses vetted proxies: name lookups, composites, or macro defaults
- Guarded by whitelist to prevent masking alignment bugs
- Feature flag controlled (FLAGS.enable_proxy_alignment)

Stage Z Rationale:
- Fills catalog gaps (e.g., bell pepper, herbs, uncommon produce)
- Only runs if all previous stages (1-5) failed
- Strictest gates: energy bands, macro validation, ingredient sanity, processing checks
- Feature flag controlled (FLAGS.stageZ_branded_fallback)

Each stage returns AlignmentResult with full telemetry for debugging.
"""
import json
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from ..types import FdcEntry, AlignmentResult, ConvertedEntry
from ..conversions.cook_convert import convert_from_raw, load_energy_bands
from ..utils.method_resolver import resolve_method, get_method_confidence_penalty, methods_compatible
from ..rails.energy_atwater import (
    compute_energy_similarity_score,
    validate_atwater_consistency
)
from ...config.feature_flags import FLAGS


def print_alignment_banner():
    """Print flags and version banner at batch start."""
    print("\n" + "="*70)
    print("FDC ALIGNMENT ENGINE - BATCH RUN")
    print("="*70)
    print(f"Timestamp: {datetime.datetime.now().isoformat()}")
    print(f"Version: 5-Stage + Stage-5 Proxy (v2.1)")
    print(f"\nFeature Flags:")
    print(f"  prefer_raw_foundation_convert: {FLAGS.prefer_raw_foundation_convert}")
    print(f"  enable_proxy_alignment: {FLAGS.enable_proxy_alignment}")
    print(f"  stageZ_branded_fallback: {FLAGS.stageZ_branded_fallback}")
    print(f"  vision_mass_only: {FLAGS.vision_mass_only}")
    print(f"  strict_cooked_exact_gate: {FLAGS.strict_cooked_exact_gate}")
    print("="*70 + "\n")


def load_cook_conversions(cfg_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load cook_conversions.v2.json configuration.

    Args:
        cfg_path: Path to cook_conversions.v2.json

    Returns:
        Conversion config dict
    """
    if cfg_path is None:
        cfg_path = Path(__file__).parent.parent.parent / "data" / "cook_conversions.v2.json"

    with open(cfg_path, 'r') as f:
        return json.load(f)


class FDCAlignmentWithConversion:
    """
    FDC database alignment with raw→cooked conversion support.
    """

    def __init__(
        self,
        cook_cfg_path: Optional[Path] = None,
        energy_bands_path: Optional[Path] = None,
        # NEW: External config support for pipeline convergence
        class_thresholds: Optional[Dict[str, float]] = None,
        negative_vocab: Optional[Dict[str, List[str]]] = None,
        feature_flags: Optional[Dict[str, bool]] = None
    ):
        """
        Initialize alignment engine.

        Args:
            cook_cfg_path: Path to cook_conversions.v2.json
            energy_bands_path: Path to energy_bands.json
            class_thresholds: Per-class Jaccard thresholds (or None for defaults)
            negative_vocab: Per-class negative vocabulary (or None for defaults)
            feature_flags: Feature flags dict (or None for defaults)
        """
        self.cook_cfg = load_cook_conversions(cook_cfg_path)
        self.energy_bands = load_energy_bands(energy_bands_path)

        # NEW: Store external configs (or None to trigger fallback in align methods)
        self._external_class_thresholds = class_thresholds
        self._external_negative_vocab = negative_vocab
        self._external_feature_flags = feature_flags

        # Track config source for telemetry
        self.config_source = (
            "external" if any([class_thresholds, negative_vocab, feature_flags])
            else "fallback"
        )

        # Emit warning if using fallback
        if self.config_source == "fallback":
            print("[WARNING] Using hardcoded config defaults in align_convert.py.")
            print("[WARNING] Load from configs/ directory for reproducibility.")

        # Telemetry counters for micro-fixes (Fix 5.6) + Stage Z
        self.telemetry = {
            "stage1_method_rejections": 0,
            "stage1_energy_proximity_rejections": 0,
            "stage4_token_coverage_2_raised_floor": 0,
            # Stage Z telemetry
            "stageZ_attempts": 0,
            "stageZ_passes": 0,
            "stageZ_reject_energy_band": 0,
            "stageZ_reject_macro_gates": 0,
            "stageZ_reject_ingredients": 0,
            "stageZ_reject_processing": 0,
            "stageZ_reject_score_floor": 0,
            "stageZ_top_rejected": [],
        }

    # Candidate classification helpers (Phase A1)
    def is_foundation_raw(self, entry: FdcEntry) -> bool:
        """Check if candidate is Foundation/SR Legacy raw."""
        return (entry.source in ("foundation", "sr_legacy") and
                entry.form == "raw")

    def is_foundation_or_sr_cooked(self, entry: FdcEntry) -> bool:
        """Check if candidate is Foundation/SR Legacy cooked."""
        return (entry.source in ("foundation", "sr_legacy") and
                entry.form == "cooked")

    def is_branded(self, entry: FdcEntry) -> bool:
        """Check if candidate is branded."""
        return entry.source == "branded"

    def align_food_item(
        self,
        predicted_name: str,
        predicted_form: str,
        predicted_kcal_100g: float,
        fdc_candidates: List[Dict[str, Any]],
        confidence: float = 0.8
    ) -> AlignmentResult:
        """
        Align a predicted food item to FDC database with 5-stage priority.

        Args:
            predicted_name: Predicted food name (e.g., "rice")
            predicted_form: Predicted form/method (e.g., "cooked", "grilled")
            predicted_kcal_100g: Predicted energy density
            fdc_candidates: List of FDC database candidates (dicts)
            confidence: Model's prediction confidence

        Returns:
            AlignmentResult with best match and telemetry
        """
        import os  # For ALIGN_VERBOSE env var

        # Step 1: Normalize to core class
        core_class = self._normalize_to_core_class(predicted_name)

        # Step 2: Resolve method FIRST (before any candidate processing)
        method, method_reason = resolve_method(
            core_class,
            predicted_form,
            self.cook_cfg
        )
        method_inferred = (method_reason != "explicit_match")

        # Verbose logging (behind env var)
        if os.getenv('ALIGN_VERBOSE', '0') == '1':
            print(f"[ALIGN] Starting alignment for '{predicted_name}' (form={predicted_form})")
            print(f"[ALIGN] Method resolved: {method} (reason={method_reason}, inferred={method_inferred})")

        # Track method inference in run-level telemetry
        if method_inferred:
            if not hasattr(self, 'telemetry'):
                self.telemetry = {}
            self.telemetry["method_inferred_count"] = \
                self.telemetry.get("method_inferred_count", 0) + 1

        # Apply method confidence penalty
        method_penalty = get_method_confidence_penalty(method_reason)
        adjusted_confidence = max(0.05, confidence - method_penalty)

        # Step 3: Convert to FdcEntry objects
        fdc_entries = [self._dict_to_fdc_entry(c) for c in fdc_candidates]

        # Step 4: Partition candidates by type ONCE (CRITICAL FIX)
        raw_foundation = [e for e in fdc_entries if self.is_foundation_raw(e)]
        cooked_sr_legacy = [e for e in fdc_entries if self.is_foundation_or_sr_cooked(e)]
        branded = [e for e in fdc_entries if self.is_branded(e)]

        if os.getenv('ALIGN_VERBOSE', '0') == '1':
            print(f"[ALIGN] Candidates partitioned: raw_foundation={len(raw_foundation)}, "
                  f"cooked_sr_legacy={len(cooked_sr_legacy)}, branded={len(branded)}")

        # Step 5: PROACTIVE Stage 1 gate - skip if raw Foundation exists
        stage1_blocked = False
        if FLAGS.prefer_raw_foundation_convert and len(raw_foundation) > 0:
            stage1_blocked = True
            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"[ALIGN] Stage 1 BLOCKED: raw Foundation exists "
                      f"(prefer_raw_foundation_convert=True, {len(raw_foundation)} candidates)")

            # NEW: Try Stage 1b FIRST if predicted form is raw/fresh/empty
            if predicted_form in {"raw", "fresh", "", None}:
                if os.getenv('ALIGN_VERBOSE', '0') == '1':
                    print(f"[ALIGN] Trying Stage 1b (raw Foundation direct) for raw/fresh/empty form...")

                stage1b_result = self._stage1b_raw_foundation_direct(
                    core_class, predicted_kcal_100g, raw_foundation
                )

                if stage1b_result:
                    match, score = stage1b_result
                    if os.getenv('ALIGN_VERBOSE', '0') == '1':
                        print(f"[ALIGN] ✓ Matched via stage1b_raw_foundation_direct: {match.name} (score={score:.3f})")

                    result = self._build_result(
                        match, "stage1b_raw_foundation_direct", adjusted_confidence, method, method_reason,
                        stage1_blocked=stage1_blocked,
                        candidate_pool_total=len(fdc_entries),
                        candidate_pool_raw_foundation=len(raw_foundation),
                        candidate_pool_cooked_sr_legacy=len(cooked_sr_legacy),
                        candidate_pool_branded=len(branded)
                    )
                    # Add Stage 1b score to telemetry
                    result.telemetry["stage1b_score"] = score
                    return result

            # NEW: Try Stage 1c (cooked SR direct) for cooked proteins BEFORE Stage 2
            if predicted_form in {"cooked", "fried", "grilled", "pan_seared", "boiled", "scrambled", "baked", "poached"}:
                if os.getenv('ALIGN_VERBOSE', '0') == '1':
                    print(f"[ALIGN] Trying Stage 1c (cooked SR direct) for cooked protein...")

                stage1c_result = self._stage1c_cooked_sr_direct(core_class, cooked_sr_legacy)

                if stage1c_result:
                    if os.getenv('ALIGN_VERBOSE', '0') == '1':
                        print(f"[ALIGN] ✓ Matched via stage1c_cooked_sr_direct: {stage1c_result.name}")

                    result = self._build_result(
                        stage1c_result, "stage1c_cooked_sr_direct", adjusted_confidence, method, method_reason,
                        stage1_blocked=stage1_blocked,
                        candidate_pool_total=len(fdc_entries),
                        candidate_pool_raw_foundation=len(raw_foundation),
                        candidate_pool_cooked_sr_legacy=len(cooked_sr_legacy),
                        candidate_pool_branded=len(branded)
                    )
                    return result

            # Try Stage 2 (raw + convert) for cooked forms OR if Stage 1b/1c failed
            # IMPORTANT: Stage 2 runs even when Stage 1 blocked (allows cooked veg conversion)
            match = self._stage2_raw_convert(
                core_class, method, predicted_kcal_100g, raw_foundation, predicted_form
            )
            if match:
                if os.getenv('ALIGN_VERBOSE', '0') == '1':
                    match_name = match.name if hasattr(match, 'name') else match.original.name
                    print(f"[ALIGN] ✓ Matched via stage2_raw_convert: {match_name}")
                return self._build_result(
                    match, "stage2_raw_convert", adjusted_confidence, method, method_reason,
                    stage1_blocked=stage1_blocked,
                    candidate_pool_total=len(fdc_entries),
                    candidate_pool_raw_foundation=len(raw_foundation),
                    candidate_pool_cooked_sr_legacy=len(cooked_sr_legacy),
                    candidate_pool_branded=len(branded)
                )

            # Stage 2 failed, go directly to branded (skip Stage 1)
            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"[ALIGN] Stage 2 failed, skipping to branded stages")

        else:
            # Normal flow: try Stage 1 first (cooked exact)
            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"[ALIGN] Trying Stage 1 (cooked exact)...")

            match = self._stage1_cooked_exact(
                core_class, method, predicted_kcal_100g, cooked_sr_legacy
            )
            if match:
                if os.getenv('ALIGN_VERBOSE', '0') == '1':
                    print(f"[ALIGN] ✓ Matched via stage1_cooked_exact: {match.name}")
                return self._build_result(
                    match, "stage1_cooked_exact", adjusted_confidence, method, method_reason,
                    stage1_blocked=False,
                    candidate_pool_total=len(fdc_entries),
                    candidate_pool_raw_foundation=len(raw_foundation),
                    candidate_pool_cooked_sr_legacy=len(cooked_sr_legacy),
                    candidate_pool_branded=len(branded)
                )

            # Stage 1 failed, try Stage 2 (raw + convert)
            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"[ALIGN] Stage 1 failed, trying Stage 2 (raw + convert)...")

            match = self._stage2_raw_convert(
                core_class, method, predicted_kcal_100g, raw_foundation, predicted_form
            )
            if match:
                if os.getenv('ALIGN_VERBOSE', '0') == '1':
                    match_name = match.name if hasattr(match, 'name') else match.original.name
                    print(f"[ALIGN] ✓ Matched via stage2_raw_convert: {match_name}")
                return self._build_result(
                    match, "stage2_raw_convert", adjusted_confidence, method, method_reason,
                    stage1_blocked=False,
                    candidate_pool_total=len(fdc_entries),
                    candidate_pool_raw_foundation=len(raw_foundation),
                    candidate_pool_cooked_sr_legacy=len(cooked_sr_legacy),
                    candidate_pool_branded=len(branded)
                )

        # Stages 1+2 failed, try branded
        if os.getenv('ALIGN_VERBOSE', '0') == '1':
            print(f"[ALIGN] Stages 1+2 failed, trying Stage 3 (branded cooked)...")

        # Stage 3: Branded cooked exact match
        match = self._stage3_branded_cooked(
            core_class, method, predicted_kcal_100g, branded
        )
        if match:
            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"[ALIGN] ✓ Matched via stage3_branded_cooked: {match.name}")
            branded_confidence = max(0.05, adjusted_confidence - 0.20)
            return self._build_result(
                match, "stage3_branded_cooked", branded_confidence, method, method_reason,
                stage1_blocked=stage1_blocked,
                candidate_pool_total=len(fdc_entries),
                candidate_pool_raw_foundation=len(raw_foundation),
                candidate_pool_cooked_sr_legacy=len(cooked_sr_legacy),
                candidate_pool_branded=len(branded)
            )

        # Stage 4: Branded closest energy density
        if os.getenv('ALIGN_VERBOSE', '0') == '1':
            print(f"[ALIGN] Stage 3 failed, trying Stage 4 (branded energy)...")

        match = self._stage4_branded_energy(
            core_class, predicted_kcal_100g, branded, predicted_name
        )
        if match:
            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"[ALIGN] ✓ Matched via stage4_branded_energy: {match.name}")
            fallback_confidence = max(0.05, adjusted_confidence - 0.40)
            return self._build_result(
                match, "stage4_branded_energy", fallback_confidence, method, method_reason,
                stage1_blocked=stage1_blocked,
                candidate_pool_total=len(fdc_entries),
                candidate_pool_raw_foundation=len(raw_foundation),
                candidate_pool_cooked_sr_legacy=len(cooked_sr_legacy),
                candidate_pool_branded=len(branded)
            )

        # Stage 5: Proxy alignment (whitelisted classes only)
        if FLAGS.enable_proxy_alignment:
            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"[ALIGN] Stage 4 failed, trying Stage 5 (proxy alignment)...")

            match = self._stage5_proxy_alignment(
                core_class, method, predicted_kcal_100g, predicted_form, None
            )
            if match:
                if os.getenv('ALIGN_VERBOSE', '0') == '1':
                    match_name = match.name if hasattr(match, 'name') else match.original.name
                    print(f"[ALIGN] ✓ Matched via stage5_proxy_alignment: {match_name}")
                proxy_confidence = max(0.05, adjusted_confidence - 0.15)
                return self._build_result(
                    match, "stage5_proxy_alignment", proxy_confidence, method, method_reason,
                    stage1_blocked=stage1_blocked,
                    candidate_pool_total=len(fdc_entries),
                    candidate_pool_raw_foundation=len(raw_foundation),
                    candidate_pool_cooked_sr_legacy=len(cooked_sr_legacy),
                    candidate_pool_branded=len(branded)
                )

        # Stage Z: Energy-only last resort (STRICT eligibility)
        if FLAGS.stageZ_branded_fallback:
            from .stage_z_guards import can_use_stageZ, build_energy_only_proxy, get_stagez_telemetry_fields, infer_category_from_class

            # Infer category for eligibility check
            category = infer_category_from_class(core_class)

            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"[ALIGN] Stage 5 failed, checking Stage-Z eligibility...")
                print(f"[ALIGN]   Category: {category}, Raw Foundation pool: {len(raw_foundation)}")

            # Check strict eligibility (NO raw Foundation, allowed category)
            if can_use_stageZ(core_class, category, len(raw_foundation), len(fdc_entries)):
                if os.getenv('ALIGN_VERBOSE', '0') == '1':
                    print(f"[ALIGN] ✓ Stage-Z eligible, building energy-only proxy...")

                # Build energy-only proxy with plausibility clamping
                proxy = build_energy_only_proxy(core_class, category, predicted_kcal_100g)

                # Create synthetic FDC entry from proxy
                from ..types import FdcEntry
                synthetic_entry = FdcEntry(
                    fdc_id=f"stagez_{core_class}",
                    name=proxy["name"],
                    source="stagez_proxy",  # FIXED: Add required source field
                    form="energy_only_proxy",  # FIXED: Add required form field
                    data_type="stageZ_energy_only",
                    core_class=core_class,
                    method=method,
                    kcal_100g=proxy["kcal_100g"],
                    protein_100g=0.0,  # Placeholder (None not allowed in FdcEntry)
                    carbs_100g=0.0,
                    fat_100g=0.0,
                    fiber_100g=0.0
                )

                stageZ_confidence = max(0.05, adjusted_confidence - 0.70)
                result = self._build_result(
                    synthetic_entry, "stageZ_energy_only", stageZ_confidence, method, method_reason,
                    stage1_blocked=stage1_blocked,
                    candidate_pool_total=len(fdc_entries),
                    candidate_pool_raw_foundation=len(raw_foundation),
                    candidate_pool_cooked_sr_legacy=len(cooked_sr_legacy),
                    candidate_pool_branded=len(branded)
                )

                # Add Stage-Z telemetry
                result.telemetry.update(get_stagez_telemetry_fields(proxy, category))
                result.telemetry["last_resort"] = True

                if os.getenv('ALIGN_VERBOSE', '0') == '1':
                    print(f"[ALIGN] ✓ Returning Stage-Z energy-only proxy: {proxy['clamped_kcal']} kcal/100g")

                return result
            else:
                if os.getenv('ALIGN_VERBOSE', '0') == '1':
                    print(f"[ALIGN] ✗ Stage-Z blocked (category={category}, raw_foundation={len(raw_foundation)})")

        # No match found
        if os.getenv('ALIGN_VERBOSE', '0') == '1':
            print(f"[ALIGN] ✗ No candidates matched")

        return self._build_result(
            None, "stage0_no_candidates", adjusted_confidence, method, method_reason,
            stage1_blocked=stage1_blocked,
            candidate_pool_total=len(fdc_entries),
            candidate_pool_raw_foundation=len(raw_foundation),
            candidate_pool_cooked_sr_legacy=len(cooked_sr_legacy),
            candidate_pool_branded=len(branded)
        )

    def _stage1_cooked_exact(
        self,
        core_class: str,
        method: str,
        predicted_kcal: float,
        candidates: List[FdcEntry]
    ) -> Optional[FdcEntry]:
        """
        Stage 1: Foundation/Legacy cooked exact match.

        Candidates list is pre-filtered by caller to contain only cooked SR/Legacy entries.
        Gate logic (raw Foundation check) is handled in align_food_item().

        Args:
            core_class: Normalized food class
            method: Resolved cooking method
            predicted_kcal: Predicted energy density
            candidates: Pre-filtered list of cooked Foundation/SR Legacy candidates only

        Returns:
            Best matching cooked entry, or None if no suitable match
        """
        # Gate removed - now handled proactively in align_food_item()
        # Candidates are pre-filtered to cooked SR/Legacy only

        for entry in candidates:
            # Candidates are already filtered to cooked SR/Legacy, but verify core class
            if entry.core_class != core_class:
                continue

            # Fix 5.1: Stricter method compatibility check
            if FLAGS.strict_cooked_exact_gate:
                if entry.method and entry.method != method:
                    # Check if methods are compatible (e.g., roasted ≈ baked)
                    if not methods_compatible(entry.method, method):
                        self.telemetry["stage1_method_rejections"] += 1
                        continue
            else:
                # Original behavior: method should match (or be unspecified)
                if entry.method and entry.method != method:
                    continue

            # Fix 5.1: Tighter energy proximity (±20% instead of ±30%)
            if FLAGS.strict_cooked_exact_gate:
                energy_diff_pct = abs(predicted_kcal - entry.kcal_100g) / predicted_kcal
                if energy_diff_pct > 0.20:
                    self.telemetry["stage1_energy_proximity_rejections"] += 1
                    continue
            else:
                # Original behavior: check energy similarity (within 30%)
                energy_score = compute_energy_similarity_score(
                    predicted_kcal, entry.kcal_100g
                )
                if energy_score <= 0:  # Not within 30%
                    continue

            # All gates passed
            return entry

        return None

    def _stage1b_raw_foundation_direct(
        self,
        core_class: str,
        predicted_kcal: float,
        raw_foundation: List[FdcEntry]
    ) -> Optional[Tuple[FdcEntry, float]]:
        """
        Stage 1b: Raw Foundation direct match.

        For raw-form predictions (form="raw", "fresh", or empty), directly match
        against raw Foundation entries using name token overlap + energy similarity.

        Scoring: 0.7 * name_token_jaccard + 0.3 * energy_similarity
        Threshold: ≥0.55
        Returns: (best_match, score) or None

        This stage was added to fix web app misses where raw foods (olives, celery,
        apple, grapes) were returning stage0_no_candidates despite having raw
        Foundation candidates.

        Args:
            core_class: Normalized food class (e.g., "grape", "apple")
            predicted_kcal: Predicted energy density (kcal/100g)
            raw_foundation: Pre-filtered list of raw Foundation candidates

        Returns:
            Tuple of (best matching entry, score) or None if no suitable match
        """
        import os  # For ALIGN_VERBOSE env var
        import re  # For token cleanup

        if not raw_foundation:
            return None

        best_match = None
        best_score = 0.0

        # SURGICAL FIX: Stop-words that contaminate Jaccard scores
        # These are processing descriptors, not food identifiers
        STOP_TOKENS = {
            "and", "or", "with", "without", "in", "of", "the",
            "raw", "cooked", "boiled", "steamed", "roasted", "fried", "grilled", "baked",
            "fresh", "frozen", "dried", "dehydrated", "bottled", "canned", "pickled",
            "ripe", "green", "red", "jumbo-super", "colossal", "small-extra", "large",
            "stuffed", "manzanilla", "pimiento", "sliced", "chopped", "prepared"
        }

        # Class-specific negatives (exclude processed/derived forms)
        # Use external config if provided, otherwise fall back to hardcoded defaults
        if self._external_negative_vocab:
            NEGATIVES_BY_CLASS = {
                cls: set(words) for cls, words in self._external_negative_vocab.items()
            }
        else:
            # Fallback to hardcoded defaults
            NEGATIVES_BY_CLASS = {
                "apple": {"strudel", "pie", "juice", "sauce", "chip", "dried"},
                "grape": {"juice", "jam", "jelly", "raisin"},
                "almond": {"oil", "butter", "flour", "meal", "paste"},  # NEW
                "potato": {"bread", "flour", "starch", "powder"},
                "sweet_potato": {"leave", "leaf", "flour", "starch", "powder"},
            }

        def _norm_token(t: str) -> str:
            """Normalize token: strip punctuation, plural 's', lowercase."""
            t = t.lower()
            t = re.sub(r"[^\w]+", "", t)  # Strip punctuation (), -, etc.
            # Strip plural 's' (but preserve special words like "brussels")
            if len(t) > 2 and t.endswith("s") and t not in {"brussels", "lentils", "beans", "peas"}:
                t = t[:-1]
            return t

        def _tokenize_clean(s: str) -> set:
            """Tokenize string and remove stop-words/processing terms."""
            tokens = [_norm_token(part) for part in s.replace("_", " ").split()]
            return {t for t in tokens if t and t not in STOP_TOKENS}

        # Parse core_class tokens with stop-word removal
        base_class = core_class.lower()
        class_tokens = _tokenize_clean(core_class)

        # Get class-specific negatives (e.g., "apple" excludes "strudel", "juice")
        class_negatives = NEGATIVES_BY_CLASS.get(base_class, set())

        # Determine threshold based on category (relaxed for fruits/veg)
        # Token cleanup makes scores much higher, so we can use consistent thresholds
        fruit_veg_classes = {
            "apple", "apples", "grape", "grapes", "berries", "strawberry",
            "strawberries", "blueberry", "blueberries", "raspberry", "raspberries",
            "blackberry", "blackberries", "cantaloupe", "honeydew", "melon", "melons",
            "watermelon", "banana", "bananas", "orange", "oranges",
            "spinach", "carrot", "carrots", "celery", "lettuce", "tomato", "tomatoes",
            "broccoli", "cauliflower", "pepper", "peppers", "cucumber", "cucumbers",
            "brussels_sprouts", "brussels", "olive", "olives"  # Include all veg
        }

        # Base threshold
        if any(fv in base_class for fv in fruit_veg_classes):
            threshold = 0.50  # Relaxed for fruits/veg (after token cleanup)
        else:
            threshold = 0.55  # Standard threshold

        # Class-specific threshold overrides (for single-token matching leniency)
        # Use external config if provided, otherwise fall back to hardcoded defaults
        if self._external_class_thresholds:
            CLASS_THRESHOLDS = self._external_class_thresholds
        else:
            # Fallback to hardcoded defaults
            CLASS_THRESHOLDS = {
                "grape": 0.30,        # Single-token, high verbosity in FDC
                "cantaloupe": 0.30,   # Single-token melon
                "honeydew": 0.30,     # Single-token melon
                "almond": 0.30,       # Single-token nut
                "olive": 0.35,        # Processing-heavy (pickled, stuffed, etc.)
                "tomato": 0.35,       # Processing-heavy (cherry, grape, etc.)
            }
        threshold = CLASS_THRESHOLDS.get(base_class, threshold)

        for entry in raw_foundation:
            # HARD FILTER: Skip candidates containing class-specific negative words
            # (e.g., skip "Strudel apple" for "apple", "Almond oil" for "almond")
            entry_name_lower = entry.name.lower()
            if any(neg in entry_name_lower for neg in class_negatives):
                continue  # Skip entirely - don't score

            # Token overlap (Jaccard coefficient) with stop-word removal
            entry_name_tokens = _tokenize_clean(entry.name)

            # Calculate Jaccard similarity (with leniency for single-token core classes)
            # For single-token classes like "grape", require core token presence,
            # then score based on simplicity (fewer extra tokens = better)
            if len(class_tokens) == 1:
                core_token = list(class_tokens)[0]
                if core_token not in entry_name_tokens:
                    continue  # Skip if core token not present
                # Single-token scoring: 1.0 with penalty for verbosity
                # Simple entries like "Grapes raw" score higher than "Grapes red Thompson seedless raw"
                jaccard = 1.0 / (1.0 + len(entry_name_tokens) * 0.05)
            else:
                # Multi-token classes use standard Jaccard
                intersection = len(class_tokens & entry_name_tokens)
                union = len(class_tokens | entry_name_tokens) or 1  # Avoid division by zero
                jaccard = intersection / union

            # Energy similarity (within 60 kcal = full credit)
            energy_diff = abs(predicted_kcal - entry.kcal_100g) if predicted_kcal else 60
            energy_sim = max(0.0, 1.0 - min(1.0, energy_diff / 60.0))

            # Combined score: 70% name match + 30% energy match
            score = 0.7 * jaccard + 0.3 * energy_sim

            # DEBUG: Log all scores in verbose mode
            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"  [Stage1b] Candidate: {entry.name[:50]}")
                print(f"    class_tokens: {class_tokens}")
                print(f"    entry_tokens: {entry_name_tokens}")
                print(f"    jaccard: {jaccard:.3f}, energy_sim: {energy_sim:.3f}, score: {score:.3f}, threshold: {threshold:.2f}, pass: {score >= threshold}")

            if score > best_score and score >= threshold:
                best_score = score
                best_match = entry

        if best_match:
            return (best_match, best_score)

        return None

    def _stage1c_cooked_sr_direct(
        self,
        core_class: str,
        cooked_sr_pool: List[FdcEntry]
    ) -> Optional[FdcEntry]:
        """
        Stage 1c: Cooked SR Legacy direct match (tiny whitelist for proteins).

        Only handles specific cooked proteins that have reliable SR Legacy entries:
        - Bacon (cooked/fried)
        - Eggs (scrambled, fried, boiled)
        - Egg whites (boiled/cooked)
        - Sausage (cooked)

        Args:
            core_class: Normalized food class (e.g., "bacon", "egg_scrambled")
            cooked_sr_pool: Pre-filtered list of cooked SR Legacy candidates

        Returns:
            Best matching entry or None
        """
        import re

        if not cooked_sr_pool:
            return None

        # Normalize token helper (reuse from Stage 1b)
        def _norm_token(t: str) -> str:
            t = t.lower().strip("_-(),.")
            if t.endswith("s") and len(t) > 2:
                t = t[:-1]
            return t

        # Whitelist of core classes with required tokens
        WHITELIST = {
            "bacon": {"bacon"},
            "egg_scrambled": {"egg", "scrambled"},
            "egg_fried": {"egg", "fried"},
            "egg_boiled": {"egg", "boiled"},
            "egg_white": {"egg", "white"},
            "sausage": {"sausage"},
        }

        want = WHITELIST.get(core_class, None)
        if not want:
            return None  # Not whitelisted

        # Find first entry with all required tokens
        for entry in cooked_sr_pool:
            entry_tokens = {_norm_token(t) for t in entry.name.lower().split()}
            if all(w in entry_tokens for w in want):
                return entry

        return None

    def _is_canonical_stage2(self, core_class: str, entry_name: str) -> bool:
        """
        Check if entry is a canonical raw base for Stage 2 conversion.

        Excludes non-food forms like leaves, flour, bread, starch, powder.
        Validates against canonical hints for specific classes.

        Args:
            core_class: Normalized food class (e.g., "sweet_potato")
            entry_name: FDC entry name (e.g., "Sweet potato leaves raw")

        Returns:
            True if canonical, False otherwise (e.g., "leaves", "flour")
        """
        import re

        # Normalize tokens (reuse from Stage 1b logic)
        def _norm_token(t: str) -> str:
            t = t.lower().strip("_-(),.")
            if t.endswith("s") and len(t) > 2:
                t = t[:-1]
            return t

        # Exclude non-food forms (leaves, flour, etc.)
        EXCLUDE_TOKENS_STAGE2 = {"leave", "leaf", "flour", "bread", "powder", "starch"}
        toks = {_norm_token(t) for t in entry_name.lower().split()}
        if any(x in toks for x in EXCLUDE_TOKENS_STAGE2):
            return False

        # Canonical hints (require specific tokens for certain classes)
        CANONICAL_HINTS = {
            "potato": {"potato"},  # Exclude "potato bread/flour"
            "sweet_potato": {"sweet", "potato"},  # Require both, exclude "sweet potato leaves"
            "brussels_sprouts": {"brussel", "sprout"},  # Require sprout tokens
        }
        hints = CANONICAL_HINTS.get(core_class, set())
        if hints:
            return all(h in toks for h in hints)

        # Default: accept if not excluded
        return True

    def _stage2_raw_convert(
        self,
        core_class: str,
        method: str,
        predicted_kcal: float,
        candidates: List[FdcEntry],
        predicted_form: Optional[str] = None
    ) -> Optional[ConvertedEntry]:
        """
        Stage 2: Foundation/Legacy raw + conversion (PREFERRED PATH).

        Find Foundation/Legacy raw entry and convert to cooked.

        Method is already resolved in align_food_item() before calling this stage,
        so we just use the provided method directly.
        """
        # Method is pre-resolved - no need for inference here
        # This was moved to align_food_item() to make conversion layer "unmissable"

        # Find best raw candidate (CANONICAL ONLY - exclude leaves/flour/etc.)
        raw_candidates_all = []

        for entry in candidates:
            # Must be Foundation or SR Legacy
            if entry.source not in ("foundation", "sr_legacy"):
                continue

            # Must be raw form
            if entry.form != "raw":
                continue

            # Must match core class
            if entry.core_class != core_class:
                continue

            raw_candidates_all.append(entry)

        if not raw_candidates_all:
            return None

        # Filter to canonical bases (exclude "sweet potato leaves", "potato flour", etc.)
        canonical_pool = [e for e in raw_candidates_all if self._is_canonical_stage2(core_class, e.name)]
        pool = canonical_pool if canonical_pool else raw_candidates_all  # Fallback if no canonical

        # Score and select best
        raw_candidate = None
        best_score = 0.0

        for entry in pool:
            # Score based on name match quality (simple heuristic)
            score = 1.0  # Base score for raw Foundation/Legacy
            if entry.name.lower().startswith(core_class.replace("_", " ")):
                score += 0.5

            if score > best_score:
                best_score = score
                raw_candidate = entry

        if not raw_candidate:
            return None

        # Convert raw → cooked
        converted = convert_from_raw(
            raw_candidate,
            core_class,
            method,
            self.cook_cfg,
            self.energy_bands
        )

        # Check energy similarity after conversion
        energy_score = compute_energy_similarity_score(
            predicted_kcal, converted.kcal_100g
        )

        # Accept if within 30% or if energy was clamped (clamping implies plausible)
        if energy_score > 0 or converted.energy_clamped:
            return converted

        return None

    def _stage3_branded_cooked(
        self,
        core_class: str,
        method: str,
        predicted_kcal: float,
        candidates: List[FdcEntry]
    ) -> Optional[FdcEntry]:
        """
        Stage 3: Branded cooked exact match.

        Look for branded entries that are already cooked.
        """
        for entry in candidates:
            # Must be branded
            if entry.source != "branded":
                continue

            # Must be cooked
            if entry.form != "cooked":
                continue

            # Core class should match (may be looser for branded)
            if entry.core_class != core_class:
                # Allow partial match for branded (e.g., "rice" in name)
                if core_class.split("_")[0] not in entry.name.lower():
                    continue

            # Check energy similarity
            energy_score = compute_energy_similarity_score(
                predicted_kcal, entry.kcal_100g
            )
            if energy_score > 0:
                return entry

        return None

    def _stage4_branded_energy(
        self,
        core_class: str,
        predicted_kcal: float,
        candidates: List[FdcEntry],
        predicted_name: str = ""
    ) -> Optional[FdcEntry]:
        """
        Stage 4: Branded closest energy density (LAST RESORT).

        NEW: Enhanced with strict admission gates:
        - Score floor ≥2.0
        - Token coverage ≥2 (at least 2 matching words)
        - Macro plausibility check
        - Energy within 30%

        Find branded entry with closest energy match, regardless of form.
        """
        best_match = None
        best_diff = float('inf')
        best_score = 0.0

        # Tokenize predicted name for coverage check
        pred_tokens = set(predicted_name.lower().split())

        for entry in candidates:
            # Must be branded
            if entry.source != "branded":
                continue

            # Core class should at least partially match
            if core_class.split("_")[0] not in entry.name.lower():
                continue

            # NEW: Token coverage requirement (at least 2 matching words)
            cand_tokens = set(entry.name.lower().split())
            token_coverage = len(pred_tokens & cand_tokens)
            if token_coverage < 2:
                continue

            # NEW: Compute simple name match score
            # Score = token_coverage / max(len(pred_tokens), len(cand_tokens))
            score = token_coverage / max(len(pred_tokens), len(cand_tokens))

            # NEW: Produce raw-first preference in Stage 4 branded
            # Import produce classes from fdc_alignment_v2
            from ...adapters.fdc_alignment_v2 import PRODUCE_CLASSES
            if core_class in PRODUCE_CLASSES:
                cand_name_lower = entry.name.lower()
                if "raw" in cand_name_lower or "fresh" in cand_name_lower:
                    score += 0.5  # Boost raw produce
                elif any(kw in cand_name_lower for kw in ["canned", "fried", "prepared", "cooked"]):
                    score -= 0.5  # Penalize processed produce

            # NEW: Score floor - must be ≥2.0 on a 0-5 scale
            # Convert to 0-5 scale: score * 5
            scaled_score = score * 5.0

            # Fix 5.2: Raise floor to 2.5 for meats/cured items when only 2 tokens match
            floor = 2.0
            if FLAGS.branded_two_token_floor_25:
                if token_coverage == 2:
                    # Check if this is a meat/cured item
                    meat_classes = {
                        "bacon", "sausage", "chicken_breast", "chicken_thigh",
                        "beef_steak", "beef_ground", "pork_chop", "turkey_breast",
                        "salmon_fillet", "white_fish", "tuna_steak", "shrimp"
                    }
                    if any(meat in core_class for meat in meat_classes):
                        floor = 2.5
                        self.telemetry["stage4_token_coverage_2_raised_floor"] = \
                            self.telemetry.get("stage4_token_coverage_2_raised_floor", 0) + 1

            if scaled_score < floor:
                continue

            # NEW: Macro plausibility gate
            # Check if macros make sense for this food class
            from ...adapters.fdc_alignment_v2 import macro_plausible_for_class
            if not macro_plausible_for_class(
                core_class,
                entry.protein_100g,
                entry.carbs_100g,
                entry.fat_100g,
                entry.kcal_100g
            ):
                continue

            # Find closest energy match
            energy_diff = abs(predicted_kcal - entry.kcal_100g)
            if energy_diff < best_diff:
                best_diff = energy_diff
                best_match = entry
                best_score = scaled_score

        # Only accept if within 30%
        if best_match and (best_diff / predicted_kcal) < 0.30:
            return best_match

        return None

    def _stage5_proxy_alignment(
        self,
        core_class: str,
        method: str,
        predicted_kcal: float,
        predicted_form: str,
        fdc_db: Any
    ) -> Optional[ConvertedEntry]:
        """
        Stage 5: Proxy Alignment (Whitelisted Classes Only).

        For food classes lacking Foundation/Legacy entries, use vetted proxy entries:
        1. leafy_mixed_salad → 50% romaine + 50% green leaf (composite)
        2. squash_summer_yellow → zucchini (name lookup)
        3. tofu_plain_raw → Foundation tofu (macro defaults)

        Args:
            core_class: Normalized food class
            method: Cooking method
            predicted_kcal: Predicted energy (kcal/100g)
            predicted_form: Predicted form (raw/cooked)
            fdc_db: FDC database instance (for lookups)

        Returns:
            ConvertedEntry with proxy macros, or None if not whitelisted
        """
        # CRITICAL: Strict whitelist enforcement
        STAGE5_WHITELIST = {
            "leafy_mixed_salad",
            "squash_summer_yellow",
            "tofu_plain_raw"
        }

        if core_class not in STAGE5_WHITELIST:
            return None

        # Initialize telemetry
        if not hasattr(self, 'telemetry'):
            self.telemetry = {}

        # Proxy 1: Leafy Mixed Salad (Composite)
        if core_class == "leafy_mixed_salad":
            # 50% romaine lettuce + 50% green leaf lettuce
            # Default portion: 55g (1 cup shredded)
            # Energy-anchored blend
            proxy_macros = {
                "protein_100g": 1.2,  # Average of romaine (1.2) and green leaf (1.4)
                "carbs_100g": 3.6,    # Average of romaine (3.3) and green leaf (3.9)
                "fat_100g": 0.2,      # Average of romaine (0.3) and green leaf (0.2)
                "kcal_100g": 17.0     # Energy-anchored blend target
            }

            # Validate against predicted energy (within 20%)
            energy_diff = abs(predicted_kcal - proxy_macros["kcal_100g"])
            if energy_diff / predicted_kcal > 0.20:
                self.telemetry["stage5_reject_energy_mismatch"] = \
                    self.telemetry.get("stage5_reject_energy_mismatch", 0) + 1
                return None

            # Create composite entry
            provenance = {
                "proxy_used": True,
                "proxy_type": "composite_blend",
                "proxy_formula": "50% romaine + 50% green_leaf",
                "default_portion_g": 55,
                "energy_anchored": True
            }

            # Create FdcEntry for original (romaine as base)
            original = FdcEntry(
                fdc_id=169249,  # Romaine FDC ID
                core_class="lettuce_romaine",
                name="Lettuce, cos or romaine, raw",
                source="foundation",
                form="raw",
                method=None,
                protein_100g=1.2,
                carbs_100g=3.3,
                fat_100g=0.3,
                kcal_100g=17
            )

            # Import conversion factors (done once above)
            from ..types import ConversionFactors
            temp_mock_factors = ConversionFactors(
                hydration_factor=None,
                shrinkage_fraction=None,
                fat_render_fraction=None,
                oil_uptake_g_per_100g=None,
                protein_retention=1.0,
                carbs_retention=1.0,
                fat_retention=1.0
            )

            result = ConvertedEntry(
                original=original,
                protein_100g=proxy_macros["protein_100g"],
                carbs_100g=proxy_macros["carbs_100g"],
                fat_100g=proxy_macros["fat_100g"],
                kcal_100g=proxy_macros["kcal_100g"],
                fiber_100g=0.7,  # Romaine/green leaf avg fiber
                conversion_factors=temp_mock_factors,
                method="raw",  # No conversion applied
                provenance=provenance
            )

            self.telemetry["stage5_proxy_leafy_mixed_salad"] = \
                self.telemetry.get("stage5_proxy_leafy_mixed_salad", 0) + 1

            return result

        # Create mock conversion factors (used by all proxies)
        from ..types import ConversionFactors
        mock_factors = ConversionFactors(
            hydration_factor=None,
            shrinkage_fraction=None,
            fat_render_fraction=None,
            oil_uptake_g_per_100g=None,
            protein_retention=1.0,
            carbs_retention=1.0,
            fat_retention=1.0
        )

        # Proxy 2: Yellow Squash (Zucchini Lookup)
        if core_class == "squash_summer_yellow":
            # Try name lookup for zucchini raw
            try:
                # Mock lookup - in production, use fdc_db.search()
                # For now, use fallback macros if lookup fails
                zucchini_macros = {
                    "protein_100g": 1.2,
                    "carbs_100g": 3.1,
                    "fat_100g": 0.3,
                    "kcal_100g": 17.0
                }

                # Validate against predicted energy (within 30%)
                energy_diff = abs(predicted_kcal - zucchini_macros["kcal_100g"])
                if energy_diff / predicted_kcal > 0.30:
                    self.telemetry["stage5_reject_energy_mismatch"] = \
                        self.telemetry.get("stage5_reject_energy_mismatch", 0) + 1
                    return None

                provenance = {
                    "proxy_used": True,
                    "proxy_type": "name_lookup",
                    "proxy_formula": "zucchini_raw_as_proxy",
                    "fallback_used": True
                }

                # Create FdcEntry for original (zucchini as base)
                original = FdcEntry(
                    fdc_id=169291,  # Zucchini raw FDC ID
                    core_class="squash_summer_zucchini",
                    name="Squash, summer, zucchini, includes skin, raw",
                    source="foundation",
                    form="raw",
                    method=None,
                    protein_100g=1.2,
                    carbs_100g=3.1,
                    fat_100g=0.3,
                    kcal_100g=17
                )

                result = ConvertedEntry(
                    original=original,
                    protein_100g=zucchini_macros["protein_100g"],
                    carbs_100g=zucchini_macros["carbs_100g"],
                    fat_100g=zucchini_macros["fat_100g"],
                    kcal_100g=zucchini_macros["kcal_100g"],
                    fiber_100g=1.0,  # Zucchini fiber
                    conversion_factors=mock_factors,
                    method="raw",
                    provenance=provenance
                )

                self.telemetry["stage5_proxy_yellow_squash"] = \
                    self.telemetry.get("stage5_proxy_yellow_squash", 0) + 1

                return result

            except Exception as e:
                self.telemetry["stage5_lookup_failed"] = \
                    self.telemetry.get("stage5_lookup_failed", 0) + 1
                return None

        # Proxy 3: Tofu Plain Raw (Macro Defaults)
        if core_class == "tofu_plain_raw":
            # Foundation tofu macros (extra firm)
            tofu_macros = {
                "protein_100g": 10.0,
                "carbs_100g": 2.0,
                "fat_100g": 6.0,
                "kcal_100g": 94.0
            }

            # Validate against predicted energy (within 25%)
            energy_diff = abs(predicted_kcal - tofu_macros["kcal_100g"])
            if energy_diff / predicted_kcal > 0.25:
                self.telemetry["stage5_reject_energy_mismatch"] = \
                    self.telemetry.get("stage5_reject_energy_mismatch", 0) + 1
                return None

            provenance = {
                "proxy_used": True,
                "proxy_type": "macro_defaults",
                "proxy_formula": "foundation_tofu_extra_firm",
                "default_portion_g": 100
            }

            # Create FdcEntry for original (Foundation tofu)
            original = FdcEntry(
                fdc_id=172449,  # Tofu FDC ID
                core_class="tofu_plain",
                name="Tofu, raw, regular, prepared with calcium sulfate",
                source="foundation",
                form="raw",
                method=None,
                protein_100g=10.0,
                carbs_100g=2.0,
                fat_100g=6.0,
                kcal_100g=94
            )

            result = ConvertedEntry(
                original=original,
                protein_100g=tofu_macros["protein_100g"],
                carbs_100g=tofu_macros["carbs_100g"],
                fat_100g=tofu_macros["fat_100g"],
                kcal_100g=tofu_macros["kcal_100g"],
                fiber_100g=0.3,  # Tofu fiber
                conversion_factors=mock_factors,
                method="raw",
                provenance=provenance
            )

            self.telemetry["stage5_proxy_tofu"] = \
                self.telemetry.get("stage5_proxy_tofu", 0) + 1

            return result

        # Should never reach here due to whitelist check at top
        return None

    def _stageZ_branded_last_resort(
        self,
        core_class: str,
        method: str,
        predicted_kcal: float,
        candidates: List[FdcEntry],
        predicted_name: str,
        predicted_form: str
    ) -> Optional[FdcEntry]:
        """
        Stage Z: Branded universal last-resort fallback (TIGHTEST GATES).

        This stage runs ONLY if all previous stages (1-4) failed to find a match.
        It provides a safety net for catalog gaps (e.g., bell pepper, herbs, uncommon produce)
        while maintaining strict quality gates to prevent misalignments.

        Gates Applied (ALL must pass):
        1. Token overlap ≥2 (after synonym expansion)
        2. Energy band compliance (category-aware)
        3. Macro plausibility (per-category rules)
        4. Ingredient sanity (single-ingredient requires ≤2 components)
        5. Processing mismatch detection
        6. Sodium/sugar sanity for raw produce
        7. Score floor ≥2.4 (higher than Stage 4's 2.0/2.5)

        Args:
            core_class: Normalized food class
            method: Cooking method
            predicted_kcal: Predicted energy density
            candidates: List of FDC candidates
            predicted_name: Original predicted food name
            predicted_form: Original predicted form

        Returns:
            Best branded candidate if gates pass, else None
        """
        from ...adapters.fdc_taxonomy import expand_with_synonyms
        from ..rails.stage_z_gates import passes_stage_z_gates

        # Telemetry
        self.telemetry["stageZ_attempts"] = self.telemetry.get("stageZ_attempts", 0) + 1

        # Track which core classes use Stage Z (for last-resort usage analysis)
        if "stageZ_core_classes" not in self.telemetry:
            self.telemetry["stageZ_core_classes"] = []
        self.telemetry["stageZ_core_classes"].append(core_class)

        best_match = None
        best_score = 0.0
        rejected_candidates = []  # Track top 3 rejected for diagnostics

        # Expand predicted name with synonyms for better token matching
        expanded_names = expand_with_synonyms(predicted_name)
        all_pred_tokens = set()
        for name in expanded_names:
            all_pred_tokens.update(name.lower().split())

        for entry in candidates:
            # Must be branded
            if entry.source != "branded":
                continue

            # Core class should at least partially match
            if core_class.split("_")[0] not in entry.name.lower():
                continue

            # Token overlap ≥2 (using expanded synonyms)
            cand_tokens = set(entry.name.lower().split())
            token_coverage = len(all_pred_tokens & cand_tokens)
            if token_coverage < 2:
                continue

            # Apply Stage Z gates (ALL must pass)
            gates_pass, gate_results = passes_stage_z_gates(
                predicted_name,
                predicted_form,
                entry,
                core_class,
                method,
                self.energy_bands
            )

            if not gates_pass:
                # Track rejection reason for telemetry
                reason = gate_results.get("rejection_reason", "unknown")
                rejected_candidates.append({
                    "name": entry.name,
                    "reason": reason,
                    "token_coverage": token_coverage
                })

                # Update rejection counters
                if "energy_band" in reason:
                    self.telemetry["stageZ_reject_energy_band"] = \
                        self.telemetry.get("stageZ_reject_energy_band", 0) + 1
                elif "macro" in reason:
                    self.telemetry["stageZ_reject_macro_gates"] = \
                        self.telemetry.get("stageZ_reject_macro_gates", 0) + 1
                elif "ingredient" in reason:
                    self.telemetry["stageZ_reject_ingredients"] = \
                        self.telemetry.get("stageZ_reject_ingredients", 0) + 1
                elif "processing" in reason:
                    self.telemetry["stageZ_reject_processing"] = \
                        self.telemetry.get("stageZ_reject_processing", 0) + 1

                continue

            # Calculate score: token_coverage / max(pred, cand) * 5.0
            max_tokens = max(len(all_pred_tokens), len(cand_tokens))
            score = (token_coverage / max_tokens) * 5.0

            # Apply penalties
            ingredients = getattr(entry, 'ingredients', None)
            if not ingredients or len(ingredients) == 0:
                score -= 0.3  # Missing ingredients penalty

            # Check for preparation terms
            prep_terms = ["prepared", "seasoned", "marinated", "kit", "mix"]
            if any(term in entry.name.lower() for term in prep_terms):
                score -= 0.5  # Preparation penalty

            # Score floor: 2.4 (higher than Stage 4)
            if score < 2.4:
                rejected_candidates.append({
                    "name": entry.name,
                    "reason": f"score_floor_{score:.2f}<2.4",
                    "token_coverage": token_coverage
                })
                self.telemetry["stageZ_reject_score_floor"] = \
                    self.telemetry.get("stageZ_reject_score_floor", 0) + 1
                continue

            # Track best candidate
            if score > best_score:
                best_score = score
                best_match = entry

        # Log top 3 rejected candidates for diagnostics
        if rejected_candidates:
            rejected_candidates.sort(key=lambda x: x["token_coverage"], reverse=True)
            self.telemetry["stageZ_top_rejected"] = rejected_candidates[:3]

        if best_match:
            self.telemetry["stageZ_passes"] = self.telemetry.get("stageZ_passes", 0) + 1
            # Mark as last-resort for telemetry tracking
            best_match.last_resort = True
            return best_match

        return None

    def _normalize_to_core_class(self, name: str) -> str:
        """
        Normalize food name to core class.

        Args:
            name: Predicted food name (e.g., "white rice", "grilled chicken")

        Returns:
            Core class (e.g., "rice_white", "chicken_breast")
        """
        # Simple normalization (can be enhanced with taxonomy)
        name_lower = name.lower().strip()

        # Common mappings
        if "white rice" in name_lower or "rice white" in name_lower:
            return "rice_white"
        elif "brown rice" in name_lower or "rice brown" in name_lower:
            return "rice_brown"
        elif "rice" in name_lower:
            return "rice_white"  # Default to white

        if "chicken breast" in name_lower:
            return "chicken_breast"
        elif "chicken thigh" in name_lower:
            return "chicken_thigh"
        elif "chicken" in name_lower:
            return "chicken_breast"  # Default to breast

        if "beef steak" in name_lower or "steak" in name_lower:
            return "beef_steak"
        elif "ground beef" in name_lower:
            return "beef_ground_85"
        elif "beef" in name_lower:
            return "beef_steak"

        if "salmon" in name_lower:
            return "salmon_fillet"
        if "cod" in name_lower:
            return "white_fish_cod"
        if "tuna" in name_lower:
            return "tuna_steak"

        if "spinach" in name_lower:
            return "spinach"
        if "broccoli" in name_lower:
            return "broccoli"
        if "carrot" in name_lower:
            return "carrot"

        # NEW: Stage 5 proxy classes (Phase 1)
        if any(term in name_lower for term in ["mixed salad greens", "mixed greens", "spring mix",
                                                  "salad mix", "baby greens", "field greens",
                                                  "mesclun", "lettuce mix", "salad greens"]):
            return "leafy_mixed_salad"

        if "yellow squash" in name_lower:
            return "squash_summer_yellow"

        if "tofu" in name_lower:
            return "tofu_plain_raw"

        if "potato" in name_lower and "sweet" not in name_lower:
            return "potato_russet"
        if "sweet potato" in name_lower:
            return "sweet_potato"

        # SURGICAL FIX: Add missing normalizations for common vegetables/fruits
        # Olives (handles both "olive" and "olives")
        if "olive" in name_lower:
            return "olive"

        # Brussels sprouts (currently defaults to "brussels" from first word)
        if "brussels" in name_lower or "brussel" in name_lower:
            return "brussels_sprouts"

        # Tomatoes (handles plural)
        if "tomato" in name_lower:
            return "tomato"

        # Bell peppers
        if "bell pepper" in name_lower:
            return "bell_pepper"
        elif "pepper" in name_lower and "bell" not in name_lower:
            return "pepper"

        # Onions (distinguish red from regular)
        if "red onion" in name_lower:
            return "onion_red"
        elif "onion" in name_lower:
            return "onion"

        # Celery (make explicit even though it already works)
        if "celery" in name_lower:
            return "celery"

        # Garlic
        if "garlic" in name_lower:
            return "garlic"

        # Melons (honeydew, cantaloupe/muskmelon)
        if "honeydew" in name_lower:
            return "honeydew"
        if "cantaloupe" in name_lower or "muskmelon" in name_lower:
            return "cantaloupe"

        # Default: use first word with underscores
        return name_lower.split()[0].replace(" ", "_")

    def _dict_to_fdc_entry(self, candidate: Dict[str, Any]) -> FdcEntry:
        """
        Convert FDC candidate dict to FdcEntry.

        Args:
            candidate: FDC database record as dict

        Returns:
            FdcEntry dataclass
        """
        # Extract core class from name
        core_class = self._normalize_to_core_class(candidate.get("name", ""))

        # Infer form (raw/cooked/dried)
        name_lower = candidate.get("name", "").lower()
        if any(w in name_lower for w in ("cooked", "boiled", "grilled", "fried", "roasted", "baked")):
            form = "cooked"
        elif any(w in name_lower for w in ("raw", "fresh", "uncooked")):
            form = "raw"
        elif "dried" in name_lower:
            form = "dried"
        else:
            form = "raw"  # Default

        # Infer method if cooked
        method = None
        if form == "cooked":
            for m in ("grilled", "boiled", "fried", "roasted", "baked", "steamed"):
                if m in name_lower:
                    method = m
                    break

        return FdcEntry(
            fdc_id=candidate.get("fdc_id", 0),
            core_class=core_class,
            name=candidate.get("name", ""),
            source=candidate.get("data_type", "unknown").replace("_food", ""),
            form=form,
            method=method,
            protein_100g=float(candidate.get("protein_value", 0)),
            carbs_100g=float(candidate.get("carbohydrates_value", 0)),
            fat_100g=float(candidate.get("total_fat_value", 0)),
            kcal_100g=float(candidate.get("calories_value", 0))
        )

    def _build_result(
        self,
        match: Any,  # FdcEntry or ConvertedEntry (or None for no-match)
        stage: str,
        confidence: float,
        method: str,
        method_reason: str,
        stage1_blocked: bool = False,
        candidate_pool_total: int = 0,
        candidate_pool_raw_foundation: int = 0,
        candidate_pool_cooked_sr_legacy: int = 0,
        candidate_pool_branded: int = 0
    ) -> AlignmentResult:
        """
        Build AlignmentResult with mandatory telemetry.

        Args:
            match: FdcEntry or ConvertedEntry (or None for no-match)
            stage: Alignment stage identifier (must be valid)
            confidence: Adjusted confidence
            method: Resolved cooking method
            method_reason: Method resolution reason
            stage1_blocked: Whether Stage 1 was blocked due to raw Foundation existing
            candidate_pool_total: Total number of FDC candidates
            candidate_pool_raw_foundation: Number of raw Foundation/SR candidates
            candidate_pool_cooked_sr_legacy: Number of cooked Foundation/SR candidates
            candidate_pool_branded: Number of branded candidates

        Returns:
            AlignmentResult with full telemetry
        """
        import os  # For ALIGN_VERBOSE

        # Validate stage (CRITICAL: prevent "unknown")
        VALID_STAGES = {
            "stage0_no_candidates",
            "stage1_cooked_exact",
            "stage1b_raw_foundation_direct",  # NEW: Raw Foundation direct match
            "stage1c_cooked_sr_direct",  # NEW: Cooked SR direct (proteins only)
            "stage2_raw_convert",
            "stage3_branded_cooked",
            "stage4_branded_energy",
            "stage5_proxy_alignment",
            "stageZ_energy_only",  # NEW: Energy-only last resort
            "stageZ_branded_last_resort",
        }
        assert stage in VALID_STAGES, \
            f"Invalid alignment_stage: '{stage}' (must be one of {VALID_STAGES})"

        # Handle no-match case
        if match is None:
            telemetry = {
                "alignment_stage": stage,
                "method": method,
                "method_reason": method_reason,
                "method_inferred": (method_reason != "explicit_match"),
                "conversion_applied": False,
                "stage1_blocked_raw_foundation_exists": stage1_blocked,
                "sodium_gate_blocks": 0,
                "sodium_gate_passes": 0,
                "negative_vocab_blocks": 0,
                "oil_uptake_g_per_100g": 0,
                "candidate_pool_size": candidate_pool_total,
                "candidate_pool_raw_foundation": candidate_pool_raw_foundation,
                "candidate_pool_cooked_sr_legacy": candidate_pool_cooked_sr_legacy,
                "candidate_pool_branded": candidate_pool_branded,
            }

            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"[ALIGN] Telemetry: id=None stage={stage} method={method} "
                      f"converted=False oil=0.0g")

            return AlignmentResult(
                fdc_id=None,
                name="NO_MATCH",
                source="none",
                protein_100g=0.0,
                carbs_100g=0.0,
                fat_100g=0.0,
                kcal_100g=0.0,
                match_score=0.0,
                confidence=confidence,
                alignment_stage=stage,
                method=method,
                method_reason=method_reason,
                conversion_applied=False,
                telemetry=telemetry
            )

        # Handle ConvertedEntry vs FdcEntry
        if isinstance(match, ConvertedEntry):
            conversion_applied = True
            fdc_id = match.original.fdc_id
            name = f"{match.original.name} ({method})"
            source = match.original.source
            protein = match.protein_100g
            carbs = match.carbs_100g
            fat = match.fat_100g
            kcal = match.kcal_100g
            telemetry = match.provenance.copy()  # Start with conversion telemetry

            # Extract oil uptake if present
            oil_uptake = telemetry.get('oil_uptake_g_per_100g', 0)

        else:  # FdcEntry
            conversion_applied = False
            fdc_id = match.fdc_id
            name = match.name
            source = match.source
            protein = match.protein_100g
            carbs = match.carbs_100g
            fat = match.fat_100g
            kcal = match.kcal_100g
            telemetry = {}
            oil_uptake = 0

        # Validate Atwater
        atwater_ok, atwater_kcal, deviation = validate_atwater_consistency(
            protein, carbs, fat, kcal
        )

        # Build comprehensive telemetry (MANDATORY FIELDS)
        telemetry.update({
            "alignment_stage": stage,
            "method": method,
            "method_reason": method_reason,
            "method_inferred": (method_reason != "explicit_match"),
            "conversion_applied": conversion_applied,
            "atwater_ok": atwater_ok,
            "atwater_deviation_pct": deviation,
            "stage1_blocked_raw_foundation_exists": stage1_blocked,
            "oil_uptake_g_per_100g": oil_uptake,
            # Initialize gate counters (will be overwritten by search if applicable)
            "sodium_gate_blocks": telemetry.get("sodium_gate_blocks", 0),
            "sodium_gate_passes": telemetry.get("sodium_gate_passes", 0),
            "negative_vocab_blocks": telemetry.get("negative_vocab_blocks", 0),
            # Candidate pool counts (NEW - Phase 0.2)
            "candidate_pool_size": candidate_pool_total,
            "candidate_pool_raw_foundation": candidate_pool_raw_foundation,
            "candidate_pool_cooked_sr_legacy": candidate_pool_cooked_sr_legacy,
            "candidate_pool_branded": candidate_pool_branded,
        })

        # Compact proof line (behind ALIGN_VERBOSE)
        if os.getenv('ALIGN_VERBOSE', '0') == '1':
            print(f"[ALIGN] Telemetry: id={fdc_id} stage={stage} method={method} "
                  f"converted={conversion_applied} oil={oil_uptake:.1f}g")

        return AlignmentResult(
            fdc_id=fdc_id,
            name=name,
            source=source,
            protein_100g=protein,
            carbs_100g=carbs,
            fat_100g=fat,
            kcal_100g=kcal,
            match_score=0.85,  # Placeholder
            confidence=confidence,
            alignment_stage=stage,
            method=method,
            method_reason=method_reason,
            conversion_applied=conversion_applied,
            telemetry=telemetry
        )
