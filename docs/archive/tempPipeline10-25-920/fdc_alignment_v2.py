"""
Improved FDC Database Alignment Module (V2)

Features:
- Food taxonomy classification
- Multi-word phrase handling
- Robust nutrition field extraction with fallbacks
- Class-constrained search
- Semantic scoring
- Mass-based scaling with calorie fallback
- Raw→cooked conversion with 4-stage alignment priority (NEW)
- Candidate quality filters: processing-mismatch guard, negative vocabulary, macro plausibility
"""
from typing import Dict, List, Optional, Any
import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ===== CANDIDATE QUALITY FILTERS =====

# Processing-mismatch guard: Reject breaded/battered/processed foods when prediction doesn't want them
PROCESSING_BAD = re.compile(
    r"\b(breaded|breading|battered|nugget|tender|patty|microwaved|"
    r"frozen prepared|glazed|tempura|stuffed|convenience|ready-to-eat|"
    r"fast foods|restaurant)\b",
    re.I
)

# Class-specific negative vocabulary: Prevent ingredient leakage & species substitution
CLASS_DISALLOWED_ALIASES = {
    # Meats - Processing & Species/Substitution variants
    "chicken_breast": ["breaded", "battered", "tender", "nugget", "patty", "microwaved", "fried prepared",
                       "plant-based", "plant based", "soy", "tofu", "seitan", "impossible", "beyond"],
    "chicken_thigh": ["breaded", "battered", "tender", "nugget", "patty", "microwaved",
                      "plant-based", "plant based", "soy", "tofu", "seitan"],
    "beef_steak": ["breaded", "battered", "patty", "burger", "microwaved",
                   "plant-based", "plant based", "soy", "impossible", "beyond", "turkey"],
    "bacon": ["meatless", "soy", "plant-based", "plant based", "imitation",
              "turkey", "chicken", "vegetarian", "vegan", "tempeh"],

    # Eggs - Substitution variants
    "egg": ["substitute", "imitation", "powder", "just egg", "vegan", "egg beaters"],

    # Starches - Form variants
    "potato_russet": ["flour", "starch", "powder", "mix", "dough", "dehydrated", "granules", "instant"],
    "rice_white": ["flour", "starch", "powder", "bran", "polish"],
    "rice_brown": ["flour", "starch", "powder", "bran"],
    "couscous": ["mix", "seasoned", "flavored"],

    # Vegetables/Legumes - Processed variants
    "peas": ["snack", "crisps", "chips", "puffs", "wasabi"],

    # Fruits/Dried - Ingredient leakage
    "raisins": ["cookie", "cookies", "cake", "muffin", "bread", "cereal"],
    "oats": ["cookie", "cookies", "granola bar", "cereal bar"],
}

# NEW: Produce classes for raw-first enforcement
PRODUCE_CLASSES = {
    # Fruits
    "apple", "banana", "blueberries", "blackberries", "raspberries",
    "strawberries", "grapes", "watermelon", "cantaloupe", "pineapple",
    "tomato", "cherry_tomatoes", "grape_tomatoes", "plum_tomatoes",

    # Vegetables
    "broccoli", "cauliflower", "carrot", "bell_pepper", "bell_pepper_green",
    "bell_pepper_red", "bell_pepper_yellow", "onion", "red_onion", "eggplant",
    "zucchini", "squash_yellow", "bok_choy", "brussels_sprouts", "cabbage",
    "cucumber", "spinach", "kale", "asparagus", "celery", "lettuce",
}

# NEW: Whole-food classes + ingredient-form ban regex
WHOLE_FOOD_CLASSES = {
    "potato_russet", "potato_red", "sweet_potato", "rice_white",
    "rice_brown", "oats", "corn", "wheat",
}

WHOLE_FOOD_INGREDIENT_BAN = re.compile(
    r"\b(flour|starch|powder|mix|dough|batter|meal|crumbs|coating)\b",
    re.I
)

# NEW: Cooked method token extraction (for branded cooked method matching)
COOKED_METHOD_TOKENS = re.compile(
    r"\b(fried|deep[- ]fried|pan[- ]seared|seared|grilled|roasted|"
    r"baked|steamed|boiled|poached|air[- ]fried|stir[- ]fried|"
    r"breaded|battered|tempura)\b",
    re.I
)

