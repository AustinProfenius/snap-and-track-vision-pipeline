#!/usr/bin/env python3
"""
Analyze Consolidated Batch Test - Missed Food Matches

Analyzes the consolidated JSON output from run_first_50_consolidated.py
to extract and report on missed food matches.

Usage:
    python analyze_consolidated_misses.py runs/first_50_batch_20251029_202918.json
    python analyze_consolidated_misses.py --input runs/first_50_batch_XXXXXX.json --output misses_report.json
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def analyze_miss_patterns(misses: List[Dict]) -> Dict[str, Any]:
    """Analyze patterns in missed matches."""
    miss_by_food = defaultdict(int)
    miss_by_form = defaultdict(int)
    miss_patterns = []

    for miss in misses:
        food_name = miss['food_name']
        food_form = miss.get('food_form', 'unknown')

        miss_by_food[food_name] += 1
        miss_by_form[food_form] += 1

        # Check for patterns
        if food_form == 'raw':
            miss_patterns.append('raw_form_miss')
        if any(meat in food_name.lower() for meat in ['chicken', 'steak', 'beef', 'pork']):
            miss_patterns.append('meat_miss')
        if 'eggplant' in food_name.lower():
            miss_patterns.append('eggplant_miss')

    return {
        'most_common_foods': dict(sorted(miss_by_food.items(), key=lambda x: x[1], reverse=True)[:10]),
        'misses_by_form': dict(sorted(miss_by_form.items(), key=lambda x: x[1], reverse=True)),
        'patterns': dict(defaultdict(int, [(p, miss_patterns.count(p)) for p in set(miss_patterns)]))
    }


def extract_misses_from_consolidated(consolidated_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract all missed foods from consolidated batch results."""
    all_misses = []

    # Build telemetry lookup by image_id and query
    telemetry_lookup = defaultdict(list)
    for tel in consolidated_data.get('telemetry', []):
        image_id = tel.get('image_id')
        query = tel.get('query')
        if image_id and query:
            telemetry_lookup[(image_id, query)].append(tel)

    # Iterate through results
    for result in consolidated_data.get('results', []):
        image_id = result.get('image_id')

        for food_idx, food in enumerate(result.get('foods', [])):
            # A food is a MISS if it has no FDC ID (regardless of stage)
            fdc_id = food.get('fdc_id')

            # Check for missing FDC ID: None, empty string, or 'null'
            is_miss = (fdc_id is None or fdc_id == '' or fdc_id == 'null')

            if is_miss:
                food_name = food.get('name', 'unknown')
                alignment_stage = food.get('alignment_stage', 'unknown')

                # Find matching telemetry
                food_telemetry = None
                key = (image_id, food_name)
                if key in telemetry_lookup:
                    # Get the telemetry for this food (may be multiple, take first)
                    food_telemetry = telemetry_lookup[key][0] if telemetry_lookup[key] else None

                miss_entry = {
                    'dish_id': image_id,
                    'food_name': food_name,
                    'food_form': food.get('form', 'unknown'),
                    'food_index': food_idx,
                    'stage': alignment_stage,
                    'telemetry': food_telemetry,
                    'fdc_id': fdc_id,
                    'fdc_name': food.get('fdc_name')
                }

                all_misses.append(miss_entry)

    return all_misses


