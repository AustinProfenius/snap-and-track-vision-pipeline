"""
Food taxonomy and classification system for FDC database alignment.
Maps predicted food names to classes, forms, and normalized phrases.
"""
from typing import List, Dict, Set, Optional

# Food class hierarchies - maps core food types to their variations
FOOD_CLASSES = {
    "rice": {"rice", "white rice", "brown rice", "basmati", "jasmine", "long-grain", "short-grain", "wild rice"},
    "tomatoes": {"tomato", "tomatoes", "cherry tomatoes", "grape tomatoes", "roma tomatoes", "plum tomatoes"},
    "grapes": {"grape", "grapes", "red grapes", "green grapes", "seedless grapes", "seeded grapes", "concord grapes"},
    "almonds": {"almond", "almonds"},
    "spinach": {"spinach", "baby spinach"},
    "carrots": {"carrot", "carrots", "baby carrots"},
    "onions": {"onion", "onions", "white onions", "red onions", "yellow onions", "green onions", "scallions"},
    "chicken": {"chicken", "chicken breast", "chicken thigh", "chicken drumstick", "chicken wings"},
    "beef": {"beef", "ground beef", "steak", "sirloin", "ribeye"},
    "pork": {"pork", "pork chop", "bacon", "ham"},
    "fish": {"fish", "salmon", "tuna", "cod", "tilapia", "trout"},
    "eggs": {"egg", "eggs"},
    "milk": {"milk", "whole milk", "skim milk", "2% milk"},
    "cheese": {"cheese", "cheddar", "mozzarella", "parmesan", "swiss"},
    "bread": {"bread", "white bread", "whole wheat bread", "sourdough"},
    "pasta": {"pasta", "spaghetti", "penne", "macaroni", "fettuccine"},
    "potatoes": {"potato", "potatoes", "russet", "red potatoes", "sweet potato"},
    "beans": {"beans", "black beans", "kidney beans", "pinto beans", "chickpeas"},
    "lettuce": {"lettuce", "romaine", "iceberg lettuce", "butter lettuce"},
    "broccoli": {"broccoli"},
    "apple": {"apple", "apples", "granny smith", "fuji", "gala", "honeycrisp"},
    "banana": {"banana", "bananas"},
    "orange": {"orange", "oranges"},
    "strawberries": {"strawberry", "strawberries"},
    "blueberries": {"blueberry", "blueberries"},
    "watermelon": {"watermelon"},
    "honeydew": {"honeydew", "honeydew melon"},
    "cantaloupe": {"cantaloupe"},
    "pineapple": {"pineapple"},
    "mango": {"mango", "mangoes"},
    "peach": {"peach", "peaches"},
    "pear": {"pear", "pears"},
    "plum": {"plum", "plums"},
    "avocado": {"avocado", "avocados"},
}

# Food preparation forms
FORMS = {
    "cooked": {"cooked", "boiled", "steamed", "baked", "roasted", "grilled"},
    "raw": {"raw", "fresh", "uncooked"},
    "dried": {"dried", "dehydrated"},
    "canned": {"canned"},
    "frozen": {"frozen"},
    "fried": {"fried", "pan-fried", "deep-fried"},
}

# Multi-word phrases that should be treated as units (prevent splitting)
PHRASES = {
    "white rice", "brown rice", "wild rice",
    "grape tomatoes", "cherry tomatoes", "roma tomatoes",
    "baby spinach", "baby carrots",
    "red grapes", "green grapes", "seedless grapes",
    "chicken breast", "chicken thigh",
    "ground beef",
    "sweet potato",
    "black beans", "kidney beans", "pinto beans",
    "whole wheat bread",
    "honeydew melon",
}

# Modifiers to skip when extracting core nouns
SKIP_WORDS = {
    "fresh", "raw", "cooked", "boiled", "fried", "grilled", "roasted",
    "steamed", "baked", "with", "without", "medium", "large", "small",
    "shredded", "sliced", "diced", "chopped", "minced", "piece", "pieces",
    "organic", "natural", "whole", "half", "quarter",
}


def extract_features(food_name: str) -> dict:
    """
    Extract food taxonomy features from a predicted food name.

    Args:
        food_name: Predicted food name (e.g., "cooked white rice")

    Returns:
        Dict with:
            - phrase: Locked multi-word phrase if found
            - core: Food class (rice, tomatoes, etc.)
            - form: Preparation form (cooked, raw, etc.)
            - tokens: Clean tokens for searching
    """
    s = food_name.lower().strip()

    # Check for locked phrases first
    phrase = None
    for p in PHRASES:
        if p in s:
            phrase = p
            break

    # Extract tokens
    tokens = [t.strip("(),") for t in s.split()]
    clean_tokens = [t for t in tokens if t and t not in SKIP_WORDS and len(t) > 2]

    # Extract form
    form = None
    for f, keywords in FORMS.items():
        if any(k in s for k in keywords):
            form = f
            break

    # Extract core class
    core = None
    if phrase:
        # Try to find class by phrase
        for cls, names in FOOD_CLASSES.items():
            if phrase in names:
                core = cls
                break

    if not core:
        # Try to find class by tokens
        for cls, names in FOOD_CLASSES.items():
            if any(t in names for t in clean_tokens):
                core = cls
                break

    return {
        "phrase": phrase,
        "core": core,
        "form": form,
        "tokens": clean_tokens,
        "original": food_name
    }


