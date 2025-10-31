"""
Phase Z4: Recipe Decomposition Framework

Provides multi-component recipe templates (pizza, sandwich, chia pudding) with ratio-based
mass allocation. Each recipe specifies:
- Trigger patterns (tokens/regex for matching)
- Component list with ratios (must sum to 1.0)
- Preferred FDC IDs or Stage Z keys for component alignment
- Energy bounds and reject patterns for plausibility

Runs as Stage 5C (after Stage 5B salad decomposition, before Stage Z).
"""
import os
import re
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from pydantic import BaseModel, field_validator


class RecipeComponent(BaseModel):
    """Single component of a recipe with alignment hints."""

    key: str  # Component identifier (e.g., "crust", "cheese", "sauce")
    ratio: float  # Mass fraction (all components must sum to 1.0 ± 1e-6)
    prefer: Optional[List[str]] = None  # Stage Z keys or variant keys to try first
    fdc_ids: Optional[List[int]] = None  # Hard-pinned FDC IDs (override search)
    notes: Optional[str] = None  # Human-readable notes
    kcal_per_100g: Optional[Tuple[int, int]] = None  # Energy bounds [min, max]
    reject_patterns: Optional[List[str]] = None  # Patterns to reject (e.g., "seasoned", "with sauce")

    @field_validator('ratio')
    @classmethod
    def validate_ratio(cls, v):
        """Ensure ratio is in valid range."""
        if not (0.0 < v <= 1.0):
            raise ValueError(f"Component ratio must be in (0.0, 1.0], got {v}")
        return v

    @field_validator('kcal_per_100g')
    @classmethod
    def validate_kcal_bounds(cls, v):
        """Ensure energy bounds are valid."""
        if v is not None:
            min_kcal, max_kcal = v
            if min_kcal < 0 or max_kcal < 0:
                raise ValueError(f"Energy bounds must be non-negative, got {v}")
            if min_kcal > max_kcal:
                raise ValueError(f"Min energy must be <= max energy, got {v}")
        return v


class RecipeTemplate(BaseModel):
    """Template for a recipe with trigger patterns and component list."""

    name: str  # Recipe name (e.g., "pizza_cheese")
    triggers: List[str]  # Token patterns or regex for matching (case-insensitive)
    components: List[RecipeComponent]  # List of components with ratios
    notes: Optional[str] = None  # Human-readable description

    @field_validator('components')
    @classmethod
    def validate_component_ratios(cls, v):
        """Ensure component ratios sum to 1.0 ± 1e-6."""
        if not v:
            raise ValueError("Recipe must have at least one component")

        total_ratio = sum(comp.ratio for comp in v)
        if abs(total_ratio - 1.0) > 1e-6:
            raise ValueError(
                f"Component ratios must sum to 1.0, got {total_ratio:.6f} "
                f"(components: {[comp.key for comp in v]})"
            )
        return v

    def matches(self, predicted_name: str) -> bool:
        """
        Check if predicted_name matches any trigger pattern.

        Args:
            predicted_name: Normalized food name (lowercase)

        Returns:
            True if any trigger matches
        """
        predicted_lower = predicted_name.lower()

        for trigger in self.triggers:
            trigger_lower = trigger.lower()

            # Simple substring match for now (can extend to regex later)
            if trigger_lower in predicted_lower:
                return True

        return False


