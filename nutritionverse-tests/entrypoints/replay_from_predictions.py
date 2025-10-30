#!/usr/bin/env python3
"""
Prediction Replay - Zero-cost alignment iteration

Replays prior LLM/vision predictions through alignment engine without re-calling vision API.
Supports batch iteration on alignment logic with frozen predictions.

Usage:
    python replay_from_predictions.py --in batch.json --out runs/replay_<ts>/ [--schema auto]
    python replay_from_predictions.py --in file1.json --in file2.jsonl --out runs/ --limit 100
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import hashlib
from decimal import Decimal

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers import detect_schema, PredictionSchemaV1Parser, PredictionSchemaV2Parser
from src.adapters.alignment_adapter import AlignmentEngineAdapter


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder that converts Decimal objects to float."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def load_prediction_file(file_path: Path, schema: str = "auto") -> tuple:
    """
    Load and parse prediction file.

    Args:
        file_path: Path to prediction file (JSON or JSONL)
        schema: Schema version ("auto", "v1", "v2")

    Returns:
        Tuple of (detected_schema, predictions_iterator)
    """
    print(f"Loading {file_path}...")

    with open(file_path) as f:
        if file_path.suffix == '.jsonl':
            # JSONL format
            data = [json.loads(line) for line in f if line.strip()]
            # Wrap in results structure for V1 parser
            data = {"results": [{"prediction": item} for item in data]}
        else:
            # Regular JSON
            data = json.load(f)

    # Auto-detect schema if needed
    if schema == "auto":
        detected = detect_schema(data)
        if detected == "unknown":
            raise ValueError(f"Could not detect schema for {file_path}. Try specifying --schema explicitly.")
        schema = detected
        print(f"  Detected schema: {schema}")

    # Get appropriate parser
    if schema == "v1":
        parser = PredictionSchemaV1Parser
    elif schema == "v2":
        parser = PredictionSchemaV2Parser
    else:
        raise ValueError(f"Unknown schema: {schema}")

    # Parse predictions
    predictions = list(parser.parse(data))
    print(f"  Loaded {len(predictions)} predictions")

    return schema, predictions


def run_replay(
    input_files: List[Path],
    output_dir: Path,
    schema: str = "auto",
    limit: int = None
) -> Dict[str, Any]:
    """
    Run prediction replay.

    Args:
        input_files: List of prediction files to replay
        output_dir: Output directory for results
        schema: Schema version
        limit: Optional limit on number of predictions to process

    Returns:
        Replay manifest dict
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize alignment adapter
    print("\nInitializing alignment engine...")
    adapter = AlignmentEngineAdapter(enable_conversion=True)

    # Print config info (requirement: show config on init)
    print(f"[CFG] fallbacks_loaded={getattr(adapter._alignment_engine, '_external_stageZ_branded_fallbacks', {}).get('fallbacks', {}) if hasattr(adapter, '_alignment_engine') else 'N/A'}")
    print(f"[CFG] allow_stageZ_for_partial_pools={getattr(adapter._alignment_engine, '_external_feature_flags', {}).get('allow_stageZ_for_partial_pools', False) if hasattr(adapter, '_alignment_engine') else 'N/A'}")
    print(f"[CFG] db_available={adapter._alignment_engine._fdc_db is not None if hasattr(adapter, '_alignment_engine') and hasattr(adapter._alignment_engine, '_fdc_db') else False}")

    # Load all predictions
    all_predictions = []
    schema_used = schema

    for input_file in input_files:
        detected_schema, predictions = load_prediction_file(input_file, schema)
        schema_used = detected_schema  # Use last detected schema
        all_predictions.extend(predictions)

    # Apply limit if specified
    if limit:
        all_predictions = all_predictions[:limit]
        print(f"\nProcessing limited to {limit} predictions")

    print(f"\nTotal predictions to process: {len(all_predictions)}")

    # Process predictions
    results = []
    telemetry_records = []

    print("\nProcessing predictions...")
    for idx, prediction in enumerate(all_predictions):
        if (idx + 1) % 50 == 0:
            print(f"  [{idx + 1}/{len(all_predictions)}] Processing...")

        # Run alignment on prediction
        try:
            result = adapter.run_from_prediction_dict(prediction)

            # Add source tracking
            result['source'] = 'prediction_replay'
            result['prediction_id'] = prediction['prediction_id']
            result['prediction_hash'] = prediction['prediction_hash']
            result['input_schema_version'] = prediction['input_schema_version']

            results.append(result)

            # Extract telemetry
            if 'telemetry' in result:
                telemetry = result['telemetry'].copy()
                telemetry['source'] = 'prediction_replay'
                telemetry['prediction_id'] = prediction['prediction_id']
                telemetry['prediction_hash'] = prediction['prediction_hash']
                telemetry_records.append(telemetry)

        except Exception as e:
            print(f"  ERROR processing prediction {prediction['prediction_id']}: {e}")
            results.append({
                'source': 'prediction_replay',
                'prediction_id': prediction['prediction_id'],
                'error': str(e),
                'available': False
            })

    # Write results
    results_file = output_dir / "results.jsonl"
    with open(results_file, 'w') as f:
        for result in results:
            f.write(json.dumps(result, cls=DecimalEncoder) + '\n')
    print(f"\n✓ Results written to: {results_file}")

    # Write telemetry
    telemetry_file = output_dir / "telemetry.jsonl"
    with open(telemetry_file, 'w') as f:
        for record in telemetry_records:
            f.write(json.dumps(record, cls=DecimalEncoder) + '\n')
    print(f"✓ Telemetry written to: {telemetry_file}")

    # Create replay manifest
    manifest = {
        "source": "prediction_replay",
        "timestamp": timestamp,
        "input_files": [str(f) for f in input_files],
        "input_schema_version": schema_used,
        "total_predictions": len(all_predictions),
        "processed": len(results),
        "output_dir": str(output_dir),
        "files": {
            "results": str(results_file),
            "telemetry": str(telemetry_file)
        }
    }

    manifest_file = output_dir / "replay_manifest.json"
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2, cls=DecimalEncoder)
    print(f"✓ Manifest written to: {manifest_file}")

    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Replay predictions through alignment engine (zero vision API cost)"
    )
    parser.add_argument(
        "--in",
        dest="input_files",
        action="append",
        required=True,
        help="Input prediction file(s) - JSON or JSONL format (can specify multiple times)"
    )
    parser.add_argument(
        "--out",
        dest="output_dir",
        required=True,
        help="Output directory for results"
    )
    parser.add_argument(
        "--schema",
        default="auto",
        choices=["auto", "v1", "v2"],
        help="Prediction schema version (default: auto-detect)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of predictions to process"
    )

    args = parser.parse_args()

    # Convert paths
    input_files = [Path(f) for f in args.input_files]
    output_dir = Path(args.output_dir)

    # Validate inputs
    for f in input_files:
        if not f.exists():
            print(f"ERROR: Input file not found: {f}")
            sys.exit(1)

    # Run replay
    print("=" * 80)
    print("PREDICTION REPLAY - Zero-cost Alignment Iteration")
    print("=" * 80)
    print(f"Input files: {len(input_files)}")
    for f in input_files:
        print(f"  - {f}")
    print(f"Output dir: {output_dir}")
    print(f"Schema: {args.schema}")
    if args.limit:
        print(f"Limit: {args.limit}")
    print("=" * 80)

    manifest = run_replay(
        input_files=input_files,
        output_dir=output_dir,
        schema=args.schema,
        limit=args.limit
    )

    print("\n" + "=" * 80)
    print("REPLAY COMPLETE")
    print("=" * 80)
    print(f"Processed: {manifest['processed']} predictions")
    print(f"Results: {manifest['files']['results']}")
    print(f"Telemetry: {manifest['files']['telemetry']}")
    print(f"Manifest: {output_dir / 'replay_manifest.json'}")
    print("=" * 80)


if __name__ == "__main__":
    main()
