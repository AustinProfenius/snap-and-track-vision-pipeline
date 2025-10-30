#!/usr/bin/env python3
"""
Phase Z2: Apply Remaining Implementation Changes

This script applies the remaining Phase Z2 changes that don't require
extensive code analysis (config updates). The normalization fixes to
align_convert.py should be applied manually due to their complexity.

Usage:
    python apply_phase_z2_remaining.py
"""

import sys
from pathlib import Path
import yaml

def add_celery_to_stage_z_config():
    """Add celery root mapping to Stage Z config."""
    config_path = Path("configs/stageZ_branded_fallbacks.yml")

    print(f"[1/2] Adding celery mapping to {config_path}...")

    if not config_path.exists():
        print(f"  ERROR: {config_path} not found")
        return False

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Check if celery already exists
    if 'celery' in config.get('fallbacks', {}):
        print(f"  ⚠ Celery entry already exists, skipping")
        return True

    # Add celery entry
    config['fallbacks']['celery'] = {
        'synonyms': ['celery root', 'celeriac', 'celery stalk', 'celery stalks'],
        'primary': {
            'brand': 'Generic',
            'fdc_id': 2346405,
            'kcal_per_100g': [10, 25]
        },
        'alternates': []
    }

    # Write back
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"  ✓ Added celery mapping (FDC 2346405)")
    return True


def add_ignore_rules_to_negative_vocab():
    """Add tatsoi, alcohol, and deprecated ignore rules."""
    vocab_path = Path("configs/negative_vocabulary.yml")

    print(f"\n[2/2] Adding ignore rules to {vocab_path}...")

    if not vocab_path.exists():
        print(f"  ERROR: {vocab_path} not found")
        return False

    with open(vocab_path, 'r') as f:
        vocab = yaml.safe_load(f) or {}

    # Add tatsoi
    if 'tatsoi' not in vocab:
        vocab['tatsoi'] = ['all']
        print(f"  ✓ Added tatsoi ignore rule")
    else:
        print(f"  ⚠ tatsoi rule already exists")

    # Add deprecated
    if 'deprecated' not in vocab:
        vocab['deprecated'] = ['all']
        print(f"  ✓ Added deprecated ignore rule")
    else:
        print(f"  ⚠ deprecated rule already exists")

    # Add alcohol entries
    alcohol_entries = {
        'white_wine': ['all'],
        'red_wine': ['all'],
        'beer': ['all'],
        'wine': ['all'],
        'vodka': ['all'],
        'whiskey': ['all'],
        'rum': ['all'],
        'tequila': ['all'],
        'sake': ['all']
    }

    alcohol_added = 0
    for drink, rules in alcohol_entries.items():
        if drink not in vocab:
            vocab[drink] = rules
            alcohol_added += 1

    if alcohol_added > 0:
        print(f"  ✓ Added {alcohol_added} alcoholic beverage ignore rules")
    else:
        print(f"  ⚠ All alcohol rules already exist")

    # Write back
    with open(vocab_path, 'w') as f:
        yaml.dump(vocab, f, default_flow_style=False, sort_keys=False)

    return True


def main():
    print("=" * 80)
    print("Phase Z2: Apply Remaining Config Changes")
    print("=" * 80)
    print()

    # Change to project root
    project_root = Path(__file__).parent
    import os
    os.chdir(project_root)

    success = True

    # Apply config changes
    if not add_celery_to_stage_z_config():
        success = False

    if not add_ignore_rules_to_negative_vocab():
        success = False

    print()
    print("=" * 80)
    if success:
        print("✓ Config changes applied successfully!")
    else:
        print("✗ Some changes failed (see errors above)")
    print("=" * 80)
    print()

    print("Next steps:")
    print("1. Manually apply normalization fixes to align_convert.py")
    print("   See: docs/phase_z2_normalization_patch.md")
    print()
    print("2. Add telemetry enhancements")
    print("   See: PHASE_Z2_README.md → Step 4")
    print()
    print("3. Create test suite")
    print("   See: PHASE_Z2_README.md → Step 5")
    print()
    print("4. Run integration validation")
    print("   ./phase_z2_quickstart.sh")
    print()

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