def is_class_match(candidate_name: str, core_class: str) -> bool:
    """
    Check if a candidate food name belongs to the expected class.

    Args:
        candidate_name: Name from database
        core_class: Expected class (rice, tomatoes, etc.)

    Returns:
        True if candidate matches the class
    """
    if not core_class or core_class not in FOOD_CLASSES:
        return True  # No class constraint

    name_lower = candidate_name.lower()
    class_keywords = FOOD_CLASSES[core_class]

    # Check if any class keyword appears in candidate name
    return any(keyword in name_lower for keyword in class_keywords)


def compute_match_score(candidate_name: str, features: dict,
                        candidate_kcal_100g: float = None,
                        predicted_kcal_100g: float = None) -> float:
    """
    Compute a match score for a candidate against extracted features.

    Args:
        candidate_name: Name from database
        features: Dict from extract_features()
        candidate_kcal_100g: Energy density from database (kcal/100g)
        predicted_kcal_100g: Model's energy density estimate (kcal/100g)

    Returns:
        Score (higher is better)
    """
    name_lower = candidate_name.lower()
    score = 0.0

    # Exact phrase match (highest priority)
    if features["phrase"] and features["phrase"] == name_lower:
        score += 3.0
    elif features["phrase"] and features["phrase"] in name_lower:
        score += 2.0

    # Core word at start (very strong signal)
    if features["core"] and name_lower.startswith(features["core"]):
        score += 1.5
    elif features["core"] and features["core"] in name_lower:
        score += 1.0

    # Form match (cooked, raw, etc.)
    if features["form"]:
        form_keywords = FORMS[features["form"]]
        if any(k in name_lower for k in form_keywords):
            score += 0.5

    # Token presence
    matching_tokens = sum(1 for t in features["tokens"] if t in name_lower)
    score += 0.2 * matching_tokens

    # Energy density similarity (if both values available)
    if candidate_kcal_100g is not None and predicted_kcal_100g is not None and predicted_kcal_100g > 0:
        energy_diff = abs(candidate_kcal_100g - predicted_kcal_100g) / predicted_kcal_100g
        if energy_diff < 0.15:  # Within 15%
            score += 1.0  # Strong energy match
        elif energy_diff < 0.30:  # Within 30%
            score += 0.5  # Moderate energy match
        # No bonus if >30% difference (likely wrong food)

    return score


# ===== SYNONYM SUPPORT FOR STAGE Z =====

# Food name synonyms for better token matching in Stage Z
FOOD_SYNONYMS = {
    "bell_pepper": ["capsicum", "sweet pepper", "bell peppers"],
    "zucchini": ["courgette", "zucchinis"],
    "scallion": ["green onion", "spring onion", "scallions", "green onions"],
    "chickpeas": ["garbanzo beans", "garbanzo", "chickpea", "garbanzos"],
    "eggplant": ["aubergine", "eggplants"],
    "cilantro": ["coriander leaves", "coriander", "cilantros"],
    "arugula": ["rocket", "rocket lettuce"],
    "shrimp": ["prawns", "prawn"],
    "corn": ["maize", "sweet corn"],
    "lima_beans": ["butter beans"],
    "snow_peas": ["sugar snap peas", "snap peas"],
    "romaine": ["cos lettuce"],
    "rutabaga": ["swede", "turnip"],
    "beets": ["beetroot", "beet"],
}


def expand_with_synonyms(food_name: str) -> List[str]:
    """
    Expand a food name with all known synonyms for better token matching.

    Used in Stage Z to improve token overlap detection when food names
    use regional or alternative terminology.

    Args:
        food_name: Original food name (e.g., "bell pepper")

    Returns:
        List of [food_name] + all synonyms (e.g., ["bell pepper", "capsicum", "sweet pepper"])

    Examples:
        >>> expand_with_synonyms("bell pepper")
        ["bell pepper", "capsicum", "sweet pepper", "bell peppers"]

        >>> expand_with_synonyms("chicken breast")
        ["chicken breast"]  # No synonyms, returns original only
    """
    # Normalize food name
    name_lower = food_name.lower().strip()

    # Start with original name
    expanded = [food_name]

    # Check if any synonym key matches
    for key, synonyms in FOOD_SYNONYMS.items():
        # Normalize key for comparison (replace _ with space)
        key_normalized = key.replace("_", " ")

        # Check if the key or any synonym appears in food_name
        if key_normalized in name_lower or any(syn.lower() in name_lower for syn in synonyms):
            # Add all synonyms (avoiding duplicates)
            for syn in synonyms:
                if syn.lower() not in [e.lower() for e in expanded]:
                    expanded.append(syn)

            # Also add the key itself if not already there
            if key_normalized not in [e.lower() for e in expanded]:
                expanded.append(key_normalized)

    return expanded
