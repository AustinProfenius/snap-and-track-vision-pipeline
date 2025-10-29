"""
Dataset loader with index slicing and iteration support.
"""
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Iterator
from dataclasses import dataclass

from .schema import SchemaDiscovery, SchemaMapper


@dataclass
class DatasetItem:
    """Single dataset item with ground truth."""
    index: int
    dish_id: str
    image_path: Path
    ground_truth: Dict[str, Any]
    raw_annotation: Optional[Dict[str, Any]] = None


class NutritionVerseLoader:
    """
    Load and iterate over NutritionVerse-Real dataset with flexible slicing.
    """

    def __init__(self, data_dir: Path, schema_map_path: Path, cache_dir: Optional[Path] = None):
        """
        Initialize the dataset loader.

        Args:
            data_dir: Path to dataset root (contains images + annotations)
            schema_map_path: Path to schema mapping YAML
            cache_dir: Optional cache directory for preprocessed data
        """
        self.data_dir = Path(data_dir)
        self.schema_mapper = SchemaMapper(schema_map_path)
        self.cache_dir = Path(cache_dir) if cache_dir else None

        # Load and index all items
        self.items = self._load_all_items()

    def _load_all_items(self) -> List[DatasetItem]:
        """Load all dataset items and sort deterministically."""
        annotation_files = sorted(self.data_dir.glob("**/*.json"))

        items = []
        for idx, ann_file in enumerate(annotation_files):
            try:
                with open(ann_file) as f:
                    raw_annotation = json.load(f)

                # Map to uniform schema
                ground_truth = self.schema_mapper.map_annotation(raw_annotation)

                # Resolve image path
                image_relpath = ground_truth["image_relpath"]
                image_path = self.data_dir / image_relpath

                if not image_path.exists():
                    # Try finding image in same directory as annotation
                    image_path = ann_file.parent / Path(image_relpath).name
                    if not image_path.exists():
                        print(f"Warning: Image not found for {ann_file}: {image_relpath}")
                        continue

                # Fill in metadata
                ground_truth["dish_id"] = ground_truth.get("dish_id") or f"dish_{idx:05d}"

                item = DatasetItem(
                    index=idx,
                    dish_id=ground_truth["dish_id"],
                    image_path=image_path,
                    ground_truth=ground_truth,
                    raw_annotation=raw_annotation
                )
                items.append(item)

            except Exception as e:
                print(f"Error loading {ann_file}: {e}")
                continue

        return items

    def __len__(self) -> int:
        """Return total number of items."""
        return len(self.items)

    def __getitem__(self, idx: int) -> DatasetItem:
        """Get item by index."""
        return self.items[idx]

    def get_slice(self, start: Optional[int] = None, end: Optional[int] = None) -> List[DatasetItem]:
        """
        Get a slice of dataset items.

        Args:
            start: Start index (inclusive), None for 0
            end: End index (exclusive), None for len

        Returns:
            List of dataset items in range [start, end)
        """
        start = start or 0
        end = end or len(self.items)

        return self.items[start:end]

    def get_by_ids(self, dish_ids: List[str]) -> List[DatasetItem]:
        """
        Get items by dish IDs.

        Args:
            dish_ids: List of dish IDs

        Returns:
            List of matching dataset items
        """
        id_set = set(dish_ids)
        return [item for item in self.items if item.dish_id in id_set]

    def get_by_indices(self, indices: List[int]) -> List[DatasetItem]:
        """
        Get items by explicit indices.

        Args:
            indices: List of dataset indices

        Returns:
            List of dataset items at those indices
        """
        return [self.items[idx] for idx in indices if 0 <= idx < len(self.items)]

    def iter_slice(self, start: Optional[int] = None, end: Optional[int] = None) -> Iterator[DatasetItem]:
        """
        Iterate over a slice of the dataset.

        Args:
            start: Start index (inclusive)
            end: End index (exclusive)

        Yields:
            DatasetItem objects
        """
        items = self.get_slice(start, end)
        for item in items:
            yield item

    def get_statistics(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        if not self.items:
            return {}

        total_calories = [item.ground_truth["totals"]["calories_kcal"] for item in self.items]
        total_protein = [item.ground_truth["totals"]["macros_g"]["protein"] for item in self.items]
        num_foods = [len(item.ground_truth["foods"]) for item in self.items]

        import statistics

        return {
            "total_samples": len(self.items),
            "calories": {
                "mean": statistics.mean(total_calories),
                "median": statistics.median(total_calories),
                "min": min(total_calories),
                "max": max(total_calories)
            },
            "protein_g": {
                "mean": statistics.mean(total_protein),
                "median": statistics.median(total_protein),
                "min": min(total_protein),
                "max": max(total_protein)
            },
            "foods_per_dish": {
                "mean": statistics.mean(num_foods),
                "median": statistics.median(num_foods),
                "min": min(num_foods),
                "max": max(num_foods)
            }
        }


def load_ids_from_file(ids_file: Path) -> List[str]:
    """
    Load dish IDs from a text file (one ID per line).

    Args:
        ids_file: Path to IDs file

    Returns:
        List of dish IDs
    """
    with open(ids_file) as f:
        return [line.strip() for line in f if line.strip()]


def main():
    """CLI for dataset inspection and schema discovery."""
    parser = argparse.ArgumentParser(description="NutritionVerse dataset loader")
    parser.add_argument("--data-dir", type=Path, default="data/nvreal",
                       help="Path to dataset directory")
    parser.add_argument("--inspect", action="store_true",
                       help="Run schema discovery and print to stdout")
    parser.add_argument("--stats", action="store_true",
                       help="Print dataset statistics")
    parser.add_argument("--schema-map", type=Path, default="configs/schema_map.yaml",
                       help="Path to schema map YAML")
    parser.add_argument("--sample-size", type=int, default=5,
                       help="Number of samples for schema discovery")

    args = parser.parse_args()

    if args.inspect:
        # Schema discovery mode
        print("Running schema discovery...")
        discovery = SchemaDiscovery(args.data_dir)
        schema_map = discovery.inspect_annotations(sample_size=args.sample_size)

        # Save to file
        discovery.save_schema_map(schema_map, args.schema_map)
        print(f"\nSchema map saved to {args.schema_map}")

        # Also print to stdout
        import yaml
        print("\nDiscovered schema:")
        print(yaml.dump(schema_map, default_flow_style=False))

    elif args.stats:
        # Statistics mode
        if not args.schema_map.exists():
            print(f"Error: Schema map not found at {args.schema_map}")
            print("Run with --inspect first to generate schema map")
            return

        loader = NutritionVerseLoader(args.data_dir, args.schema_map)
        stats = loader.get_statistics()

        print(f"\nDataset Statistics ({args.data_dir}):")
        print(f"Total samples: {stats['total_samples']}")
        print(f"\nCalories (kcal):")
        print(f"  Mean: {stats['calories']['mean']:.1f}")
        print(f"  Median: {stats['calories']['median']:.1f}")
        print(f"  Range: [{stats['calories']['min']:.1f}, {stats['calories']['max']:.1f}]")
        print(f"\nProtein (g):")
        print(f"  Mean: {stats['protein_g']['mean']:.1f}")
        print(f"  Median: {stats['protein_g']['median']:.1f}")
        print(f"  Range: [{stats['protein_g']['min']:.1f}, {stats['protein_g']['max']:.1f}]")
        print(f"\nFoods per dish:")
        print(f"  Mean: {stats['foods_per_dish']['mean']:.1f}")
        print(f"  Median: {stats['foods_per_dish']['median']:.1f}")
        print(f"  Range: [{stats['foods_per_dish']['min']}, {stats['foods_per_dish']['max']}]")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
