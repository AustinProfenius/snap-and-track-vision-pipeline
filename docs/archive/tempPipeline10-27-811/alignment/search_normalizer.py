"""
Search query normalization for FDC database quirks.

Handles:
- Plural → singular conversions (except FDC quirks where plural is correct)
- FDC-specific naming patterns (e.g., "Melons, cantaloupe, raw")
- Common synonym mappings (e.g., "scrambled eggs" → "egg scrambled")
- Fruit/nut/berry variants
- Bidirectional search (singular ↔ plural) with FDC hints

This normalization layer helps match user queries to FDC database entries
that may use non-standard naming conventions.
"""

import re
from typing import Dict, List

# Plural → Singular (or FDC-preferred form)
PLURAL_MAP: Dict[str, str] = {
    # Nuts (FDC uses singular + "raw")
    "almonds": "almond raw",

    # Berries (FDC uses singular + "raw")
    "strawberries": "strawberry raw",
    "blueberries": "blueberry raw",
    "raspberries": "raspberry raw",
    "blackberries": "blackberry raw",

    # FDC quirk: uses PLURAL for grapes
    "grape": "grapes raw",  # singular → plural for FDC

    # Tomato variants (FDC format: "Tomatoes, <type>, raw")
    "grape tomatoes": "tomatoes grape raw",
    "cherry tomatoes": "tomatoes cherry raw",
}

# FDC naming quirks and common synonyms
SYNONYMS: Dict[str, str] = {
    # Melons (FDC format: "Melons, <type>, raw")
    "cantaloupe": "melons cantaloupe raw",
    "honeydew melon": "melons honeydew raw",
    "honeydew": "melons honeydew raw",
    "watermelon": "melons watermelon raw",

    # Fruits with skin variations (FDC often specifies "with skin")
    "apple": "apples raw with skin",
    "apples": "apples raw with skin",

    # Breakfast meats (prefer cooked profiles)
    "bacon": "bacon cooked",
    "sausage": "sausage pork cooked",
    "pork sausage": "sausage pork cooked",

    # Eggs (FDC format: "Egg, <preparation>")
    "scrambled eggs": "egg scrambled",
    "scrambled egg": "egg scrambled",
    "fried egg": "egg fried",
    "fried eggs": "egg fried",
    "boiled egg": "egg boiled",
    "boiled eggs": "egg boiled",
}


def normalize_query(q: str) -> str:
    """
    Normalize food query for FDC database search.

    Handles plurals, FDC naming conventions, and common synonyms.

    Args:
        q: Raw query string (e.g., "grapes", "scrambled eggs", "cantaloupe")

    Returns:
        Normalized query optimized for FDC search (e.g., "grapes raw", "egg scrambled", "melons cantaloupe raw")

    Examples:
        >>> normalize_query("grapes")
        'grapes raw'
        >>> normalize_query("scrambled eggs")
        'egg scrambled'
        >>> normalize_query("cantaloupe")
        'melons cantaloupe raw'
    """
    if not q:
        return ""

    x = q.strip().lower()

    # Check synonyms first (exact matches take precedence)
    if x in SYNONYMS:
        return SYNONYMS[x]

    # Check plural map
    if x in PLURAL_MAP:
        return PLURAL_MAP[x]

    # Default: return cleaned query (normalize whitespace)
    x = re.sub(r"\s+", " ", x)
    return x


def get_normalization_info(q: str) -> Dict[str, str]:
    """
    Get normalization details for debugging/telemetry.

    Args:
        q: Raw query string

    Returns:
        Dict with original and normalized queries
    """
    normalized = normalize_query(q)
    return {
        "original_query": q.strip().lower(),
        "normalized_query": normalized,
        "was_normalized": (q.strip().lower() != normalized)
    }


