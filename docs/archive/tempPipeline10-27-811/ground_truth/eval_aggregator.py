#!/usr/bin/env python3
"""
Evaluation Aggregator Tool

Computes MVP metrics from evaluation JSON output:
- top1_name_alignment: % of items where predicted name matches ground truth
- calorie_MAPE: Mean Absolute Percentage Error for calorie estimates
- conversion_hit_rate: % of items where conversion was applied
- branded_fallback_rate: % of items that fell back to branded database
- pickled_gate_rate: % of pickled items that passed sodium gate

Acceptance Criteria:
- conversion_hit_rate ≥60%
- top1_name_alignment ≥75-78%
- calorie_MAPE ≤20%
- branded_fallback_rate ≤5%
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass


@dataclass
class EvaluationMetrics:
    """Container for evaluation metrics."""
    total_items: int
    top1_name_alignment: float
    calorie_mape: float
    conversion_hit_rate: float
    branded_fallback_rate: float
    pickled_gate_rate: float
    avg_confidence: float

    # Detailed breakdowns
    conversion_applied_count: int
    branded_fallback_count: int
    pickled_items_count: int
    pickled_gated_count: int

    # Error analysis
    high_error_items: List[Dict]  # Items with >50% calorie error


def load_evaluation_json(json_path: Path) -> Dict:
    """Load evaluation JSON file."""
    with open(json_path, 'r') as f:
        return json.load(f)


def compute_name_alignment(items: List[Dict]) -> Tuple[float, int]:
    """
    Compute top-1 name alignment rate.

    Returns:
        (alignment_rate, num_aligned)
    """
    if not items:
        return 0.0, 0

    aligned = 0
    for item in items:
        pred_name = item.get('predicted_name', '').lower().strip()
        gt_name = item.get('ground_truth_name', '').lower().strip()

        if not pred_name or not gt_name:
            continue

        # Check if predicted name is in ground truth or vice versa
        # (handles cases like "chicken breast" vs "chicken breast, grilled")
        if pred_name in gt_name or gt_name in pred_name:
            aligned += 1
        # Also check exact word overlap (for multi-word foods)
        elif len(set(pred_name.split()) & set(gt_name.split())) >= 2:
            aligned += 1

    return (aligned / len(items)) * 100 if items else 0.0, aligned


def compute_calorie_mape(items: List[Dict]) -> Tuple[float, List[Dict]]:
    """
    Compute Mean Absolute Percentage Error for calories.

    Returns:
        (mape, high_error_items)
    """
    if not items:
        return 0.0, []

    errors = []
    high_error_items = []

    for item in items:
        pred_cal = item.get('predicted_calories')
        gt_cal = item.get('ground_truth_calories')

        if pred_cal is None or gt_cal is None or gt_cal == 0:
            continue

        # Absolute percentage error
        ape = abs(pred_cal - gt_cal) / gt_cal * 100
        errors.append(ape)

        # Track high-error items (>50% error)
        if ape > 50:
            high_error_items.append({
                'name': item.get('predicted_name', 'unknown'),
                'predicted_cal': pred_cal,
                'ground_truth_cal': gt_cal,
                'error_pct': ape,
                'mass_g': item.get('mass_g'),
                'telemetry': item.get('telemetry', {})
            })

    mape = sum(errors) / len(errors) if errors else 0.0
    return mape, high_error_items


def compute_conversion_hit_rate(items: List[Dict]) -> Tuple[float, int]:
    """
    Compute conversion hit rate.

    Returns:
        (hit_rate, conversion_count)
    """
    if not items:
        return 0.0, 0

    conversion_count = 0

    for item in items:
        telemetry = item.get('telemetry', {})

        # Check if conversion was applied
        if telemetry.get('conversion_applied'):
            conversion_count += 1
        # Also check for method_name field (indicates conversion)
        elif telemetry.get('method_name'):
            conversion_count += 1
        # Check conversion_applied_count
        elif telemetry.get('conversion_applied_count', 0) > 0:
            conversion_count += 1

    hit_rate = (conversion_count / len(items)) * 100 if items else 0.0
    return hit_rate, conversion_count


def compute_branded_fallback_rate(items: List[Dict]) -> Tuple[float, int]:
    """
    Compute branded fallback rate.

    Returns:
        (fallback_rate, branded_count)
    """
    if not items:
        return 0.0, 0

    branded_count = 0

    for item in items:
        telemetry = item.get('telemetry', {})

        # Check if branded database was used
        if telemetry.get('source') == 'branded':
            branded_count += 1
        elif telemetry.get('database_source') == 'branded':
            branded_count += 1
        elif telemetry.get('branded_fallback'):
            branded_count += 1

    fallback_rate = (branded_count / len(items)) * 100 if items else 0.0
    return fallback_rate, branded_count


def compute_pickled_gate_rate(items: List[Dict]) -> Tuple[float, int, int]:
    """
    Compute pickled item sodium gate pass rate.

    Returns:
        (gate_pass_rate, pickled_count, gated_count)
    """
    if not items:
        return 0.0, 0, 0

    pickled_count = 0
    gated_count = 0

    for item in items:
        name = item.get('predicted_name', '').lower()
        telemetry = item.get('telemetry', {})

        # Detect pickled items
        pickled_keywords = ['pickle', 'pickled', 'olive', 'caper', 'fermented', 'kimchi', 'sauerkraut']
        if any(kw in name for kw in pickled_keywords):
            pickled_count += 1

            # Check if sodium gate was applied
            if telemetry.get('sodium_gate_passed'):
                gated_count += 1
            elif telemetry.get('sodium_mg_per_100g', 0) >= 600:
                gated_count += 1

    gate_rate = (gated_count / pickled_count) * 100 if pickled_count > 0 else 0.0
    return gate_rate, pickled_count, gated_count


def compute_avg_confidence(items: List[Dict]) -> float:
    """Compute average prediction confidence."""
    if not items:
        return 0.0

    confidences = [item.get('confidence', 0.0) for item in items if 'confidence' in item]
    return sum(confidences) / len(confidences) if confidences else 0.0


def aggregate_evaluation(json_path: Path) -> EvaluationMetrics:
    """
    Aggregate evaluation metrics from JSON file.

    Args:
        json_path: Path to evaluation JSON file

    Returns:
        EvaluationMetrics object with computed metrics
    """
    data = load_evaluation_json(json_path)
    items = data.get('items', [])

    if not items:
        raise ValueError(f"No items found in {json_path}")

    # Compute all metrics
    name_align, aligned_count = compute_name_alignment(items)
    cal_mape, high_error = compute_calorie_mape(items)
    conv_rate, conv_count = compute_conversion_hit_rate(items)
    brand_rate, brand_count = compute_branded_fallback_rate(items)
    pickle_rate, pickle_count, pickle_gated = compute_pickled_gate_rate(items)
    avg_conf = compute_avg_confidence(items)

    return EvaluationMetrics(
        total_items=len(items),
        top1_name_alignment=name_align,
        calorie_mape=cal_mape,
        conversion_hit_rate=conv_rate,
        branded_fallback_rate=brand_rate,
        pickled_gate_rate=pickle_rate,
        avg_confidence=avg_conf,
        conversion_applied_count=conv_count,
        branded_fallback_count=brand_count,
        pickled_items_count=pickle_count,
        pickled_gated_count=pickle_gated,
        high_error_items=high_error
    )


def validate_telemetry_schema(items: List[Dict]) -> None:
    """
    Validate telemetry schema before aggregation.

    Required fields:
    - alignment_stage (str, not "unknown")
    - method (str, not "unknown")
    - conversion_applied (bool)
    - candidate_pool_size (int)

    Raises ValueError on schema violations.
    """
    required_fields = [
        "alignment_stage",
        "method",
        "conversion_applied",
        "candidate_pool_size"
    ]

    violations = []

    for idx, item in enumerate(items):
        telemetry = item.get('telemetry', {})

        # Check required fields
        for field in required_fields:
            if field not in telemetry:
                violations.append(
                    f"Item {idx}: Missing required telemetry field '{field}'"
                )

        # Validate no unknowns
        if telemetry.get("alignment_stage") == "unknown":
            violations.append(
                f"Item {idx}: alignment_stage='unknown' (schema violation)"
            )

        if telemetry.get("method") == "unknown":
            violations.append(
                f"Item {idx}: method='unknown' (schema violation)"
            )

    if violations:
        error_msg = "❌ TELEMETRY SCHEMA VALIDATION FAILED:\n" + "\n".join(violations[:10])
        if len(violations) > 10:
            error_msg += f"\n... and {len(violations) - 10} more violations"
        raise ValueError(error_msg)


def compute_telemetry_stats(items: List[Dict]) -> Dict[str, Any]:
    """Compute comprehensive telemetry statistics from evaluation items."""
    if not items:
        return {}

    # Validate schema FIRST
    validate_telemetry_schema(items)

    telemetry_stats = {
        "total_items": len(items),
        "conversion_applied_count": 0,
        "conversion_eligible_count": 0,  # NEW: Items with raw Foundation candidates
        "method_inferred_count": 0,
        "sodium_gate_blocks": 0,
        "sodium_gate_passes": 0,
        "negative_vocab_blocks": 0,
        "stage1_blocked_raw_foundation_exists": 0,
        "oil_uptake_applied_count": 0,
        "alignment_stages": {},
        "method_resolution": {},
        "stage1b_count": 0,  # NEW: Stage 1b raw Foundation direct match count
        "stage5_count": 0,  # NEW: Stage 5 proxy alignment count
        "stage5_whitelist_violations": [],  # NEW: Track non-whitelisted Stage 5 usage
        "stageZ_count": 0,  # NEW: Stage-Z energy-only last resort count
        "stageZ_fruit_nut_violations": [],  # NEW: Track fruit/nut Stage-Z violations (should never happen)
    }

    for item in items:
        prov = item.get('provenance', {})
        telemetry = item.get('telemetry', {})

        # Track conversion application
        if prov.get('conversion_applied') or telemetry.get('conversion_applied'):
            telemetry_stats["conversion_applied_count"] += 1

        # Track conversion eligibility (items with raw Foundation candidates)
        candidate_pool_raw = telemetry.get('candidate_pool_raw_foundation', 0)
        if candidate_pool_raw > 0:
            telemetry_stats["conversion_eligible_count"] += 1

        # Track method inference (check both telemetry.method_inferred and provenance.method_reason)
        if telemetry.get('method_inferred'):
            telemetry_stats["method_inferred_count"] += 1
        elif prov.get('method_reason') in ['conversion_config', 'class_default', 'category_default']:
            telemetry_stats["method_inferred_count"] += 1

        # Track sodium gates
        telemetry_stats["sodium_gate_blocks"] += telemetry.get('sodium_gate_blocks', 0)
        telemetry_stats["sodium_gate_passes"] += telemetry.get('sodium_gate_passes', 0)

        # Track negative vocab blocks
        telemetry_stats["negative_vocab_blocks"] += telemetry.get('negative_vocab_blocks', 0)

        # Track Stage 1 blocks
        if telemetry.get('stage1_blocked_raw_foundation_exists'):
            telemetry_stats["stage1_blocked_raw_foundation_exists"] += 1

        # Track oil uptake
        if telemetry.get('oil_uptake_g_per_100g', 0) > 0:
            telemetry_stats["oil_uptake_applied_count"] += 1

        # Track alignment stages
        stage = telemetry.get('alignment_stage', prov.get('alignment_stage', 'unknown'))
        telemetry_stats["alignment_stages"][stage] = \
            telemetry_stats["alignment_stages"].get(stage, 0) + 1

        # Track Stage 1b usage (raw Foundation direct match)
        if stage == "stage1b_raw_foundation_direct":
            telemetry_stats["stage1b_count"] += 1

        # Track Stage 5 usage and whitelist enforcement
        if stage == "stage5_proxy_alignment":
            telemetry_stats["stage5_count"] += 1

            # Verify whitelist compliance
            STAGE5_WHITELIST_KEYWORDS = {
                "romaine",  # leafy_mixed_salad
                "green_leaf",  # leafy_mixed_salad
                "zucchini",  # squash_summer_yellow
                "tofu"  # tofu_plain_raw
            }

            # Extract core_class from item (may need to look at dish_id or predicted_name)
            dish_id = item.get('dish_id', 'unknown')
            predicted_name = item.get('predicted_name', 'unknown')

            # Check if proxy_formula is in telemetry
            proxy_formula = telemetry.get('proxy_formula', prov.get('proxy_formula', ''))

            # Validate proxy formula contains whitelisted keywords
            if not any(keyword in proxy_formula.lower() for keyword in STAGE5_WHITELIST_KEYWORDS):
                telemetry_stats["stage5_whitelist_violations"].append({
                    "dish_id": dish_id,
                    "predicted_name": predicted_name,
                    "proxy_formula": proxy_formula
                })

        # Track Stage-Z usage and fruit/nut guard enforcement
        if stage == "stageZ_energy_only":
            telemetry_stats["stageZ_count"] += 1

            # STRICT CHECK: Stage-Z should NEVER be used for fruits, nuts, or vegetables
            STAGEZ_FORBIDDEN_CATEGORIES = {
                "fruit", "nuts_seeds", "vegetable"
            }

            # Check category in telemetry
            stagez_category = telemetry.get('stagez_category', prov.get('stagez_category', ''))
            core_class = item.get('core_class', item.get('predicted_name', 'unknown').lower())

            # Detect fruit/nut/vegetable from core_class if category not in telemetry
            if not stagez_category:
                core_lower = core_class.lower()
                if any(x in core_lower for x in ["apple", "grape", "berry", "melon", "banana"]):
                    stagez_category = "fruit"
                elif any(x in core_lower for x in ["almond", "walnut", "peanut", "nut"]):
                    stagez_category = "nuts_seeds"
                elif any(x in core_lower for x in ["lettuce", "spinach", "carrot", "broccoli", "pepper"]):
                    stagez_category = "vegetable"

            # Verify Stage-Z not used for forbidden categories
            if stagez_category in STAGEZ_FORBIDDEN_CATEGORIES:
                dish_id = item.get('dish_id', 'unknown')
                predicted_name = item.get('predicted_name', 'unknown')
                telemetry_stats["stageZ_fruit_nut_violations"].append({
                    "dish_id": dish_id,
                    "predicted_name": predicted_name,
                    "core_class": core_class,
                    "category": stagez_category
                })

        # Track method distribution
        method = telemetry.get('method', prov.get('method', 'unknown'))
        telemetry_stats["method_resolution"][method] = \
            telemetry_stats["method_resolution"].get(method, 0) + 1

    # Compute rates
    total = telemetry_stats["total_items"]
    eligible = telemetry_stats["conversion_eligible_count"]

    if total > 0:
        telemetry_stats["conversion_hit_rate"] = \
            telemetry_stats["conversion_applied_count"] / total
        telemetry_stats["method_inferred_rate"] = \
            telemetry_stats["method_inferred_count"] / total
        telemetry_stats["oil_uptake_rate"] = \
            telemetry_stats["oil_uptake_applied_count"] / total
    else:
        telemetry_stats["conversion_hit_rate"] = 0.0
        telemetry_stats["method_inferred_rate"] = 0.0
        telemetry_stats["oil_uptake_rate"] = 0.0

    # NEW: Eligible conversion rate (among items with raw Foundation candidates)
    if eligible > 0:
        telemetry_stats["conversion_eligible_rate"] = \
            telemetry_stats["conversion_applied_count"] / eligible
    else:
        telemetry_stats["conversion_eligible_rate"] = 0.0

    # SANITY CHECK: Fail if "unknown" present in stages
    if "unknown" in telemetry_stats["alignment_stages"]:
        unknown_count = telemetry_stats["alignment_stages"]["unknown"]
        raise ValueError(
            f"❌ VALIDATION FAILED: {unknown_count} items have alignment_stage='unknown'. "
            f"All items must have explicit stages. This indicates a bug in the alignment flow."
        )

    # SANITY CHECK: Fail if "unknown" present in methods
    if "unknown" in telemetry_stats["method_resolution"]:
        unknown_count = telemetry_stats["method_resolution"]["unknown"]
        raise ValueError(
            f"❌ VALIDATION FAILED: {unknown_count} items have method='unknown'. "
            f"All items must have resolved methods. This indicates a bug in method resolution."
        )

    # SANITY CHECK: Warn if conversion_hit_rate is exactly 0
    if telemetry_stats["conversion_hit_rate"] == 0.0 and total > 10:
        print(f"\n⚠️  WARNING: Conversion hit rate is 0.0% on a batch of {total} items.")
        print(f"    Conversion layer may not be wired correctly.")
        print(f"    Expected: ≥50% conversion rate for typical food batches.\n")

    # NEW: SANITY CHECK: Stage 5 whitelist enforcement (Phase 1)
    if telemetry_stats["stage5_whitelist_violations"]:
        violations = telemetry_stats["stage5_whitelist_violations"]
        raise ValueError(
            f"❌ STAGE 5 WHITELIST VIOLATION: {len(violations)} items used Stage 5 "
            f"for non-whitelisted classes.\n"
            f"Whitelisted classes: leafy_mixed_salad, squash_summer_yellow, tofu_plain_raw\n"
            f"Violations: {violations[:5]}"  # Show first 5
        )

    # NEW: SANITY CHECK: Stage-Z fruit/nut guard enforcement (should NEVER happen)
    if telemetry_stats["stageZ_fruit_nut_violations"]:
        violations = telemetry_stats["stageZ_fruit_nut_violations"]
        raise ValueError(
            f"❌ STAGE-Z FRUIT/NUT VIOLATION: {len(violations)} items used Stage-Z "
            f"for forbidden categories (fruit, nuts_seeds, vegetable).\n"
            f"Stage-Z eligibility check FAILED. This should never happen.\n"
            f"Violations: {violations[:5]}"  # Show first 5
        )

    # Print Stage 1b summary if used
    if telemetry_stats["stage1b_count"] > 0:
        print(f"\n✓ Stage 1b Raw Foundation Direct: {telemetry_stats['stage1b_count']} items")

    # Print Stage 5 summary if used
    if telemetry_stats["stage5_count"] > 0:
        print(f"\n✓ Stage 5 Proxy Alignment: {telemetry_stats['stage5_count']} items")
        print(f"  Whitelist enforcement: PASSED (0 violations)")

    # Print Stage-Z summary if used
    if telemetry_stats["stageZ_count"] > 0:
        print(f"\n✓ Stage-Z Energy-Only Last Resort: {telemetry_stats['stageZ_count']} items")
        print(f"  Fruit/Nut guard enforcement: PASSED (0 violations)")

    return telemetry_stats


def print_metrics(metrics: EvaluationMetrics, verbose: bool = False, telemetry_stats: Optional[Dict] = None):
    """Print metrics in a formatted way."""
    print("\n" + "="*60)
    print("EVALUATION METRICS SUMMARY")
    print("="*60)
    print(f"\nTotal Items: {metrics.total_items}")
    print(f"Average Confidence: {metrics.avg_confidence:.1f}%")
    print("\n" + "-"*60)
    print("MVP METRICS")
    print("-"*60)

    # Top-1 Name Alignment
    status = "✅" if metrics.top1_name_alignment >= 75 else "❌"
    print(f"{status} Top-1 Name Alignment: {metrics.top1_name_alignment:.1f}% (target: ≥75-78%)")

    # Calorie MAPE
    status = "✅" if metrics.calorie_mape <= 20 else "❌"
    print(f"{status} Calorie MAPE: {metrics.calorie_mape:.1f}% (target: ≤20%)")

    # Conversion Hit Rate
    status = "✅" if metrics.conversion_hit_rate >= 60 else "❌"
    print(f"{status} Conversion Hit Rate: {metrics.conversion_hit_rate:.1f}% ({metrics.conversion_applied_count}/{metrics.total_items}) (target: ≥60%)")

    # Branded Fallback Rate
    status = "✅" if metrics.branded_fallback_rate <= 5 else "❌"
    print(f"{status} Branded Fallback Rate: {metrics.branded_fallback_rate:.1f}% ({metrics.branded_fallback_count}/{metrics.total_items}) (target: ≤5%)")

    # Pickled Gate Rate
    if metrics.pickled_items_count > 0:
        print(f"   Pickled Gate Rate: {metrics.pickled_gate_rate:.1f}% ({metrics.pickled_gated_count}/{metrics.pickled_items_count})")

    # High error items
    if verbose and metrics.high_error_items:
        print("\n" + "-"*60)
        print(f"HIGH ERROR ITEMS (>50% error): {len(metrics.high_error_items)}")
        print("-"*60)
        for i, item in enumerate(metrics.high_error_items[:10], 1):  # Top 10
            print(f"\n{i}. {item['name']}")
            print(f"   Predicted: {item['predicted_cal']:.0f} kcal | Ground Truth: {item['ground_truth_cal']:.0f} kcal")
            print(f"   Error: {item['error_pct']:.1f}% | Mass: {item.get('mass_g', 'N/A')}g")
            if item.get('telemetry'):
                tel = item['telemetry']
                print(f"   Source: {tel.get('source', 'N/A')} | Method: {tel.get('method_name', 'N/A')}")

    # Telemetry stats
    if telemetry_stats:
        print("\n" + "-"*60)
        print("TELEMETRY STATS")
        print("-"*60)

        # Conversion & method metrics
        print(f"\n🔄 Conversion & Method Metrics:")
        print(f"   Conversion Hit Rate (Overall): {telemetry_stats['conversion_hit_rate']:.1%} "
              f"({telemetry_stats['conversion_applied_count']}/{telemetry_stats['total_items']})")
        print(f"   Conversion Eligible Rate: {telemetry_stats['conversion_eligible_rate']:.1%} "
              f"({telemetry_stats['conversion_applied_count']}/{telemetry_stats['conversion_eligible_count']} eligible)")
        print(f"   Method Inferred Rate: {telemetry_stats['method_inferred_rate']:.1%} "
              f"({telemetry_stats['method_inferred_count']}/{telemetry_stats['total_items']})")
        print(f"   Oil Uptake Applied: {telemetry_stats['oil_uptake_applied_count']} items "
              f"({telemetry_stats['oil_uptake_rate']:.1%})")

        # Alignment stage distribution
        if telemetry_stats['alignment_stages']:
            print(f"\n🎯 Alignment Stage Distribution:")
            for stage in sorted(telemetry_stats['alignment_stages'].keys()):
                count = telemetry_stats['alignment_stages'][stage]
                pct = count / telemetry_stats['total_items'] * 100
                print(f"   {stage}: {count} ({pct:.1f}%)")

        # Method distribution (top 10)
        if telemetry_stats['method_resolution']:
            print(f"\n🔧 Method Resolution Distribution (Top 10):")
            sorted_methods = sorted(
                telemetry_stats['method_resolution'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            for method, count in sorted_methods:
                pct = count / telemetry_stats['total_items'] * 100
                print(f"   {method}: {count} ({pct:.1f}%)")

        # Guard & gate statistics
        print(f"\n🚧 Guard & Gate Statistics:")
        print(f"   Stage 1 blocks (raw Foundation exists): {telemetry_stats['stage1_blocked_raw_foundation_exists']}")
        print(f"   Sodium gate blocks: {telemetry_stats['sodium_gate_blocks']}")
        print(f"   Sodium gate passes: {telemetry_stats['sodium_gate_passes']}")
        print(f"   Negative vocab blocks: {telemetry_stats['negative_vocab_blocks']}")

    print("\n" + "="*60)


def check_acceptance_criteria(metrics: EvaluationMetrics) -> bool:
    """
    Check if metrics meet acceptance criteria.

    Returns:
        True if all criteria met, False otherwise
    """
    criteria = [
        metrics.conversion_hit_rate >= 60,
        metrics.top1_name_alignment >= 75,
        metrics.calorie_mape <= 20,
        metrics.branded_fallback_rate <= 5
    ]
    return all(criteria)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python eval_aggregator.py <path_to_evaluation_json> [--verbose]")
        print("\nExample:")
        print("  python eval_aggregator.py ../tempPipeline10-25-920/results/gpt_5_302images_20251025_153955.json")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    if not json_path.exists():
        print(f"Error: File not found: {json_path}")
        sys.exit(1)

    try:
        # Load data
        data = load_evaluation_json(json_path)
        items = data.get('items', [])

        # Compute metrics and telemetry
        metrics = aggregate_evaluation(json_path)
        telemetry_stats = compute_telemetry_stats(items)

        # Print results
        print_metrics(metrics, verbose=verbose, telemetry_stats=telemetry_stats)

        # Check acceptance criteria
        if check_acceptance_criteria(metrics):
            print("\n✅ All acceptance criteria met!")
            sys.exit(0)
        else:
            print("\n❌ Some acceptance criteria not met. See above for details.")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
