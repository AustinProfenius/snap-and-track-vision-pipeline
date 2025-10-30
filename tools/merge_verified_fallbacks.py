#!/usr/bin/env python3
"""
CSV → Stage Z Merger (Phase Z2)

Ingests manually-verified FDC mappings from missed_food_names.csv and generates/merges
Stage Z branded fallback entries with DB validation and precedence rules.

Usage:
    python tools/merge_verified_fallbacks.py \\
        --csv ./missed_food_names.csv \\
        --out configs/stageZ_branded_fallbacks_verified.yml \\
        --merge-into configs/stageZ_branded_fallbacks.yml \\
        --report runs/csv_merge_report.json
"""

import csv
import json
import re
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime

# Try to import FDC database (optional for validation)
try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "nutritionverse-tests"))
    from src.nutrition.fdc_lookup import FDCDatabase
    HAS_FDC = True
except ImportError:
    HAS_FDC = False
    print("[WARN] FDC database not available; skipping DB validation")

try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML not installed. Run: pip install pyyaml")
    sys.exit(1)


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal types."""
    def default(self, obj):
        from decimal import Decimal
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def normalize_key(name: str) -> str:
    """
    Normalize food name to Stage Z config key format.

    Rules:
    - Lowercase
    - Spaces → underscores
    - Strip punctuation (except underscores)
    - Strip leading/trailing whitespace

    Examples:
        "Cherry Tomatoes" → "cherry_tomatoes"
        "Sun-Dried Tomatoes" → "sun_dried_tomatoes"
        "Celery Root" → "celery_root"
    """
    key = name.lower().strip()
    # Replace hyphens and spaces with underscores
    key = re.sub(r'[\s-]+', '_', key)
    # Remove all punctuation except underscores
    key = re.sub(r'[^\w_]', '', key)
    # Collapse multiple underscores
    key = re.sub(r'_+', '_', key)
    return key.strip('_')


def infer_kcal_bounds(name: str, data_type: str, category: str) -> Tuple[int, int]:
    """
    Infer kcal/100g bounds based on food type if not provided in CSV.

    Rules (from spec):
    - Produce/leafy: [10, 100] (leafy greens: [10, 50])
    - Proteins: [100, 300]
    - Grains raw: [300, 400] | cooked: [100, 200]
    - Oils/sauces: [60, 900]
    """
    name_lower = name.lower()
    category_lower = category.lower() if category else ""

    # Leafy greens
    if any(x in name_lower for x in ['spinach', 'lettuce', 'tatsoi', 'arugula', 'kale', 'chard']):
        return (10, 50)

    # Oils and sauces
    if any(x in name_lower for x in ['oil', 'vinaigrette', 'dressing', 'sauce']):
        return (60, 900)

    # Proteins
    if any(x in name_lower for x in ['chicken', 'beef', 'steak', 'fish', 'salmon', 'tuna', 'cod', 'turkey']):
        return (100, 300)

    # Cheese/dairy
    if any(x in name_lower for x in ['cheese', 'yogurt', 'cottage']):
        return (50, 400)

    # Grains
    if any(x in name_lower for x in ['rice', 'wheat', 'grain', 'pilaf', 'noodle']):
        # Check if cooked
        if any(x in name_lower for x in ['cooked', 'prepared', 'ready']):
            return (100, 200)
        return (300, 400)

    # Eggs
    if 'egg' in name_lower or 'scrambled' in name_lower:
        return (120, 200)

    # Produce (default for vegetables/fruits)
    if any(x in category_lower for x in ['vegetable', 'fruit', 'produce']):
        return (10, 100)

    # Default: produce range
    return (10, 100)


def parse_csv_row(row: Dict[str, str], row_num: int) -> Optional[Dict[str, Any]]:
    """
    Parse a CSV row into a normalized food entry dict.

    Returns None if row is malformed or missing required fields.
    """
    # Normalize column names (case-insensitive)
    row_normalized = {k.strip().lower(): v.strip() for k, v in row.items()}

    # Required fields
    name = row_normalized.get('name', '').strip()
    fdc_id_str = row_normalized.get('fdc_id', '').strip()

    if not name or not fdc_id_str:
        print(f"[WARN] Row {row_num}: Missing required fields (name or fdc_id), skipping")
        return None

    try:
        fdc_id = int(fdc_id_str)
    except ValueError:
        print(f"[WARN] Row {row_num}: Invalid fdc_id '{fdc_id_str}', skipping")
        return None

    # Optional fields
    normalized_key = row_normalized.get('normalized_key', '').strip()
    if not normalized_key:
        normalized_key = normalize_key(name)
    else:
        normalized_key = normalize_key(normalized_key)  # Normalize even if provided

    # Parse synonyms (semicolon-separated)
    synonyms_str = row_normalized.get('synonyms', '').strip()
    synonyms = [s.strip() for s in synonyms_str.split(';') if s.strip()] if synonyms_str else []

    # Parse kcal bounds
    kcal_min_str = row_normalized.get('kcal_min', '').strip()
    kcal_max_str = row_normalized.get('kcal_max', '').strip()

    data_type = row_normalized.get('data_type', '').strip()
    category = row_normalized.get('food_category_id', '').strip()

    if kcal_min_str and kcal_max_str:
        try:
            kcal_min = int(float(kcal_min_str))
            kcal_max = int(float(kcal_max_str))
            kcal_inferred = False
        except ValueError:
            kcal_min, kcal_max = infer_kcal_bounds(name, data_type, category)
            kcal_inferred = True
    else:
        kcal_min, kcal_max = infer_kcal_bounds(name, data_type, category)
        kcal_inferred = True

    # Notes
    notes = row_normalized.get('notes', '').strip()

    return {
        'row_num': row_num,
        'name': name,
        'normalized_key': normalized_key,
        'fdc_id': fdc_id,
        'synonyms': synonyms,
        'kcal_min': kcal_min,
        'kcal_max': kcal_max,
        'kcal_inferred': kcal_inferred,
        'data_type': data_type,
        'category': category,
        'notes': notes
    }


def validate_fdc_id(fdc_id: int, fdc_db: Optional[Any]) -> bool:
    """Check if FDC ID exists in database."""
    if not fdc_db or not HAS_FDC:
        return None  # Unknown (DB not available)

    try:
        entry = fdc_db.get_by_fdc_id(fdc_id)
        return entry is not None
    except Exception as e:
        print(f"[WARN] Error validating FDC ID {fdc_id}: {e}")
        return None


def apply_special_case_rules(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply special case rules from CSV notes (per user specification).

    Rules:
    1. Cherry tomato (line 24): Use Foundation 321360 only if DB-verified
    2. Chicken (line 25): Apply 2646170 only when query has "breast" tokens
    3. Chilaquiles (line 29): Add low_confidence_mapping note, tight kcal guard
    4. Orange with peel (line 59): Normalize to "orange", add peel hint
    """
    key = entry['normalized_key']
    name = entry['name'].lower()
    notes = entry.get('notes', '').lower()

    # Cherry tomato: Only use foundation if explicitly validated
    if 'cherry' in key and 'tomato' in key:
        if entry['fdc_id'] == 321360 and entry.get('data_type') == 'foundation_food':
            # This is the foundation entry from CSV
            entry['notes_processed'] = "Foundation entry (CSV line 24); use if DB-verified"
        elif 'grape branded' in notes or 'unreliable' in notes:
            entry['notes_processed'] = "CSV note: grape branded unreliable"

    # Chicken breast: Add note that this should only apply to "breast" queries
    if 'chicken' in key and ('breast' in name or entry['fdc_id'] == 2646170):
        entry['token_constraint'] = ['breast']  # Only match if "breast" in query
        entry['notes_processed'] = "Apply only when query contains 'breast' tokens"

    # Chilaquiles: Low confidence mapping
    if 'chilaquiles' in name.lower():
        entry['low_confidence'] = True
        entry['kcal_min'] = max(entry['kcal_min'], 120)
        entry['kcal_max'] = min(entry['kcal_max'], 200)
        entry['reject_patterns'] = ['with sauce', 'cheese', 'refried']
        entry['notes_processed'] = "Low confidence mapping (CSV line 29)"

    # Orange with peel: Normalize to "orange", add peel hint
    if 'orange' in key and ('peel' in name or 'peel' in notes):
        entry['normalized_key'] = 'orange'  # Normalize to plain orange
        entry['peel_hint'] = True
        entry['notes_processed'] = "Peel qualifier → telemetry hint only"

    return entry


