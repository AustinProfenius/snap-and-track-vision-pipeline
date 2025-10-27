#!/usr/bin/env python3
"""
Export evaluation results to various formats.

Usage:
    python scripts/export_results.py {run_id} --format csv
    python scripts/export_results.py {run_id} --format parquet
    python scripts/export_results.py {run_id} --format excel
"""
import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.store import ResultStore


def main():
    parser = argparse.ArgumentParser(description="Export evaluation results")
    parser.add_argument("run_id", help="Run ID to export")
    parser.add_argument("--format", choices=["csv", "parquet", "excel"], default="csv",
                       help="Output format")
    parser.add_argument("--output", type=Path, default=None,
                       help="Output file path (auto-generated if not specified)")
    parser.add_argument("--results-dir", type=Path, default="runs/results",
                       help="Results directory")

    args = parser.parse_args()

    # Load results
    store = ResultStore(args.results_dir)
    store.jsonl_path = args.results_dir / f"{args.run_id}.jsonl"

    if not store.jsonl_path.exists():
        print(f"Error: Results not found for run {args.run_id}")
        sys.exit(1)

    print(f"Loading results from {store.jsonl_path}...")
    df = store.to_dataframe()

    print(f"Loaded {len(df)} samples")

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = args.results_dir / f"{args.run_id}.{args.format}"

    # Export
    print(f"Exporting to {output_path}...")

    if args.format == "csv":
        df.to_csv(output_path, index=False)
    elif args.format == "parquet":
        df.to_parquet(output_path, index=False)
    elif args.format == "excel":
        df.to_excel(output_path, index=False)

    print(f"✓ Exported successfully to {output_path}")
    print(f"  Size: {output_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
