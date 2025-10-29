"""
Prompts optimized for NutritionVerse evaluation with macro-only and micronutrient modes.
"""
import json
from typing import Dict, Any


SYSTEM_MESSAGE = """You are a professional nutrition analyst with expertise in food recognition and nutritional estimation.

Your task is to analyze food images and provide accurate nutritional information in a structured JSON format.

CRITICAL INSTRUCTIONS:
- Return ONLY valid JSON matching the exact schema provided
- Do NOT add any extra fields or keys
- Do NOT include explanatory text before or after the JSON
- Do NOT wrap JSON in markdown code blocks (no ```json or ```)
- Start your response with { and end with }
- Be as accurate as possible with mass and nutrition estimates
- List ALL visible food items separately
- Do NOT invent items not visible in the image
- Round only at the very end; keep internal calculations as floats

IMPORTANT - Food Item Identification:
- ALWAYS identify each food item separately - NEVER group them as "mixed greens", "mixed vegetables", "salad mix"
- If you see multiple vegetables/items, list EACH ONE individually with separate estimates
- Example: Instead of "mixed greens", list "spinach", "romaine lettuce", "arugula" as separate items

IMPORTANT - Food Naming Convention:
- Use ONLY base food names WITHOUT cooking method adjectives
- DO NOT use: "steamed", "cooked", "grilled", "roasted", "baked", "fried", "boiled", "sautéed"
- ✓ Good: "broccoli", "chicken breast", "white rice", "salmon", "asparagus"
- ✗ NEVER: "steamed broccoli", "grilled chicken breast", "cooked rice", "baked salmon", "roasted asparagus"
- Exception: Only include cooking method if it fundamentally changes the food (e.g., "popcorn" vs "corn")

TWO-PASS WORKFLOW (Internal - Do Not Output):
You must mentally perform this two-stage analysis:

STAGE A - PERCEPTION:
1. Identify all visible food items
2. For discrete items (nuts, tomatoes, grapes): count them
3. For bulk foods (rice, spinach, salad): estimate volume (e.g., ½ cup, 1 cup)
4. Identify food form for each item (raw/cooked/dried/juice/canned/baby)
5. For COOKED items, identify cooking method if visible:
   - Look for grill marks → "grilled"
   - Look for browning/crust → "pan_seared" or "roasted"
   - Look for wetness/steam → "boiled" or "steamed"
   - Look for oil sheen/crispy edges → "fried"
   - If method unclear but clearly cooked → "cooked"
   - IMPORTANT: If breading/batter is visible, explicitly state "breaded" or "battered" in the form field
   - For plain proteins without coating, do NOT imply breading (e.g., say "grilled chicken" not "fried chicken" unless breading is visible)
6. Use visual cues (fork ≈18.5cm, plate ≈27cm, credit card ≈8.5cm) for size reference
7. Estimate energy density (kcal/100g) for each item based on form and cooking method

STAGE B - ESTIMATION:
1. Calculate mass_g from count (discrete) or volume (bulk) or visual size
2. Ensure calories are consistent with mass_g × kcal_per_100g_est (±10% tolerance)
3. Calculate macros using Atwater factors: 4 kcal/g protein, 4 kcal/g carbs, 9 kcal/g fat
4. Verify total calories ≈ 4×protein + 4×carbs + 9×fat (±10% tolerance)
5. Assign confidence score (0-1) based on visibility and estimation certainty"""


