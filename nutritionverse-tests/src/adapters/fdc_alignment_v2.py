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
from typing import Dict, List, Optional, Any, Tuple
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

    # Eggs - Substitution variants + Part disambiguation (NEW: Fix #2)
    "egg": ["substitute", "imitation", "powder", "just egg", "vegan", "egg beaters"],
    "egg_whole": ["white", "whites", "yolk only"],  # Reject parts when whole intended
    "egg_white": ["yolk", "yolks", "whole egg", "beaten egg", "whites of eggs"],  # CRITICAL: Reject yolk when whites intended
    "egg_yolk": ["white", "whites", "egg white"],  # Reject whites when yolk intended
    "egg_scrambled": ["yolk only", "yolk"],  # NEW: Ban yolk for scrambled unless explicit
    "egg_omelet": ["yolk only", "yolk"],  # NEW: Ban yolk for omelet unless explicit

    # Starches - Form variants
    "potato_russet": ["flour", "starch", "powder", "mix", "dough", "dehydrated", "granules", "instant"],
    "rice_white": ["flour", "starch", "powder", "bran", "polish"],
    "rice_brown": ["flour", "starch", "powder", "bran"],
    "couscous": ["mix", "seasoned", "flavored"],

    # Vegetables/Legumes - Processed variants
    "peas": ["snack", "crisps", "chips", "puffs", "wasabi"],

    # Pumpkin/Squash - Two-way guard: prevent seeds/pie + require flesh keywords (NEW Phase 1)
    "pumpkin": ["seeds", "pepitas", "pie", "pie filling", "roasted seeds", "seed oil", "pumpkin seed"],
    "pumpkin_sugar": ["seeds", "pepitas", "pie", "pie filling", "roasted seeds", "seed oil", "pumpkin seed"],
    "squash": ["seeds", "pie", "seed oil"],
    "squash_summer": ["seeds", "pie", "seed oil"],
    "squash_butternut": ["seeds", "pie", "seed oil"],
    "squash_kabocha": ["seeds", "pie", "seed oil"],
    "squash_acorn": ["seeds", "pie", "seed oil"],

    # Tofu - Processing variants (default ban, use positive allow-list)
    "tofu": [],  # Empty = no default bans, use CLASS_POSITIVE_ALLOWED instead
    "tofu_plain_raw": [],  # Stage 5 proxy class

    # Corn - Kernel vs processed grain products (NEW: Fix #3 - CRITICAL)
    "corn": ["flour", "meal", "grits", "polenta", "starch", "cornstarch", "corn starch", "masa"],
    "corn_kernels": ["flour", "meal", "grits", "polenta", "starch"],
    "sweet_corn": ["flour", "meal", "grits", "polenta", "starch"],

    # Fruits/Dried - Ingredient leakage
    "raisins": ["cookie", "cookies", "cake", "muffin", "bread", "cereal"],
    "oats": ["cookie", "cookies", "granola bar", "cereal bar"],

    # NEW: Sweet potato - Block leaves (tuber vs greens)
    "sweet_potato": ["leaf", "leaves", "greens", "tops"],
    "sweet_potato_tuber": ["leaf", "leaves", "greens", "tops"],

    # NEW: Rice - Block crackers and processed snacks
    "rice_white": ["cracker", "crackers", "biscuit", "multigrain", "gluten", "gluten-free", "snack", "chip", "chips"],
    "rice_brown": ["cracker", "crackers", "biscuit", "multigrain", "gluten", "gluten-free", "snack", "chip", "chips"],
    "rice": ["cracker", "crackers", "biscuit", "multigrain", "gluten", "gluten-free", "snack", "chip", "chips"],

    # NEW: Fruit/Nut processing variants (whole food vs processed)
    "grape": ["juice", "concentrate", "raisin", "raisins", "jelly", "jam"],
    "apple": ["juice", "sauce", "butter", "pie"],
    "strawberry": ["jam", "jelly", "preserves"],
    "blueberry": ["jam", "jelly", "preserves"],
    "raspberry": ["jam", "jelly", "preserves"],
    "blackberry": ["jam", "jelly", "preserves"],
    "almond": ["milk", "flour", "butter"],
}

# NEW: Positive allow-list (Phase 1) - Required keywords for drift-prone classes
CLASS_POSITIVE_ALLOWED = {
    "tofu": ["fried", "stir-fried", "pan-fried", "deep-fried", "crispy", "air-fried"],
    "tofu_plain_raw": ["raw", "plain", "firm", "extra-firm", "soft", "silken", "regular"],
}

