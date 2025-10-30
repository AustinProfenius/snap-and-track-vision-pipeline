#!/usr/bin/env python3
"""
Analyze First 50 Dishes Test - Missed Food Matches

Extracts all missed food matches from the log file and consolidates
results and telemetry from multiple run directories into a single JSON report.

Usage:
    python analyze_first_50_misses.py
    python analyze_first_50_misses.py --log runs/first_50_latest.log
    python analyze_first_50_misses.py --output first_50_misses_report.json
"""

import json
import re
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def parse_log_file(log_path: Path) -> Dict[str, Any]:
    """Parse the log file to extract dish processing information and misses."""
    print(f"Parsing log file: {log_path}")

    dishes = []
    current_dish = None
    current_dish_foods = []
    total_misses = 0

    with open(log_path, 'r') as f:
        for line in f:
            line = line.strip()

            # Match dish header: [N/50] Processing dish_ID...
            dish_match = re.match(r'\[(\d+)/(\d+)\] Processing (dish_\d+)\.\.\.', line)
            if dish_match:
                # Save previous dish if exists
                if current_dish:
                    current_dish['foods'] = current_dish_foods
                    current_dish['miss_count'] = sum(1 for f in current_dish_foods if f['missed'])
                    total_misses += current_dish['miss_count']
                    dishes.append(current_dish)

                # Start new dish
                dish_idx, total, dish_id = dish_match.groups()
                current_dish = {
                    'dish_id': dish_id,
                    'dish_index': int(dish_idx),
                    'total_dishes': int(total),
                    'runs_dir': None,
                    'stage_distribution': {}
                }
                current_dish_foods = []

            # Match food alignment attempts
            food_align_match = re.match(r'\[ADAPTER\] \[(\d+)/(\d+)\] Aligning: (.+) \((.+)\)', line)
            if food_align_match and current_dish:
                food_idx, food_total, food_name, food_form = food_align_match.groups()
                current_dish_foods.append({
                    'food_index': int(food_idx),
                    'name': food_name,
                    'form': food_form,
                    'missed': False,
                    'match_info': None,
                    'stage': None
                })

            # Match successful matches
            if '✓ Matched:' in line and current_dish_foods:
                match_info = line.split('✓ Matched:')[1].strip()
                stage_match = re.search(r'stage=([^,\)]+)', match_info)
                if stage_match:
                    current_dish_foods[-1]['stage'] = stage_match.group(1)
                current_dish_foods[-1]['match_info'] = match_info

            # Match decomposition
            if '✓ Decomposed' in line and current_dish_foods:
                current_dish_foods[-1]['stage'] = 'stage5b_salad_decomposition'
                current_dish_foods[-1]['match_info'] = line.split('✓ Decomposed')[1].strip()

            # Match misses
            if '✗ No match' in line and current_dish_foods:
                current_dish_foods[-1]['missed'] = True
                current_dish_foods[-1]['stage'] = 'stage0_no_candidates'

            # Match runs directory
            if '[PIPELINE] Artifacts saved to:' in line:
                runs_dir_match = re.search(r'runs/(\d+_\d+)/', line)
                if runs_dir_match and current_dish:
                    current_dish['runs_dir'] = runs_dir_match.group(1)

            # Match stage distribution
            if 'Stage distribution:' in line:
                stage_dist_match = re.search(r"Stage distribution: ({.+})", line)
                if stage_dist_match and current_dish:
                    try:
                        current_dish['stage_distribution'] = eval(stage_dist_match.group(1))
                    except:
                        pass

    # Save last dish
    if current_dish:
        current_dish['foods'] = current_dish_foods
        current_dish['miss_count'] = sum(1 for f in current_dish_foods if f['missed'])
        total_misses += current_dish['miss_count']
        dishes.append(current_dish)

    return {
        'dishes': dishes,
        'total_dishes': len(dishes),
        'total_misses': total_misses
    }


def load_telemetry_for_dish(runs_dir: str, dish_data: Dict) -> List[Dict[str, Any]]:
    """Load telemetry data for a specific dish from its runs directory."""
    telemetry_path = Path('runs') / runs_dir / 'telemetry.jsonl'

    if not telemetry_path.exists():
        return []

    telemetry = []
    with open(telemetry_path, 'r') as f:
        for line in f:
            if line.strip():
                telemetry.append(json.loads(line))

    return telemetry


