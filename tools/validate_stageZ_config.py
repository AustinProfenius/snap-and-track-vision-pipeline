#!/usr/bin/env python3
"""
Stage Z Config Validator (Phase Z2)

Validates stageZ_branded_fallbacks.yml for:
- No duplicate keys
- kcal_min < kcal_max
- FDC IDs exist in database (if DB available)
- No conflicting synonyms across entries

Usage:
    python tools/validate_stageZ_config.py configs/stageZ_branded_fallbacks.yml
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict

try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML not installed. Run: pip install pyyaml")
    sys.exit(1)

# Try to import FDC database (optional for validation)
try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "nutritionverse-tests"))
    from src.nutrition.fdc_lookup import FDCDatabase
    HAS_FDC = True
except ImportError:
    HAS_FDC = False


class ValidationError(Exception):
    """Critical validation error that should fail the check."""
    pass


class ValidationWarning:
    """Non-critical validation warning."""
    def __init__(self, message: str):
        self.message = message


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load Stage Z config YAML."""
    if not config_path.exists():
        raise ValidationError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def check_duplicate_keys(fallbacks: Dict[str, Any]) -> List[str]:
    """Check for duplicate keys (should be impossible in YAML, but validate structure)."""
    errors = []
    keys = list(fallbacks.keys())
    seen = set()

    for key in keys:
        if key in seen:
            errors.append(f"Duplicate key found: '{key}'")
        seen.add(key)

    return errors


def check_kcal_ranges(fallbacks: Dict[str, Any]) -> Tuple[List[str], List[ValidationWarning]]:
    """Validate kcal_min < kcal_max for all entries."""
    errors = []
    warnings = []

    for key, entry in fallbacks.items():
        # Check primary
        primary = entry.get('primary', {})
        kcal_range = primary.get('kcal_per_100g')

        if kcal_range and isinstance(kcal_range, list) and len(kcal_range) == 2:
            kcal_min, kcal_max = kcal_range
            if kcal_min >= kcal_max:
                errors.append(f"Key '{key}': kcal_min ({kcal_min}) >= kcal_max ({kcal_max})")
            elif kcal_min < 0 or kcal_max < 0:
                errors.append(f"Key '{key}': negative kcal values not allowed")
            elif kcal_max > 1000:
                warnings.append(ValidationWarning(
                    f"Key '{key}': unusually high kcal_max ({kcal_max})"
                ))
        else:
            warnings.append(ValidationWarning(
                f"Key '{key}': missing or malformed kcal_per_100g in primary"
            ))

        # Check alternates
        alternates = entry.get('alternates', [])
        for i, alt in enumerate(alternates):
            kcal_range = alt.get('kcal_per_100g')
            if kcal_range and isinstance(kcal_range, list) and len(kcal_range) == 2:
                kcal_min, kcal_max = kcal_range
                if kcal_min >= kcal_max:
                    errors.append(f"Key '{key}' alternate {i}: kcal_min ({kcal_min}) >= kcal_max ({kcal_max})")
                elif kcal_min < 0 or kcal_max < 0:
                    errors.append(f"Key '{key}' alternate {i}: negative kcal values not allowed")

    return errors, warnings