# Macro plausibility gates: Cheap pre-filters for category mismatches
def macro_plausible_for_class(
    core_class: str,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    kcal: float,
    predicted_kcal_est: Optional[float] = None,
    method: Optional[str] = None,
    energy_bands: Optional[Dict[str, Dict[str, float]]] = None
) -> bool:
    """
    Check if macros and energy are plausible for the food class.

    NEW: Enhanced with lean protein density floor, energy band check,
    and low-pred vs high-cand rejection.

    Args:
        core_class: Food class (e.g., "chicken_breast", "rice_white")
        protein_g, carbs_g, fat_g, kcal: Nutrition per 100g
        predicted_kcal_est: Model's predicted kcal/100g (optional)
        method: Cooking method (optional, for energy band check)
        energy_bands: Energy bands dict (optional)

    Returns:
        True if plausible, False if obviously wrong
    """
    # Meats should have low carbs (<5g/100g) and protein >10g
    if core_class in ("chicken_breast", "chicken_thigh", "beef_steak", "pork_chop", "turkey_breast", "salmon_fillet", "white_fish_cod"):
        if carbs_g > 5.0:  # Meats shouldn't have significant carbs
            return False
        if protein_g < 10.0:  # Meats should have decent protein
            return False

    # NEW: Lean protein density floor (chicken breast, white fish, egg white)
    if core_class in ("chicken_breast", "white_fish_cod", "egg_white"):
        if protein_g < 18.0:  # Lean proteins should be protein-dense
            return False

    # Grains/starches should have high carbs (>10g/100g cooked)
    if core_class in ("rice_white", "rice_brown", "pasta_wheat", "couscous", "quinoa"):
        if carbs_g < 10.0:  # Too low for a grain
            return False
        if protein_g > 20.0:  # Grains shouldn't be protein-rich
            return False

    # Vegetables should be low calorie (<150 kcal/100g)
    if core_class in ("broccoli", "carrot", "spinach", "peas", "beans_green"):
        if kcal > 150.0:  # Too high for a veggie
            return False

    # Fruits should be moderate carbs, low protein/fat
    if core_class in ("apple", "banana", "berries_mixed", "orange", "raisins"):
        if protein_g > 5.0 or fat_g > 5.0:  # Fruits are mostly carbs
            return False

    # NEW: Low-pred vs high-cand energy rejection
    # If model predicted low-cal (<60 kcal/100g) but candidate is high-cal (>120), reject
    if predicted_kcal_est is not None and predicted_kcal_est < 60 and kcal > 120:
        return False

    # NEW: Energy band check (if method and energy_bands available)
    if method and energy_bands and core_class:
        from ..nutrition.rails.energy_atwater import is_in_energy_band
        if not is_in_energy_band(kcal, core_class, method, energy_bands):
            return False

    return True

# Import FDC database connector and taxonomy
try:
    from .fdc_database import FDCDatabase
    from .fdc_taxonomy import extract_features, is_class_match, compute_match_score
    from .atwater_reconciliation import reconcile_energy
    FDC_AVAILABLE = True
except ImportError:
    FDC_AVAILABLE = False

# Import raw→cooked conversion system
try:
    from ..nutrition.alignment.align_convert import FDCAlignmentWithConversion
    from ..nutrition.rails.mass_rails import apply_mass_soft_clamp
    CONVERSION_AVAILABLE = True
except ImportError:
    CONVERSION_AVAILABLE = False
    print("[WARNING] Cooked-form conversion system not available")


def extract_base_nutrition(match: dict) -> Optional[Dict[str, float]]:
    """
    Extract nutrition values from database record using Atwater reconciliation.

    Uses reconcile_energy() to handle:
    - Missing/zero energy entries (derive from macros)
    - Energy-macro inconsistencies (use Atwater)
    - Consistent entries (use database value)

    Args:
        match: Database record dict

    Returns:
        Dict with calories, protein_g, carbs_g, fat_g, provenance per 100g,
        or None if macros are all zero
    """
    # Use Atwater reconciliation to get reliable energy
    reconciled = reconcile_energy(match, inconsistency_threshold=0.15)

    # Check if we have any meaningful nutrition data
    if (reconciled["kcal_100g"] <= 0 and
        reconciled["protein_g"] <= 0 and
        reconciled["carbs_g"] <= 0 and
        reconciled["fat_g"] <= 0):
        print(f"[ALIGN] WARNING: No nutrition data for {match.get('name', 'unknown')}")
        return None

    return {
        "calories": reconciled["kcal_100g"],
        "protein_g": reconciled["protein_g"],
        "carbs_g": reconciled["carbs_g"],
        "fat_g": reconciled["fat_g"],
        "fiber_g": reconciled["fiber_g"],
        "provenance": reconciled["provenance"]
    }


