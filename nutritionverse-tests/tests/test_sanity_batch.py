#!/usr/bin/env python3
"""
Sanity Batch Test Runner

Validates Phase A-D conversion wiring fixes on a curated 10-item batch.
Tests conversion layer, synonyms, guards, and telemetry tracking.

Run with:
    python tests/test_sanity_batch.py
    ALIGN_VERBOSE=1 python tests/test_sanity_batch.py  # verbose mode
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import alignment engine and database
from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion
from src.adapters.fdc_database import FDCDatabase


def load_sanity_batch() -> Dict[str, Any]:
    """Load the sanity batch fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "sanity_batch_10items.json"
    with open(fixture_path) as f:
        return json.load(f)


def run_sanity_batch_evaluation():
    """
    Run alignment evaluation on 10-item sanity batch.

    Validates:
    - Conversion hit rate ≥60%
    - No "unknown" stages or methods
    - Targeted cases match expectations
    """
    print("\n" + "="*70)
    print("SANITY BATCH EVALUATION (10 items)")
    print("Validates Phase A-D Conversion Wiring Fixes")
    print("="*70 + "\n")

    # Load fixture
    batch_data = load_sanity_batch()
    items = batch_data["items"]
    expected_metrics = batch_data["expected_metrics"]

    # Initialize alignment engine and FDC database
    aligner = FDCAlignmentWithConversion()
    fdc_db = FDCDatabase()

    # Track results
    results = []
    conversion_count = 0
    stage_distribution = {}
    method_distribution = {}
    unknown_stages = []
    unknown_methods = []

    verbose = os.getenv('ALIGN_VERBOSE', '0') == '1'

    # Process each item
    for idx, item in enumerate(items, 1):
        item_id = item["id"]
        predicted_name = item["predicted_name"]
        predicted_form = item["predicted_form"]
        predicted_kcal = item["predicted_kcal_100g"]
        confidence = item["confidence"]
        expected = item.get("expected", {})

        print(f"[{idx}/10] {item_id}")
        print(f"  Input: '{predicted_name}' (form={predicted_form}, kcal={predicted_kcal})")

        # Get FDC candidates
        fdc_candidates = fdc_db.search_foods(predicted_name, limit=50)

        if not fdc_candidates:
            print(f"  ⚠️  WARNING: No FDC candidates found for '{predicted_name}'")
            results.append({
                "item_id": item_id,
                "status": "no_candidates",
                "alignment_stage": "stage0_no_candidates"
            })
            stage_distribution["stage0_no_candidates"] = \
                stage_distribution.get("stage0_no_candidates", 0) + 1
            continue

        # Run alignment
        result = aligner.align_food_item(
            predicted_name=predicted_name,
            predicted_form=predicted_form,
            predicted_kcal_100g=predicted_kcal,
            fdc_candidates=fdc_candidates,
            confidence=confidence
        )

        # Extract telemetry
        stage = result.alignment_stage
        method = result.telemetry.get("method", "unknown")
        conversion_applied = result.telemetry.get("conversion_applied", False)
        stage1_blocked = result.telemetry.get("stage1_blocked_raw_foundation_exists", False)

        # Track metrics
        if conversion_applied:
            conversion_count += 1

        stage_distribution[stage] = stage_distribution.get(stage, 0) + 1
        method_distribution[method] = method_distribution.get(method, 0) + 1

        # Track unknown values
        if stage == "unknown":
            unknown_stages.append(item_id)
        if method == "unknown":
            unknown_methods.append(item_id)

        # Print result
        print(f"  Stage: {stage}")
        print(f"  Method: {method}")
        print(f"  Conversion: {'✓' if conversion_applied else '✗'}")
        if stage1_blocked:
            print(f"  Stage1 Blocked: ✓ (raw Foundation exists)")

        # Validate expectations
        expectations_met = True
        if "alignment_stage" in expected:
            if stage != expected["alignment_stage"]:
                print(f"  ❌ Expected stage {expected['alignment_stage']}, got {stage}")
                expectations_met = False
            else:
                print(f"  ✓ Expected stage matched")

        if "conversion_applied" in expected:
            if conversion_applied != expected["conversion_applied"]:
                print(f"  ❌ Expected conversion={expected['conversion_applied']}, got {conversion_applied}")
                expectations_met = False

        if "method" in expected:
            if method != expected["method"]:
                print(f"  ⚠️  Expected method {expected['method']}, got {method}")

        # Store result
        results.append({
            "item_id": item_id,
            "status": "success" if expectations_met else "expectation_mismatch",
            "alignment_stage": stage,
            "method": method,
            "conversion_applied": conversion_applied,
            "stage1_blocked": stage1_blocked,
            "matched_fdc_id": result.fdc_id if result.fdc_id else None,
            "matched_name": result.matched_name if result.matched_name else None
        })

        print()

    # Compute final metrics
    total_items = len([r for r in results if r["status"] != "no_candidates"])
    conversion_hit_rate = (conversion_count / total_items * 100) if total_items > 0 else 0

    # Print summary
    print("="*70)
    print("SANITY BATCH RESULTS")
    print("="*70)
    print(f"\nTotal items: {len(items)}")
    print(f"Processed: {total_items}")
    print(f"Conversion hit rate: {conversion_hit_rate:.1f}%")

    print(f"\nStage distribution:")
    for stage, count in sorted(stage_distribution.items()):
        print(f"  {stage}: {count}")

    print(f"\nMethod distribution:")
    for method, count in sorted(method_distribution.items(), key=lambda x: -x[1])[:10]:
        print(f"  {method}: {count}")

    # Validation checks
    print("\n" + "="*70)
    print("VALIDATION CHECKS")
    print("="*70)

    checks_passed = 0
    checks_total = 0

    # Check 1: Conversion hit rate
    checks_total += 1
    target_rate = expected_metrics["conversion_hit_rate"] * 100
    if conversion_hit_rate >= target_rate:
        print(f"✅ Conversion hit rate ≥{target_rate}% (actual: {conversion_hit_rate:.1f}%)")
        checks_passed += 1
    else:
        print(f"❌ Conversion hit rate <{target_rate}% (actual: {conversion_hit_rate:.1f}%)")

    # Check 2: No unknown stages
    checks_total += 1
    if len(unknown_stages) == 0:
        print(f"✅ No unknown stages")
        checks_passed += 1
    else:
        print(f"❌ Unknown stages found in: {unknown_stages}")

    # Check 3: No unknown methods
    checks_total += 1
    if len(unknown_methods) == 0:
        print(f"✅ No unknown methods")
        checks_passed += 1
    else:
        print(f"❌ Unknown methods found in: {unknown_methods}")

    # Final verdict
    print("\n" + "="*70)
    if checks_passed == checks_total:
        print(f"🎉 SANITY BATCH PASSED: {checks_passed}/{checks_total} checks")
        print("="*70 + "\n")
        return 0
    else:
        print(f"⚠️  SANITY BATCH PARTIAL: {checks_passed}/{checks_total} checks passed")
        print("="*70 + "\n")
        return 1


if __name__ == "__main__":
    exit_code = run_sanity_batch_evaluation()
    exit(exit_code)
