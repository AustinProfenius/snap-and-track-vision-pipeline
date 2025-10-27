"""
Prompt templates for nutrition estimation tasks.
"""
from typing import Dict, Any
import json


SYSTEM_MESSAGE = """You are a professional nutrition analyst with expertise in food recognition and nutritional estimation.

Your task is to analyze food images and provide accurate nutritional information in a structured JSON format.

CRITICAL INSTRUCTIONS:
- Return ONLY valid JSON matching the exact schema provided
- Do NOT add any extra fields or keys
- Do NOT include explanatory text before or after the JSON
- If you cannot identify something, use empty strings for names or 0 for numbers
- Be as accurate as possible with mass and nutrition estimates

IMPORTANT - Food Item Identification:
- ALWAYS identify each food item separately - NEVER group them as "mixed greens", "mixed vegetables", etc.
- If you see multiple vegetables/items, list EACH ONE individually with separate estimates
- Example: Instead of "mixed greens", list "spinach", "romaine lettuce", "arugula" as separate items

IMPORTANT - Food Naming Convention:
- Use ONLY base food names WITHOUT cooking method adjectives
- DO NOT use: "steamed", "cooked", "grilled", "roasted", "baked", "fried", "boiled", "sautéed"
- ✓ Good: "broccoli", "chicken breast", "white rice", "salmon"
- ✗ NEVER: "steamed broccoli", "grilled chicken breast", "cooked rice", "baked salmon"
- Exception: Only include cooking method if it fundamentally changes the food (e.g., "popcorn" vs "corn")"""


def get_prompt_template(task: str) -> str:
    """Get the appropriate prompt template for a task."""
    templates = {
        "dish_totals": DISH_TOTALS_TEMPLATE,
        "itemized": ITEMIZED_TEMPLATE,
        "names_only": NAMES_ONLY_TEMPLATE
    }

    return templates.get(task, ITEMIZED_TEMPLATE)


DISH_TOTALS_TEMPLATE = """Analyze this food image and estimate the TOTAL nutritional content for the entire dish.

You must return a JSON object matching this exact schema:

{
  "dish_id": "string (leave empty, will be filled automatically)",
  "image_relpath": "string (leave empty, will be filled automatically)",
  "foods": [],
  "totals": {
    "mass_g": number,
    "calories_kcal": number,
    "macros_g": {
      "protein": number,
      "carbs": number,
      "fat": number
    }
  }
}

Focus on providing accurate estimates for:
1. Total mass of all food in grams
2. Total calories (kcal)
3. Total macronutrients: protein, carbohydrates, and fat in grams

Example output:
{
  "dish_id": "",
  "image_relpath": "",
  "foods": [],
  "totals": {
    "mass_g": 350,
    "calories_kcal": 520,
    "macros_g": {
      "protein": 35,
      "carbs": 45,
      "fat": 18
    }
  }
}

Return ONLY the JSON, no other text."""


ITEMIZED_TEMPLATE = """Analyze this food image and identify each individual food item with detailed nutritional estimates.

CRITICAL:
- Identify EACH food item separately - NEVER group as "mixed greens", "mixed vegetables", "salad"
- Use ONLY base food names WITHOUT cooking methods (e.g., "chicken breast" not "grilled chicken breast")

You must return a JSON object matching this exact schema:

{
  "dish_id": "string (leave empty, will be filled automatically)",
  "image_relpath": "string (leave empty, will be filled automatically)",
  "foods": [
    {
      "name": "string (specific food item name - base name only, no cooking methods)",
      "mass_g": number,
      "calories_kcal": number,
      "macros_g": {
        "protein": number,
        "carbs": number,
        "fat": number
      }
    }
  ],
  "totals": {
    "mass_g": number,
    "calories_kcal": number,
    "macros_g": {
      "protein": number,
      "carbs": number,
      "fat": number
    }
  }
}

For each food item, provide:
1. Base food name WITHOUT cooking methods (e.g., "chicken breast", "broccoli", "white rice")
2. Estimated mass in grams
3. Estimated calories (kcal)
4. Estimated macronutrients (protein, carbs, fat) in grams

The "totals" field should be the sum of all individual food items.

Example output:
{
  "dish_id": "",
  "image_relpath": "",
  "foods": [
    {
      "name": "chicken breast",
      "mass_g": 150,
      "calories_kcal": 248,
      "macros_g": {
        "protein": 47,
        "carbs": 0,
        "fat": 5
      }
    },
    {
      "name": "brown rice",
      "mass_g": 200,
      "calories_kcal": 218,
      "macros_g": {
        "protein": 5,
        "carbs": 45,
        "fat": 2
      }
    }
  ],
  "totals": {
    "mass_g": 350,
    "calories_kcal": 466,
    "macros_g": {
      "protein": 52,
      "carbs": 45,
      "fat": 7
    }
  }
}

Return ONLY the JSON, no other text."""


