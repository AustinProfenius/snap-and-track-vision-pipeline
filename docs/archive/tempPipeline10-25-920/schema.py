"""
Schema discovery and mapping utilities for NutritionVerse-Real dataset.
"""
import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict


class SchemaDiscovery:
    """Discover and map dataset schema to uniform JSON format."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)

    def inspect_annotations(self, sample_size: int = 5) -> Dict[str, Any]:
        """
        Inspect a sample of annotations to infer schema structure.

        Args:
            sample_size: Number of annotation files to sample

        Returns:
            Inferred schema mapping
        """
        annotation_files = list(self.data_dir.glob("**/*.json"))[:sample_size]

        if not annotation_files:
            raise ValueError(f"No annotation files found in {self.data_dir}")

        # Collect field paths from samples
        field_paths = defaultdict(list)

        for ann_file in annotation_files:
            with open(ann_file) as f:
                data = json.load(f)
                self._extract_paths(data, "", field_paths)

        # Infer the schema mapping
        schema_map = self._infer_mapping(field_paths, annotation_files[0])

        return schema_map

    def _extract_paths(self, obj: Any, prefix: str, paths: Dict[str, List]):
        """Recursively extract all field paths from a nested object."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_prefix = f"{prefix}.{key}" if prefix else key
                paths[new_prefix].append(type(value).__name__)
                self._extract_paths(value, new_prefix, paths)
        elif isinstance(obj, list) and obj:
            # Sample first item of list
            new_prefix = f"{prefix}[*]"
            self._extract_paths(obj[0], new_prefix, paths)

    def _infer_mapping(self, paths: Dict[str, List], sample_file: Path) -> Dict[str, Any]:
        """
        Infer schema mapping based on common field names and types.

        Args:
            paths: Dictionary of field paths and their types
            sample_file: Sample annotation file for validation

        Returns:
            Schema mapping configuration
        """
        # Load a sample to validate
        with open(sample_file) as f:
            sample = json.load(f)

        # Common field name patterns
        image_candidates = ["image_path", "image", "img_path", "file_path"]
        foods_candidates = ["ingredients", "foods", "items", "components"]
        dish_id_candidates = ["dish_id", "id", "sample_id", "annotation_id"]

        schema_map = {
            "dataset_format": "nutritionverse_real",
            "image_path": self._find_field(paths, image_candidates),
            "foods_path": self._find_field(paths, foods_candidates),
            "dish_id_field": self._find_field(paths, dish_id_candidates),
            "food_fields": {},
            "totals_fields": {},
            "optional_fields": {}
        }

        # Infer food item fields
        food_field_candidates = {
            "name": ["name", "food_name", "item_name", "ingredient_name"],
            "mass_g": ["mass_g", "weight_g", "grams", "mass", "weight"],
            "calories_kcal": ["calories_kcal", "calories", "kcal", "energy"],
            "protein_g": ["protein_g", "protein", "protein_grams"],
            "carbs_g": ["carbs_g", "carbohydrates_g", "carbs", "carbohydrates"],
            "fat_g": ["fat_g", "total_fat_g", "fat", "total_fat"]
        }

        for field, candidates in food_field_candidates.items():
            # Look for fields within the foods array
            foods_path = schema_map["foods_path"]
            prefix = f"{foods_path}[*]."
            food_paths = {k: v for k, v in paths.items() if k.startswith(prefix)}

            found = self._find_field(food_paths, candidates, prefix)
            if found:
                schema_map["food_fields"][field] = found.replace(f"{foods_path}[*].", "")

        # Infer totals fields
        totals_candidates = {
            "mass_g": ["totals.mass_g", "total_mass_g", "totals.weight_g"],
            "calories_kcal": ["totals.calories_kcal", "total_calories", "totals.kcal"],
            "protein_g": ["totals.protein_g", "total_protein_g", "totals.protein"],
            "carbs_g": ["totals.carbs_g", "total_carbs_g", "totals.carbohydrates"],
            "fat_g": ["totals.fat_g", "total_fat_g", "totals.fat"]
        }

        for field, candidates in totals_candidates.items():
            found = self._find_field(paths, candidates)
            if found:
                schema_map["totals_fields"][field] = found

        # Optional fields
        optional_candidates = {
            "segmentation_mask": ["mask_path", "segmentation", "mask"],
            "category": ["category", "dish_category", "food_category"]
        }

        for field, candidates in optional_candidates.items():
            found = self._find_field(paths, candidates)
            if found:
                schema_map["optional_fields"][field] = found

        return schema_map

    def _find_field(self, paths: Dict[str, List], candidates: List[str],
                   prefix: str = "") -> Optional[str]:
        """Find the first matching field from candidates in the paths."""
        for candidate in candidates:
            full_path = f"{prefix}{candidate}" if prefix else candidate
            if full_path in paths:
                return candidate if prefix else full_path
        return None

    def save_schema_map(self, schema_map: Dict[str, Any], output_path: Path):
        """Save schema map to YAML file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            yaml.dump(schema_map, f, default_flow_style=False, sort_keys=False)


class SchemaMapper:
    """Map dataset annotations to uniform JSON schema."""

    def __init__(self, schema_map_path: Path):
        with open(schema_map_path) as f:
            self.schema_map = yaml.safe_load(f)

    def map_annotation(self, annotation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map a raw annotation to the uniform schema.

        Args:
            annotation: Raw annotation from dataset

        Returns:
            Uniform schema JSON
        """
        uniform = {
            "dish_id": self._get_nested(annotation, self.schema_map["dish_id_field"]),
            "image_relpath": self._get_nested(annotation, self.schema_map["image_path"]),
            "foods": [],
            "totals": {
                "mass_g": 0.0,
                "calories_kcal": 0.0,
                "macros_g": {"protein": 0.0, "carbs": 0.0, "fat": 0.0}
            }
        }

        # Map foods
        foods_raw = self._get_nested(annotation, self.schema_map["foods_path"]) or []
        for food_raw in foods_raw:
            food = self._map_food(food_raw)
            uniform["foods"].append(food)

        # Map totals
        uniform["totals"] = self._map_totals(annotation)

        # Optional fields
        for opt_field, path in self.schema_map.get("optional_fields", {}).items():
            value = self._get_nested(annotation, path)
            if value is not None:
                uniform[opt_field] = value

        return uniform

    def _map_food(self, food_raw: Dict[str, Any]) -> Dict[str, Any]:
        """Map a single food item to uniform schema."""
        food_fields = self.schema_map["food_fields"]

        return {
            "name": food_raw.get(food_fields.get("name", "name"), ""),
            "mass_g": float(food_raw.get(food_fields.get("mass_g", "mass_g"), 0)),
            "calories_kcal": float(food_raw.get(food_fields.get("calories_kcal", "calories_kcal"), 0)),
            "macros_g": {
                "protein": float(food_raw.get(food_fields.get("protein_g", "protein_g"), 0)),
                "carbs": float(food_raw.get(food_fields.get("carbs_g", "carbs_g"), 0)),
                "fat": float(food_raw.get(food_fields.get("fat_g", "fat_g"), 0))
            }
        }

    def _map_totals(self, annotation: Dict[str, Any]) -> Dict[str, Any]:
        """Map totals to uniform schema."""
        totals_fields = self.schema_map["totals_fields"]

        return {
            "mass_g": float(self._get_nested(annotation, totals_fields.get("mass_g", "totals.mass_g")) or 0),
            "calories_kcal": float(self._get_nested(annotation, totals_fields.get("calories_kcal", "totals.calories_kcal")) or 0),
            "macros_g": {
                "protein": float(self._get_nested(annotation, totals_fields.get("protein_g", "totals.protein_g")) or 0),
                "carbs": float(self._get_nested(annotation, totals_fields.get("carbs_g", "totals.carbs_g")) or 0),
                "fat": float(self._get_nested(annotation, totals_fields.get("fat_g", "totals.fat_g")) or 0)
            }
        }

    def _get_nested(self, obj: Dict, path: str) -> Any:
        """Get nested value from object using dot notation path."""
        keys = path.split('.')
        current = obj

        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None

            if current is None:
                return None

        return current
