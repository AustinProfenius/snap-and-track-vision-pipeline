"""
Cooking method resolution for raw→cooked conversion.

Resolves cooking method from model predictions using priority cascade:
1. Explicit method match (if model says "grilled" and we have "grilled")
2. Alias expansion (sauteed→pan_seared, baked→roasted_oven)
3. Class-specific fallback (e.g., rice→boiled, beef→grilled)
4. Category bucket fallback (meat_poultry→grilled, starch_grain→boiled)
5. First available method in config

Returns: (method, reason_code) for telemetry tracking
"""
from typing import Tuple, Optional, Dict, Any
import json
import re
from pathlib import Path


# Cache for class synonyms (loaded once)
_CLASS_SYNONYMS_CACHE: Optional[Dict[str, str]] = None


def load_class_synonyms() -> Dict[str, str]:
    """
    Load class_synonyms.json mapping vision strings → conversion config classes.

    Returns normalized (lowercase, stripped) synonym dict.
    Caches result to avoid repeated file reads.
    """
    global _CLASS_SYNONYMS_CACHE

    if _CLASS_SYNONYMS_CACHE is not None:
        return _CLASS_SYNONYMS_CACHE

    try:
        synonyms_path = Path(__file__).parent.parent.parent / "data" / "class_synonyms.json"
        if not synonyms_path.exists():
            print(f"[METHOD_RESOLVER] WARNING: class_synonyms.json not found at {synonyms_path}")
            _CLASS_SYNONYMS_CACHE = {}
            return _CLASS_SYNONYMS_CACHE

        with open(synonyms_path) as f:
            config = json.load(f)

        # Extract synonyms dict, normalize keys
        raw_synonyms = config.get("synonyms", {})
        _CLASS_SYNONYMS_CACHE = {
            k.lower().strip(): v
            for k, v in raw_synonyms.items()
            if not k.startswith("_comment")  # Skip comment keys
        }

        print(f"[METHOD_RESOLVER] Loaded {len(_CLASS_SYNONYMS_CACHE)} class synonyms")
        return _CLASS_SYNONYMS_CACHE

    except Exception as e:
        print(f"[METHOD_RESOLVER] ERROR loading class_synonyms.json: {e}")
        _CLASS_SYNONYMS_CACHE = {}
        return _CLASS_SYNONYMS_CACHE


def normalize_vision_class(vision_string: str) -> str:
    """
    Normalize vision model output to conversion config class key.

    Applies:
    - Lowercase
    - Strip whitespace
    - Remove punctuation (except underscores)
    - Lookup in class_synonyms.json

    Args:
        vision_string: Raw string from vision model (e.g., "Chicken Breast", "hash-browns")

    Returns:
        Normalized class key (e.g., "chicken_breast", "potato_russet")
        Falls back to normalized input if no synonym found
    """
    # Normalize input
    normalized = vision_string.lower().strip()

    # Remove common punctuation (but keep spaces/underscores for synonym matching)
    normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove all non-word, non-space chars
    normalized = re.sub(r'\s+', ' ', normalized).strip()  # Collapse multiple spaces

    # Lookup in synonyms
    synonyms = load_class_synonyms()
    if normalized in synonyms:
        return synonyms[normalized]

    # Fallback: convert spaces to underscores
    return normalized.replace(' ', '_')



# Cooking method aliases (normalized → canonical)
METHOD_ALIASES = {
    "sauteed": "pan_seared",
    "saute": "pan_seared",
    "pan-fried": "pan_seared",
    "pan fried": "pan_seared",  # NEW: space variant
    "seared": "pan_seared",
    "pan seared": "pan_seared",  # NEW: space variant
    "baked": "roasted_oven",
    "oven-roasted": "roasted_oven",
    "oven roasted": "roasted_oven",  # NEW: space variant
    "oven": "roasted_oven",
    "roasted": "roasted_oven",  # NEW: explicit mapping
    "poached": "boiled",
    "simmered": "boiled",
    "deep-fried": "fried",
    "deep fried": "fried",
    "stir-fried": "fried",
    "stir fried": "fried",
    # New aliases (from improvement plan)
    "broiled": "grilled",
    "toasted": "roasted_oven",
    "charred": "grilled",
    "air-fried": "roasted_oven",
    "air fried": "roasted_oven",
}