class FDCAlignmentEngineV2:
    """
    Improved FDC database alignment engine with taxonomy and semantic matching.
    """

    def __init__(self, enable_conversion: bool = True):
        """
        Initialize alignment engine.

        Args:
            enable_conversion: Enable raw→cooked conversion (default True)
        """
        load_dotenv(override=True)

        if not FDC_AVAILABLE:
            self.db_available = False
            print("[WARNING] FDC database module not available. Alignment disabled.")
            return

        connection_url = os.getenv("NEON_CONNECTION_URL")
        if not connection_url:
            self.db_available = False
            print("[WARNING] NEON_CONNECTION_URL not set. Alignment disabled.")
            return

        # Test connection
        try:
            with FDCDatabase(connection_url) as db:
                pass
            self.db_available = True
            self.connection_url = connection_url
            print("[INFO] FDC database alignment enabled (V2).")
        except Exception as e:
            self.db_available = False
            print(f"[WARNING] FDC database connection failed: {e}")

        # Initialize conversion system
        self.conversion_enabled = enable_conversion and CONVERSION_AVAILABLE
        if self.conversion_enabled:
            try:
                self.conversion_engine = FDCAlignmentWithConversion()
                print("[INFO] Raw→cooked conversion system enabled.")
            except Exception as e:
                self.conversion_enabled = False
                print(f"[WARNING] Failed to initialize conversion system: {e}")

    def search_best_match(self, food_name: str, data_types: List[str] = None,
                          predicted_kcal_100g: float = None, telemetry: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        Search for best matching food using taxonomy and semantic scoring.
        Falls back to legacy foods if no foundation food matches are found.

        Args:
            food_name: Predicted food name
            data_types: Food data types (default: foundation_food with legacy fallback)
            predicted_kcal_100g: Model's energy density estimate for better matching

        Returns:
            Best match dict or None
        """
        print(f"[ALIGN] Searching for: '{food_name}' (pred_kcal_100g: {predicted_kcal_100g})")

        if not self.db_available:
            print("[ALIGN] Database not available")
            return None

        # Default: try foundation_food first, then fallback to legacy
        if data_types is None:
            data_types = ["foundation_food"]
            use_legacy_fallback = True
        else:
            # If user explicitly provided data_types, respect their choice
            use_legacy_fallback = False

        # Extract taxonomic features
        features = extract_features(food_name)
        print(f"[ALIGN] Features: core={features['core']}, form={features['form']}, phrase={features['phrase']}")

        if not features["core"]:
            print("[ALIGN] WARNING: Could not identify food class, results may be poor")

        # Build search queries
        queries = []
        if features["phrase"]:
            queries.append(features["phrase"])  # Locked phrase first
        if features["core"] and features["form"]:
            queries.append(f"{features['core']} {features['form']}")  # e.g., "rice cooked"
        if features["core"]:
            queries.append(features["core"])  # Core word
        queries.append(food_name)  # Original as fallback

        # Search and collect candidates
        candidates = []
        seen_ids = set()

        try:
            with FDCDatabase(self.connection_url) as db:
                for query in queries:
                    results = db.search_foods(
                        query=query,
                        limit=20,
                        data_types=data_types
                    )

                    for r in results:
                        fdc_id = r["fdc_id"]
                        if fdc_id in seen_ids:
                            continue
                        seen_ids.add(fdc_id)

                        # Hard constraint: class must match
                        if features["core"] and not is_class_match(r["name"], features["core"]):
                            print(f"[ALIGN] Rejected {r['name']}: wrong class (expected {features['core']})")
                            continue

                        # NEW: Whole-food ingredient-form ban
                        if features["core"] in WHOLE_FOOD_CLASSES:
                            if WHOLE_FOOD_INGREDIENT_BAN.search(r["name"]):
                                print(f"[ALIGN] Rejected {r['name']}: ingredient-form ban (whole food)")
                                if telemetry is not None:
                                    telemetry["ingredient_form_bans"] = telemetry.get("ingredient_form_bans", 0) + 1
                                continue

                        # NEW: Processing-mismatch guard
                        # Reject breaded/battered foods unless prediction explicitly wants them
                        if PROCESSING_BAD.search(r["name"]):
                            # Check if prediction wanted processed form
                            if not any(kw in food_name.lower() for kw in ["breaded", "battered", "nugget", "tender", "fried"]):
                                print(f"[ALIGN] Rejected {r['name']}: processing mismatch (breaded/battered not wanted)")
                                if telemetry is not None:
                                    telemetry["processing_mismatch_blocks"] += 1
                                continue

                        # NEW: Class-specific negative vocabulary
                        # Prevent ingredient leakage (e.g., "flour potato", "cookie raisins")
                        if features["core"] in CLASS_DISALLOWED_ALIASES:
                            disallowed = CLASS_DISALLOWED_ALIASES[features["core"]]
                            candidate_lower = r["name"].lower()
                            if any(bad_word in candidate_lower for bad_word in disallowed):
                                print(f"[ALIGN] Rejected {r['name']}: negative vocabulary match ({features['core']} disallowed terms)")
                                if telemetry is not None:
                                    telemetry["negative_vocabulary_blocks"] += 1
                                continue

                        # Extract nutrition (rejects 0-calorie entries)
                        base_nutrition = extract_base_nutrition(r)
                        if not base_nutrition:
                            continue

                        # NEW: Macro plausibility gate
                        # Cheap filter for obviously wrong macros (e.g., chicken with 50g carbs)
                        if features["core"] and not macro_plausible_for_class(
                            features["core"],
                            base_nutrition["protein_g"],
                            base_nutrition["carbs_g"],
                            base_nutrition["fat_g"],
                            base_nutrition["calories"]
                        ):
                            print(f"[ALIGN] Rejected {r['name']}: macro implausible for {features['core']} "
                                  f"(P:{base_nutrition['protein_g']:.1f} C:{base_nutrition['carbs_g']:.1f} "
                                  f"F:{base_nutrition['fat_g']:.1f} kcal:{base_nutrition['calories']:.0f})")
                            if telemetry is not None:
                                telemetry["macro_plausibility_blocks"] += 1
                            continue

                        # NEW: Produce raw-first scoring adjustment
                        score_adjustment = 0.0
                        if features["core"] in PRODUCE_CLASSES:
                            pred_form_raw = (
                                not features.get("form") or
                                features.get("form") == "raw"
                            )

                            cand_name_lower = r["name"].lower()
                            cand_is_cooked_canned = any(
                                kw in cand_name_lower
                                for kw in ["cooked", "canned", "fried", "roasted", "grilled", "boiled"]
                            )

                            if pred_form_raw and cand_is_cooked_canned:
                                score_adjustment = -1.5  # Penalize cooked/canned
                                if telemetry is not None:
                                    telemetry["produce_raw_first_penalties"] = telemetry.get("produce_raw_first_penalties", 0) + 1
                                print(f"[ALIGN] Produce penalty: {r['name']} (pred=raw, cand=cooked/canned)")
                            elif pred_form_raw and "raw" in cand_name_lower:
                                score_adjustment = +1.0  # Boost raw matches
                                print(f"[ALIGN] Produce boost: {r['name']} (both raw)")

                        # Compute semantic score with energy density similarity
                        score = compute_match_score(
                            r["name"],
                            features,
                            candidate_kcal_100g=base_nutrition["calories"],
                            predicted_kcal_100g=predicted_kcal_100g
                        )

                        # Apply produce adjustment
                        score += score_adjustment

                        candidates.append({
                            "score": score,
                            "record": r,
                            "nutrition": base_nutrition
                        })

        except Exception as e:
            print(f"[ALIGN] ERROR: Search failed: {e}")
            import traceback
            traceback.print_exc()
            return None

        # If no candidates found in foundation foods, try legacy foods as fallback
        if not candidates and use_legacy_fallback:
            print(f"[ALIGN] No foundation food matches found for '{food_name}', trying legacy foods...")
            try:
                with FDCDatabase(self.connection_url) as db:
                    for query in queries:
                        results = db.search_foods(
                            query=query,
                            limit=20,
                            data_types=["sr_legacy_food"]
                        )

                        for r in results:
                            fdc_id = r["fdc_id"]
                            if fdc_id in seen_ids:
                                continue
                            seen_ids.add(fdc_id)

                            # Hard constraint: class must match
                            if features["core"] and not is_class_match(r["name"], features["core"]):
                                print(f"[ALIGN] Rejected {r['name']} (legacy): wrong class (expected {features['core']})")
                                continue

                            # NEW: Whole-food ingredient-form ban (same as foundation)
                            if features["core"] in WHOLE_FOOD_CLASSES:
                                if WHOLE_FOOD_INGREDIENT_BAN.search(r["name"]):
                                    print(f"[ALIGN] Rejected {r['name']} (legacy): ingredient-form ban")
                                    if telemetry is not None:
                                        telemetry["ingredient_form_bans"] = telemetry.get("ingredient_form_bans", 0) + 1
                                    continue

                            # NEW: Processing-mismatch guard (same as foundation)
                            if PROCESSING_BAD.search(r["name"]):
                                if not any(kw in food_name.lower() for kw in ["breaded", "battered", "nugget", "tender", "fried"]):
                                    print(f"[ALIGN] Rejected {r['name']} (legacy): processing mismatch")
                                    if telemetry is not None:
                                        telemetry["processing_mismatch_blocks"] += 1
                                    continue

                            # NEW: Class-specific negative vocabulary (same as foundation)
                            if features["core"] in CLASS_DISALLOWED_ALIASES:
                                disallowed = CLASS_DISALLOWED_ALIASES[features["core"]]
                                candidate_lower = r["name"].lower()
                                if any(bad_word in candidate_lower for bad_word in disallowed):
                                    print(f"[ALIGN] Rejected {r['name']} (legacy): negative vocabulary match")
                                    if telemetry is not None:
                                        telemetry["negative_vocabulary_blocks"] += 1
                                    continue

                            # Extract nutrition (rejects 0-calorie entries)
                            base_nutrition = extract_base_nutrition(r)
                            if not base_nutrition:
                                continue

                            # NEW: Macro plausibility gate (same as foundation)
                            if features["core"] and not macro_plausible_for_class(
                                features["core"],
                                base_nutrition["protein_g"],
                                base_nutrition["carbs_g"],
                                base_nutrition["fat_g"],
                                base_nutrition["calories"]
                            ):
                                print(f"[ALIGN] Rejected {r['name']} (legacy): macro implausible")
                                if telemetry is not None:
                                    telemetry["macro_plausibility_blocks"] += 1
                                continue

                            # NEW: Produce raw-first scoring adjustment (same as foundation)
                            score_adjustment = 0.0
                            if features["core"] in PRODUCE_CLASSES:
                                pred_form_raw = (
                                    not features.get("form") or
                                    features.get("form") == "raw"
                                )

                                cand_name_lower = r["name"].lower()
                                cand_is_cooked_canned = any(
                                    kw in cand_name_lower
                                    for kw in ["cooked", "canned", "fried", "roasted", "grilled", "boiled"]
                                )

                                if pred_form_raw and cand_is_cooked_canned:
                                    score_adjustment = -1.5  # Penalize cooked/canned
                                    if telemetry is not None:
                                        telemetry["produce_raw_first_penalties"] = telemetry.get("produce_raw_first_penalties", 0) + 1
                                    print(f"[ALIGN] Produce penalty (legacy): {r['name']} (pred=raw, cand=cooked/canned)")
                                elif pred_form_raw and "raw" in cand_name_lower:
                                    score_adjustment = +1.0  # Boost raw matches
                                    print(f"[ALIGN] Produce boost (legacy): {r['name']} (both raw)")

                            # Compute semantic score with energy density similarity
                            score = compute_match_score(
                                r["name"],
                                features,
                                candidate_kcal_100g=base_nutrition["calories"],
                                predicted_kcal_100g=predicted_kcal_100g
                            )

                            # Apply produce adjustment
                            score += score_adjustment

                            candidates.append({
                                "score": score,
                                "record": r,
                                "nutrition": base_nutrition
                            })

                if candidates:
                    print(f"[ALIGN] Found {len(candidates)} candidates in legacy foods")
            except Exception as e:
                print(f"[ALIGN] ERROR: Legacy fallback search failed: {e}")
                import traceback
                traceback.print_exc()

        if not candidates:
            print(f"[ALIGN] No valid candidates found for '{food_name}' in foundation or legacy foods")
            return None

        # Sort by score and return best
        candidates.sort(key=lambda x: x["score"], reverse=True)
        best = candidates[0]

        print(f"[ALIGN] Best match: {best['record']['name']} (FDC: {best['record']['fdc_id']}, score: {best['score']:.2f})")
        print(f"[ALIGN] Base nutrition/100g: {best['nutrition']}")

        # Show runner-ups for debugging
        if len(candidates) > 1:
            print(f"[ALIGN] Runner-ups:")
            for c in candidates[1:3]:
                print(f"[ALIGN]   - {c['record']['name']} (score: {c['score']:.2f})")

        return {
            "fdc_id": best["record"]["fdc_id"],
            "name": best["record"]["name"],
            "data_type": best["record"].get("data_type", "unknown"),
            "confidence": min(0.95, 0.6 + 0.1 * best["score"]),
            "score": best["score"],
            "base_nutrition_per_100g": best["nutrition"]
        }

    def compute_nutrition(self, base_per_100g: Dict[str, float],
                         predicted_food: Dict[str, Any]) -> Dict[str, float]:
        """
        Compute nutrition scaled from database.

        Always uses calorie-based scaling when calories are available to ensure
        output calories match prediction exactly.

        Args:
            base_per_100g: Base nutrition per 100g from database
            predicted_food: Predicted food dict with mass_g and/or calories

        Returns:
            Scaled nutrition dict
        """
        pred_mass = predicted_food.get("mass_g")
        pred_calories = predicted_food.get("calories")

        print(f"[ALIGN] Computing nutrition: pred_mass={pred_mass}g, pred_cal={pred_calories}kcal")

        # Always prefer calorie-based scaling when calories are available
        if pred_calories and pred_calories > 0:
            base_cal = base_per_100g["calories"]
            if base_cal <= 0:
                print("[ALIGN] ERROR: Cannot scale by calories, base is 0")
                return {"mass_g": 0, "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}

            mass = (pred_calories / base_cal) * 100.0
            scale_factor = mass / 100.0

            # NEW: Mass inflation guard for ultra-low kcal foods (vegetables/fruits)
            # If computed mass inflates by >2× and we have predicted mass, use predicted mass instead
            if pred_mass and pred_mass > 0:
                inflation_ratio = mass / pred_mass
                if inflation_ratio > 2.0:
                    print(f"[ALIGN] ⚠️  MASS INFLATION GUARD: computed {mass:.1f}g is {inflation_ratio:.1f}× predicted {pred_mass:.1f}g")
                    print(f"[ALIGN]    Likely ultra-low kcal food (base: {base_cal:.1f} kcal/100g)")
                    print(f"[ALIGN]    Using predicted mass and scaling macros proportionally")

                    # Use predicted mass, scale macros only
                    scale_factor = pred_mass / 100.0
                    result = {
                        "mass_g": pred_mass,  # Use predicted mass
                        "calories": pred_calories,  # Keep predicted calories
                        "protein_g": base_per_100g["protein_g"] * scale_factor,
                        "carbs_g": base_per_100g["carbs_g"] * scale_factor,
                        "fat_g": base_per_100g["fat_g"] * scale_factor,
                    }
                    return result

            result = {
                "mass_g": mass,
                "calories": pred_calories,  # Use exact predicted calories
                "protein_g": base_per_100g["protein_g"] * scale_factor,
                "carbs_g": base_per_100g["carbs_g"] * scale_factor,
                "fat_g": base_per_100g["fat_g"] * scale_factor,
            }
            print(f"[ALIGN] Calorie-based scaling: {pred_calories}kcal → {mass:.1f}g")

            # Note if predicted mass differs significantly
            if pred_mass and pred_mass > 0:
                mass_diff_pct = abs(mass - pred_mass) / pred_mass * 100
                if mass_diff_pct > 20:
                    print(f"[ALIGN] NOTE: Computed mass {mass:.1f}g differs from predicted {pred_mass}g by {mass_diff_pct:.1f}%")

            return result

        # Mass-based scaling (when no calories from vision - mass-only mode)
        if pred_mass and pred_mass > 0:
            scale_factor = pred_mass / 100.0

            result = {
                "mass_g": pred_mass,
                "calories": base_per_100g["calories"] * scale_factor,
                "protein_g": base_per_100g["protein_g"] * scale_factor,
                "carbs_g": base_per_100g["carbs_g"] * scale_factor,
                "fat_g": base_per_100g["fat_g"] * scale_factor,
            }
            print(f"[ALIGN] Mass-based scaling: {pred_mass}g → {result['calories']:.1f}kcal")
            return result

        print("[ALIGN] ERROR: No mass or calories to scale by")
        return {"mass_g": 0, "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}

    def align_predicted_food(self, food_name: str, predicted_food: Dict[str, Any], telemetry: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        Align a single predicted food to database.

        NEW: Attempts raw→cooked conversion for cooked foods before falling
        back to legacy search.

        Args:
            food_name: Food name
            predicted_food: Dict with mass_g, calories, form (optional),
                           and optionally kcal_per_100g_est

        Returns:
            Alignment dict or None
        """
        # Fix 5.5: Mass soft clamps (apply early before alignment)
        # Normalize core_class from food_name for mass rail lookup
        from .fdc_taxonomy import extract_features
        features = extract_features(food_name)
        core_class = (features.get("core") or "").replace(" ", "_") if features else ""

        pred_mass = predicted_food.get("mass_g")
        pred_confidence = predicted_food.get("confidence", 0.8)

        if pred_mass and CONVERSION_AVAILABLE:
            clamped_mass, was_clamped, clamp_reason = apply_mass_soft_clamp(
                core_class, pred_mass, pred_confidence
            )

            if was_clamped:
                # Apply mass adjustment
                predicted_food["mass_g"] = clamped_mass
                if telemetry is not None:
                    telemetry["mass_clamps_applied"] = telemetry.get("mass_clamps_applied", 0) + 1
                print(f"[ALIGN] {clamp_reason}")

        # Extract energy density estimate and form
        predicted_kcal_100g = predicted_food.get("kcal_per_100g_est")
        predicted_form = predicted_food.get("form", "")

        # Check if this is a cooked food and conversion is enabled
        is_cooked = any(keyword in predicted_form.lower() for keyword in
                       ("cooked", "grilled", "fried", "roasted", "boiled", "steamed", "baked", "pan_seared"))

        if is_cooked and self.conversion_enabled and predicted_kcal_100g:
            print(f"[ALIGN] Attempting 4-stage alignment with conversion for '{food_name}' ({predicted_form})")

            try:
                # Get FDC candidates for conversion system (with quality filters)
                candidates = self._get_fdc_candidates_for_conversion(food_name, telemetry=telemetry)

                if candidates:
                    # Use 4-stage alignment with conversion
                    alignment_result = self.conversion_engine.align_food_item(
                        predicted_name=food_name,
                        predicted_form=predicted_form,
                        predicted_kcal_100g=predicted_kcal_100g,
                        fdc_candidates=candidates,
                        confidence=predicted_food.get("confidence", 0.8)
                    )

                    if alignment_result.fdc_id:
                        # Successful alignment via conversion system
                        print(f"[ALIGN] ✓ Conversion alignment: {alignment_result.alignment_stage} "
                              f"(FDC {alignment_result.fdc_id})")

                        # Scale nutrition to predicted mass/calories
                        base_nutrition = {
                            "calories": alignment_result.kcal_100g,
                            "protein_g": alignment_result.protein_100g,
                            "carbs_g": alignment_result.carbs_100g,
                            "fat_g": alignment_result.fat_100g
                        }

                        nutrition = self.compute_nutrition(base_nutrition, predicted_food)

                        return {
                            "fdc_id": alignment_result.fdc_id,
                            "matched_name": alignment_result.name,
                            "data_type": alignment_result.source,
                            "confidence": alignment_result.confidence,
                            "score": alignment_result.match_score,
                            "nutrition": nutrition,
                            "provenance": {
                                "alignment_stage": alignment_result.alignment_stage,
                                "method": alignment_result.method,
                                "method_reason": alignment_result.method_reason,
                                "conversion_applied": alignment_result.conversion_applied,
                                **alignment_result.telemetry
                            }
                        }

            except Exception as e:
                print(f"[ALIGN] WARNING: Conversion alignment failed: {e}, falling back to legacy search")
                import traceback
                traceback.print_exc()

        # Fallback to legacy search (original V2 logic)
        print(f"[ALIGN] Using legacy search for '{food_name}'")
        match = self.search_best_match(food_name, predicted_kcal_100g=predicted_kcal_100g, telemetry=telemetry)
        if not match:
            return None

        nutrition = self.compute_nutrition(
            match["base_nutrition_per_100g"],
            predicted_food
        )

        return {
            "fdc_id": match["fdc_id"],
            "matched_name": match["name"],
            "data_type": match["data_type"],
            "confidence": match["confidence"],
            "score": match["score"],
            "nutrition": nutrition,
            "provenance": match["base_nutrition_per_100g"].get("provenance", {})
        }

    def _get_fdc_candidates_for_conversion(self, food_name: str, limit: int = 50, telemetry: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Get FDC candidates for conversion system (Foundation, Legacy, Branded).

        NEW: Applies same quality filters as legacy search to ensure clean candidates.

        Args:
            food_name: Food name to search
            limit: Max candidates per data type
            telemetry: Optional telemetry dict for rejection tracking

        Returns:
            List of FDC candidate dicts (filtered for quality)
        """
        # Extract features for filtering
        features = extract_features(food_name)

        candidates = []
        seen_ids = set()

        try:
            with FDCDatabase(self.connection_url) as db:
                # Search Foundation foods
                for data_type in ["foundation_food", "sr_legacy_food", "branded_food"]:
                    results = db.search_foods(
                        query=food_name,
                        limit=limit,
                        data_types=[data_type]
                    )

                    for r in results:
                        if r["fdc_id"] in seen_ids:
                            continue

                        # NEW: Apply quality filters (same as search_best_match)

                        # Processing-mismatch guard
                        if PROCESSING_BAD.search(r["name"]):
                            if not any(kw in food_name.lower() for kw in ["breaded", "battered", "nugget", "tender", "fried"]):
                                if telemetry is not None:
                                    telemetry["processing_mismatch_blocks"] += 1
                                continue

                        # Class-specific negative vocabulary
                        if features["core"] in CLASS_DISALLOWED_ALIASES:
                            disallowed = CLASS_DISALLOWED_ALIASES[features["core"]]
                            candidate_lower = r["name"].lower()
                            if any(bad_word in candidate_lower for bad_word in disallowed):
                                if telemetry is not None:
                                    telemetry["negative_vocabulary_blocks"] += 1
                                continue

                        # NEW: Whole-food ingredient-form ban
                        if features["core"] in WHOLE_FOOD_CLASSES:
                            if WHOLE_FOOD_INGREDIENT_BAN.search(r["name"]):
                                if telemetry is not None:
                                    telemetry["ingredient_form_bans"] = telemetry.get("ingredient_form_bans", 0) + 1
                                continue

                        # NEW: Branded cooked method match requirement
                        if data_type == "branded_food":
                            cand_name_lower = r["name"].lower()
                            cand_method_match = COOKED_METHOD_TOKENS.search(cand_name_lower)

                            if cand_method_match:
                                # Extract method from candidate name
                                cand_method = cand_method_match.group(0)

                                # Check if prediction form matches
                                pred_form = food_name.lower()
                                pred_method_match = COOKED_METHOD_TOKENS.search(pred_form)

                                if pred_method_match:
                                    # Both have methods - check if compatible
                                    from ..nutrition.utils.method_resolver import canonical_form
                                    cand_canonical = canonical_form(cand_method)
                                    pred_canonical = canonical_form(pred_method_match.group(0))

                                    # Reject if methods don't match
                                    if pred_canonical != cand_canonical:
                                        if telemetry is not None:
                                            telemetry["branded_cooked_method_mismatch_rejects"] = telemetry.get("branded_cooked_method_mismatch_rejects", 0) + 1
                                        continue
                                else:
                                    # Prediction has no cooked method but candidate does - reject
                                    if telemetry is not None:
                                        telemetry["branded_cooked_method_mismatch_rejects"] = telemetry.get("branded_cooked_method_mismatch_rejects", 0) + 1
                                    continue

                        # Add to candidates (macro plausibility check happens later in alignment stages)
                        seen_ids.add(r["fdc_id"])
                        candidates.append(r)

        except Exception as e:
            print(f"[ALIGN] ERROR: Failed to get FDC candidates: {e}")

        return candidates

    def align_prediction_batch(self, prediction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Align all foods in a prediction.

        Args:
            prediction: Prediction dict with "foods" list

        Returns:
            Dict with alignments and totals
        """
        print(f"[ALIGN] ===== Starting batch alignment (V2) =====")
        print(f"[ALIGN] DB Available: {self.db_available}")

        if not self.db_available:
            print("[ALIGN] Database not available")
            return {
                "available": False,
                "foods": [],
                "totals": {"mass_g": 0, "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
            }

        foods = prediction.get("foods", [])
        print(f"[ALIGN] Processing {len(foods)} foods")

        aligned_foods = []
        totals = {"mass_g": 0, "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}

        # NEW: Conversion telemetry tracking
        telemetry = {
            "total_items": len(foods),
            "alignment_stages": {},
            "method_resolution": {},
            "conversion_applied_count": 0,
            "energy_band_outliers": 0,
            "mass_inflation_guards": 0,
            "kcal_deltas": [],  # Track pre→post kcal/100g changes
            # NEW: Rejection tracking
            "processing_mismatch_blocks": 0,
            "negative_vocabulary_blocks": 0,
            "macro_plausibility_blocks": 0,
            "species_mismatch_blocks": 0,  # NEW: bacon→meatless, chicken→plant-based
            "branded_gate_rejects": 0,  # NEW: Stage 4 strict gates
            "why_not_chosen": [],  # NEW: Top rejected candidates with reasons
            # NEW: Guardrails V2 telemetry
            "produce_raw_first_penalties": 0,
            "ingredient_form_bans": 0,
            "branded_last_resort_used": 0,
            "branded_cooked_method_mismatch_rejects": 0,
        }

        for i, food in enumerate(foods):
            name = food.get("name", "")
            if not name:
                print(f"[ALIGN] Food {i+1}: skipped (no name)")
                continue

            print(f"[ALIGN] Food {i+1}: '{name}'")

            # Build predicted_food dict for scaling (include energy density and form)
            predicted_food = {
                "mass_g": food.get("mass_g"),
                "calories": food.get("calories"),
                "kcal_per_100g_est": food.get("kcal_per_100g_est"),
                "form": food.get("form", ""),  # CRITICAL: Include form for conversion system
                "confidence": food.get("confidence", 0.8)
            }

            # Skip if no mass (calories are optional with mass-only vision mode)
            if not predicted_food["mass_g"]:
                print(f"[ALIGN] Food {i+1}: skipped (no mass)")
                continue

            alignment = self.align_predicted_food(name, predicted_food, telemetry=telemetry)

            if alignment:
                aligned_foods.append({
                    "predicted_name": name,
                    "fdc_id": alignment["fdc_id"],
                    "matched_name": alignment["matched_name"],
                    "data_type": alignment["data_type"],
                    "confidence": alignment["confidence"],
                    "score": alignment["score"],
                    "nutrition": alignment["nutrition"],
                    "provenance": alignment.get("provenance", {})
                })

                # Add to totals
                for key in totals:
                    totals[key] += alignment["nutrition"][key]

                # NEW: Collect telemetry from provenance
                prov = alignment.get("provenance", {})

                # Track alignment stage
                stage = prov.get("alignment_stage", "unknown")
                telemetry["alignment_stages"][stage] = telemetry["alignment_stages"].get(stage, 0) + 1

                # Track method resolution
                method_reason = prov.get("method_reason", "unknown")
                telemetry["method_resolution"][method_reason] = telemetry["method_resolution"].get(method_reason, 0) + 1

                # Track conversion applied
                if prov.get("conversion_applied", False):
                    telemetry["conversion_applied_count"] += 1

                # Track energy band outliers
                if prov.get("energy_band_outlier", False):
                    telemetry["energy_band_outliers"] += 1

                print(f"[ALIGN] Food {i+1}: aligned successfully")
            else:
                print(f"[ALIGN] Food {i+1}: failed to align")

        print(f"[ALIGN] Batch complete: {len(aligned_foods)}/{len(foods)} aligned")
        print(f"[ALIGN] Totals: {totals['mass_g']:.1f}g, {totals['calories']:.1f} kcal")

        # NEW: Calculate telemetry percentages
        if len(aligned_foods) > 0:
            telemetry["conversion_hit_rate"] = telemetry["conversion_applied_count"] / len(aligned_foods)
            telemetry["energy_band_outlier_rate"] = telemetry["energy_band_outliers"] / len(aligned_foods)

            print(f"\n[ALIGN] ===== CONVERSION TELEMETRY =====")
            print(f"[ALIGN] Conversion hit rate: {telemetry['conversion_hit_rate']:.1%} ({telemetry['conversion_applied_count']}/{len(aligned_foods)})")
            print(f"[ALIGN] Alignment stages: {telemetry['alignment_stages']}")
            print(f"[ALIGN] Method resolution: {telemetry['method_resolution']}")
            print(f"[ALIGN] Energy band outliers: {telemetry['energy_band_outliers']} ({telemetry['energy_band_outlier_rate']:.1%})")
            print(f"\n[ALIGN] ===== QUALITY FILTERS =====")
            print(f"[ALIGN] Processing mismatch blocks: {telemetry['processing_mismatch_blocks']}")
            print(f"[ALIGN] Species mismatch blocks: {telemetry['species_mismatch_blocks']}")  # NEW
            print(f"[ALIGN] Negative vocabulary blocks: {telemetry['negative_vocabulary_blocks']}")
            print(f"[ALIGN] Macro plausibility blocks: {telemetry['macro_plausibility_blocks']}")
            print(f"[ALIGN] Branded gate rejects: {telemetry['branded_gate_rejects']}")  # NEW
            print(f"[ALIGN] Total why_not_chosen entries: {len(telemetry['why_not_chosen'])}")  # NEW
            print(f"\n[ALIGN] ===== GUARDRAILS V2 =====")
            print(f"[ALIGN] Produce raw-first penalties: {telemetry['produce_raw_first_penalties']}")
            print(f"[ALIGN] Ingredient-form bans: {telemetry['ingredient_form_bans']}")
            print(f"[ALIGN] Branded last-resort used: {telemetry['branded_last_resort_used']}")
            print(f"[ALIGN] Branded cooked method mismatch rejects: {telemetry['branded_cooked_method_mismatch_rejects']}")
            print(f"[ALIGN] ===================================\n")

        return {
            "available": True,
            "foods": aligned_foods,
            "totals": totals,
            "telemetry": telemetry  # NEW: Include telemetry in results
        }
