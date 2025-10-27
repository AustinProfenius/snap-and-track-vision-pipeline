"""
Prediction Rails - Hard constraints for nutrition estimation quality.

Implements:
1. Energy density clamping based on food class priors
2. Count-based mass correction for discrete items
3. Plate reference scaling for bulk foods
4. Atwater factor consistency checks
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import re


class PredictionRails:
    """Post-processing rails to prevent unrealistic predictions."""

    def __init__(self, class_priors_path: Optional[Path] = None):
        """
        Initialize prediction rails with class priors.

        Args:
            class_priors_path: Path to class_priors.json file
        """
        if class_priors_path is None:
            class_priors_path = Path(__file__).parent.parent / "data" / "class_priors.json"

        with open(class_priors_path, 'r') as f:
            priors = json.load(f)

        self.energy_bands = priors["energy_density_bands"]
        self.item_masses = priors["typical_item_masses"]

    def _get_food_class_key(self, name: str, form: Optional[str] = None) -> Optional[str]:
        """
        Map food name + form to class prior key.

        Args:
            name: Food name (e.g., "rice", "spinach", "almonds")
            form: Food form (e.g., "raw", "cooked")

        Returns:
            Class key if found (e.g., "rice_cooked"), None otherwise
        """
        # Normalize name
        name_lower = name.lower().strip()
        form_lower = (form or "raw").lower().strip()

        # Try exact match first
        class_key = f"{name_lower}_{form_lower}"
        if class_key in self.energy_bands:
            return class_key

        # Try common variations
        for key in self.energy_bands.keys():
            if name_lower in key and form_lower in key:
                return key

        # Try without form
        for key in self.energy_bands.keys():
            if name_lower in key:
                return key

        return None

    def apply_energy_density_clamp(self, food_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clamp energy density to plausible range based on food class.

        If model's kcal_per_100g_est is outside the class band, pull it toward
        the band center using Huber clamp (soft beyond 1 std, hard beyond range).

        Args:
            food_item: Food dict with name, form, mass_g, calories, kcal_per_100g_est

        Returns:
            Modified food_item with clamped energy density
        """
        name = food_item.get("name", "")
        form = food_item.get("form")
        model_kcal_100g = food_item.get("kcal_per_100g_est")

        if not model_kcal_100g:
            # No estimate to clamp
            return food_item

        class_key = self._get_food_class_key(name, form)
        if not class_key:
            # No prior for this food
            print(f"[RAILS] No energy density prior for {name} ({form})")
            return food_item

        band = self.energy_bands[class_key]
        mean_kcal = band["mean"]
        min_kcal = band["min"]
        max_kcal = band["max"]
        std_kcal = band.get("std", (max_kcal - min_kcal) / 4)

        # Check if outside range
        if model_kcal_100g < min_kcal or model_kcal_100g > max_kcal:
            # Huber clamp: pull toward mean
            # If slightly outside (within 2 std), soft pull (70% toward mean)
            # If far outside, hard clamp to boundary

            if model_kcal_100g < min_kcal:
                if model_kcal_100g >= mean_kcal - 2 * std_kcal:
                    # Soft pull
                    clamped = model_kcal_100g * 0.3 + mean_kcal * 0.7
                else:
                    # Hard clamp
                    clamped = min_kcal
            else:  # model_kcal_100g > max_kcal
                if model_kcal_100g <= mean_kcal + 2 * std_kcal:
                    # Soft pull
                    clamped = model_kcal_100g * 0.3 + mean_kcal * 0.7
                else:
                    # Hard clamp
                    clamped = max_kcal

            print(f"[RAILS] Energy density clamp for {name}: {model_kcal_100g:.1f} → {clamped:.1f} kcal/100g (expected {min_kcal}-{max_kcal})")

            # Recalculate calories or mass to maintain consistency
            mass_g = food_item.get("mass_g", 0)
            if mass_g > 0:
                # Recalculate calories from clamped density
                new_calories = (mass_g / 100) * clamped
                food_item["calories"] = new_calories
                food_item["kcal_per_100g_est"] = clamped
                food_item["_rails_applied"] = food_item.get("_rails_applied", []) + ["energy_clamp"]

        return food_item

    def apply_count_mass_correction(self, food_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Override mass estimate using count × typical_mass for discrete items.

        Blends 70% count-based with 30% model estimate.

        Args:
            food_item: Food dict with name, count (optional), mass_g

        Returns:
            Modified food_item with corrected mass
        """
        count = food_item.get("count")
        if not count or count <= 0:
            # No count provided
            return food_item

        name = food_item.get("name", "").lower().strip()

        # Find matching item mass prior
        item_key = None
        for key in self.item_masses.keys():
            if key in name or name in key:
                item_key = key
                break

        if not item_key:
            # No typical mass for this item
            print(f"[RAILS] No typical mass prior for discrete item: {name}")
            return food_item

        typical_mass = self.item_masses[item_key]
        avg_mass_per_item = typical_mass["mean"]

        # Calculate count-based mass
        count_based_mass = count * avg_mass_per_item

        # Blend with model estimate (70% count-based, 30% model)
        model_mass = food_item.get("mass_g", count_based_mass)
        blended_mass = count_based_mass * 0.7 + model_mass * 0.3

        if abs(model_mass - blended_mass) / model_mass > 0.15:  # >15% difference
            print(f"[RAILS] Count-mass correction for {name}: {count} items × {avg_mass_per_item:.1f}g = {count_based_mass:.1f}g (model: {model_mass:.1f}g, using blended: {blended_mass:.1f}g)")

            # Update mass and recalculate calories if kcal_per_100g_est available
            food_item["mass_g"] = blended_mass

            kcal_100g = food_item.get("kcal_per_100g_est")
            if kcal_100g:
                food_item["calories"] = (blended_mass / 100) * kcal_100g

            food_item["_rails_applied"] = food_item.get("_rails_applied", []) + ["count_mass_correction"]

        return food_item

    def apply_atwater_consistency_check(self, food_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify calories are consistent with Atwater factors.

        Atwater: 4 kcal/g protein, 4 kcal/g carbs, 9 kcal/g fat, 2 kcal/g fiber

        Args:
            food_item: Food dict with protein_g, carbs_g, fat_g, calories

        Returns:
            Modified food_item with warning if inconsistent
        """
        protein_g = food_item.get("protein_g", 0)
        carbs_g = food_item.get("carbs_g", 0)
        fat_g = food_item.get("fat_g", 0)
        calories = food_item.get("calories", 0)

        # Calculate Atwater calories (simplified, no fiber adjustment)
        atwater_calories = 4 * protein_g + 4 * carbs_g + 9 * fat_g

        if calories > 0 and atwater_calories > 0:
            diff_pct = abs(calories - atwater_calories) / calories * 100

            if diff_pct > 15:  # >15% deviation
                print(f"[RAILS] WARNING: Atwater inconsistency for {food_item.get('name')}: "
                      f"stated {calories:.1f} kcal vs calculated {atwater_calories:.1f} kcal ({diff_pct:.1f}% diff)")
                food_item["_atwater_deviation_pct"] = diff_pct

        return food_item

    def apply_all_rails(self, prediction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply all prediction rails to a complete prediction.

        Args:
            prediction: Full prediction dict with foods array

        Returns:
            Modified prediction with rails applied
        """
        if "foods" not in prediction:
            return prediction

        modified_foods = []
        for food in prediction["foods"]:
            # Apply rails in sequence
            food = self.apply_energy_density_clamp(food)
            food = self.apply_count_mass_correction(food)
            food = self.apply_atwater_consistency_check(food)
            modified_foods.append(food)

        # Update prediction
        prediction["foods"] = modified_foods

        # Recalculate totals
        prediction["totals"] = {
            "mass_g": sum(f.get("mass_g", 0) for f in modified_foods),
            "calories": sum(f.get("calories", 0) for f in modified_foods),
            "protein_g": sum(f.get("protein_g", 0) for f in modified_foods),
            "carbs_g": sum(f.get("carbs_g", 0) for f in modified_foods),
            "fat_g": sum(f.get("fat_g", 0) for f in modified_foods)
        }

        return prediction
