"""
FDC Database Alignment Module

Matches predicted foods to FDC database entries and computes nutrition
based on predicted calories for three-way comparison (Ground Truth vs Predicted vs Database-Aligned).
"""
from typing import Dict, List, Optional, Any
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Import FDC database connector
try:
    from .fdc_database import FDCDatabase
    FDC_AVAILABLE = True
except ImportError:
    FDC_AVAILABLE = False


class FDCAlignmentEngine:
    """
    Aligns predicted foods with FDC database entries and computes nutrition.
    """

    def __init__(self):
        """Initialize FDC alignment engine."""
        # Reload environment in case .env changed
        load_dotenv(override=True)

        # Check if database module is available
        if not FDC_AVAILABLE:
            self.db_available = False
            print("[WARNING] FDC database module not available. Alignment features disabled.")
            return

        # Check if connection URL is set
        connection_url = os.getenv("NEON_CONNECTION_URL")
        if not connection_url:
            self.db_available = False
            print("[WARNING] NEON_CONNECTION_URL not set. Alignment features disabled.")
            return

        # Try to test connection
        try:
            with FDCDatabase(connection_url) as db:
                # Just test the connection works
                pass
            self.db_available = True
            print("[INFO] FDC database alignment enabled.")
        except Exception as e:
            self.db_available = False
            print(f"[WARNING] FDC database connection failed: {e}. Alignment features disabled.")

    def search_best_match(self, food_name: str, data_types: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        Search FDC database for best matching food.

        Args:
            food_name: Name of predicted food
            data_types: Food data types to search (default: foundation_food only)

        Returns:
            Best match dict with fdc_id, name, confidence, and base nutrition (per 100g)
        """
        print(f"[ALIGN] Searching for food: '{food_name}'")

        if not self.db_available:
            print(f"[ALIGN] Database not available, skipping search")
            return None

        if data_types is None:
            data_types = ["foundation_food"]  # Only use foundation foods

        try:
            with FDCDatabase() as db:
                # Try full name first
                results = db.search_foods(
                    query=food_name,
                    limit=3,
                    data_types=data_types
                )

                # If no results, try extracting key words
                if not results:
                    # Extract meaningful noun (skip modifiers and look for main food item)
                    skip_words = {"fresh", "raw", "cooked", "boiled", "fried", "grilled", "roasted",
                                 "steamed", "baked", "with", "without", "medium", "large", "small",
                                 "shredded", "sliced", "diced", "chopped", "minced", "piece", "pieces"}
                    words = food_name.lower().split()
                    key_words = []

                    for word in words:
                        # Remove parentheses and commas
                        clean_word = word.strip("(),")
                        if clean_word and clean_word not in skip_words and len(clean_word) > 3:
                            key_words.append(clean_word)

                    # Try each key word until we find matches
                    for key_word in key_words:
                        print(f"[ALIGN] No direct match, trying key word: '{key_word}'")

                        # Try plural form first (apples, carrots, etc.) to avoid substring matches
                        plural_key = key_word + "s" if not key_word.endswith('s') else key_word
                        plural_results = db.search_foods(
                            query=plural_key,
                            limit=5,
                            data_types=data_types
                        )

                        if plural_results:
                            # Filter to prefer raw foods
                            raw_plural = [r for r in plural_results if 'raw' in r['name'].lower()]
                            if raw_plural:
                                results = raw_plural
                                print(f"[ALIGN] Found {len(results)} raw {plural_key} entries")
                            else:
                                results = plural_results
                                print(f"[ALIGN] Found {len(results)} {plural_key} entries")

                        if not plural_results:
                            # Fall back to singular "key_word raw"
                            raw_results = db.search_foods(
                                query=f"{key_word} raw",
                                limit=5,
                                data_types=data_types
                            )

                            if raw_results:
                                # Filter to prefer foods that start with the key word
                                # (e.g., prefer "Apples raw" over "Pineapple raw" when searching for "apple")
                                starting_results = [r for r in raw_results if r['name'].lower().startswith(key_word)]
                                if starting_results:
                                    results = starting_results
                                    print(f"[ALIGN] Found {len(results)} raw {key_word} entries starting with '{key_word}'")
                                else:
                                    results = raw_results
                                    print(f"[ALIGN] Found {len(results)} raw {key_word} entries")
                            else:
                                # Fall back to just the key word
                                results = db.search_foods(
                                    query=key_word,
                                    limit=5,
                                    data_types=data_types
                                )
                                if results:
                                    print(f"[ALIGN] Found {len(results)} {key_word} entries")
                                    # Filter results to prefer raw/simple foods over prepared dishes
                                    simple_results = []
                                    for r in results:
                                        name_lower = r['name'].lower()
                                        # Prefer foods with "raw" or that start with the key word
                                        if 'raw' in name_lower or name_lower.startswith(key_word):
                                            simple_results.append(r)

                                    if simple_results:
                                        results = simple_results
                                        print(f"[ALIGN] Filtered to {len(results)} simple entries")

                        if results:
                            break

                if not results:
                    print(f"[ALIGN] No match found for '{food_name}'")
                    return None

                print(f"[ALIGN] Found {len(results)} potential matches")

                # Return best match
                match = results[0]
                print(f"[ALIGN] Found match: {match['name']} (FDC: {match['fdc_id']})")

                base_nutrition = {
                    "calories": float(match.get("calories_value", 0) or 0),
                    "protein_g": float(match.get("protein_value", 0) or 0),
                    "carbs_g": float(match.get("carbohydrates_value", 0) or 0),
                    "fat_g": float(match.get("total_fat_value", 0) or 0)
                }
                print(f"[ALIGN] Base nutrition (per 100g): {base_nutrition}")

                return {
                    "fdc_id": match["fdc_id"],
                    "name": match["name"],
                    "data_type": match.get("data_type", "unknown"),
                    "confidence": 0.85,  # Default confidence for search match
                    "base_nutrition_per_100g": base_nutrition
                }

        except Exception as e:
            print(f"[ERROR] FDC search failed for '{food_name}': {e}")
            import traceback
            traceback.print_exc()
            return None

    def compute_nutrition_from_calories(self, base_nutrition_per_100g: Dict[str, float],
                                       target_calories: float) -> Dict[str, float]:
        """
        Compute nutrition values scaled from database based on target calories.

        Args:
            base_nutrition_per_100g: Base nutrition per 100g from database
            target_calories: Predicted calories to match

        Returns:
            Scaled nutrition dict with mass_g, calories, protein_g, carbs_g, fat_g
        """
        print(f"[ALIGN] Computing nutrition for {target_calories} kcal")
        print(f"[ALIGN] Base nutrition: {base_nutrition_per_100g}")

        base_cal_per_100g = base_nutrition_per_100g.get("calories", 0)

        if base_cal_per_100g == 0:
            print(f"[ALIGN] WARNING: Base calories is 0, cannot scale")
            # Cannot scale if no calorie reference
            return {
                "mass_g": 0,
                "calories": 0,
                "protein_g": 0,
                "carbs_g": 0,
                "fat_g": 0
            }

        # Calculate required mass to achieve target calories
        # target_calories = base_cal_per_100g * (mass_g / 100)
        # mass_g = (target_calories / base_cal_per_100g) * 100
        mass_g = (target_calories / base_cal_per_100g) * 100

        # Scale all nutrients proportionally
        scale_factor = mass_g / 100

        result = {
            "mass_g": mass_g,
            "calories": target_calories,  # Use exact predicted calories
            "protein_g": base_nutrition_per_100g.get("protein_g", 0) * scale_factor,
            "carbs_g": base_nutrition_per_100g.get("carbs_g", 0) * scale_factor,
            "fat_g": base_nutrition_per_100g.get("fat_g", 0) * scale_factor
        }
        print(f"[ALIGN] Computed nutrition: {result}")
        return result

    def align_predicted_food(self, food_name: str, predicted_calories: float) -> Optional[Dict[str, Any]]:
        """
        Align a single predicted food to FDC database and compute nutrition.

        Args:
            food_name: Predicted food name
            predicted_calories: Predicted calorie value

        Returns:
            Dict with matched food info and computed nutrition, or None if no match
        """
        # Search for best match
        match = self.search_best_match(food_name)

        if not match:
            return None

        # Compute nutrition based on predicted calories
        nutrition = self.compute_nutrition_from_calories(
            match["base_nutrition_per_100g"],
            predicted_calories
        )

        return {
            "fdc_id": match["fdc_id"],
            "matched_name": match["name"],
            "data_type": match["data_type"],
            "confidence": match["confidence"],
            "nutrition": nutrition
        }

    def align_prediction_batch(self, prediction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Align all foods in a prediction to FDC database.

        Args:
            prediction: Full prediction dict with "foods" list

        Returns:
            Dict with per-food alignments and totals
        """
        print(f"[ALIGN] ===== Starting batch alignment =====")
        print(f"[ALIGN] DB Available: {self.db_available}")

        if not self.db_available:
            print(f"[ALIGN] Database not available, returning empty result")
            return {
                "available": False,
                "foods": [],
                "totals": {
                    "mass_g": 0,
                    "calories": 0,
                    "protein_g": 0,
                    "carbs_g": 0,
                    "fat_g": 0
                }
            }

        foods_list = prediction.get("foods", [])
        print(f"[ALIGN] Processing {len(foods_list)} foods from prediction")

        aligned_foods = []
        total_mass = 0
        total_calories = 0
        total_protein = 0
        total_carbs = 0
        total_fat = 0

        for i, food in enumerate(foods_list):
            food_name = food.get("name", "")
            pred_calories = food.get("calories", 0)

            print(f"[ALIGN] Food {i+1}: '{food_name}' with {pred_calories} kcal")

            # Skip if no name or calories
            if not food_name or pred_calories <= 0:
                print(f"[ALIGN] Skipping food {i+1}: empty name or zero calories")
                continue

            # Align to database
            alignment = self.align_predicted_food(food_name, pred_calories)

            if alignment:
                aligned_foods.append({
                    "predicted_name": food_name,
                    "fdc_id": alignment["fdc_id"],
                    "matched_name": alignment["matched_name"],
                    "data_type": alignment["data_type"],
                    "confidence": alignment["confidence"],
                    "nutrition": alignment["nutrition"]
                })

                # Add to totals
                total_mass += alignment["nutrition"]["mass_g"]
                total_calories += alignment["nutrition"]["calories"]
                total_protein += alignment["nutrition"]["protein_g"]
                total_carbs += alignment["nutrition"]["carbs_g"]
                total_fat += alignment["nutrition"]["fat_g"]

                print(f"[ALIGN] Food {i+1} aligned successfully")
            else:
                print(f"[ALIGN] Food {i+1} failed to align")

        print(f"[ALIGN] Batch alignment complete: {len(aligned_foods)} foods aligned")
        print(f"[ALIGN] Totals: {total_mass:.1f}g, {total_calories:.1f} kcal")

        return {
            "available": True,
            "foods": aligned_foods,
            "totals": {
                "mass_g": total_mass,
                "calories": total_calories,
                "protein_g": total_protein,
                "carbs_g": total_carbs,
                "fat_g": total_fat
            }
        }