# NEW: Pumpkin flesh guard - Require flesh/cubed/diced for pumpkin classes (Phase 1)
PUMPKIN_FLESH_REQUIRED = {
    "pumpkin": ["flesh", "cubed", "diced", "cooked", "mashed", "puree", "raw"],
    "pumpkin_sugar": ["flesh", "cubed", "diced", "cooked", "mashed", "puree", "raw"],
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
    "zucchini", "squash_summer", "squash_yellow", "squash_butternut", "squash_kabocha",
    "squash_acorn", "pumpkin_sugar", "bok_choy", "brussels_sprouts", "cabbage",
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

# NEW: Color/species token extraction
COLOR_TOKENS = {
    "red", "green", "yellow", "orange", "purple", "white", "black",
    "brown", "pink"
}

SPECIES_TOKENS = {
    "pork", "turkey", "chicken", "beef", "wild", "farmed", "atlantic",
    "pacific", "king", "coho", "sockeye"
}

# NEW: Class name mapping for alignment hints (mass-only mode)
CLASS_NAME_PATTERNS = {
    # Produce with color variants
    r"(bell[- ])?pepper.*green": "bell_pepper_green",
    r"(bell[- ])?pepper.*red": "bell_pepper_red",
    r"(bell[- ])?pepper.*yellow": "bell_pepper_yellow",
    r"(bell[- ])?pepper": "bell_pepper",
    r"onion.*red": "red_onion",
    r"onion": "onion",
    r"tomato.*cherry": "cherry_tomatoes",
    r"tomato.*grape": "grape_tomatoes",
    r"tomato.*plum": "plum_tomatoes",
    r"tomato": "tomato",

    # Leafy greens and salad mixes (NEW)
    r"mixed.*salad.*green": "lettuce",
    r"spring.*mix": "lettuce",
    r"salad.*mix": "lettuce",
    r"green.*salad.*mix": "lettuce",
    r"greens.*mix": "lettuce",
    r"lettuce": "lettuce",

    # Carrot variants (NEW)
    r"(shredded|grated)\s+carrot": "carrot",
    r"carrot": "carrot",

    # Pumpkin and squash variants (NEW - expanded to avoid seeds)
    r"butternut.*squash": "squash_butternut",
    r"sugar.*pumpkin": "pumpkin_sugar",
    r"kabocha": "squash_kabocha",
    r"pumpkin.*flesh": "pumpkin_sugar",
    r"pumpkin": "pumpkin_sugar",
    r"squash": "squash_yellow",

    # Rice variants
    r"rice.*brown": "rice_brown",
    r"rice.*white": "rice_white",
    r"rice": "rice_white",  # default

    # Potato variants
    r"potato.*sweet": "sweet_potato",
    r"potato.*russet": "potato_russet",
    r"potato.*red": "potato_red",
    r"potato": "potato_russet",  # default

    # Meats with species
    r"bacon.*pork": "bacon_pork",
    r"bacon.*turkey": "bacon_turkey",
    r"bacon": "bacon_pork",  # default
    r"chicken.*breast": "chicken_breast",
    r"chicken.*thigh": "chicken_thigh",
    r"chicken": "chicken_breast",  # default
    r"beef.*steak": "beef_steak",
    r"beef.*ground": "beef_ground_85",
    r"beef": "beef_steak",  # default
    r"salmon": "salmon_fillet",
    r"cod": "white_fish_cod",
    r"tuna": "tuna_steak",
}

# NEW: Default forms by food category (for mass-only mode when form missing)
CATEGORY_DEFAULT_FORMS = {
    # Produce → raw
    "produce": "raw",
    # Grains/pasta → boiled (if mass > 40g and count is 0)
    "grain": "boiled",
    # Meats → cooked (generic)
    "meat": "cooked",
    # Eggs → cooked
    "egg": "cooked",
    # Dairy → raw (unprocessed)
    "dairy": "raw",
}

# NEW: Plausibility bands - kcal/100g ranges by category (Fix #6)
# Used to catch extreme misalignments (egg whites→yolk, corn→flour)
PLAUSIBILITY_BANDS = {
    # Produce
    "leafy_greens": (10, 30),
    "lettuce": (10, 20),
    "spinach": (15, 30),
    "kale": (25, 50),

    # Vegetables
    "bell_pepper": (20, 45),
    "tomato": (15, 25),
    "cucumber": (10, 20),
    "carrot": (30, 50),
    "broccoli": (25, 45),
    "cauliflower": (20, 35),
    "onion": (30, 50),
    "zucchini": (15, 25),

    # Fruits
    "apple": (40, 65),
    "banana": (80, 110),
    "berries": (30, 80),
    "watermelon": (25, 40),

    # Corn products (CRITICAL for Fix #3)
    "corn_kernels": (70, 110),  # Sweet corn kernels
    "corn_flour": (330, 380),    # Milled corn products
    "corn_meal": (330, 380),

    # Starchy vegetables
    "potato_raw": (60, 90),
    "potato_boiled": (75, 105),
    "potato_roasted": (90, 130),
    "potato_fried": (150, 280),  # Hash browns, fries
    "sweet_potato": (75, 110),

    # Grains
    "rice_raw": (330, 380),
    "rice_cooked": (110, 145),
    "pasta_raw": (330, 380),
    "pasta_cooked": (130, 165),
    "oats_raw": (350, 400),
    "oats_cooked": (60, 80),

    # Eggs (CRITICAL for Fix #2)
    "egg_whole_raw": (130, 160),
    "egg_white_raw": (40, 60),   # Whites
    "egg_yolk_raw": (300, 360),  # Yolk
    "egg_cooked": (140, 180),

    # Meats (raw)
    "chicken_breast": (100, 130),
    "chicken_thigh": (170, 210),
    "beef_steak": (170, 260),
    "pork_chop": (130, 200),
    "salmon": (180, 230),
    "white_fish": (70, 110),

    # Dairy
    "milk": (40, 70),
    "cheese_hard": (350, 420),
    "yogurt": (50, 110),

    # Flours and dry grains
    "flour_wheat": (330, 380),
    "flour_all": (330, 380),
}

# NEW: Sodium gating for pickled/fermented items
# Minimum sodium (mg/100g) required to accept pickled/fermented foods
# Used to prevent raw vegetables being misaligned as pickled variants
SODIUM_GATE_ITEMS = {
    "pickles": {"min_sodium_mg_per_100g": 600, "keywords": ["pickle", "pickled", "gherkin", "dill"]},
    "olives": {"min_sodium_mg_per_100g": 600, "keywords": ["olive", "olives", "kalamata", "black olive", "green olive"]},
    "capers": {"min_sodium_mg_per_100g": 1500, "keywords": ["caper", "capers"]},
    "kimchi": {"min_sodium_mg_per_100g": 500, "keywords": ["kimchi"]},
    "sauerkraut": {"min_sodium_mg_per_100g": 500, "keywords": ["sauerkraut", "kraut"]},
    "fermented": {"min_sodium_mg_per_100g": 400, "keywords": ["fermented", "pickled"]},
}

# NEW: Category classification for default form inference
FOOD_CATEGORIES = {
    # Produce
    "apple": "produce", "banana": "produce", "tomato": "produce",
    "bell_pepper": "produce", "bell_pepper_green": "produce", "bell_pepper_red": "produce",
    "bell_pepper_yellow": "produce", "onion": "produce", "red_onion": "produce",
    "carrot": "produce", "broccoli": "produce", "cauliflower": "produce",
    "spinach": "produce", "lettuce": "produce", "cucumber": "produce",
    "zucchini": "produce", "eggplant": "produce", "squash": "produce",
    "squash_yellow": "produce", "squash_butternut": "produce", "squash_kabocha": "produce",
    "pumpkin_sugar": "produce", "asparagus": "produce",

    # Grains/starches
    "rice_white": "grain", "rice_brown": "grain", "pasta_wheat": "grain",
    "couscous": "grain", "quinoa": "grain", "oats": "grain",
    "potato_russet": "grain", "sweet_potato": "grain",

    # Meats
    "chicken_breast": "meat", "chicken_thigh": "meat",
    "beef_steak": "meat", "beef_ground_85": "meat",
    "pork_chop": "meat", "bacon_pork": "meat", "bacon_turkey": "meat",
    "salmon_fillet": "meat", "white_fish_cod": "meat", "tuna_steak": "meat",

    # Eggs
    "egg_whole": "egg", "egg_white": "egg", "egg": "egg",

    # Dairy
    "milk": "dairy", "cheese": "dairy", "yogurt": "dairy", "cream_cheese": "dairy",
}


def derive_alignment_hints(pred_item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive alignment hints from sparse vision output (mass-only mode).

    Compensates for lost calories/macros signal by extracting metadata
    from available fields: name, modifiers, form, mass_g, count.

    Extracts:
    - class_from_name: canonical class from name + modifiers
    - implied_form: default form if missing (produce→raw, grains→boiled, meats→cooked)
    - color_tokens: color adjectives for produce scoring
    - species_tokens: species identifiers for meat scoring
    - discrete_hint: mass_per_unit for discrete items (eggs, nuts, strips)

    Args:
        pred_item: Prediction item dict with {name, form?, mass_g, count?, modifiers?}

    Returns:
        Hints dict with derived metadata (does NOT modify pred_item)
    """
    name = pred_item.get("name", "").lower().strip()
    form = pred_item.get("form", "").lower().strip()
    mass_g = pred_item.get("mass_g", 0)
    count = pred_item.get("count")
    modifiers = pred_item.get("modifiers", [])  # NEW: optional list from vision

    hints = {
        "class_from_name": None,
        "implied_form": None,
        "color_tokens": set(),
        "species_tokens": set(),
        "discrete_hint": None,
    }

    # Combine name + modifiers for full search string
    search_str = name
    if modifiers:
        search_str = f"{name} {' '.join(modifiers)}"

    # Extract class_from_name using pattern matching
    for pattern, class_name in CLASS_NAME_PATTERNS.items():
        if re.search(pattern, search_str, re.I):
            hints["class_from_name"] = class_name
            break

    # Fallback: use first word as class if no pattern matched
    if not hints["class_from_name"]:
        first_word = name.split()[0] if name else ""
        hints["class_from_name"] = first_word.replace(" ", "_")

    # Extract color tokens
    for word in search_str.split():
        if word.lower() in COLOR_TOKENS:
            hints["color_tokens"].add(word.lower())

    # Extract species tokens
    for word in search_str.split():
        if word.lower() in SPECIES_TOKENS:
            hints["species_tokens"].add(word.lower())

    # Infer form if missing
    if not form or form == "cooked":  # Generic "cooked" is weak signal
        core_class = hints["class_from_name"]
        category = FOOD_CATEGORIES.get(core_class, None)

        if category == "produce":
            hints["implied_form"] = "raw"
        elif category == "grain":
            # Boiled if bulk (count=0 or None, mass>40g)
            if (count is None or count == 0) and mass_g > 40:
                hints["implied_form"] = "boiled"
            else:
                hints["implied_form"] = "raw"
        elif category in ("meat", "egg"):
            hints["implied_form"] = "cooked"  # Generic cooked (will be refined by method_resolver)
        elif category == "dairy":
            hints["implied_form"] = "raw"
        else:
            hints["implied_form"] = "raw"  # Conservative default
    else:
        # Form exists and is specific
        hints["implied_form"] = form

    # Discrete hint: compute mass_per_unit for count-based items
    if count and count > 0 and mass_g > 0:
        hints["discrete_hint"] = {
            "mass_per_unit": mass_g / count,
            "count": count
        }

    return hints


def detect_salad_context(all_food_items: List[Dict[str, Any]]) -> bool:
    """
    Detect if food items form a salad context (Fix #4).

    Salad indicators:
    - Presence of dressing, parmesan, cheese, croutons
    - Leafy tokens: lettuce, greens, mix, spinach, arugula
    - Multiple produce items together

    Args:
        all_food_items: List of predicted food items from vision

    Returns:
        True if salad context detected
    """
    salad_toppings = {"parmesan", "cheese", "dressing", "croutons", "crouton",
                      "vinaigrette", "ranch", "caesar", "italian dressing"}

    leafy_tokens = {"lettuce", "greens", "mix", "salad", "spinach", "arugula",
                    "kale", "spring mix", "mixed greens"}

    # Check for toppings
    has_topping = False
    has_leafy = False

    for item in all_food_items:
        name = item.get("name", "").lower()
        modifiers = item.get("modifiers", [])
        search_str = f"{name} {' '.join(modifiers)}".lower()

        if any(topping in search_str for topping in salad_toppings):
            has_topping = True

        if any(leafy in search_str for leafy in leafy_tokens):
            has_leafy = True

    # Salad context = has toppings + leafy tokens mentioned somewhere
    return has_topping and has_leafy


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


def check_plausibility_band(
    food_class: str,
    kcal_100g: float,
    hints: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Check if kcal/100g falls within plausibility band for food class (Fix #6).

    Catches extreme misalignments like:
    - Egg whites → yolk (52 vs 334 kcal/100g)
    - Corn kernels → flour (86 vs 364 kcal/100g)

    Args:
        food_class: Normalized food class (e.g., "chicken_breast", "corn", "egg")
        kcal_100g: Calories per 100g from FDC candidate
        hints: Alignment hints with class_from_name

    Returns:
        (is_plausible, violation_reason) tuple
    """
    # Determine which band to check
    band_key = None

    # Use hints if available for more specific matching
    if hints and hints.get("class_from_name"):
        class_hint = hints["class_from_name"]

        # Egg part-specific bands
        if "egg" in class_hint:
            if "white" in class_hint:
                band_key = "egg_white_raw"
            elif "yolk" in class_hint:
                band_key = "egg_yolk_raw"
            else:
                band_key = "egg_whole_raw"

        # Corn product-specific bands
        elif "corn" in class_hint:
            if any(kw in class_hint for kw in ["flour", "meal", "grits"]):
                band_key = "corn_flour"
            else:
                band_key = "corn_kernels"

        # Potato form-specific bands
        elif "potato" in class_hint:
            # Check form to determine band
            if hints.get("implied_form") == "raw":
                band_key = "potato_raw"
            else:
                band_key = "potato_boiled"  # Generic cooked

        # Generic class lookup
        else:
            band_key = class_hint

    # Fallback to direct food_class lookup
    if not band_key:
        band_key = food_class

    # Lookup band
    band = PLAUSIBILITY_BANDS.get(band_key)
    if not band:
        # No band defined - allow (don't block)
        return (True, None)

    min_kcal, max_kcal = band

    # Check if within band (with 20% tolerance)
    tolerance = 0.20
    if kcal_100g < min_kcal * (1 - tolerance) or kcal_100g > max_kcal * (1 + tolerance):
        reason = f"plausibility_violation_{band_key}_{int(kcal_100g)}kcal_outside_{min_kcal}-{max_kcal}"
        return (False, reason)

    return (True, None)


def check_sodium_gate(
    food_name: str,
    candidate_name: str,
    sodium_mg_per_100g: float
) -> Tuple[bool, Optional[str]]:
    """
    Check if candidate passes sodium gate for pickled/fermented items.

    Prevents raw vegetables from being misaligned as pickled variants.
    For example:
    - "olives" should have ≥600mg sodium/100g (prevent raw olive fruit match)
    - "pickles" should have ≥600mg sodium/100g (prevent fresh cucumber match)

    Args:
        food_name: User's food name (e.g., "olives", "pickles")
        candidate_name: FDC candidate name
        sodium_mg_per_100g: Sodium content from FDC entry

    Returns:
        (passes_gate, reason) tuple:
            - (True, None) if no gate applies or sodium sufficient
            - (False, reason) if gate applies but sodium too low
    """
    food_lower = food_name.lower().strip()
    cand_lower = candidate_name.lower().strip()

    # Check if any sodium gate items apply
    for gate_category, gate_config in SODIUM_GATE_ITEMS.items():
        keywords = gate_config["keywords"]
        min_sodium = gate_config["min_sodium_mg_per_100g"]

        # Check if food name contains any keywords
        food_matches = any(kw in food_lower for kw in keywords)
        # Also check candidate name for pickled indicators
        cand_matches = any(kw in cand_lower for kw in keywords)

        if food_matches or cand_matches:
            # Gate applies - check sodium level
            if sodium_mg_per_100g < min_sodium:
                reason = f"sodium_gate_fail_{gate_category}_{int(sodium_mg_per_100g)}mg_below_{min_sodium}mg"
                return (False, reason)
            else:
                # Sodium sufficient - gate passed
                return (True, f"sodium_gate_pass_{gate_category}_{int(sodium_mg_per_100g)}mg")

    # No gate applies
    return (True, None)


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

    def _try_curated_branded_fallback(self, food_name: str, features: Dict[str, str],
                                       hints: Optional[Dict[str, Any]] = None,
                                       telemetry: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        Curated branded fallback - last resort after foundation/legacy fails.

        Searches branded items with strict quality gates:
        - Single-ingredient only (≤2 ingredients: food + water/salt)
        - Fresh produce OR raw meats/eggs
        - Sodium < 30mg per 100g for produce
        - Macro plausibility gates

        Args:
            food_name: Original food name
            features: Extracted features dict
            hints: Alignment hints from derive_alignment_hints()
            telemetry: Telemetry dict

        Returns:
            Best match dict or None
        """
        from src.config.feature_flags import FLAGS

        if not FLAGS.mass_brand_last_resort:
            return None

        print(f"[ALIGN] Trying curated branded fallback for '{food_name}'")

        # Only allow for specific safe categories
        core_class = hints.get("class_from_name") if hints else features.get("core")
        if not core_class:
            return None

        # Check if food is in safe categories (produce, raw meats, eggs)
        is_produce = core_class in PRODUCE_CLASSES
        is_meat = core_class in {"chicken_breast", "chicken_thigh", "beef_steak", "salmon_fillet",
                                 "white_fish_cod", "tuna_steak", "pork_chop"}
        is_egg = "egg" in core_class.lower()

        if not (is_produce or is_meat or is_egg):
            print(f"[ALIGN] Skipping branded fallback: '{core_class}' not in safe categories")
            return None

        # Search branded items
        candidates = []
        seen_ids = set()

        try:
            with FDCDatabase(self.connection_url) as db:
                queries = [features.get("core"), food_name]

                for query in queries:
                    if not query:
                        continue

                    results = db.search_foods(
                        query=query,
                        limit=15,
                        data_types=["branded_food"]
                    )

                    for r in results:
                        fdc_id = r["fdc_id"]
                        if fdc_id in seen_ids:
                            continue
                        seen_ids.add(fdc_id)

                        # Gate 1: Class match
                        if features["core"] and not is_class_match(r["name"], features["core"]):
                            continue

                        # Gate 2: Ingredient count (single-ingredient check)
                        ingredients = r.get("ingredients")
                        if ingredients and len(ingredients) > 2:
                            # Check if extra ingredients are just water/salt
                            normalized = [ing.lower().strip() for ing in ingredients]
                            acceptable = {"water", "salt", "sea salt"}
                            extra = [ing for ing in normalized if ing not in acceptable]
                            if len(extra) > 1:
                                continue

                        # Gate 3: Sodium check for produce
                        if is_produce:
                            sodium_mg = r.get("sodium_mg_100g", 0)
                            if sodium_mg and sodium_mg > 30.0:
                                continue

                        # Gate 4: Macro plausibility (use existing logic)
                        kcal = r.get("kcal_100g", 0)
                        protein = r.get("protein_100g", 0)
                        carbs = r.get("carbs_100g", 0)
                        fat = r.get("fat_100g", 0)

                        # Simple plausibility checks
                        if is_produce:
                            # Produce: low cal, low protein, low fat
                            if kcal > 100 or protein > 3 or fat > 2:
                                continue
                        elif is_meat:
                            # Meat: high protein, low carbs
                            if protein < 15 or carbs > 5:
                                continue

                        # Score the candidate (simple scoring for branded)
                        score = self._score_match(food_name, r, features)

                        # Apply negative vocabulary filter
                        if features["core"] in CLASS_DISALLOWED_ALIASES:
                            banned = CLASS_DISALLOWED_ALIASES[features["core"]]
                            if any(term in r["name"].lower() for term in banned):
                                continue

                        candidates.append({
                            "fdc_id": fdc_id,
                            "name": r["name"],
                            "data_type": r.get("data_type", "branded_food"),
                            "score": score,
                            "record": r
                        })

        except Exception as e:
            print(f"[ALIGN] ERROR: Branded fallback search failed: {e}")
            return None

        if not candidates:
            print(f"[ALIGN] No valid branded candidates found")
            return None

        # Sort and return best
        candidates.sort(key=lambda x: x["score"], reverse=True)
        best = candidates[0]

        # Require minimum score
        if best["score"] < 2.0:
            print(f"[ALIGN] Best branded candidate score too low: {best['score']:.2f}")
            return None

        print(f"[ALIGN] BRANDED FALLBACK: {best['name']} (score: {best['score']:.2f})")

        if telemetry is not None:
            telemetry["branded_last_resort_count"] = telemetry.get("branded_last_resort_count", 0) + 1

        # Extract nutrition using existing function
        nutrition = extract_base_nutrition(best["record"])
        if not nutrition:
            return None

        return {
            "fdc_id": best["fdc_id"],
            "name": best["name"],
            "data_type": best["data_type"],
            "score": best["score"],
            "confidence": 0.50,  # Lower confidence for branded fallback
            "kcal_100g": nutrition["kcal_100g"],
            "protein_g": nutrition["protein_g"],
            "carbs_g": nutrition["carbs_g"],
            "fat_g": nutrition["fat_g"],
            "provenance": f"branded_fallback_{nutrition['provenance']}",
        }

    def search_best_match(self, food_name: str, data_types: List[str] = None,
                          predicted_kcal_100g: float = None, telemetry: Optional[Dict] = None,
                          pred_item: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Search for best matching food using taxonomy and semantic scoring.
        Falls back to legacy foods if no foundation food matches are found.

        Args:
            food_name: Predicted food name
            data_types: Food data types (default: foundation_food with legacy fallback)
            predicted_kcal_100g: Model's energy density estimate for better matching
            pred_item: Full prediction item dict (for mass-only mode enrichment)

        Returns:
            Best match dict or None
        """
        print(f"[ALIGN] Searching for: '{food_name}' (pred_kcal_100g: {predicted_kcal_100g})")

        if not self.db_available:
            print("[ALIGN] Database not available")
            return None

        # NEW: Derive alignment hints from sparse vision output (mass-only mode)
        hints = None
        if pred_item:
            hints = derive_alignment_hints(pred_item)
            print(f"[ALIGN] Derived hints: class={hints['class_from_name']}, implied_form={hints['implied_form']}, "
                  f"colors={hints['color_tokens']}, species={hints['species_tokens']}")
            if telemetry is not None:
                telemetry["alignment_hints_derived"] = telemetry.get("alignment_hints_derived", 0) + 1

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

                        # NEW: Sodium gate for pickled/fermented items
                        # Prevent raw vegetables from being misaligned as pickled variants
                        sodium_mg_100g = r.get("sodium_mg_100g", 0.0) or 0.0
                        passes_sodium_gate, sodium_reason = check_sodium_gate(
                            food_name, r["name"], sodium_mg_100g
                        )
                        if not passes_sodium_gate:
                            print(f"[ALIGN] Rejected {r['name']}: {sodium_reason}")
                            if telemetry is not None:
                                telemetry["sodium_gate_blocks"] = telemetry.get("sodium_gate_blocks", 0) + 1
                            continue
                        elif sodium_reason:  # Gate passed with explicit reason
                            if telemetry is not None:
                                telemetry["sodium_gate_passes"] = telemetry.get("sodium_gate_passes", 0) + 1
                            print(f"[ALIGN] Sodium gate passed: {sodium_reason}")

                        # NEW: Produce raw-first scoring adjustment + color token enforcement
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

                            # Check for canned/pickled - apply -∞ reject if prediction lacks those modifiers
                            cand_is_canned_pickled = any(
                                kw in cand_name_lower
                                for kw in ["canned", "pickled", "preserved"]
                            )
                            if pred_form_raw and cand_is_canned_pickled:
                                # Hard reject - skip this candidate entirely
                                print(f"[ALIGN] Produce reject: {r['name']} (canned/pickled when pred=raw)")
                                if telemetry is not None:
                                    telemetry["produce_color_mismatch_rejects"] = telemetry.get("produce_color_mismatch_rejects", 0) + 1
                                continue  # Skip this candidate

                            # Color token enforcement for produce
                            if hints and hints["color_tokens"]:
                                # Check if candidate has conflicting color
                                cand_colors = [c for c in COLOR_TOKENS if c in cand_name_lower]
                                pred_colors = hints["color_tokens"]

                                if cand_colors and pred_colors:
                                    # Both have colors - must match
                                    if not any(pc in cand_colors for pc in pred_colors):
                                        # Color mismatch (e.g., pred=green but cand=red)
                                        print(f"[ALIGN] Produce color reject: {r['name']} has {cand_colors} but pred has {pred_colors}")
                                        if telemetry is not None:
                                            telemetry["produce_color_mismatch_rejects"] = telemetry.get("produce_color_mismatch_rejects", 0) + 1
                                        continue  # Skip this candidate

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

                        # NEW: Apply alignment hints scoring (mass-only mode enrichment)
                        if hints:
                            cand_name_lower = r["name"].lower()

                            # +0.5 if candidate class matches class_from_name
                            if hints["class_from_name"] and hints["class_from_name"] in cand_name_lower:
                                score += 0.5
                                print(f"[ALIGN] Class match bonus: {hints['class_from_name']} in {r['name']}")

                            # +1.0 if candidate matches color tokens (increased from +0.5)
                            if hints["color_tokens"]:
                                matched_colors = [c for c in hints["color_tokens"] if c in cand_name_lower]
                                if matched_colors:
                                    score += 1.0
                                    print(f"[ALIGN] Color match bonus: {matched_colors} in {r['name']}")

                            # +0.5 if candidate matches species tokens
                            if hints["species_tokens"]:
                                matched_species = [s for s in hints["species_tokens"] if s in cand_name_lower]
                                if matched_species:
                                    score += 0.5
                                    print(f"[ALIGN] Species match bonus: {matched_species} in {r['name']}")

                        # NEW: Egg part disambiguation scoring (Fix #2 - CRITICAL)
                        # Strong boost/penalty to prevent egg whites → yolk misalignment
                        if "egg" in food_name.lower():
                            cand_name_lower = r["name"].lower()
                            food_lower = food_name.lower()

                            # If prediction says "white/whites", boost white entries, penalize yolk
                            if "white" in food_lower:
                                if "egg white" in cand_name_lower or "white of egg" in cand_name_lower:
                                    score += 2.0  # Strong boost
                                    print(f"[ALIGN] Egg white match bonus: +2.0 for {r['name']}")
                                elif "yolk" in cand_name_lower:
                                    score -= 2.0  # Strong penalty
                                    print(f"[ALIGN] Egg yolk penalty: -2.0 for {r['name']} (whites intended)")

                            # If prediction says "yolk", boost yolk entries, penalize white
                            elif "yolk" in food_lower:
                                if "yolk" in cand_name_lower:
                                    score += 2.0  # Strong boost
                                    print(f"[ALIGN] Egg yolk match bonus: +2.0 for {r['name']}")
                                elif "white" in cand_name_lower:
                                    score -= 2.0  # Strong penalty
                                    print(f"[ALIGN] Egg white penalty: -2.0 for {r['name']} (yolk intended)")

                        # NEW: Corn kernel vs flour disambiguation (Fix #3 - CRITICAL)
                        # Prevent "corn" → "corn flour" misalignment (4× calorie error)
                        if "corn" in food_name.lower():
                            cand_name_lower = r["name"].lower()
                            food_lower = food_name.lower()

                            # Strong preferences based on explicit keywords
                            has_kernel_keyword = any(kw in food_lower for kw in ["kernel", "kernels", "cob", "sweet corn", "corn on"])
                            has_milled_keyword = any(kw in food_lower for kw in ["flour", "meal", "grits", "polenta", "masa", "starch"])

                            # If no milled keyword but candidate is milled → strong penalty
                            if not has_milled_keyword:
                                if any(kw in cand_name_lower for kw in ["flour", "meal", "grits", "polenta", "masa", "starch"]):
                                    score -= 1.5  # Strong penalty for milled form
                                    print(f"[ALIGN] Corn milled penalty: -1.5 for {r['name']} (kernels intended)")

                            # If kernel keyword present, boost kernel entries
                            if has_kernel_keyword:
                                if any(kw in cand_name_lower for kw in ["kernel", "kernels", "sweet", "yellow corn", "canned corn"]):
                                    score += 1.0  # Boost kernel forms
                                    print(f"[ALIGN] Corn kernel match bonus: +1.0 for {r['name']}")

                        if hints:
                            # +0.5 if candidate state matches implied_form (after normalization)
                            if hints["implied_form"]:
                                from ..nutrition.utils.method_resolver import canonical_form
                                normalized_implied = canonical_form(hints["implied_form"])

                                # Check if candidate name contains form indicators
                                cand_is_raw = any(kw in cand_name_lower for kw in ["raw", "fresh", "uncooked"])
                                cand_is_cooked = any(kw in cand_name_lower for kw in ["cooked", "boiled", "grilled", "fried", "roasted"])

                                if normalized_implied == "raw" and cand_is_raw:
                                    score += 0.5
                                    print(f"[ALIGN] Form match bonus: raw in {r['name']}")
                                elif normalized_implied != "raw" and cand_is_cooked:
                                    score += 0.5
                                    print(f"[ALIGN] Form match bonus: cooked in {r['name']}")

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

                            # NEW: Produce raw-first scoring adjustment + color enforcement (same as foundation)
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

                                # Check for canned/pickled - hard reject
                                cand_is_canned_pickled = any(
                                    kw in cand_name_lower
                                    for kw in ["canned", "pickled", "preserved"]
                                )
                                if pred_form_raw and cand_is_canned_pickled:
                                    print(f"[ALIGN] (legacy) Produce reject: {r['name']} (canned/pickled when pred=raw)")
                                    if telemetry is not None:
                                        telemetry["produce_color_mismatch_rejects"] = telemetry.get("produce_color_mismatch_rejects", 0) + 1
                                    continue  # Skip this candidate

                                # Color token enforcement
                                if hints and hints["color_tokens"]:
                                    cand_colors = [c for c in COLOR_TOKENS if c in cand_name_lower]
                                    pred_colors = hints["color_tokens"]

                                    if cand_colors and pred_colors:
                                        if not any(pc in cand_colors for pc in pred_colors):
                                            print(f"[ALIGN] (legacy) Produce color reject: {r['name']} has {cand_colors} but pred has {pred_colors}")
                                            if telemetry is not None:
                                                telemetry["produce_color_mismatch_rejects"] = telemetry.get("produce_color_mismatch_rejects", 0) + 1
                                            continue  # Skip this candidate

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

                            # NEW: Apply alignment hints scoring (mass-only mode enrichment - same as Foundation)
                            if hints:
                                cand_name_lower = r["name"].lower()

                                # +0.5 if candidate class matches class_from_name
                                if hints["class_from_name"] and hints["class_from_name"] in cand_name_lower:
                                    score += 0.5
                                    print(f"[ALIGN] (legacy) Class match bonus: {hints['class_from_name']} in {r['name']}")

                                # +1.0 if candidate matches color tokens (increased from +0.5)
                                if hints["color_tokens"]:
                                    matched_colors = [c for c in hints["color_tokens"] if c in cand_name_lower]
                                    if matched_colors:
                                        score += 1.0
                                        print(f"[ALIGN] (legacy) Color match bonus: {matched_colors} in {r['name']}")

                                # +0.5 if candidate matches species tokens
                                if hints["species_tokens"]:
                                    matched_species = [s for s in hints["species_tokens"] if s in cand_name_lower]
                                    if matched_species:
                                        score += 0.5
                                        print(f"[ALIGN] (legacy) Species match bonus: {matched_species} in {r['name']}")

                            # NEW: Egg part disambiguation scoring (Fix #2 - CRITICAL) - same as Foundation
                            if "egg" in food_name.lower():
                                cand_name_lower = r["name"].lower()
                                food_lower = food_name.lower()

                                if "white" in food_lower:
                                    if "egg white" in cand_name_lower or "white of egg" in cand_name_lower:
                                        score += 2.0
                                        print(f"[ALIGN] (legacy) Egg white match bonus: +2.0 for {r['name']}")
                                    elif "yolk" in cand_name_lower:
                                        score -= 2.0
                                        print(f"[ALIGN] (legacy) Egg yolk penalty: -2.0 for {r['name']} (whites intended)")

                                elif "yolk" in food_lower:
                                    if "yolk" in cand_name_lower:
                                        score += 2.0
                                        print(f"[ALIGN] (legacy) Egg yolk match bonus: +2.0 for {r['name']}")
                                    elif "white" in cand_name_lower:
                                        score -= 2.0
                                        print(f"[ALIGN] (legacy) Egg white penalty: -2.0 for {r['name']} (yolk intended)")

                            # NEW: Corn kernel vs flour disambiguation (Fix #3 - CRITICAL) - same as Foundation
                            if "corn" in food_name.lower():
                                cand_name_lower = r["name"].lower()
                                food_lower = food_name.lower()

                                has_kernel_keyword = any(kw in food_lower for kw in ["kernel", "kernels", "cob", "sweet corn", "corn on"])
                                has_milled_keyword = any(kw in food_lower for kw in ["flour", "meal", "grits", "polenta", "masa", "starch"])

                                if not has_milled_keyword:
                                    if any(kw in cand_name_lower for kw in ["flour", "meal", "grits", "polenta", "masa", "starch"]):
                                        score -= 1.5
                                        print(f"[ALIGN] (legacy) Corn milled penalty: -1.5 for {r['name']} (kernels intended)")

                                if has_kernel_keyword:
                                    if any(kw in cand_name_lower for kw in ["kernel", "kernels", "sweet", "yellow corn", "canned corn"]):
                                        score += 1.0
                                        print(f"[ALIGN] (legacy) Corn kernel match bonus: +1.0 for {r['name']}")

                            if hints:
                                # +0.5 if candidate state matches implied_form
                                if hints["implied_form"]:
                                    from ..nutrition.utils.method_resolver import canonical_form
                                    normalized_implied = canonical_form(hints["implied_form"])

                                    cand_is_raw = any(kw in cand_name_lower for kw in ["raw", "fresh", "uncooked"])
                                    cand_is_cooked = any(kw in cand_name_lower for kw in ["cooked", "boiled", "grilled", "fried", "roasted"])

                                    if normalized_implied == "raw" and cand_is_raw:
                                        score += 0.5
                                        print(f"[ALIGN] (legacy) Form match bonus: raw in {r['name']}")
                                    elif normalized_implied != "raw" and cand_is_cooked:
                                        score += 0.5
                                        print(f"[ALIGN] (legacy) Form match bonus: cooked in {r['name']}")

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

            # NEW: Try curated branded fallback as last resort
            branded_result = self._try_curated_branded_fallback(food_name, features, hints, telemetry)
            if branded_result:
                return branded_result

            return None

        # Sort by score and return best
        candidates.sort(key=lambda x: x["score"], reverse=True)
        best = candidates[0]

        # NEW: Sparse-signal scoring floor (mass-only mode)
        # If best score is below normal floor (1.6) but within sparse acceptance range,
        # accept with lower confidence
        from src.config.feature_flags import FLAGS

        sparse_accept = False
        if FLAGS.vision_mass_only and FLAGS.accept_sparse_stage2_on_floor:
            normal_floor = 1.6
            sparse_floor = 1.1  # Lowered from 1.3 to accept more sparse matches

            if sparse_floor <= best["score"] < normal_floor:
                # Check if this is a Stage 2 candidate with class match
                is_stage2_raw = best["record"].get("data_type") in ("foundation_food", "sr_legacy_food")
                class_matches = False

                if hints and hints["class_from_name"]:
                    class_matches = hints["class_from_name"] in best["record"]["name"].lower()

                if is_stage2_raw and class_matches:
                    sparse_accept = True
                    print(f"[ALIGN] Sparse accept: score {best['score']:.2f} below normal floor {normal_floor} "
                          f"but above sparse floor {sparse_floor} with class match")
                    if telemetry is not None:
                        telemetry["sparse_accept_count"] = telemetry.get("sparse_accept_count", 0) + 1

        print(f"[ALIGN] Best match: {best['record']['name']} (FDC: {best['record']['fdc_id']}, score: {best['score']:.2f})")
        print(f"[ALIGN] Base nutrition/100g: {best['nutrition']}")

        # Show runner-ups for debugging
        if len(candidates) > 1:
            print(f"[ALIGN] Runner-ups:")
            for c in candidates[1:3]:
                print(f"[ALIGN]   - {c['record']['name']} (score: {c['score']:.2f})")

        # Calculate confidence
        if sparse_accept:
            # Lower confidence for sparse accept (0.55 as specified)
            confidence = 0.55
        else:
            confidence = min(0.95, 0.6 + 0.1 * best["score"])

        return {
            "fdc_id": best["record"]["fdc_id"],
            "name": best["record"]["name"],
            "data_type": best["record"].get("data_type", "unknown"),
            "confidence": confidence,
            "score": best["score"],
            "base_nutrition_per_100g": best["nutrition"],
            "sparse_accept": sparse_accept  # NEW: flag for telemetry
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
        # Pass full predicted_food dict for hint derivation
        match = self.search_best_match(food_name, predicted_kcal_100g=predicted_kcal_100g,
                                       telemetry=telemetry, pred_item=predicted_food)
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
            # NEW: Mass-only mode enrichment telemetry
            "alignment_hints_derived": 0,
            "sparse_accept_count": 0,
            "produce_color_mismatch_rejects": 0,
            "method_inferred_defaults_used": {},  # by class
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