def group_entries_by_key(entries: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group parsed entries by normalized_key for deduplication."""
    grouped = defaultdict(list)
    for entry in entries:
        grouped[entry['normalized_key']].append(entry)
    return grouped


def build_yaml_entry(key: str, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a Stage Z YAML entry from one or more CSV rows with the same normalized key.

    If multiple rows exist (e.g., 5 steak variants), use first as primary, rest as alternates.
    """
    if not entries:
        return None

    # Sort by row number (preserve CSV order)
    entries = sorted(entries, key=lambda e: e['row_num'])

    primary_entry = entries[0]
    alternates = entries[1:] if len(entries) > 1 else []

    # Collect all unique synonyms
    all_synonyms = set()
    for entry in entries:
        all_synonyms.update(entry['synonyms'])
        # Add the original name as a synonym if different from key
        if entry['name'].lower() != key:
            all_synonyms.add(entry['name'].lower())

    all_synonyms = sorted(list(all_synonyms))

    # Build YAML structure
    yaml_entry = {
        'synonyms': all_synonyms,
        'primary': {
            'brand': 'Generic',  # Default brand
            'fdc_id': primary_entry['fdc_id'],
            'kcal_per_100g': [primary_entry['kcal_min'], primary_entry['kcal_max']]
        }
    }

    # Add alternates if any
    if alternates:
        yaml_entry['alternates'] = [
            {
                'brand': 'Generic',
                'fdc_id': alt['fdc_id'],
                'kcal_per_100g': [alt['kcal_min'], alt['kcal_max']]
            }
            for alt in alternates
        ]

    # Add metadata for special cases
    metadata = {}
    if primary_entry.get('low_confidence'):
        metadata['low_confidence'] = True
        if primary_entry.get('reject_patterns'):
            metadata['reject_patterns'] = primary_entry['reject_patterns']

    if primary_entry.get('token_constraint'):
        metadata['token_constraint'] = primary_entry['token_constraint']

    if primary_entry.get('peel_hint'):
        metadata['peel_hint'] = True

    if primary_entry.get('notes_processed'):
        metadata['_notes'] = primary_entry['notes_processed']

    if metadata:
        yaml_entry['_metadata'] = metadata

    return yaml_entry


def load_existing_config(config_path: Path) -> Dict[str, Any]:
    """Load existing Stage Z config YAML."""
    if not config_path.exists():
        print(f"[WARN] Config file not found: {config_path}, starting fresh")
        return {
            'version': 1,
            'enabled': True,
            'selection_rules': {
                'preferred_descriptors': ['raw', 'plain', 'unseasoned'],
                'reject_patterns': ['seasoned', 'sauce', 'flavored', 'with oil', 'with butter',
                                   'sweetened', 'glazed', 'candied', 'fried', 'fast food', 'baby food']
            },
            'plausibility_guards': {
                'produce': [10, 100],
                'eggs': [120, 200],
                'protein': [100, 300]
            },
            'fallbacks': {}
        }

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def merge_entries(existing_config: Dict[str, Any],
                  csv_entries: Dict[str, Dict[str, Any]],
                  fdc_db: Optional[Any],
                  precedence_mode: str = 'csv_if_verified') -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Merge CSV entries into existing config with precedence rules.

    Precedence:
    - If existing entry is DB-verified and CSV entry is NOT verified → keep existing
    - Otherwise, CSV entry wins (it's manually verified)

    Returns:
        (merged_config, merge_report)
    """
    merged = existing_config.copy()
    if 'fallbacks' not in merged:
        merged['fallbacks'] = {}

    report = {
        'replaced_keys': [],
        'new_keys': [],
        'skipped_due_to_precedence': [],
        'db_validation_summary': {
            'verified': 0,
            'missing_in_db': 0,
            'unknown': 0
        }
    }

    for key, yaml_entry in csv_entries.items():
        csv_fdc_id = yaml_entry['primary']['fdc_id']
        csv_db_verified = validate_fdc_id(csv_fdc_id, fdc_db)

        # Track DB validation stats
        if csv_db_verified is True:
            report['db_validation_summary']['verified'] += 1
        elif csv_db_verified is False:
            report['db_validation_summary']['missing_in_db'] += 1
        else:
            report['db_validation_summary']['unknown'] += 1

        existing_entry = merged['fallbacks'].get(key)

        if existing_entry:
            # Check if existing entry is DB-verified
            existing_fdc_id = existing_entry.get('primary', {}).get('fdc_id')
            existing_db_verified = validate_fdc_id(existing_fdc_id, fdc_db) if existing_fdc_id else None

            # Precedence rule: Don't overwrite verified with unverified
            if existing_db_verified is True and csv_db_verified is False:
                report['skipped_due_to_precedence'].append({
                    'key': key,
                    'reason': 'Existing entry is DB-verified, CSV entry is not',
                    'existing_fdc_id': existing_fdc_id,
                    'csv_fdc_id': csv_fdc_id
                })
                continue

            report['replaced_keys'].append({
                'key': key,
                'old_fdc_id': existing_fdc_id,
                'new_fdc_id': csv_fdc_id
            })
        else:
            report['new_keys'].append({
                'key': key,
                'fdc_id': csv_fdc_id
            })

        # Mark if FDC ID is missing in DB
        if csv_db_verified is False:
            if '_metadata' not in yaml_entry:
                yaml_entry['_metadata'] = {}
            yaml_entry['_metadata']['fdc_id_missing_in_db'] = True

        merged['fallbacks'][key] = yaml_entry

    return merged, report


def main():
    parser = argparse.ArgumentParser(
        description='Merge verified FDC mappings from CSV into Stage Z config'
    )
    parser.add_argument('--csv', type=Path, required=True,
                       help='Path to missed_food_names.csv')
    parser.add_argument('--out', type=Path, required=True,
                       help='Output path for generated verified YAML')
    parser.add_argument('--merge-into', type=Path,
                       help='Existing config to merge into (optional)')
    parser.add_argument('--report', type=Path,
                       help='Output path for merge report JSON')
    parser.add_argument('--fdc-db-path', type=Path,
                       help='Path to FDC SQLite database (for validation)')

    args = parser.parse_args()

    print("=" * 80)
    print("CSV → Stage Z Merger (Phase Z2)")
    print("=" * 80)
    print()

    # Load FDC database for validation (if available)
    fdc_db = None
    if HAS_FDC:
        try:
            if args.fdc_db_path:
                fdc_db = FDCDatabase(str(args.fdc_db_path))
            else:
                # Try default path
                default_db_path = Path(__file__).parent.parent / "fdc_database.db"
                if default_db_path.exists():
                    fdc_db = FDCDatabase(str(default_db_path))
            if fdc_db:
                print(f"[INFO] FDC database loaded for validation")
        except Exception as e:
            print(f"[WARN] Could not load FDC database: {e}")

    # Parse CSV
    print(f"[1/4] Parsing CSV: {args.csv}")
    parsed_entries = []
    skipped_rows = []

    with open(args.csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
            entry = parse_csv_row(row, row_num)
            if entry:
                # Apply special case rules
                entry = apply_special_case_rules(entry)
                parsed_entries.append(entry)
            else:
                skipped_rows.append(row_num)

    print(f"  Parsed: {len(parsed_entries)} entries")
    print(f"  Skipped: {len(skipped_rows)} malformed rows")

    # Group by normalized key
    print(f"\n[2/4] Grouping entries by normalized key...")
    grouped = group_entries_by_key(parsed_entries)
    print(f"  Unique keys: {len(grouped)}")

    # Build YAML entries
    print(f"\n[3/4] Building YAML entries...")
    yaml_entries = {}
    kcal_inferred_count = 0

    for key, entries in grouped.items():
        yaml_entry = build_yaml_entry(key, entries)
        if yaml_entry:
            yaml_entries[key] = yaml_entry
            if any(e['kcal_inferred'] for e in entries):
                kcal_inferred_count += 1

    print(f"  Generated: {len(yaml_entries)} YAML entries")
    print(f"  Kcal bounds inferred: {kcal_inferred_count}")

    # Generate verified YAML file
    verified_config = {
        'version': 1,
        'enabled': True,
        '_generated_from': str(args.csv),
        '_generated_at': datetime.now().isoformat(),
        'fallbacks': yaml_entries
    }

    print(f"\n[4/4] Writing outputs...")

    # Write verified YAML
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, 'w') as f:
        yaml.dump(verified_config, f, default_flow_style=False, sort_keys=False)
    print(f"  ✓ Verified config: {args.out}")

    # Merge into existing config if specified
    merge_report = None
    if args.merge_into:
        print(f"\n  Merging into: {args.merge_into}")
        existing_config = load_existing_config(args.merge_into)
        merged_config, merge_report = merge_entries(existing_config, yaml_entries, fdc_db)

        # Write merged config
        with open(args.merge_into, 'w') as f:
            yaml.dump(merged_config, f, default_flow_style=False, sort_keys=False)
        print(f"  ✓ Merged config: {args.merge_into}")
        print(f"    - New keys: {len(merge_report['new_keys'])}")
        print(f"    - Replaced keys: {len(merge_report['replaced_keys'])}")
        print(f"    - Skipped (precedence): {len(merge_report['skipped_due_to_precedence'])}")

    # Write merge report
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        full_report = {
            'timestamp': datetime.now().isoformat(),
            'csv_file': str(args.csv),
            'verified_output': str(args.out),
            'merge_target': str(args.merge_into) if args.merge_into else None,
            'parsing': {
                'total_rows': len(parsed_entries) + len(skipped_rows),
                'parsed': len(parsed_entries),
                'skipped': len(skipped_rows),
                'skipped_rows': skipped_rows
            },
            'generation': {
                'unique_keys': len(yaml_entries),
                'kcal_inferred_count': kcal_inferred_count
            },
            'merge': merge_report if merge_report else None
        }

        with open(args.report, 'w') as f:
            json.dump(full_report, f, indent=2, cls=DecimalEncoder)
        print(f"  ✓ Merge report: {args.report}")

    print("\n" + "=" * 80)
    print("CSV merge complete!")
    print("=" * 80)

    return 0


if __name__ == '__main__':
    sys.exit(main())