def check_fdc_ids(fallbacks: Dict[str, Any], fdc_db: Any) -> Tuple[List[str], List[ValidationWarning], Dict[str, Any]]:
    """Validate FDC IDs exist in database."""
    errors = []
    warnings = []
    stats = {
        'total_ids_checked': 0,
        'verified': 0,
        'missing': 0,
        'unknown': 0
    }

    if not fdc_db:
        warnings.append(ValidationWarning("FDC database not available; skipping ID validation"))
        return errors, warnings, stats

    missing_ids = []

    for key, entry in fallbacks.items():
        # Check primary
        primary = entry.get('primary', {})
        fdc_id = primary.get('fdc_id')

        if fdc_id:
            stats['total_ids_checked'] += 1
            try:
                fdc_entry = fdc_db.get_by_fdc_id(fdc_id)
                if fdc_entry is None:
                    stats['missing'] += 1
                    missing_ids.append((key, fdc_id, 'primary'))
                    warnings.append(ValidationWarning(
                        f"Key '{key}': primary FDC ID {fdc_id} not found in database"
                    ))
                else:
                    stats['verified'] += 1
            except Exception as e:
                stats['unknown'] += 1
                warnings.append(ValidationWarning(
                    f"Key '{key}': error validating FDC ID {fdc_id}: {e}"
                ))

        # Check alternates
        alternates = entry.get('alternates', [])
        for i, alt in enumerate(alternates):
            alt_fdc_id = alt.get('fdc_id')
            if alt_fdc_id:
                stats['total_ids_checked'] += 1
                try:
                    fdc_entry = fdc_db.get_by_fdc_id(alt_fdc_id)
                    if fdc_entry is None:
                        stats['missing'] += 1
                        missing_ids.append((key, alt_fdc_id, f'alternate {i}'))
                        warnings.append(ValidationWarning(
                            f"Key '{key}' alternate {i}: FDC ID {alt_fdc_id} not found in database"
                        ))
                    else:
                        stats['verified'] += 1
                except Exception as e:
                    stats['unknown'] += 1

    return errors, warnings, stats


def check_synonym_conflicts(fallbacks: Dict[str, Any]) -> Tuple[List[str], List[ValidationWarning]]:
    """Check for conflicting synonyms (same synonym mapping to multiple keys)."""
    errors = []
    warnings = []

    synonym_map = defaultdict(list)  # synonym -> list of keys that use it

    for key, entry in fallbacks.items():
        synonyms = entry.get('synonyms', [])
        for syn in synonyms:
            syn_normalized = syn.lower().strip()
            synonym_map[syn_normalized].append(key)

    # Find conflicts
    conflicts = {syn: keys for syn, keys in synonym_map.items() if len(keys) > 1}

    for syn, keys in conflicts.items():
        warnings.append(ValidationWarning(
            f"Synonym '{syn}' used by multiple keys: {', '.join(keys)}"
        ))

    return errors, warnings


def print_summary_table(fallbacks: Dict[str, Any], fdc_stats: Dict[str, Any]):
    """Print a summary table of all entries."""
    print("\n" + "=" * 100)
    print("STAGE Z CONFIG SUMMARY")
    print("=" * 100)
    print(f"{'Key':<30} {'FDC ID':<12} {'Kcal Bounds':<15} {'Synonyms':<10} {'DB Verified':<12}")
    print("-" * 100)

    for key, entry in sorted(fallbacks.items()):
        primary = entry.get('primary', {})
        fdc_id = primary.get('fdc_id', 'N/A')
        kcal_range = primary.get('kcal_per_100g', [])
        kcal_str = f"[{kcal_range[0]}, {kcal_range[1]}]" if len(kcal_range) == 2 else "N/A"
        synonyms_count = len(entry.get('synonyms', []))
        alternates_count = len(entry.get('alternates', []))

        # Check if metadata indicates missing in DB
        metadata = entry.get('_metadata', {})
        db_verified_str = "❌ Missing" if metadata.get('fdc_id_missing_in_db') else "✓" if fdc_stats else "?"

        key_display = key[:28] + ".." if len(key) > 30 else key
        print(f"{key_display:<30} {str(fdc_id):<12} {kcal_str:<15} {synonyms_count:<10} {db_verified_str:<12}")

        if alternates_count > 0:
            print(f"  └─ {alternates_count} alternates")

    print("-" * 100)
    print(f"Total entries: {len(fallbacks)}")
    if fdc_stats:
        print(f"FDC IDs checked: {fdc_stats['total_ids_checked']}")
        print(f"  ✓ Verified: {fdc_stats['verified']}")
        print(f"  ❌ Missing: {fdc_stats['missing']}")
        print(f"  ? Unknown: {fdc_stats['unknown']}")
    print("=" * 100)


