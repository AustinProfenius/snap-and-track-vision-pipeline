"""
Optimized loader for NutritionVerse dataset with CSV-based metadata.
"""
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class FoodItem:
    """Single food item with nutritional data."""
    name: str
    mass_g: float
    calories: float
    fat_g: float
    carbs_g: float
    protein_g: float
    # Micronutrients
    calcium_mg: float = 0.0
    iron_mg: float = 0.0
    magnesium_mg: float = 0.0
    potassium_mg: float = 0.0
    sodium_mg: float = 0.0
    vitamin_d_ug: float = 0.0
    vitamin_b12_ug: float = 0.0


@dataclass
class DishData:
    """Complete dish data with ground truth."""
    dish_id: int
    image_filename: str
    image_path: Path
    split: str  # Train, Val, Test

    # Ground truth totals
    total_mass_g: float
    total_calories: float
    total_fat_g: float
    total_carbs_g: float
    total_protein_g: float
    total_calcium_mg: float
    total_iron_mg: float
    total_magnesium_mg: float
    total_potassium_mg: float
    total_sodium_mg: float
    total_vitamin_d_ug: float
    total_vitamin_b12_ug: float

    # Individual food items
    foods: List[FoodItem]


class NutritionVerseDataset:
    """Load and manage NutritionVerse dataset."""

    def __init__(self, dataset_root: Path):
        """
        Initialize dataset loader.

        Args:
            dataset_root: Path to nutritionverse directory
        """
        self.root = Path(dataset_root)
        self.metadata_path = self.root / "nutritionverse_dish_metadata3.csv"
        self.images_dir = self.root / "nutritionverse-manual" / "nutritionverse-manual" / "images"
        self.splits_path = self.root / "nutritionverse-manual" / "nutritionverse-manual" / "updated-manual-dataset-splits.csv"

        # Load data
        self.metadata_df = pd.read_csv(self.metadata_path)
        self.splits_df = pd.read_csv(self.splits_path)

        # Create filename to split mapping
        self.filename_to_split = dict(zip(self.splits_df['file_name'], self.splits_df['category']))

        # Build dish index
        self.dishes = self._load_all_dishes()

    def _load_all_dishes(self) -> List[DishData]:
        """Load all dish data from CSV - creates one entry per IMAGE."""
        dishes = []

        for _, row in self.metadata_df.iterrows():
            dish_id = int(row['dish_id'])

            # Parse food items (same for all images of this dish)
            foods = []
            for i in range(1, 8):  # up to 7 food items
                food_type_col = f'food_item_type_{i}'
                if food_type_col not in row or pd.isna(row[food_type_col]):
                    break

                food = FoodItem(
                    name=str(row[food_type_col]),
                    mass_g=float(row[f'food_weight_g_{i}']),
                    calories=float(row[f'calories(kCal)_{i}']),
                    fat_g=float(row[f'fat(g)_{i}']),
                    carbs_g=float(row[f'carbohydrates(g)_{i}']),
                    protein_g=float(row[f'protein(g)_{i}']),
                    calcium_mg=float(row[f'calcium(mg)_{i}']),
                    iron_mg=float(row[f'iron(mg)_{i}']),
                    magnesium_mg=float(row[f'magnesium(mg)_{i}']),
                    potassium_mg=float(row[f'potassium(mg)_{i}']),
                    sodium_mg=float(row[f'sodium(mg)_{i}']),
                    vitamin_d_ug=float(row[f'vitamin_d(µg)_{i}']),
                    vitamin_b12_ug=float(row[f'vitamin_b12(µg)_{i}'])
                )
                foods.append(food)

            # Find ALL matching image files for this dish
            image_files = sorted(list(self.images_dir.glob(f"dish_{dish_id}_*.jpg")))
            if not image_files:
                continue

            # Create separate entry for EACH image of this dish
            # This ensures image shown in UI matches image sent to API
            for image_file in image_files:
                split = self.filename_to_split.get(image_file.name, "Unknown")

                dish = DishData(
                    dish_id=dish_id,
                    image_filename=image_file.name,
                    image_path=image_file,
                    split=split,
                    total_mass_g=float(row['total_food_weight']),
                    total_calories=float(row['total_calories']),
                    total_fat_g=float(row['total_fats']),
                    total_carbs_g=float(row['total_carbohydrates']),
                    total_protein_g=float(row['total_protein']),
                    total_calcium_mg=float(row['total_calcium']),
                    total_iron_mg=float(row['total_iron']),
                    total_magnesium_mg=float(row['total_magnesium']),
                    total_potassium_mg=float(row['total_potassium']),
                    total_sodium_mg=float(row['total_sodium']),
                    total_vitamin_d_ug=float(row['total_vitamin_d']),
                    total_vitamin_b12_ug=float(row['total_vitamin_b12']),
                    foods=foods
                )
                dishes.append(dish)

        return dishes

    def __len__(self) -> int:
        """Get total number of dishes."""
        return len(self.dishes)

    def __getitem__(self, idx: int) -> DishData:
        """Get dish by index."""
        return self.dishes[idx]

    def get_by_split(self, split: str) -> List[DishData]:
        """Get all dishes in a split (Train, Val, Test)."""
        return [d for d in self.dishes if d.split == split]

    def get_statistics(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        splits = {}
        for split in ['Train', 'Val', 'Test', 'Unknown']:
            split_dishes = self.get_by_split(split)
            if split_dishes:
                splits[split] = len(split_dishes)

        calories = [d.total_calories for d in self.dishes]
        num_foods = [len(d.foods) for d in self.dishes]

        return {
            'total_dishes': len(self.dishes),
            'splits': splits,
            'calories': {
                'mean': sum(calories) / len(calories) if calories else 0,
                'min': min(calories) if calories else 0,
                'max': max(calories) if calories else 0
            },
            'foods_per_dish': {
                'mean': sum(num_foods) / len(num_foods) if num_foods else 0,
                'min': min(num_foods) if num_foods else 0,
                'max': max(num_foods) if num_foods else 0
            }
        }