# Category-based fallback methods
CATEGORY_FALLBACKS = {
    "meat_poultry": "grilled",
    "fish_seafood": "pan_seared",
    "starch_grain": "boiled",
    "vegetable": "steamed",
    "egg": "scrambled",
    "legume": "boiled",
}

# Food class to category mapping
CLASS_TO_CATEGORY = {
    # Starches & Grains
    "rice_white": "starch_grain",
    "rice_brown": "starch_grain",
    "pasta_wheat": "starch_grain",
    "couscous": "starch_grain",
    "quinoa": "starch_grain",
    "potato_russet": "starch_grain",
    "sweet_potato": "starch_grain",

    # Meats & Poultry
    "beef_steak": "meat_poultry",
    "beef_ground_85": "meat_poultry",
    "pork_chop": "meat_poultry",
    "chicken_breast": "meat_poultry",
    "chicken_thigh": "meat_poultry",
    "turkey_breast": "meat_poultry",

    # Fish & Seafood
    "salmon_fillet": "fish_seafood",
    "white_fish_cod": "fish_seafood",
    "tuna_steak": "fish_seafood",
    "shrimp": "fish_seafood",

    # Eggs
    "egg_whole": "egg",

    # Legumes
    "beans_black": "legume",
    "beans_kidney": "legume",
    "chickpeas": "legume",
    "lentils_brown": "legume",

    # Vegetables
    "broccoli": "vegetable",
    "carrot": "vegetable",
    "spinach": "vegetable",
    "mushrooms_white": "vegetable",
    "onion": "vegetable",
}


def normalize_method(raw_method: str) -> str:
    """
    Normalize a raw method string to canonical form.

    Args:
        raw_method: Raw method string from model (e.g., "sauteed", "baked")

    Returns:
        Canonical method (e.g., "pan_seared", "roasted_oven")
    """
    method_lower = raw_method.lower().strip().replace(" ", "_")

    # Check aliases
    if method_lower in METHOD_ALIASES:
        return METHOD_ALIASES[method_lower]

    return method_lower


def canonical_form(form: str) -> str:
    """
    Public alias for normalize_method() - canonical form for alignment.

    Normalizes raw form/method string to canonical cooking method.
    Used throughout alignment system for consistent form matching.

    Args:
        form: Raw form string from prediction (e.g., "sauteed", "baked", "air-fried")

    Returns:
        Canonical method (e.g., "pan_seared", "roasted_oven")

    Examples:
        >>> canonical_form("sauteed")
        "pan_seared"
        >>> canonical_form("baked")
        "roasted_oven"
        >>> canonical_form("air-fried")
        "roasted_oven"
    """
    return normalize_method(form)


def resolve_method(
    core_class: str,
    raw_method_str: Optional[str],
    cfg: Dict[str, Any],
    vision_hints: Optional[Dict[str, Any]] = None
) -> Tuple[str, str]:
    """
    Resolve cooking method using priority cascade.

    Priority order:
    1. Explicit method match (model prediction matches config)
    2. Alias expansion (sauteed→pan_seared)
    3. Class-specific fallback (from cook_conversions.v2.json)
    4. Category fallback (meat_poultry→grilled, etc.)
    5. First available method in config

    Args:
        core_class: Normalized food class (e.g., "rice_white", "beef_steak")
        raw_method_str: Raw method from model prediction (e.g., "grilled", "cooked")
        cfg: cook_conversions.v2.json content
        vision_hints: Future - visual cues (grill marks, browning, etc.)

    Returns:
        (method, reason_code) tuple:
            method: Canonical cooking method (e.g., "grilled", "boiled")
            reason_code: Why this method was chosen ("explicit", "alias",
                        "class_fallback", "category_fallback", "first_available")
    """
    # Handle nested structure: cfg["classes"]["rice_white"]
    classes = cfg.get("classes", cfg)  # Support both old and new structure

    # Get method profiles for this class
    if core_class not in classes:
        # No conversion profile for this class
        return (raw_method_str or "raw", "no_profile")

    class_cfg = classes[core_class]
    available_methods = set(class_cfg.get("method_profiles", {}).keys())

    if not available_methods:
        # No methods defined
        return (raw_method_str or "raw", "no_methods")

    # Priority 1: Explicit match
    if raw_method_str:
        method_normalized = normalize_method(raw_method_str)

        if method_normalized in available_methods:
            return (method_normalized, "explicit")

        # Priority 2: Alias expansion
        if method_normalized in METHOD_ALIASES:
            canonical = METHOD_ALIASES[method_normalized]
            if canonical in available_methods:
                return (canonical, "alias")

        # Priority 2.5: Generic "cooked" fallback (NEW - high priority)
        # When model says "cooked" with no specific method, use category policy
        if method_normalized == "cooked":
            category = CLASS_TO_CATEGORY.get(core_class)
            if category:
                fallback_policies = cfg.get("fallback_policies", {})
                if category in fallback_policies:
                    generic_methods = fallback_policies[category].get("generic_cooked", [])
                    for method in generic_methods:
                        if method in available_methods:
                            return (method, "generic_cooked_fallback")
            # If no category policy, continue to class/category fallback below

    # Priority 3: Class-specific fallback
    class_fallback = class_cfg.get("fallback")
    if class_fallback and class_fallback in available_methods:
        return (class_fallback, "class_fallback")

    # Priority 4: Category fallback
    category = CLASS_TO_CATEGORY.get(core_class)
    if category:
        category_method = CATEGORY_FALLBACKS.get(category)
        if category_method and category_method in available_methods:
            return (category_method, "category_fallback")

    # Priority 5: First available method
    first_method = sorted(available_methods)[0]  # Deterministic order
    return (first_method, "first_available")