def main():
    parser = argparse.ArgumentParser(
        description='Validate Stage Z branded fallbacks config'
    )
    parser.add_argument('config', type=Path,
                       help='Path to stageZ_branded_fallbacks.yml')
    parser.add_argument('--fdc-db-path', type=Path,
                       help='Path to FDC SQLite database (for ID validation)')
    parser.add_argument('--no-summary', action='store_true',
                       help='Skip summary table output')

    args = parser.parse_args()

    print("=" * 80)
    print("Stage Z Config Validator (Phase Z2)")
    print("=" * 80)
    print()

    # Load config
    print(f"[1/5] Loading config: {args.config}")
    try:
        config = load_config(args.config)
    except ValidationError as e:
        print(f"  ❌ ERROR: {e}")
        return 1

    fallbacks = config.get('fallbacks', {})
    print(f"  ✓ Loaded {len(fallbacks)} entries")

    # Load FDC database (if available)
    fdc_db = None
    fdc_stats = None
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
                print(f"  ✓ FDC database loaded for validation")
        except Exception as e:
            print(f"  ⚠ Could not load FDC database: {e}")

    # Run validations
    all_errors = []
    all_warnings = []

    print(f"\n[2/5] Checking for duplicate keys...")
    dup_errors = check_duplicate_keys(fallbacks)
    all_errors.extend(dup_errors)
    if dup_errors:
        print(f"  ❌ Found {len(dup_errors)} duplicate key(s)")
    else:
        print(f"  ✓ No duplicates")

    print(f"\n[3/5] Validating kcal ranges...")
    kcal_errors, kcal_warnings = check_kcal_ranges(fallbacks)
    all_errors.extend(kcal_errors)
    all_warnings.extend(kcal_warnings)
    if kcal_errors:
        print(f"  ❌ Found {len(kcal_errors)} invalid range(s)")
    else:
        print(f"  ✓ All ranges valid")
    if kcal_warnings:
        print(f"  ⚠ {len(kcal_warnings)} warning(s)")

    print(f"\n[4/5] Validating FDC IDs...")
    fdc_errors, fdc_warnings, fdc_stats = check_fdc_ids(fallbacks, fdc_db)
    all_errors.extend(fdc_errors)
    all_warnings.extend(fdc_warnings)
    if fdc_db:
        if fdc_stats['missing'] > 0:
            print(f"  ⚠ {fdc_stats['missing']} ID(s) not found in database")
        print(f"  ✓ Checked {fdc_stats['total_ids_checked']} ID(s)")
        print(f"    - Verified: {fdc_stats['verified']}")
        print(f"    - Missing: {fdc_stats['missing']}")
        print(f"    - Unknown: {fdc_stats['unknown']}")
    else:
        print(f"  ⚠ FDC database not available; skipping ID validation")

    print(f"\n[5/5] Checking synonym conflicts...")
    syn_errors, syn_warnings = check_synonym_conflicts(fallbacks)
    all_errors.extend(syn_errors)
    all_warnings.extend(syn_warnings)
    if syn_warnings:
        print(f"  ⚠ {len(syn_warnings)} conflict(s) found")
    else:
        print(f"  ✓ No conflicts")

    # Print all warnings
    if all_warnings:
        print("\n" + "=" * 80)
        print("WARNINGS")
        print("=" * 80)
        for warning in all_warnings:
            print(f"  ⚠ {warning.message}")

    # Print all errors
    if all_errors:
        print("\n" + "=" * 80)
        print("ERRORS")
        print("=" * 80)
        for error in all_errors:
            print(f"  ❌ {error}")

    # Print summary table
    if not args.no_summary:
        print_summary_table(fallbacks, fdc_stats)

    # Final verdict
    print("\n" + "=" * 80)
    if all_errors:
        print(f"❌ VALIDATION FAILED: {len(all_errors)} error(s), {len(all_warnings)} warning(s)")
        print("=" * 80)
        return 1
    elif all_warnings:
        print(f"✓ VALIDATION PASSED (with {len(all_warnings)} warning(s))")
        print("=" * 80)
        return 0
    else:
        print("✓ VALIDATION PASSED")
        print("=" * 80)
        return 0


if __name__ == '__main__':
    sys.exit(main())
