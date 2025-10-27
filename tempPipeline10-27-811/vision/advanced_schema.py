"""
Advanced JSON Schema for nutrition estimation with FDC database integration.
Implements two-pass detection workflow with uncertainty quantification.
"""

# Enhanced JSON Schema for meal estimation
MEAL_ESTIMATE_SCHEMA = {
    "name": "MealEstimate",
    "schema": {
        "type": "object",
        "required": ["items", "totals", "uncertainty", "notes"],
        "additionalProperties": False,
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "fdc_candidates", "portion_estimate_g", "macros", "calories_kcal", "confidence"],
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string", "description": "Food item name as detected in image"},
                        "fdc_candidates": {
                            "type": "array",
                            "description": "Top 1-3 USDA FDC database candidates",
                            "items": {
                                "type": "object",
                                "required": ["fdc_id", "match_name", "confidence"],
                                "additionalProperties": False,
                                "properties": {
                                    "fdc_id": {"type": "string", "description": "FDC database ID"},
                                    "match_name": {"type": "string", "description": "Full FDC food name"},
                                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                                }
                            }
                        },
                        "portion_estimate_g": {
                            "type": "number",
                            "minimum": 0,
                            "description": "Estimated portion mass in grams"
                        },
                        "macros": {
                            "type": "object",
                            "required": ["protein_g", "carbs_g", "fat_g"],
                            "additionalProperties": False,
                            "properties": {
                                "protein_g": {"type": "number", "minimum": 0},
                                "carbs_g": {"type": "number", "minimum": 0},
                                "fat_g": {"type": "number", "minimum": 0}
                            }
                        },
                        "calories_kcal": {"type": "number", "minimum": 0},
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Overall confidence in this item's estimation"
                        }
                    }
                }
            },
            "totals": {
                "type": "object",
                "required": ["mass_g", "protein_g", "carbs_g", "fat_g", "calories_kcal"],
                "additionalProperties": False,
                "properties": {
                    "mass_g": {"type": "number", "minimum": 0},
                    "protein_g": {"type": "number", "minimum": 0},
                    "carbs_g": {"type": "number", "minimum": 0},
                    "fat_g": {"type": "number", "minimum": 0},
                    "calories_kcal": {"type": "number", "minimum": 0}
                }
            },
            "uncertainty": {
                "type": "object",
                "required": ["kcal_low", "kcal_high", "mass_low_g", "mass_high_g"],
                "additionalProperties": False,
                "properties": {
                    "kcal_low": {"type": "number", "description": "5th percentile calorie estimate"},
                    "kcal_high": {"type": "number", "description": "95th percentile calorie estimate"},
                    "mass_low_g": {"type": "number", "description": "5th percentile mass estimate"},
                    "mass_high_g": {"type": "number", "description": "95th percentile mass estimate"}
                }
            },
            "notes": {
                "type": "object",
                "required": ["assumptions", "ambiguities", "recommended_followups"],
                "additionalProperties": False,
                "properties": {
                    "assumptions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key assumptions made during estimation"
                    },
                    "ambiguities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Unclear aspects that increase uncertainty"
                    },
                    "recommended_followups": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Suggested additional photos/angles to improve accuracy"
                    }
                }
            }
        }
    },
    "strict": True
}


# Detection-only schema for Pass A (two-pass workflow)
DETECTION_SCHEMA = {
    "name": "FoodDetection",
    "schema": {
        "type": "object",
        "required": ["items", "context"],
        "additionalProperties": False,
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "portion_estimate_g", "confidence"],
                    "additionalProperties": False,
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Detected food item name (simple, searchable)"
                        },
                        "portion_estimate_g": {
                            "type": "number",
                            "minimum": 0,
                            "description": "Best estimate of portion mass in grams"
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1
                        }
                    }
                }
            },
            "context": {
                "type": "object",
                "required": ["assumptions", "ambiguities"],
                "additionalProperties": False,
                "properties": {
                    "assumptions": {"type": "array", "items": {"type": "string"}},
                    "ambiguities": {"type": "array", "items": {"type": "string"}}
                }
            }
        }
    },
    "strict": True
}