def get_macro_only_prompt() -> str:
    """
    Get prompt for macro-only mode (calories, mass, protein, carbs, fat).

    Returns:
        Formatted prompt string
    """
    return """Analyze this food image and identify each individual food item with detailed nutritional estimates.

CRITICAL:
- Identify EACH food separately - NEVER group as "mixed greens", "mixed vegetables", "salad"
- Use base food names WITHOUT cooking methods (e.g., "chicken breast" not "grilled chicken breast")

You must return a JSON object matching this exact schema:

{
  "foods": [
    {
      "name": "string (base food name only - no cooking methods, e.g., 'chicken breast')",
      "mass_g": number (estimated mass in grams),
      "calories": number (estimated calories in kcal),
      "fat_g": number (estimated fat in grams),
      "carbs_g": number (estimated carbohydrates in grams),
      "protein_g": number (estimated protein in grams),
      "form": "string (raw/cooked/dried/juice/canned/baby/frozen OR cooking method: grilled/boiled/steamed/fried/pan_seared/roasted/baked - OPTIONAL)",
      "count": number (for discrete items like nuts, tomatoes, grapes - OPTIONAL),
      "kcal_per_100g_est": number (your energy density estimate - OPTIONAL),
      "confidence": number (0-1 confidence score - OPTIONAL)
    }
  ],
  "totals": {
    "mass_g": number (sum of all food masses),
    "calories": number (sum of all food calories),
    "fat_g": number (sum of all fat),
    "carbs_g": number (sum of all carbs),
    "protein_g": number (sum of all protein)
  }
}

IMPORTANT INSTRUCTIONS:
1. Identify EVERY separate food item visible - break down mixed dishes into individual components
2. Use base food names WITHOUT cooking methods (e.g., "chicken breast", "broccoli", "rice")
3. For DISCRETE items (nuts, grapes, tomatoes): Provide count AND state your visual reasoning
   Example: "almonds: looks like ~30 nuts at ~1.2g each → 35-40g"
4. For BULK items (rice, spinach): Estimate volume as reference (e.g., "½ cup", "1 cup")
5. Identify FORM for each item:
   - If RAW: use "raw"
   - If COOKED and method visible: use "grilled", "boiled", "steamed", "fried", "pan_seared", "roasted", "baked"
   - If COOKED but method unclear: use "cooked"
   - Other forms: "dried", "juice", "canned", "baby", "frozen"
6. Estimate ENERGY DENSITY (kcal_per_100g_est) based on food type, form, and cooking method
   - Cooking method significantly affects energy density (e.g., grilled chicken ≈165 kcal/100g, fried chicken ≈245 kcal/100g)
   - Grains/pasta expand when cooked (raw rice ~365 kcal/100g → boiled rice ~130 kcal/100g)
7. Calculate mass_g ensuring it's consistent with your kcal_per_100g_est and calories
8. Calculate macronutrients (protein, carbs, fat) for each item
9. Assign CONFIDENCE (0-1) based on visibility and certainty
10. Sum all values to get the totals

Example output:
{
  "foods": [
    {
      "name": "chicken breast",
      "mass_g": 150,
      "calories": 248,
      "fat_g": 5.4,
      "carbs_g": 0,
      "protein_g": 46.8,
      "form": "cooked",
      "kcal_per_100g_est": 165,
      "confidence": 0.85
    },
    {
      "name": "broccoli",
      "mass_g": 100,
      "calories": 34,
      "fat_g": 0.4,
      "carbs_g": 7,
      "protein_g": 2.8,
      "form": "raw",
      "kcal_per_100g_est": 34,
      "confidence": 0.9
    },
    {
      "name": "almonds",
      "mass_g": 28,
      "calories": 164,
      "fat_g": 14.2,
      "carbs_g": 6.1,
      "protein_g": 6.0,
      "form": "raw",
      "count": 24,
      "kcal_per_100g_est": 585,
      "confidence": 0.75
    }
  ],
  "totals": {
    "mass_g": 278,
    "calories": 446,
    "fat_g": 20.0,
    "carbs_g": 13.1,
    "protein_g": 55.6
  }
}

Return ONLY the JSON, no other text."""