def get_method_confidence_penalty(reason_code: str) -> float:
    """
    Get confidence penalty based on method resolution reason.

    Args:
        reason_code: Reason from resolve_method()

    Returns:
        Confidence penalty to subtract (0.0 to 0.20)
    """
    penalties = {
        "explicit": 0.0,                      # Model explicitly identified method
        "alias": 0.05,                        # Reasonable alias (sauteed→pan_seared)
        "generic_cooked_fallback": 0.08,      # Generic "cooked" → category policy (NEW)
        "class_fallback": 0.10,               # Used class default (rice→boiled)
        "category_fallback": 0.15,            # Used category default (meat→grilled)
        "first_available": 0.20,              # Total guess
        "no_profile": 0.20,                   # No conversion profile exists
        "no_methods": 0.20,                   # No methods defined
    }
    return penalties.get(reason_code, 0.15)


# Method compatibility groups for Stage 1 matching (Fix 5.4)
METHOD_COMPATIBLE = {
    "roasted_oven": {"baked", "roasted_oven", "roasted", "oven", "oven-roasted", "toasted", "air-fried", "air fried"},
    "grilled": {"grilled", "broiled", "charred"},
    "pan_seared": {"pan_seared", "sauteed", "saute", "pan-fried", "seared"},
    "boiled": {"boiled", "poached", "simmered"},
    "steamed": {"steamed", "steam"},
    "fried": {"fried", "deep-fried", "deep fried", "pan-fried"},
}


def methods_compatible(method1: str, method2: str) -> bool:
    """
    Check if two cooking methods are compatible/equivalent.

    Used by Stage 1 (cooked exact match) to allow reasonable method variations.

    Args:
        method1: First method (e.g., "roasted_oven")
        method2: Second method (e.g., "baked")

    Returns:
        True if methods are compatible, False otherwise

    Examples:
        >>> methods_compatible("roasted_oven", "baked")
        True
        >>> methods_compatible("grilled", "broiled")
        True
        >>> methods_compatible("grilled", "boiled")
        False
    """
    # Normalize both methods
    m1 = canonical_form(method1)
    m2 = canonical_form(method2)

    # Exact match
    if m1 == m2:
        return True

    # Check compatibility groups
    for base, compatible in METHOD_COMPATIBLE.items():
        if m1 in compatible and m2 in compatible:
            return True

    return False


def _get_conversion_config_method(class_name: str) -> Optional[str]:
    """
    Check cook_conversions.v2.json for class-specific method_profiles.

    Returns first available method from the class's method_profiles,
    preferring conversion-native methods over hardcoded defaults.

    Args:
        class_name: Normalized food class (e.g., "chicken_breast", "rice_white")

    Returns:
        Method name from conversion config, or None if class not found
    """
    try:
        import json
        from pathlib import Path

        # Load cook_conversions.v2.json
        cfg_path = Path(__file__).parent.parent.parent / "data" / "cook_conversions.v2.json"
        if not cfg_path.exists():
            return None

        with open(cfg_path) as f:
            config = json.load(f)

        classes = config.get("classes", {})

        # Check if class exists in conversion config
        if class_name in classes:
            method_profiles = classes[class_name].get("method_profiles", {})
            if method_profiles:
                # Return first available method (prioritized in config)
                methods = list(method_profiles.keys())
                if methods:
                    return methods[0]

    except Exception as e:
        # Silently fail, fall back to hardcoded defaults
        pass

    return None