def generate_report(input_path: Path, output_path: Path):
    """Generate comprehensive miss analysis report from consolidated JSON."""
    print("=" * 80)
    print("CONSOLIDATED BATCH TEST - MISSED MATCHES ANALYSIS")
    print("=" * 80)
    print()

    # Load consolidated JSON
    print(f"Loading consolidated results from: {input_path}")
    with open(input_path, 'r') as f:
        consolidated_data = json.load(f)

    metadata = consolidated_data.get('metadata', {})
    print(f"Batch: {metadata.get('batch_name')}")
    print(f"Timestamp: {metadata.get('timestamp')}")
    print(f"Total dishes: {metadata.get('total_dishes')}")
    print()

    # Extract misses
    all_misses = extract_misses_from_consolidated(consolidated_data)

    print(f"Total missed matches: {len(all_misses)}")
    print()

    # Analyze patterns
    patterns = analyze_miss_patterns(all_misses)

    # Extract unique missed foods (no duplicates)
    unique_missed_foods = sorted(set(miss['food_name'] for miss in all_misses))
    unique_miss_count = len(unique_missed_foods)

    # Count dishes with misses
    dishes_with_misses = len(set(miss['dish_id'] for miss in all_misses))

    # Total food items - count actual foods from results if summary is 0
    total_food_items = consolidated_data.get('summary', {}).get('total_food_items', 0)
    if total_food_items == 0:
        # Fallback: count foods directly from results
        for result in consolidated_data.get('results', []):
            total_food_items += len(result.get('foods', []))

    # Build final report
    report = {
        'metadata': {
            'input_file': str(input_path),
            'batch_timestamp': metadata.get('timestamp'),
            'total_dishes': metadata.get('total_dishes'),
            'dishes_with_misses': dishes_with_misses,
            'total_missed_foods': len(all_misses),
            'total_food_items': total_food_items
        },
        'summary': {
            'miss_rate': f"{(len(all_misses) / max(total_food_items, 1)) * 100:.1f}%",
            'dishes_with_all_matches': metadata.get('total_dishes', 0) - dishes_with_misses,
            'dishes_with_some_misses': dishes_with_misses,
            'unique_missed_foods_count': unique_miss_count,
            'total_missed_instances': len(all_misses)
        },
        'patterns': patterns,
        'unique_missed_foods': unique_missed_foods,
        'all_misses': all_misses
    }

    # Save report
    print(f"Writing report to: {output_path}")
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2, cls=DecimalEncoder)

    # Print summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Miss Rate: {report['summary']['miss_rate']}")
    print(f"Dishes with all matches: {report['summary']['dishes_with_all_matches']}")
    print(f"Dishes with some misses: {report['summary']['dishes_with_some_misses']}")
    print(f"\nUnique Foods Missed: {unique_miss_count}")
    print(f"Total Miss Instances: {len(all_misses)}")
    print()
    print("Most Common Missed Foods:")
    for food, count in list(patterns['most_common_foods'].items())[:5]:
        print(f"  {food}: {count} misses")
    print()
    print("Misses by Form:")
    for form, count in patterns['misses_by_form'].items():
        print(f"  {form}: {count} misses")
    print()
    print(f"✓ Report saved to: {output_path}")
    print()

    # Print detailed miss list
    print("=" * 80)
    print("DETAILED MISS LIST")
    print("=" * 80)
    print()

    for i, miss in enumerate(all_misses, 1):
        print(f"[{i}/{len(all_misses)}] {miss['dish_id']} - {miss['food_name']} ({miss['food_form']})")
        print(f"  Stage: {miss['stage']}")

        if miss['telemetry']:
            tel = miss['telemetry']
            print(f"  Candidate Pool Size: {tel.get('candidate_pool_size', 'N/A')}")
            print(f"  Foundation Pool Count: {tel.get('foundation_pool_count', 'N/A')}")
            print(f"  Variants Tried: {tel.get('search_variants_tried', [])}")

            if tel.get('attempted_stages'):
                print(f"  Attempted Stages: {tel['attempted_stages']}")

            if tel.get('negative_vocab_blocks'):
                print(f"  Negative Vocab Blocks: {tel['negative_vocab_blocks']}")
        else:
            print(f"  No telemetry available")

        print()

    # Print unique missed foods list
    print("=" * 80)
    print("UNIQUE MISSED FOODS (No Duplicates)")
    print("=" * 80)
    print(f"Total Unique Foods: {unique_miss_count}")
    print()
    for i, food_name in enumerate(unique_missed_foods, 1):
        # Get count of how many times this food was missed
        count = sum(1 for m in all_misses if m['food_name'] == food_name)
        print(f"{i:3d}. {food_name:30s} ({count} instances)")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Analyze missed food matches from consolidated batch test'
    )
    parser.add_argument(
        'input',
        nargs='?',
        type=Path,
        help='Path to consolidated JSON file (positional)'
    )
    parser.add_argument(
        '--input',
        dest='input_flag',
        type=Path,
        help='Path to consolidated JSON file (flag)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('consolidated_misses_report.json'),
        help='Output path for JSON report (default: consolidated_misses_report.json)'
    )

    args = parser.parse_args()

    # Use positional or flag input
    input_path = args.input or args.input_flag

    if not input_path:
        # Find latest consolidated batch file
        runs_dir = Path('runs')
        batch_files = list(runs_dir.glob('first_50_batch_*.json'))
        if not batch_files:
            print("ERROR: No consolidated batch files found in runs/")
            print("Please provide an input file path.")
            return 1

        # Use most recent
        input_path = max(batch_files, key=lambda p: p.stat().st_mtime)
        print(f"Using latest batch file: {input_path}")
        print()

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        return 1

    generate_report(input_path, args.output)
    return 0


if __name__ == '__main__':
    exit(main())