NAMES_ONLY_TEMPLATE = """Analyze this food image and identify each individual food item by name.

CRITICAL:
- Identify EACH food item separately - NEVER group as "mixed greens", "mixed vegetables", "salad"
- Use ONLY base food names WITHOUT cooking methods (e.g., "chicken breast" not "grilled chicken breast")

You must return a JSON object matching this exact schema:

{
  "dish_id": "string (leave empty, will be filled automatically)",
  "image_relpath": "string (leave empty, will be filled automatically)",
  "foods": [
    {
      "name": "string (base food name only - no cooking methods)",
      "mass_g": 0,
      "calories_kcal": 0,
      "macros_g": {
        "protein": 0,
        "carbs": 0,
        "fat": 0
      }
    }
  ],
  "totals": {
    "mass_g": 0,
    "calories_kcal": 0,
    "macros_g": {
      "protein": 0,
      "carbs": 0,
      "fat": 0
    }
  }
}

For each food item, provide ONLY:
1. Base food name WITHOUT cooking methods (e.g., "chicken breast", "broccoli", "olive oil")

Set all numerical fields to 0.

Example output:
{
  "dish_id": "",
  "image_relpath": "",
  "foods": [
    {
      "name": "chicken breast",
      "mass_g": 0,
      "calories_kcal": 0,
      "macros_g": {"protein": 0, "carbs": 0, "fat": 0}
    },
    {
      "name": "brown rice",
      "mass_g": 0,
      "calories_kcal": 0,
      "macros_g": {"protein": 0, "carbs": 0, "fat": 0}
    },
    {
      "name": "broccoli",
      "mass_g": 0,
      "calories_kcal": 0,
      "macros_g": {"protein": 0, "carbs": 0, "fat": 0}
    }
  ],
  "totals": {
    "mass_g": 0,
    "calories_kcal": 0,
    "macros_g": {"protein": 0, "carbs": 0, "fat": 0}
  }
}

Return ONLY the JSON, no other text."""


def build_user_prompt(task: str, dish_id: str = "", image_path: str = "") -> str:
    """
    Build the user prompt for a specific task.

    Args:
        task: Task name (dish_totals, itemized, names_only)
        dish_id: Optional dish ID for context
        image_path: Optional image path for context

    Returns:
        Formatted user prompt
    """
    template = get_prompt_template(task)

    # Could add dish_id or other context here if needed
    return template


def parse_json_response(response_text: str) -> Dict[str, Any]:
    """
    Parse JSON from model response, attempting to extract/repair if needed.

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


def validate_response_schema(response: Dict[str, Any]) -> bool:
    """
    Validate that response matches the expected uniform schema.

    Args:
        response: Parsed JSON response

    Returns:
        True if schema is valid, False otherwise
    """
    required_fields = ["dish_id", "image_relpath", "foods", "totals"]

    # Check top-level fields
    if not all(field in response for field in required_fields):
        return False

    # Check foods array
    if not isinstance(response["foods"], list):
        return False

    for food in response["foods"]:
        if not all(key in food for key in ["name", "mass_g", "calories_kcal", "macros_g"]):
            return False
        if not all(key in food["macros_g"] for key in ["protein", "carbs", "fat"]):
            return False

    # Check totals
    totals = response["totals"]
    if not all(key in totals for key in ["mass_g", "calories_kcal", "macros_g"]):
        return False
    if not all(key in totals["macros_g"] for key in ["protein", "carbs", "fat"]):
        return False

    return True