def infer_method_from_class(class_name: str, pred_form: Optional[str]) -> Tuple[str, str]:
    """
    Infer cooking method from class when form is missing or generic.

    NEW (Enhanced): Now uses class_synonyms.json + cook_conversions.v2.json lookups.

    Priority:
    1. If pred_form exists and is specific (not "cooked") → return normalized
    2. Normalize vision class using class_synonyms.json
    3. Check cook_conversions.v2.json for class-specific methods
    4. If pred_form is "cooked" or empty → return class-specific default
    5. Return ("raw", "default_form_missing") if no category match

    Args:
        class_name: Food class from vision model (e.g., "chicken breast", "hash browns")
        pred_form: Predicted form from vision model (may be None, "", or "cooked")

    Returns:
        (method, reason) tuple:
            method: Inferred cooking method
            reason: Why this method was chosen ("form_provided", "conversion_config",
                   "class_default", "category_default", "default_form_missing")

    Examples:
        >>> infer_method_from_class("chicken breast", None)
        ("grilled", "conversion_config")  # from cook_conversions.v2.json
        >>> infer_method_from_class("hash browns", "")
        ("hash_browns", "conversion_config")  # potato_russet + hash_browns method
        >>> infer_method_from_class("bell pepper", None)
        ("raw", "category_default")
    """
    # NEW: Normalize vision class using synonyms
    class_lower = normalize_vision_class(class_name)

    # Check if pred_form is specific (not empty and not generic "cooked")
    if pred_form and pred_form.strip() and pred_form.lower().strip() != "cooked":
        # Form is specific, use it
        return (normalize_method(pred_form), "form_provided")

    # Form is missing or generic "cooked" - infer from class

    # NEW: Check cook_conversions.v2.json for class-specific method
    conversion_method = _get_conversion_config_method(class_lower)
    if conversion_method:
        return (conversion_method, "conversion_config")

    # Fallback to hardcoded category defaults

    # Produce → raw
    produce_classes = {
        "apple", "banana", "tomato", "cherry_tomatoes", "grape_tomatoes", "plum_tomatoes",
        "bell_pepper", "bell_pepper_green", "bell_pepper_red", "bell_pepper_yellow",
        "onion", "red_onion", "garlic", "carrot", "broccoli", "cauliflower",
        "spinach", "lettuce", "cucumber", "zucchini", "eggplant", "squash",
        "asparagus", "celery", "kale", "cabbage", "bok_choy", "brussels_sprouts",
        "blueberries", "blackberries", "raspberries", "strawberries", "grapes",
        "watermelon", "cantaloupe", "pineapple"
    }
    if class_lower in produce_classes:
        return ("raw", "category_default")

    # Grains/pasta → boiled
    grain_classes = {"rice_white", "rice_brown", "pasta_wheat", "couscous", "quinoa", "oats"}
    if class_lower in grain_classes:
        return ("boiled", "class_default")

    # Meats → grilled (generic cooked)
    meat_classes = {
        "chicken_breast", "chicken_thigh", "turkey_breast",
        "beef_steak", "beef_ground_85", "pork_chop",
        "salmon_fillet", "white_fish_cod", "tuna_steak", "shrimp"
    }
    if class_lower in meat_classes:
        if "chicken" in class_lower or "turkey" in class_lower:
            return ("grilled", "class_default")  # Poultry default to grilled
        elif "fish" in class_lower or "salmon" in class_lower or "tuna" in class_lower or "cod" in class_lower:
            return ("pan_seared", "class_default")  # Fish default to pan_seared
        else:
            return ("grilled", "class_default")  # Other meats default to grilled

    # Eggs → scrambled
    egg_classes = {"egg_whole", "egg_white", "egg"}
    if class_lower in egg_classes:
        return ("scrambled", "class_default")

    # Bacon → pan_seared
    if "bacon" in class_lower:
        return ("pan_seared", "class_default")

    # Potatoes → depends on context (default to boiled for mass >100g, else roasted)
    potato_classes = {"potato_russet", "potato_red", "sweet_potato"}
    if class_lower in potato_classes:
        # Without mass context, default to boiled (safer generic)
        return ("boiled", "class_default")

    # Unknown class - default to raw (conservative)
    return ("raw", "default_form_missing")