class RecipeLoader:
    """Loads and validates recipe templates from YAML config directory."""

    def __init__(self, config_dir: Path):
        """
        Initialize loader with config directory.

        Args:
            config_dir: Path to directory containing recipes/*.yml files
        """
        self.config_dir = Path(config_dir)
        self.recipes_dir = self.config_dir / "recipes"
        self.templates: Dict[str, RecipeTemplate] = {}

        if not self.recipes_dir.exists():
            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"[RECIPE_LOADER] Warning: recipes directory not found: {self.recipes_dir}")
        else:
            self._load_all_templates()

    def _load_all_templates(self):
        """Load all recipe templates from recipes/*.yml files."""
        if not self.recipes_dir.is_dir():
            return

        for yml_file in sorted(self.recipes_dir.glob("*.yml")):
            try:
                with open(yml_file, 'r') as f:
                    data = yaml.safe_load(f)

                if not data:
                    continue

                # Each YAML can contain multiple recipes (top-level keys are recipe names)
                for recipe_name, recipe_data in data.items():
                    try:
                        # Add name to recipe_data if not present
                        if 'name' not in recipe_data:
                            recipe_data['name'] = recipe_name

                        # Parse components with ratio validation
                        components = []
                        for comp_data in recipe_data.get('components', []):
                            # Convert kcal_per_100g list to tuple if present
                            if 'kcal_per_100g' in comp_data and isinstance(comp_data['kcal_per_100g'], list):
                                comp_data['kcal_per_100g'] = tuple(comp_data['kcal_per_100g'])

                            components.append(RecipeComponent(**comp_data))

                        recipe_data['components'] = components

                        # Create template (validates ratio sum)
                        template = RecipeTemplate(**recipe_data)
                        self.templates[recipe_name] = template

                        if os.getenv('ALIGN_VERBOSE', '0') == '1':
                            print(f"[RECIPE_LOADER] Loaded recipe: {recipe_name} "
                                  f"({len(template.components)} components, "
                                  f"triggers={template.triggers})")

                    except Exception as e:
                        print(f"[RECIPE_LOADER] Error loading recipe '{recipe_name}' from {yml_file.name}: {e}")
                        continue

            except Exception as e:
                print(f"[RECIPE_LOADER] Error reading {yml_file.name}: {e}")
                continue

        if os.getenv('ALIGN_VERBOSE', '0') == '1':
            print(f"[RECIPE_LOADER] Loaded {len(self.templates)} recipe templates")

    def match_recipe(self, predicted_name: str) -> Optional[RecipeTemplate]:
        """
        Find first recipe template matching predicted_name.

        Args:
            predicted_name: Normalized food name (lowercase)

        Returns:
            RecipeTemplate if found, else None
        """
        for template in self.templates.values():
            if template.matches(predicted_name):
                if os.getenv('ALIGN_VERBOSE', '0') == '1':
                    print(f"[RECIPE_LOADER] Matched recipe: {template.name} for '{predicted_name}'")
                return template

        return None

    def get_template(self, recipe_name: str) -> Optional[RecipeTemplate]:
        """
        Get recipe template by exact name.

        Args:
            recipe_name: Recipe template name (e.g., "pizza_cheese")

        Returns:
            RecipeTemplate if found, else None
        """
        return self.templates.get(recipe_name)

    def validate_all(self, fdc_database=None) -> List[str]:
        """
        Validate all loaded templates.

        Args:
            fdc_database: Optional FDC database for validating pinned FDC IDs

        Returns:
            List of warning messages
        """
        warnings = []

        for recipe_name, template in self.templates.items():
            # Check ratio sum (should be caught by Pydantic validator)
            total_ratio = sum(comp.ratio for comp in template.components)
            if abs(total_ratio - 1.0) > 1e-6:
                warnings.append(
                    f"Recipe '{recipe_name}': ratios sum to {total_ratio:.6f}, expected 1.0"
                )

            # Check for duplicate component keys
            comp_keys = [comp.key for comp in template.components]
            if len(comp_keys) != len(set(comp_keys)):
                warnings.append(f"Recipe '{recipe_name}': duplicate component keys found")

            # Check pinned FDC IDs exist (if database provided)
            if fdc_database:
                for comp in template.components:
                    if comp.fdc_ids:
                        for fdc_id in comp.fdc_ids:
                            entry = fdc_database.get_entry_by_id(fdc_id)
                            if not entry:
                                warnings.append(
                                    f"Recipe '{recipe_name}', component '{comp.key}': "
                                    f"FDC ID {fdc_id} not found in database"
                                )

        return warnings

    def __len__(self) -> int:
        """Return number of loaded templates."""
        return len(self.templates)

    def __repr__(self) -> str:
        return f"RecipeLoader(templates={len(self.templates)}, dir={self.recipes_dir})"
