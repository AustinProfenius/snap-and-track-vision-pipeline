"""
Loader for Google Research's Nutrition5k (food-nutrients) dataset.
Dataset from: https://github.com/google-research-datasets/Nutrition5k
Cleaned version with ~3k properly aligned images and ground truth nutrition data.
"""
import json
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class Ingredient:
    """Single ingredient with nutritional data."""
    id: str
    name: str
    grams: float
    calories: float
    fat: float
    carb: float
    protein: float

    # Compatibility properties for app
    @property
    def mass_g(self) -> float:
        """Alias for grams."""
        return self.grams

    @property
    def fat_g(self) -> float:
        """Alias for fat."""
        return self.fat

    @property
    def carbs_g(self) -> float:
        """Alias for carb."""
        return self.carb

    @property
    def protein_g(self) -> float:
        """Alias for protein."""
        return self.protein

    # Micronutrients (not available, return 0)
    @property
    def calcium_mg(self) -> float:
        return 0.0

    @property
    def iron_mg(self) -> float:
        return 0.0

    @property
    def magnesium_mg(self) -> float:
        return 0.0

    @property
    def potassium_mg(self) -> float:
        return 0.0

    @property
    def sodium_mg(self) -> float:
        return 0.0

    @property
    def vitamin_d_ug(self) -> float:
        return 0.0

    @property
    def vitamin_b12_ug(self) -> float:
        return 0.0


@dataclass
class DishData:
    """Complete dish data with ground truth from food-nutrients dataset."""
    id: str
    image_filename: str
    image_path: Path
    split: str  # "test" for now

    # Ground truth totals
    total_mass: float
    total_calories: float
    total_fat: float
    total_carb: float
    total_protein: float

    # Individual ingredients
    ingredients: List[Ingredient]

    # Compatibility properties for app expecting old field names
    @property
    def dish_id(self) -> str:
        """Alias for id."""
        return self.id

    @property
    def total_mass_g(self) -> float:
        """Alias for total_mass."""
        return self.total_mass

    @property
    def total_fat_g(self) -> float:
        """Alias for total_fat."""
        return self.total_fat

    @property
    def total_carbs_g(self) -> float:
        """Alias for total_carb."""
        return self.total_carb

    @property
    def total_protein_g(self) -> float:
        """Alias for total_protein."""
        return self.total_protein

    @property
    def foods(self) -> List[Ingredient]:
        """Alias for ingredients."""
        return self.ingredients

    # Micronutrients (not available in this dataset, return 0)
    @property
    def total_calcium_mg(self) -> float:
        return 0.0

    @property
    def total_iron_mg(self) -> float:
        return 0.0

    @property
    def total_magnesium_mg(self) -> float:
        return 0.0

    @property
    def total_potassium_mg(self) -> float:
        return 0.0

    @property
    def total_sodium_mg(self) -> float:
        return 0.0

    @property
    def total_vitamin_d_ug(self) -> float:
        return 0.0

    @property
    def total_vitamin_b12_ug(self) -> float:
        return 0.0


class FoodNutrientsDataset:
    """Load and manage food-nutrients dataset from Google Research."""

    def __init__(self, dataset_root: Path):
        """
        Initialize dataset loader.

        Args:
            dataset_root: Path to food-nutrients directory
        """
        self.root = Path(dataset_root)
        self.metadata_path = self.root / "metadata.jsonl"
        self.images_dir = self.root / "test"  # All images in test/ subdirectory

        # Load data
        self.dishes = self._load_all_dishes()

    def _load_all_dishes(self) -> List[DishData]:
        """Load all dish data from JSONL metadata."""
        dishes = []

        with open(self.metadata_path, 'r') as f:
            for line in f:
                if not line.strip():
                    continue

                data = json.loads(line)

                # Parse ingredients
                ingredients = []
                for ingr_data in data.get('ingredients', []):
                    ingredient = Ingredient(
                        id=ingr_data['id'],
                        name=ingr_data['name'],
                        grams=float(ingr_data['grams']),
                        calories=float(ingr_data['calories']),
                        fat=float(ingr_data['fat']),
                        carb=float(ingr_data['carb']),
                        protein=float(ingr_data['protein'])
                    )
                    ingredients.append(ingredient)

                # Build image path (metadata has "test/dish_*.png", we need full path)
                image_filename = Path(data['file_name']).name  # Just the filename
                image_path = self.images_dir / image_filename

                # Skip if image doesn't exist
                if not image_path.exists():
                    print(f"[WARNING] Image not found: {image_path}")
                    continue

                # Create dish data
                dish = DishData(
                    id=data['id'],
                    image_filename=image_filename,
                    image_path=image_path,
                    split=data['split'],
                    total_mass=float(data['total_mass']),
                    total_calories=float(data['total_calories']),
                    total_fat=float(data['total_fat']),
                    total_carb=float(data['total_carb']),
                    total_protein=float(data['total_protein']),
                    ingredients=ingredients
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
        """Get all dishes in a split (currently only 'test')."""
        return [d for d in self.dishes if d.split == split]

    def get_statistics(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        splits = {}
        for split in ['test']:
            split_dishes = self.get_by_split(split)
            if split_dishes:
                splits[split] = len(split_dishes)

        calories = [d.total_calories for d in self.dishes]
        num_ingredients = [len(d.ingredients) for d in self.dishes]
        masses = [d.total_mass for d in self.dishes]

        return {
            'total_dishes': len(self.dishes),
            'splits': splits,
            'calories': {
                'mean': sum(calories) / len(calories) if calories else 0,
                'min': min(calories) if calories else 0,
                'max': max(calories) if calories else 0
            },
            'mass': {
                'mean': sum(masses) / len(masses) if masses else 0,
                'min': min(masses) if masses else 0,
                'max': max(masses) if masses else 0
            },
            'ingredients_per_dish': {
                'mean': sum(num_ingredients) / len(num_ingredients) if num_ingredients else 0,
                'min': min(num_ingredients) if num_ingredients else 0,
                'max': max(num_ingredients) if num_ingredients else 0
            }
        }