def get_micro_macro_prompt() -> str:
    """
    Get prompt for micronutrient + macronutrient mode.

    Returns:
        Formatted prompt string
    """
    return """Analyze this food image and identify each individual food item with comprehensive nutritional estimates including micronutrients.

CRITICAL:
- Identify EACH food separately - NEVER group as "mixed greens", "mixed vegetables", "salad"
- Use base food names WITHOUT cooking methods (e.g., "salmon" not "grilled salmon")

You must return a JSON object matching this exact schema:

{
  "foods": [
    {
      "name": "string (base food name only - no cooking methods)",
      "mass_g": number,
      "calories": number,
      "fat_g": number,
      "carbs_g": number,
      "protein_g": number,
      "calcium_mg": number,
      "iron_mg": number,
      "magnesium_mg": number,
      "potassium_mg": number,
      "sodium_mg": number,
      "vitamin_d_ug": number (micrograms),
      "vitamin_b12_ug": number (micrograms)
    }
  ],
  "totals": {
    "mass_g": number,
    "calories": number,
    "fat_g": number,
    "carbs_g": number,
    "protein_g": number,
    "calcium_mg": number,
    "iron_mg": number,
    "magnesium_mg": number,
    "potassium_mg": number,
    "sodium_mg": number,
    "vitamin_d_ug": number,
    "vitamin_b12_ug": number
  }
}

MICRONUTRIENT GUIDELINES:
- calcium_mg: Important in dairy, leafy greens
- iron_mg: Found in red meat, spinach, legumes
- magnesium_mg: Nuts, whole grains, vegetables
- potassium_mg: Bananas, potatoes, meat
- sodium_mg: Table salt, processed foods, cheese
- vitamin_d_ug: Fatty fish, eggs, fortified dairy
- vitamin_b12_ug: Animal products (meat, dairy, eggs)

IMPORTANT INSTRUCTIONS:
1. Identify EVERY separate food item visible - break down mixed dishes into individual components
2. Use base food names WITHOUT cooking methods (e.g., "salmon", "asparagus", "chicken breast")
3. Estimate the mass of each food item carefully
4. Calculate both macronutrients AND micronutrients for each item
5. Use typical nutritional values for each identified food
6. Sum all values to get the totals

Example output:
{
  "foods": [
    {
      "name": "salmon",
      "mass_g": 150,
      "calories": 280,
      "fat_g": 18,
      "carbs_g": 0,
      "protein_g": 28.5,
      "calcium_mg": 13.5,
      "iron_mg": 0.6,
      "magnesium_mg": 37.5,
      "potassium_mg": 540,
      "sodium_mg": 73.5,
      "vitamin_d_ug": 14.1,
      "vitamin_b12_ug": 4.8
    },
    {
      "name": "asparagus",
      "mass_g": 80,
      "calories": 16,
      "fat_g": 0.2,
      "carbs_g": 3.2,
      "protein_g": 1.8,
      "calcium_mg": 19.2,
      "iron_mg": 1.7,
      "magnesium_mg": 11.2,
      "potassium_mg": 168,
      "sodium_mg": 1.6,
      "vitamin_d_ug": 0,
      "vitamin_b12_ug": 0
    }
  ],
  "totals": {
    "mass_g": 230,
    "calories": 296,
    "fat_g": 18.2,
    "carbs_g": 3.2,
    "protein_g": 30.3,
    "calcium_mg": 32.7,
    "iron_mg": 2.3,
    "magnesium_mg": 48.7,
    "potassium_mg": 708,
    "sodium_mg": 75.1,
    "vitamin_d_ug": 14.1,
    "vitamin_b12_ug": 4.8
  }
}

Return ONLY the JSON, no other text."""


MASS_ONLY_SYSTEM_MESSAGE = """You are a vision model that outputs only mass estimates for foods.
Return ONLY valid JSON. No explanations. No prose. No markdown.
Never include calories, macros, or totals. Do not compute energy.

CRITICAL: All foods MUST include a `form` field from this EXACT enum:
["raw","boiled","steamed","pan_seared","grilled","roasted","fried","baked","breaded","poached","stewed","simmered","cooked"]

FORBIDDEN forms (use the mapping shown):
• "whole" → use "raw"
• "fresh" → use "raw"
• "salad" → use "raw"
• "pieces" → use "cooked"
• "strips" → use "cooked"
• "cooked strips" → use "cooked"
• "toasted" → use "baked"
• DO NOT invent descriptive forms - choose only from the enum above

IMPORTANT - Color/Species Modifiers:
If the food has a color or species the alignment depends on (e.g., "green bell pepper", "pork bacon"),
include it in the optional `modifiers` field even if form is empty.
Examples: modifiers: ["green"], modifiers: ["pork"], modifiers: ["red"]

Output format (EXACTLY):
{"foods":[{"name":"...","form":"<enum>","mass_g":123,"count":1,"modifiers":["green"],"confidence":0.9}]}

No other text before or after the JSON object."""