def generate_query_variants(q: str) -> List[str]:
    """
    Generate multiple search query variants (singular, plural, FDC hints).

    This function creates bidirectional search variants to handle FDC database
    inconsistencies where some items use plural ("Almonds, raw", "Grapes, raw")
    while others use singular ("Apple, raw", "Carrot, raw").

    Returns list of queries to try in order, with deduplication.

    Args:
        q: Raw query string (e.g., "grapes", "almond", "cantaloupe")

    Returns:
        List of query variants to try in order (e.g., ["grapes raw", "grape", "grapes"])

    Examples:
        >>> generate_query_variants("grapes")
        ['grapes', 'grapes raw', 'grape']

        >>> generate_query_variants("almonds")
        ['almonds', 'almond raw', 'almond', 'almonds raw']

        >>> generate_query_variants("cantaloupe")
        ['cantaloupe', 'melons cantaloupe raw']
    """
    if not q:
        return [""]

    base = q.strip().lower()
    variants = []

    # Apply existing normalization first
    norm = normalize_query(base)
    if norm != base:
        variants.append(norm)

    # Add plural <-> singular toggles
    if base.endswith("s") and len(base) > 1:
        # Plural → singular (e.g., "almonds" → "almond")
        singular = base[:-1]
        variants.append(singular)
        # Also try singular + "raw" (common FDC pattern)
        variants.append(f"{singular} raw")
    else:
        # Singular → plural (e.g., "grape" → "grapes")
        plural = base + "s"
        variants.append(plural)
        # Also try plural + "raw" (common FDC pattern)
        variants.append(f"{plural} raw")

    # Fruit/nut specific FDC hints (exact FDC titles)
    FDC_HINTS: Dict[str, str] = {
        # Grapes (FDC uses PLURAL)
        "grape": "grapes raw",
        "grapes": "grapes raw",

        # Almonds (FDC uses PLURAL)
        "almond": "almonds raw",
        "almonds": "almonds raw",

        # Apples (FDC specifies "with skin")
        "apple": "apples raw with skin",
        "apples": "apples raw with skin",

        # Walnuts (FDC uses PLURAL)
        "walnut": "walnuts raw",
        "walnuts": "walnuts raw",

        # Peanuts (FDC uses PLURAL)
        "peanut": "peanuts raw",
        "peanuts": "peanuts raw",

        # Strawberries (FDC uses PLURAL)
        "strawberry": "strawberries raw",
        "strawberries": "strawberries raw",

        # Blueberries (FDC uses PLURAL)
        "blueberry": "blueberries raw",
        "blueberries": "blueberries raw",

        # Carrots (FDC uses PLURAL)
        "carrot": "carrots raw",
        "carrots": "carrots raw",
    }

    if base in FDC_HINTS:
        variants.append(FDC_HINTS[base])

    # FRUIT/MELON-SPECIFIC BIASES: Prefer plural→plural+raw→singular for berries/nuts
    # These items have FDC entries with plural forms (e.g., "Grapes, raw" not "Grape, raw")
    head = base.split()[0] if base else ""

    # Ensure plural forms tried first for FDC-plural items (grapes, almonds, berries)
    PREFER_PLURAL = {"grapes", "almonds", "blueberries", "blackberries", "raspberries", "strawberries", "walnuts", "peanuts"}
    if head in PREFER_PLURAL or base in PREFER_PLURAL:
        # Reorder: plural raw → plural → singular raw → singular
        plural_raw = [v for v in variants if v.endswith("s raw")]
        plural = [v for v in variants if v.endswith("s") and not v.endswith(" raw")]
        singular_raw = [v for v in variants if not v.endswith("s") and v.endswith(" raw")]
        singular = [v for v in variants if not v.endswith("s") and not v.endswith(" raw")]
        variants = plural_raw + plural + singular_raw + singular

    # Melon-specific variants (FDC uses "Melons, <type>, raw" format)
    if "honeydew" in base:
        variants = ["melons honeydew raw", "honeydew raw", "honeydew"] + \
                   [v for v in variants if v not in {"melons honeydew raw", "honeydew raw", "honeydew"}]
    if "cantaloupe" in base or "muskmelon" in base:
        variants = ["melons cantaloupe raw", "cantaloupe raw", "cantaloupe", "muskmelon raw", "muskmelon"] + \
                   [v for v in variants if v not in {"melons cantaloupe raw", "cantaloupe raw", "cantaloupe", "muskmelon raw", "muskmelon"}]

    # Corn variants (FDC: "Corn, sweet, yellow, raw")
    if "corn" in base and ("cob" in base or base == "corn"):
        variants = ["corn sweet yellow raw", "corn sweet raw", "corn raw", "corn on the cob"] + \
                   [v for v in variants if v not in {"corn sweet yellow raw", "corn sweet raw", "corn raw", "corn on the cob"}]

    # Tomato variants (FDC: "Tomatoes, cherry, raw" or "Tomatoes, grape, raw")
    if "cherry" in base and "tomato" in base:
        variants = ["tomatoes cherry raw", "tomato cherry raw", "cherry tomatoes raw", "cherry tomato raw"] + \
                   [v for v in variants if v not in {"tomatoes cherry raw", "tomato cherry raw", "cherry tomatoes raw", "cherry tomato raw"}]
    if "grape" in base and "tomato" in base:
        variants = ["tomatoes grape raw", "tomato grape raw", "grape tomatoes raw", "grape tomato raw"] + \
                   [v for v in variants if v not in {"tomatoes grape raw", "tomato grape raw", "grape tomatoes raw", "grape tomato raw"}]

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for v in [base] + variants:
        v_stripped = v.strip()
        if v_stripped and v_stripped not in seen:
            unique.append(v_stripped)
            seen.add(v_stripped)

    return unique
