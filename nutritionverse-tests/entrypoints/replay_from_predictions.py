"""
Prediction Replay - Replay cached vision predictions through alignment engine.

Zero-cost alignment iteration by replaying prior LLM/vision predictions without calling APIs.

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
import yaml

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


def load_config_yaml(file_path: Path) -> Dict[str, Any]:
    """Load YAML config file."""
    with open(file_path) as f:
        return yaml.safe_load(f) or {}


def load_prediction_file(file_path: Path, schema: str = "auto") -> tuple:
    """
    Load and parse prediction file.

    Args:
        file_path: Path to prediction file
        schema: Schema version ("auto", "v1", or "v2")

    Returns:
        Tuple of (schema_version, list of normalized predictions)
    """
    with open(file_path) as f:
        # Handle JSONL format
        if file_path.suffix == '.jsonl':
            data = []
            for line in f:
                if line.strip():
                    data.append(json.loads(line))
            # Wrap in v1 format
            data = {
                "results": [
                    {"prediction": item} for item in data
                ]
            }
        else:
            data = json.load(f)

    # Detect schema
    if schema == "auto":
        detected = detect_schema(data)
        if detected == "unknown":
            raise ValueError(f"Could not detect schema for {file_path}")
        schema = detected

    # Parse with appropriate parser
    if schema == "v1":
        parser = PredictionSchemaV1Parser
    else:
        parser = PredictionSchemaV2Parser

    predictions = list(parser.parse(data))
    return schema, predictions


def run_replay(
    input_files: List[Path],
    output_dir: Path,
    schema: str = "auto",
    limit: int = None,
    config_dir: Path = None
) -> Dict[str, Any]:
    """
    Run prediction replay.

    Args:
        input_files: List of prediction files to replay
        output_dir: Output directory for results
        schema: Schema version
        limit: Optional limit on number of predictions to process
        config_dir: Config directory path (optional, uses auto-detection if not provided)

    Returns:
        Replay manifest dict
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize alignment adapter (auto-init will load configs)
    print("\nInitializing alignment engine...")
    adapter = AlignmentEngineAdapter(enable_conversion=True)

    # Trigger auto-initialization to load configs
    adapter._auto_initialize()

    # Print config info after initialization
    if adapter.alignment_engine and hasattr(adapter.alignment_engine, '_external_stageZ_branded_fallbacks'):
        fallbacks_count = len(adapter.alignment_engine._external_stageZ_branded_fallbacks.get('fallbacks', {}))
    else:
        fallbacks_count = 0

    if adapter.alignment_engine and hasattr(adapter.alignment_engine, '_external_feature_flags'):
        allow_z_partial = adapter.alignment_engine._external_feature_flags.get('allow_stageZ_for_partial_pools', False)
    else:
        allow_z_partial = False

    print(f"[CFG] fallbacks_loaded={fallbacks_count}")
    print(f"[CFG] allow_stageZ_for_partial_pools={allow_z_partial}")
    print(f"[CFG] db_available={adapter.db_available}")

    # Load all predictions
    print(f"Loading {len(input_files)} input file(s)...")
    all_predictions = []
    schema_used = schema

    for input_file in input_files:
        print(f"  Loading {input_file}...")
        detected_schema, predictions = load_prediction_file(input_file, schema)
        schema_used = detected_schema
        all_predictions.extend(predictions)
        print(f"  Loaded {len(predictions)} predictions (schema: {detected_schema})")

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
        if (idx + 1) % 50 == 0 or idx == 0:
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

            # Extract telemetry from foods
            if 'foods' in result:
                for food in result['foods']:
                    if 'telemetry' in food:
                        telemetry = food['telemetry'].copy()
                        telemetry['source'] = 'prediction_replay'
                        telemetry['prediction_id'] = prediction['prediction_id']
                        telemetry['prediction_hash'] = prediction['prediction_hash']
                        telemetry['food_name'] = food.get('name', '')
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
        "schema_version": schema_used,
        "processed": len(all_predictions),
        "files": {
            "results": str(results_file),
            "telemetry": str(telemetry_file)
        }
    }

    manifest_file = output_dir / "replay_manifest.json"
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2, cls=DecimalEncoder)
    print(f"✓ Manifest written to: {manifest_file}")

    # Hard assertions for Z2 activation
    stageZ_count = 0
    ignored_count = 0
    stage0_count = 0

    for record in telemetry_records:
        stage = record.get('alignment_stage', '')
        if 'stageZ' in stage:
            stageZ_count += 1
        if record.get('ignored_class'):
            ignored_count += 1
        if stage == 'stage0_no_candidates':
            stage0_count += 1

    # Assertion: Stage Z should be used if we have enough data
    if len(all_predictions) >= 50 and stageZ_count == 0:
        print(f"\n❌ ERROR: Stage Z usage == 0 on replay with {len(all_predictions)} predictions")
        print(f"[CFG] fallbacks_loaded={fallbacks_count}, allow_stageZ_for_partial_pools={allow_z_partial}")
        print("Config/flags likely not wired correctly. Check adapter initialization.")
        sys.exit(1)

    # Assertion: Negative vocabulary should trigger if expected classes present
    # (This is a softer check - only warn, don't fail)
    if ignored_count == 0 and len(all_predictions) >= 50:
        print(f"\n⚠️  WARNING: Negative vocabulary rules appear inactive (no ignored_class found)")

    print(f"\n📊 Stage Z usage: {stageZ_count} / {len(telemetry_records)} foods ({stageZ_count/len(telemetry_records)*100:.1f}%)")
    print(f"📊 Ignored items: {ignored_count}")
    print(f"📊 Stage 0 misses: {stage0_count} / {len(telemetry_records)} foods ({stage0_count/len(telemetry_records)*100:.1f}%)")

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
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=None,
        help="Config directory path (default: auto-detect from repo root)"
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
    if args.config_dir:
        print(f"Config dir: {args.config_dir}")
    print("=" * 80)

    manifest = run_replay(
        input_files=input_files,
        output_dir=output_dir,
        schema=args.schema,
        limit=args.limit,
        config_dir=args.config_dir
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