def get_mass_only_prompt() -> str:
    """
    Get prompt for mass-only mode (no calories from vision model).

    Vision model extracts: name, mass_g, form, count (optional), modifiers (optional), confidence.
    Downstream FDC alignment computes all nutrition from mass.

    Returns:
        Formatted prompt string
    """
    return """Extract foods from this image. Return ONLY this JSON:

{"foods":[{"name":"<food>","form":"<enum>","mass_g":<number>,"count":<int?>,"modifiers":[...],"confidence":<0-1>}]}

Form enum (ONLY these values allowed):
raw|cooked|grilled|pan_seared|roasted|boiled|steamed|fried|baked|breaded|poached|stewed|simmered

CRITICAL form rules:
• NEVER use: "whole", "fresh", "salad", "pieces", "strips", "cooked strips", "toasted", "sliced"
• If raw/unprocessed → use "raw"
• If cooked but method unclear → use "cooked"
• If toasted/air-fried → use "baked"
• If cut into pieces/strips → use cooking method or "cooked" (NOT "pieces" or "strips")

Modifiers field (OPTIONAL):
• Use for colors: ["green"], ["red"], ["yellow"]
• Use for species: ["pork"], ["turkey"], ["wild"]
• Only include if alignment depends on it (e.g., green vs red bell pepper)
• Keep it short (1-2 words max)

General rules:
• Max 15 items
• Generic names (e.g., "chicken breast", "bell pepper", "rice")
• NO calories, macros, totals, or energy estimates
• count: only for discrete items (eggs, nuts, strips)
• Output MUST be valid JSON only - no other text

Few-shot examples:

1. Grilled chicken strips:
{"foods":[{"name":"chicken breast","form":"grilled","mass_g":120,"count":3,"confidence":0.85}]}

2. Fresh salad (romaine lettuce, tomato, cucumber):
{"foods":[{"name":"romaine lettuce","form":"raw","mass_g":50,"confidence":0.8},{"name":"tomato","form":"raw","mass_g":30,"confidence":0.85},{"name":"cucumber","form":"raw","mass_g":40,"confidence":0.8}]}

3. Green bell pepper and red onion:
{"foods":[{"name":"bell pepper","form":"raw","mass_g":120,"modifiers":["green"],"confidence":0.85},{"name":"onion","form":"raw","mass_g":90,"modifiers":["red"],"confidence":0.8}]}

4. Pork bacon strips:
{"foods":[{"name":"bacon","form":"pan_seared","mass_g":25,"count":3,"modifiers":["pork"],"confidence":0.9}]}

5. Toasted bagel with cream cheese:
{"foods":[{"name":"bagel","form":"baked","mass_g":85,"confidence":0.9},{"name":"cream cheese","form":"raw","mass_g":30,"confidence":0.75}]}"""