def load_results_for_dish(runs_dir: str) -> Optional[Dict[str, Any]]:
    """Load results data for a specific dish from its runs directory."""
    results_path = Path('runs') / runs_dir / 'results.jsonl'

    if not results_path.exists():
        return None

    with open(results_path, 'r') as f:
        line = f.readline().strip()
        if line:
            return json.loads(line)

    return None


def analyze_miss_patterns(misses: List[Dict]) -> Dict[str, Any]:
    """Analyze patterns in missed matches."""
    miss_by_food = defaultdict(int)
    miss_by_form = defaultdict(int)
    miss_patterns = []

    for miss in misses:
        food_name = miss['food_name']
        food_form = miss['food_form']

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


def generate_report(log_path: Path, output_path: Path):
    """Generate comprehensive miss analysis report."""
    print("=" * 80)
    print("FIRST 50 DISHES - MISSED MATCHES ANALYSIS")
    print("=" * 80)
    print()

    # Parse log file
    log_data = parse_log_file(log_path)

    print(f"Total dishes processed: {log_data['total_dishes']}")
    print(f"Total missed matches: {log_data['total_misses']}")
    print()

    # Collect all misses with telemetry
    all_misses = []
    dishes_with_misses = []

    for dish in log_data['dishes']:
        if dish['miss_count'] > 0:
            # Load telemetry and results
            telemetry = []
            results = None

            if dish['runs_dir']:
                telemetry = load_telemetry_for_dish(dish['runs_dir'], dish)
                results = load_results_for_dish(dish['runs_dir'])

            # Extract missed foods with their telemetry
            for food in dish['foods']:
                if food['missed']:
                    # Find matching telemetry
                    food_telemetry = None
                    if telemetry:
                        for tel in telemetry:
                            if tel.get('query') == food['name']:
                                food_telemetry = tel
                                break

                    miss_entry = {
                        'dish_id': dish['dish_id'],
                        'dish_index': dish['dish_index'],
                        'runs_dir': dish['runs_dir'],
                        'food_name': food['name'],
                        'food_form': food['form'],
                        'food_index': food['food_index'],
                        'stage': food['stage'],
                        'telemetry': food_telemetry,
                        'full_dish_results': results
                    }

                    all_misses.append(miss_entry)

            # Add dish summary
            dishes_with_misses.append({
                'dish_id': dish['dish_id'],
                'dish_index': dish['dish_index'],
                'runs_dir': dish['runs_dir'],
                'total_foods': len(dish['foods']),
                'missed_foods': dish['miss_count'],
                'stage_distribution': dish['stage_distribution'],
                'foods': dish['foods']
            })

    # Analyze patterns
    patterns = analyze_miss_patterns([m for m in all_misses])

    # Extract unique missed foods (no duplicates)
    unique_missed_foods = sorted(set(miss['food_name'] for miss in all_misses))
    unique_miss_count = len(unique_missed_foods)

    # Build final report
    report = {
        'metadata': {
            'log_file': str(log_path),
            'generated_at': str(Path.cwd()),
            'total_dishes': log_data['total_dishes'],
            'dishes_with_misses': len(dishes_with_misses),
            'total_missed_foods': len(all_misses)
        },
        'summary': {
            'miss_rate': f"{(len(all_misses) / max(sum(len(d['foods']) for d in log_data['dishes']), 1)) * 100:.1f}%",
            'dishes_with_all_matches': log_data['total_dishes'] - len(dishes_with_misses),
            'dishes_with_some_misses': len(dishes_with_misses),
            'unique_missed_foods_count': unique_miss_count,
            'total_missed_instances': len(all_misses)
        },
        'patterns': patterns,
        'unique_missed_foods': unique_missed_foods,
        'dishes_with_misses': dishes_with_misses,
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
            print(f"  No telemetry available (runs_dir: {miss['runs_dir']})")

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
        description='Analyze missed food matches from First 50 Dishes test'
    )
    parser.add_argument(
        '--log',
        type=Path,
        default=Path('runs/first_50_latest.log'),
        help='Path to log file (default: runs/first_50_latest.log)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('first_50_misses_report.json'),
        help='Output path for JSON report (default: first_50_misses_report.json)'
    )

    args = parser.parse_args()

    if not args.log.exists():
        print(f"ERROR: Log file not found: {args.log}")
        print(f"Please provide a valid log file path.")
        return 1

    generate_report(args.log, args.output)
    return 0


if __name__ == '__main__':
    exit(main())
