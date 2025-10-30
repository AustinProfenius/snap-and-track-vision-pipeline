#!/usr/bin/env python3
"""
Batch Results Analyzer - Phase Z2 Validation

Analyzes JSON results from run_459_batch_evaluation.py to extract:
- Unique misses (foods that got stage0_no_candidates)
- Total no matches count
- Stage distribution
- Coverage class breakdown
- Special case validation
- Phase Z2 impact metrics

Usage:
    python analyze_batch_results.py results/batch_459_results_TIMESTAMP.json
    python analyze_batch_results.py results/batch_459_results_TIMESTAMP.json --verbose
    python analyze_batch_results.py results/batch_459_results_TIMESTAMP.json --compare baseline.json
"""

import json
import sys
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Any, Tuple
import argparse


class BatchResultsAnalyzer:
    """Analyzes batch evaluation results for Phase Z2 validation."""

    def __init__(self, results_path: str, verbose: bool = False):
        """
        Initialize analyzer.

        Args:
            results_path: Path to JSON results file
            verbose: Enable verbose output
        """
        self.results_path = Path(results_path)
        self.verbose = verbose
        self.data = self._load_results()
        self.items = self.data.get("items", [])
        self.metadata = self.data.get("metadata", {})

    def _load_results(self) -> Dict[str, Any]:
        """Load results JSON file."""
        if not self.results_path.exists():
            raise FileNotFoundError(f"Results file not found: {self.results_path}")

        with open(self.results_path) as f:
            return json.load(f)

    def analyze_misses(self) -> Dict[str, Any]:
        """
        Analyze alignment misses (stage0_no_candidates).

        Returns:
            Dict with miss analysis including unique foods, counts, etc.
        """
        misses = []
        miss_by_food = defaultdict(int)

        for item in self.items:
            telemetry = item.get("telemetry", {})
            stage = telemetry.get("alignment_stage", "")

            if stage == "stage0_no_candidates":
                predicted_name = item.get("predicted_name", "unknown")
                misses.append(item)
                miss_by_food[predicted_name.lower()] += 1

        # Sort by frequency
        unique_misses = sorted(
            [(food, count) for food, count in miss_by_food.items()],
            key=lambda x: x[1],
            reverse=True
        )

        return {
            "total_misses": len(misses),
            "unique_foods": len(unique_misses),
            "miss_rate": len(misses) / len(self.items) if self.items else 0,
            "unique_misses": unique_misses,
            "miss_items": misses
        }

    def analyze_stage_distribution(self) -> Dict[str, Any]:
        """
        Analyze distribution across alignment stages.

        Returns:
            Dict with stage counts and percentages
        """
        stage_counts = Counter()

        for item in self.items:
            telemetry = item.get("telemetry", {})
            stage = telemetry.get("alignment_stage", "unknown")
            stage_counts[stage] += 1

        total = len(self.items)
        stage_dist = {
            stage: {
                "count": count,
                "percentage": (count / total * 100) if total else 0
            }
            for stage, count in stage_counts.items()
        }

        return {
            "total_items": total,
            "distribution": stage_dist,
            "stage_counts": dict(stage_counts)
        }

    def analyze_coverage_class(self) -> Dict[str, Any]:
        """
        Analyze coverage by class (Foundation, converted, branded, etc.).

        Returns:
            Dict with coverage class breakdown
        """
        coverage_counts = Counter()

        for item in self.items:
            telemetry = item.get("telemetry", {})
            stage = telemetry.get("alignment_stage", "unknown")

            # Map stages to coverage classes
            if stage in ["stage1b_raw_foundation_direct", "stage1c_cooked_sr_direct"]:
                coverage_class = "foundation"
            elif stage == "stage2_raw_convert":
                coverage_class = "converted"
            elif stage == "stageZ_branded_fallback":
                # Check if verified CSV or generic
                stageZ_telem = telemetry.get("stageZ_branded_fallback", {})
                source = stageZ_telem.get("source", "existing_config")
                if source == "manual_verified_csv":
                    coverage_class = "branded_verified_csv"
                else:
                    coverage_class = "branded_generic"
            elif stage == "stage5_proxy_alignment":
                coverage_class = "proxy"
            elif stage == "stage0_no_candidates":
                coverage_class = "no_match"
            else:
                coverage_class = "other"

            coverage_counts[coverage_class] += 1

        total = len(self.items)
        coverage_dist = {
            cls: {
                "count": count,
                "percentage": (count / total * 100) if total else 0
            }
            for cls, count in coverage_counts.items()
        }

        return {
            "total_items": total,
            "distribution": coverage_dist,
            "class_counts": dict(coverage_counts)
        }

    def analyze_special_cases(self) -> Dict[str, Any]:
        """
        Analyze Phase Z2 special cases.

        Returns:
            Dict with special case validation results
        """
        special_cases = {
            "chicken_breast": [],
            "cherry_tomato": [],
            "orange_peel": [],
            "chilaquiles": [],
            "celery": [],
            "deprecated": [],
            "tatsoi": [],
            "alcohol": []
        }

        for item in self.items:
            predicted_name = item.get("predicted_name", "").lower()
            telemetry = item.get("telemetry", {})

            # Chicken breast (should have token constraint)
            if "chicken" in predicted_name and "breast" in predicted_name:
                special_cases["chicken_breast"].append({
                    "predicted_name": item.get("predicted_name"),
                    "fdc_name": item.get("fdc_name"),
                    "stage": telemetry.get("alignment_stage")
                })

            # Cherry tomato (Foundation precedence)
            if "cherry tomato" in predicted_name or "grape tomato" in predicted_name:
                special_cases["cherry_tomato"].append({
                    "predicted_name": item.get("predicted_name"),
                    "fdc_name": item.get("fdc_name"),
                    "stage": telemetry.get("alignment_stage")
                })

            # Orange with peel (peel hint)
            if "orange" in predicted_name and ("peel" in predicted_name or "skin" in predicted_name):
                form_hint = telemetry.get("form_hint", {})
                special_cases["orange_peel"].append({
                    "predicted_name": item.get("predicted_name"),
                    "fdc_name": item.get("fdc_name"),
                    "form_hint": form_hint
                })

            # Chilaquiles (low confidence)
            if "chilaquiles" in predicted_name:
                special_cases["chilaquiles"].append({
                    "predicted_name": item.get("predicted_name"),
                    "fdc_name": item.get("fdc_name"),
                    "stage": telemetry.get("alignment_stage")
                })

            # Celery root (mapping)
            if "celery" in predicted_name:
                special_cases["celery"].append({
                    "predicted_name": item.get("predicted_name"),
                    "fdc_name": item.get("fdc_name"),
                    "stage": telemetry.get("alignment_stage")
                })

            # Deprecated (should be ignored)
            if "deprecated" in predicted_name:
                special_cases["deprecated"].append({
                    "predicted_name": item.get("predicted_name"),
                    "stage": telemetry.get("alignment_stage"),
                    "ignored_class": telemetry.get("ignored_class")
                })

            # Tatsoi (should be ignored)
            if "tatsoi" in predicted_name:
                special_cases["tatsoi"].append({
                    "predicted_name": item.get("predicted_name"),
                    "stage": telemetry.get("alignment_stage"),
                    "ignored_class": telemetry.get("ignored_class")
                })

            # Alcohol (should be ignored)
            alcohol_keywords = ["wine", "beer", "vodka", "whiskey", "rum", "tequila", "sake"]
            if any(kw in predicted_name for kw in alcohol_keywords):
                special_cases["alcohol"].append({
                    "predicted_name": item.get("predicted_name"),
                    "stage": telemetry.get("alignment_stage"),
                    "ignored_class": telemetry.get("ignored_class")
                })

        return special_cases

    def analyze_phase_z2_impact(self) -> Dict[str, Any]:
        """
        Analyze Phase Z2 specific impact.

        Returns:
            Dict with Phase Z2 metrics
        """
        stageZ_items = []
        csv_verified_items = []
        normalization_hints = []
        ignored_items = []

        for item in self.items:
            telemetry = item.get("telemetry", {})
            stage = telemetry.get("alignment_stage", "")

            # Stage Z usage
            if stage == "stageZ_branded_fallback":
                stageZ_telem = telemetry.get("stageZ_branded_fallback", {})
                stageZ_items.append({
                    "predicted_name": item.get("predicted_name"),
                    "fdc_name": item.get("fdc_name"),
                    "source": stageZ_telem.get("source"),
                    "coverage_class": stageZ_telem.get("coverage_class")
                })

                # CSV verified items
                if stageZ_telem.get("source") == "manual_verified_csv":
                    csv_verified_items.append(item.get("predicted_name"))

            # Normalization hints (peel)
            if "form_hint" in telemetry:
                normalization_hints.append({
                    "predicted_name": item.get("predicted_name"),
                    "form_hint": telemetry.get("form_hint")
                })

            # Ignored items
            if "ignored_class" in telemetry:
                ignored_items.append({
                    "predicted_name": item.get("predicted_name"),
                    "ignored_class": telemetry.get("ignored_class"),
                    "stage": stage
                })

        return {
            "stageZ_usage": {
                "total": len(stageZ_items),
                "csv_verified": len(csv_verified_items),
                "items": stageZ_items
            },
            "normalization_hints": {
                "total": len(normalization_hints),
                "items": normalization_hints
            },
            "ignored_foods": {
                "total": len(ignored_items),
                "items": ignored_items
            }
        }

    def generate_report(self) -> str:
        """
        Generate comprehensive analysis report.

        Returns:
            Formatted report string
        """
        report_lines = []

        # Header
        report_lines.append("=" * 80)
        report_lines.append("PHASE Z2 BATCH RESULTS ANALYSIS")
        report_lines.append("=" * 80)
        report_lines.append(f"Results file: {self.results_path.name}")
        report_lines.append(f"Timestamp: {self.metadata.get('timestamp', 'N/A')}")
        report_lines.append(f"Total items: {len(self.items)}")
        report_lines.append("")

        # 1. Miss Analysis
        report_lines.append("1. MISS ANALYSIS (stage0_no_candidates)")
        report_lines.append("-" * 40)
        miss_analysis = self.analyze_misses()
        total_misses = miss_analysis["total_misses"]
        unique_misses = miss_analysis["unique_foods"]
        miss_rate = miss_analysis["miss_rate"] * 100

        report_lines.append(f"Total misses: {total_misses} items")
        report_lines.append(f"Unique foods: {unique_misses} foods")
        report_lines.append(f"Miss rate: {miss_rate:.1f}%")
        report_lines.append(f"Pass rate: {100 - miss_rate:.1f}%")
        report_lines.append("")

        # Phase Z2 target evaluation
        if unique_misses <= 10:
            report_lines.append(f"✅ PHASE Z2 TARGET MET: {unique_misses} unique misses ≤ 10")
        else:
            report_lines.append(f"❌ PHASE Z2 TARGET NOT MET: {unique_misses} unique misses > 10")
        report_lines.append("")

        report_lines.append("Top 20 unique misses by frequency:")
        for idx, (food, count) in enumerate(miss_analysis["unique_misses"][:20], 1):
            report_lines.append(f"  {idx:2d}. {food:40s} ({count:3d} instances)")
        report_lines.append("")

        # 2. Stage Distribution
        report_lines.append("2. STAGE DISTRIBUTION")
        report_lines.append("-" * 40)
        stage_dist = self.analyze_stage_distribution()

        for stage, data in sorted(stage_dist["distribution"].items(),
                                   key=lambda x: x[1]["count"], reverse=True):
            count = data["count"]
            pct = data["percentage"]
            report_lines.append(f"  {stage:40s} {count:4d} ({pct:5.1f}%)")
        report_lines.append("")

        # 3. Coverage Class Distribution
        report_lines.append("3. COVERAGE CLASS DISTRIBUTION")
        report_lines.append("-" * 40)
        coverage_dist = self.analyze_coverage_class()

        for cls, data in sorted(coverage_dist["distribution"].items(),
                               key=lambda x: x[1]["count"], reverse=True):
            count = data["count"]
            pct = data["percentage"]
            report_lines.append(f"  {cls:30s} {count:4d} ({pct:5.1f}%)")
        report_lines.append("")

        # 4. Phase Z2 Impact
        report_lines.append("4. PHASE Z2 IMPACT METRICS")
        report_lines.append("-" * 40)
        z2_impact = self.analyze_phase_z2_impact()

        # Stage Z usage
        stageZ_total = z2_impact["stageZ_usage"]["total"]
        stageZ_csv = z2_impact["stageZ_usage"]["csv_verified"]
        report_lines.append(f"Stage Z branded fallback usage: {stageZ_total} items")
        report_lines.append(f"  - CSV verified entries: {stageZ_csv} items")
        report_lines.append(f"  - Existing config entries: {stageZ_total - stageZ_csv} items")
        report_lines.append("")

        # Normalization hints
        hints_total = z2_impact["normalization_hints"]["total"]
        report_lines.append(f"Normalization hints (peel): {hints_total} items")
        if self.verbose and hints_total > 0:
            for hint in z2_impact["normalization_hints"]["items"][:10]:
                report_lines.append(f"  - {hint['predicted_name']}: {hint['form_hint']}")
        report_lines.append("")

        # Ignored foods
        ignored_total = z2_impact["ignored_foods"]["total"]
        report_lines.append(f"Ignored foods (negative vocab): {ignored_total} items")
        if ignored_total > 0:
            ignored_by_class = defaultdict(int)
            for item in z2_impact["ignored_foods"]["items"]:
                ignored_by_class[item.get("ignored_class", "unknown")] += 1
            for cls, count in ignored_by_class.items():
                report_lines.append(f"  - {cls}: {count} items")
        report_lines.append("")

        # 5. Special Cases Validation
        report_lines.append("5. SPECIAL CASES VALIDATION")
        report_lines.append("-" * 40)
        special_cases = self.analyze_special_cases()

        # Chicken breast
        chicken_count = len(special_cases["chicken_breast"])
        if chicken_count > 0:
            report_lines.append(f"Chicken breast items: {chicken_count}")
            if self.verbose:
                for item in special_cases["chicken_breast"][:5]:
                    report_lines.append(f"  - {item['predicted_name']} → {item['fdc_name']} ({item['stage']})")
        else:
            report_lines.append("Chicken breast items: 0 (not in test batch)")
        report_lines.append("")

        # Cherry tomato
        cherry_count = len(special_cases["cherry_tomato"])
        if cherry_count > 0:
            report_lines.append(f"Cherry/grape tomato items: {cherry_count}")
            foundation_count = sum(1 for item in special_cases["cherry_tomato"]
                                  if "stage1" in item.get("stage", ""))
            if foundation_count > 0:
                report_lines.append(f"  ✅ {foundation_count} using Foundation (preferred)")
            if self.verbose:
                for item in special_cases["cherry_tomato"][:5]:
                    report_lines.append(f"  - {item['predicted_name']} → {item['fdc_name']} ({item['stage']})")
        else:
            report_lines.append("Cherry/grape tomato items: 0 (not in test batch)")
        report_lines.append("")

        # Celery
        celery_count = len(special_cases["celery"])
        if celery_count > 0:
            report_lines.append(f"Celery items: {celery_count}")
            if self.verbose:
                for item in special_cases["celery"][:5]:
                    report_lines.append(f"  - {item['predicted_name']} → {item['fdc_name']} ({item['stage']})")
        else:
            report_lines.append("Celery items: 0 (not in test batch)")
        report_lines.append("")

        # Ignored items (tatsoi, alcohol, deprecated)
        tatsoi_count = len(special_cases["tatsoi"])
        alcohol_count = len(special_cases["alcohol"])
        deprecated_count = len(special_cases["deprecated"])

        if tatsoi_count > 0:
            report_lines.append(f"Tatsoi items: {tatsoi_count} (should be ignored)")
            ignored_count = sum(1 for item in special_cases["tatsoi"]
                               if item.get("ignored_class"))
            if ignored_count == tatsoi_count:
                report_lines.append(f"  ✅ All {tatsoi_count} correctly ignored")
        else:
            report_lines.append("Tatsoi items: 0 (not in test batch)")

        if alcohol_count > 0:
            report_lines.append(f"Alcohol items: {alcohol_count} (should be ignored)")
            ignored_count = sum(1 for item in special_cases["alcohol"]
                               if item.get("ignored_class"))
            if ignored_count == alcohol_count:
                report_lines.append(f"  ✅ All {alcohol_count} correctly ignored")
        else:
            report_lines.append("Alcohol items: 0 (not in test batch)")

        if deprecated_count > 0:
            report_lines.append(f"Deprecated items: {deprecated_count} (should be ignored)")
            ignored_count = sum(1 for item in special_cases["deprecated"]
                               if item.get("ignored_class"))
            if ignored_count == deprecated_count:
                report_lines.append(f"  ✅ All {deprecated_count} correctly ignored")
        else:
            report_lines.append("Deprecated items: 0 (not in test batch)")

        report_lines.append("")

        # Footer
        report_lines.append("=" * 80)
        report_lines.append("SUMMARY")
        report_lines.append("=" * 80)
        report_lines.append(f"Total items processed: {len(self.items)}")
        report_lines.append(f"Unique misses: {unique_misses}")
        report_lines.append(f"Pass rate: {100 - miss_rate:.1f}%")
        report_lines.append(f"Stage Z usage: {stageZ_total} items ({stageZ_csv} CSV verified)")
        report_lines.append("")

        if unique_misses <= 10:
            report_lines.append("✅ PHASE Z2 SUCCESS: Unique misses ≤ 10")
        else:
            report_lines.append(f"❌ PHASE Z2 TARGET MISSED: {unique_misses} unique misses (target: ≤10)")

        report_lines.append("=" * 80)

        return "\n".join(report_lines)

    def save_detailed_analysis(self, output_path: str):
        """
        Save detailed analysis to JSON.

        Args:
            output_path: Path to save analysis JSON
        """
        analysis = {
            "metadata": {
                "source_file": str(self.results_path),
                "timestamp": self.metadata.get("timestamp"),
                "total_items": len(self.items)
            },
            "miss_analysis": self.analyze_misses(),
            "stage_distribution": self.analyze_stage_distribution(),
            "coverage_distribution": self.analyze_coverage_class(),
            "phase_z2_impact": self.analyze_phase_z2_impact(),
            "special_cases": self.analyze_special_cases()
        }

        with open(output_path, 'w') as f:
            json.dump(analysis, f, indent=2)

        print(f"✓ Detailed analysis saved to: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze batch evaluation results for Phase Z2 validation"
    )
    parser.add_argument(
        "results_file",
        help="Path to batch results JSON file"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "-o", "--output",
        help="Save detailed analysis to JSON file"
    )
    parser.add_argument(
        "--compare",
        help="Compare with baseline results file"
    )

    args = parser.parse_args()

    # Analyze results
    analyzer = BatchResultsAnalyzer(args.results_file, verbose=args.verbose)

    # Generate and print report
    report = analyzer.generate_report()
    print(report)

    # Save detailed analysis if requested
    if args.output:
        analyzer.save_detailed_analysis(args.output)

    # Compare with baseline if provided
    if args.compare:
        print("\n" + "=" * 80)
        print("COMPARISON WITH BASELINE")
        print("=" * 80)

        baseline_analyzer = BatchResultsAnalyzer(args.compare, verbose=False)

        current_misses = analyzer.analyze_misses()
        baseline_misses = baseline_analyzer.analyze_misses()

        current_unique = current_misses["unique_foods"]
        baseline_unique = baseline_misses["unique_foods"]

        print(f"Baseline unique misses: {baseline_unique}")
        print(f"Current unique misses: {current_unique}")
        print(f"Reduction: {baseline_unique - current_unique} ({((baseline_unique - current_unique) / baseline_unique * 100):.1f}%)")

        if current_unique <= 10 and baseline_unique > 10:
            print("\n✅ PHASE Z2 TARGET ACHIEVED!")
        elif current_unique < baseline_unique:
            print(f"\n✅ IMPROVEMENT: Reduced misses by {baseline_unique - current_unique}")
        else:
            print(f"\n❌ NO IMPROVEMENT: Misses increased by {current_unique - baseline_unique}")


if __name__ == "__main__":
    main()