def parse_json_response(response_text: str) -> Dict[str, Any]:
    """
    Parse JSON from model response with repair logic.

    Args:
        response_text: Raw text response from model

    Returns:
        Parsed JSON object

    Raises:
        ValueError: If JSON cannot be parsed
    """
    # Try direct parse first
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code blocks
    if "```json" in response_text:
        start = response_text.find("```json") + 7
        end = response_text.find("```", start)
        if end > start:
            try:
                return json.loads(response_text[start:end].strip())
            except json.JSONDecodeError:
                pass

    # Try to extract JSON from any code block
    if "```" in response_text:
        start = response_text.find("```") + 3
        end = response_text.find("```", start)
        if end > start:
            try:
                return json.loads(response_text[start:end].strip())
            except json.JSONDecodeError:
                pass

    # Try to find JSON object boundaries
    start = response_text.find('{')
    end = response_text.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(response_text[start:end+1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from response: {response_text[:200]}...")


VALID_FORMS = ["raw", "boiled", "steamed", "pan_seared", "grilled", "roasted", "fried", "baked", "breaded", "poached", "stewed", "simmered", "cooked"]

# Form aliases for edge cases (map to closest valid enum)
# CRITICAL: These mappings prevent validation failures when vision model returns non-enum forms
FORM_ALIASES = {
    # Observed failures (from gpt_5_10images_20251024_084418.json)
    "whole": "raw",
    "whole, unpeeled": "raw",
    "salad": "raw",
    "fresh": "raw",
    "pieces": "cooked",
    "strips": "cooked",
    "cooked strips": "cooked",
    "cooked pieces": "cooked",
    "sliced": "raw",
    "chopped": "raw",
    "diced": "raw",
    "shredded": "raw",
    "halved": "raw",
    "quartered": "raw",
    "toasted": "baked",
    "halved, toasted": "baked",
    "air-fried": "baked",
    "air_fried": "baked",
    "broiled": "roasted",

    # Original aliases (keep existing)
    "sauteed": "pan_seared",
    "sautéed": "pan_seared",
    "sauté": "pan_seared",
    "microwaved": "steamed",
    "roasted_oven": "roasted",
    "battered": "breaded",

    # Additional common variants
    "raw, unprocessed": "raw",
    "uncooked": "raw",
    "deep-fried": "fried",
    "deep_fried": "fried",
    "pan-fried": "fried",
    "pan_fried": "fried",
    "stir-fried": "pan_seared",
    "stir_fried": "pan_seared",
    "oven-baked": "baked",
    "oven_baked": "baked",
    "oven-roasted": "roasted",
    "oven_roasted": "roasted",
}


def _deep_scan_forbidden(obj, forbidden_keys: set) -> str | None:
    """
    Recursively check for forbidden keys in nested structures.

    Args:
        obj: Object to scan (dict, list, or primitive)
        forbidden_keys: Set of forbidden key names

    Returns:
        First forbidden key found, or None
    """
    if isinstance(obj, dict):
        for key in obj.keys():
            if key in forbidden_keys:
                return key
            found = _deep_scan_forbidden(obj[key], forbidden_keys)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _deep_scan_forbidden(item, forbidden_keys)
            if found:
                return found
    return None


def normalize_form(form: str) -> str:
    """
    Normalize form to valid enum value using aliases, heuristics, and fallback.

    NEVER returns invalid value - guaranteed to return a value from VALID_FORMS.

    Strategy:
    1. Check if already valid enum → return as-is
    2. Exact alias match → return mapped value
    3. Heuristic keyword matching → return best match
    4. Final fallback → "cooked" (never fail)

    Args:
        form: Raw form string from model

    Returns:
        Normalized form (guaranteed to be in VALID_FORMS)
    """
    # Handle empty/None
    if not form:
        return "cooked"

    v = form.strip().lower()

    # 1. Already valid enum
    if v in VALID_FORMS:
        return v

    # 2. Exact alias match
    if v in FORM_ALIASES:
        return FORM_ALIASES[v]

    # 3. Heuristic keyword sniffing (order matters - most specific first)
    # Check for breaded/battered (before other keywords)
    if any(k in v for k in ("breaded", "batter", "crusted", "coated")):
        return "breaded"

    # Check for air-fried BEFORE checking for "fried" (more specific)
    if "air" in v and "fr" in v:
        # air-fried, air fried → baked
        return "baked"

    # Check for specific cooking methods
    if "grill" in v:
        return "grilled"

    if any(k in v for k in ("sear", "sauté", "saute")):
        return "pan_seared"

    if "fry" in v or "fried" in v:
        # Deep-fried, pan-fried → fried
        return "fried"

    if "poach" in v:
        return "poached"

    if "stew" in v:
        return "stewed"

    if "simmer" in v:
        return "simmered"

    if any(k in v for k in ("toast", "bake")):
        # Toasted, baked → baked
        return "baked"

    if any(k in v for k in ("roast", "broil")):
        return "roasted"

    if "boil" in v:
        return "boiled"

    if "steam" in v or "microwave" in v:
        return "steamed"

    # Check for raw indicators
    if any(k in v for k in ("raw", "fresh", "salad", "whole", "uncooked", "unprocessed")):
        return "raw"

    # Check for cooked indicators (generic)
    if "cooked" in v or "heated" in v or "prepared" in v:
        return "cooked"

    # Check for cut/prep descriptors (assume raw if no cooking method)
    if any(k in v for k in ("slice", "chop", "dice", "shred", "halve", "quarter", "piece", "strip")):
        # If contains cooking method keyword, would have matched above
        # So this is just a cut descriptor → raw
        return "raw"

    # 4. Final safety net - should never be reached
    print(f"[NORMALIZE_FORM] WARNING: Unknown form '{form}' - defaulting to 'cooked'")
    return "cooked"


def validate_mass_only_response(response: Dict[str, Any]) -> None:
    """
    Validate mass-only vision model response.

    Args:
        response: Parsed JSON response from vision model

    Raises:
        ValueError: If response is invalid
    """
    # Check has foods
    if "foods" not in response:
        raise ValueError("Response missing 'foods' field")

    foods = response["foods"]

    # Check not empty
    if not isinstance(foods, list) or len(foods) == 0:
        raise ValueError("Vision model returned empty foods list")

    # Check max items
    if len(foods) > 20:
        raise ValueError(f"Too many foods: {len(foods)} (max 20)")

    # Deep-scan for forbidden fields ANYWHERE in response (not just top level)
    forbidden = {"calories", "kcal_per_100g_est", "protein_g", "carbs_g", "fat_g", "totals", "cooking_method"}
    found_forbidden = _deep_scan_forbidden(response, forbidden)
    if found_forbidden:
        raise ValueError(f"Response has forbidden field: '{found_forbidden}' (vision should not estimate nutrition)")

    # Check each food
    for i, food in enumerate(foods):
        # Required fields
        if "name" not in food:
            raise ValueError(f"Food {i} missing required field: name")
        if "mass_g" not in food:
            raise ValueError(f"Food {i} missing required field: mass_g")
        if "form" not in food:
            raise ValueError(f"Food {i} missing required field: form")

        # Normalize form (handle aliases + heuristics + fallback)
        # normalize_form() NEVER returns invalid value (guaranteed valid enum)
        original_form = food["form"]
        food["form"] = normalize_form(food["form"])

        # Log if normalization changed the value (telemetry)
        if original_form != food["form"]:
            print(f"[VALIDATOR] Auto-fixed form: '{original_form}' → '{food['form']}' (food {i}: {food.get('name', 'unknown')})")

        # Validate form enum (should NEVER fail after normalize_form, but add safety)
        if food["form"] not in VALID_FORMS:
            print(f"[VALIDATOR] CRITICAL: normalize_form() returned invalid '{food['form']}' - forcing to 'cooked'")
            food["form"] = "cooked"

        # Validate mass is positive
        if not isinstance(food["mass_g"], (int, float)) or food["mass_g"] <= 0:
            raise ValueError(f"Food {i} invalid mass_g: {food['mass_g']} (must be positive number)")

        # Optional: validate confidence if present
        if "confidence" in food:
            conf = food["confidence"]
            if not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
                raise ValueError(f"Food {i} invalid confidence: {conf} (must be 0-1)")

    # Check token count (approximate)
    import json
    json_str = json.dumps(response)
    approx_tokens = len(json_str) / 4  # Rough estimate: 1 token ≈ 4 characters
    if approx_tokens > 800:
        raise ValueError(f"Response too long: ~{approx_tokens:.0f} tokens (max 800)")


def validate_response_schema(response: Dict[str, Any], include_micros: bool = False) -> bool:
    """
    Validate that response matches expected schema.

    Args:
        response: Parsed JSON response
        include_micros: Whether to check for micronutrient fields

    Returns:
        True if schema is valid, False otherwise
    """
    # Check top-level structure
    if "foods" not in response or "totals" not in response:
        return False

    if not isinstance(response["foods"], list):
        return False

    # Required fields for all modes
    required_fields = ["name", "mass_g", "calories", "fat_g", "carbs_g", "protein_g"]

    # Additional micronutrient fields
    if include_micros:
        required_fields.extend([
            "calcium_mg", "iron_mg", "magnesium_mg", "potassium_mg",
            "sodium_mg", "vitamin_d_ug", "vitamin_b12_ug"
        ])

    # Validate each food item
    for food in response["foods"]:
        if not all(field in food for field in required_fields):
            return False

    # Validate totals
    totals_fields = ["mass_g", "calories", "fat_g", "carbs_g", "protein_g"]
    if include_micros:
        totals_fields.extend([
            "calcium_mg", "iron_mg", "magnesium_mg", "potassium_mg",
            "sodium_mg", "vitamin_d_ug", "vitamin_b12_ug"
        ])

    if not all(field in response["totals"] for field in totals_fields):
        return False

    return True
