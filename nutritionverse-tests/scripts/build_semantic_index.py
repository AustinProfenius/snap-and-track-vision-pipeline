#!/usr/bin/env python3
"""
Build semantic index for Foundation/SR entries.

Usage:
    python scripts/build_semantic_index.py --db-path <path> --output <dir>

Example:
    python scripts/build_semantic_index.py \
        --db-path /path/to/fdc.db \
        --output semantic_indices/foundation_sr_v1
"""
import argparse
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.nutrition.alignment.semantic_index import SemanticIndexBuilder


def main():
    parser = argparse.ArgumentParser(
        description="Build semantic index for Foundation/SR entries"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        required=True,
        help="Path to FDC SQLite database"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for index files"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Sentence transformer model name (default: all-MiniLM-L6-v2)"
    )
    parser.add_argument(
        "--data-types",
        nargs="+",
        default=["foundation_food", "sr_legacy_food"],
        help="FDC data types to index (default: foundation_food sr_legacy_food)"
    )

    args = parser.parse_args()

    # Validate database exists
    if not args.db_path.exists():
        print(f"Error: Database not found at {args.db_path}")
        sys.exit(1)

    # Load FDC database
    print(f"Loading FDC database from {args.db_path}...")
    try:
        from src.nutrition.fdc_database import FDCDatabase
        fdc_db = FDCDatabase(str(args.db_path))
    except Exception as e:
        print(f"Error loading database: {e}")
        sys.exit(1)

    # Build index
    print(f"\nBuilding semantic index...")
    print(f"  Model: {args.model}")
    print(f"  Data types: {args.data_types}")
    print(f"  Output: {args.output}")
    print()

    builder = SemanticIndexBuilder(model_name=args.model)

    try:
        stats = builder.build(
            fdc_database=fdc_db,
            output_path=args.output,
            data_types=args.data_types
        )

        print(f"\n✓ Index built successfully!")
        print(f"  Entries indexed: {stats['num_entries']}")
        print(f"  Embedding dimension: {stats['embedding_dim']}")
        print(f"  Time elapsed: {stats['elapsed_time_sec']:.1f}s")
        print(f"  Index file: {stats['index_file']}")
        print(f"  Metadata file: {stats['metadata_file']}")

    except Exception as e:
        print(f"\n✗ Error building index: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
