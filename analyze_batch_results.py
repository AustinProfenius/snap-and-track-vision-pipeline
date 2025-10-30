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
            results_path: Path to JSON results file or directory with replay_manifest.json
            verbose: Enable verbose output
        """
        self.results_path = Path(results_path)
        self.verbose = verbose
        self.source = None  # "prediction_replay" or "dataset_metadata"
        self.manifest = None
        self.data = self._load_results()
        self.items = self.data.get("items", [])
        self.metadata = self.data.get("metadata", {})

    def _load_results(self) -> Dict[str, Any]:
        """
        Load results from JSON file, JSONL file, or replay directory.

        Supports three formats:
        1. Regular batch JSON (legacy format with 'items' array)
        2. JSONL file (one JSON object per line)
        3. Replay directory with replay_manifest.json + results.jsonl

        Returns:
            Dict with 'items' array and 'metadata' dict
        """
        if not self.results_path.exists():
            raise FileNotFoundError(f"Results file not found: {self.results_path}")

        # Case 1: Directory with replay_manifest.json (prediction replay output)
        if self.results_path.is_dir():
            manifest_file = self.results_path / "replay_manifest.json"
            results_file = self.results_path / "results.jsonl"

            if not manifest_file.exists():
                raise FileNotFoundError(f"No replay_manifest.json found in {self.results_path}")
            if not results_file.exists():
                raise FileNotFoundError(f"No results.jsonl found in {self.results_path}")

            # Load manifest
            with open(manifest_file) as f:
                self.manifest = json.load(f)
                self.source = self.manifest.get("source", "prediction_replay")

            # Load JSONL results
            items = []
            with open(results_file) as f:
                for line in f:
                    if line.strip():
                        items.append(json.loads(line))

            return {
                "items": items,
                "metadata": {
                    "source": self.source,
                    "manifest": self.manifest
                }
            }

        # Case 2: JSONL file (one object per line)
        if self.results_path.suffix == '.jsonl':
            items = []
            with open(self.results_path) as f:
                for line in f:
                    if line.strip():
                        item = json.loads(line)
                        items.append(item)
                        # Detect source from first item
                        if not self.source and 'source' in item:
                            self.source = item['source']

            return {
                "items": items,
                "metadata": {
                    "source": self.source or "unknown"
                }
            }

        # Case 3: Regular JSON file (legacy batch format)
        with open(self.results_path) as f:
            data = json.load(f)

            # Detect source
            if 'items' in data and len(data['items']) > 0:
                first_item = data['items'][0]
                if 'source' in first_item:
                    self.source = first_item['source']

            # Set default source for legacy format
            if not self.source:
                self.source = "dataset_metadata"

            return data

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

    def normalize_record(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a single record to handle schema differences between old/new formats.

        Phase Z3.1: Unify field names across schema versions for accurate delta comparison.

        Args:
            rec: Raw record from results file

        Returns:
            Normalized record with unified field names
        """
        normalized = rec.copy()
        telemetry = rec.get("telemetry", {})

        # Normalize alignment_stage (handle both direct and nested)
        if "alignment_stage" not in normalized and "telemetry" in rec:
            normalized["alignment_stage"] = telemetry.get("alignment_stage", "unknown")

        # Normalize stageZ telemetry (handle both old and new structure)
        if "stageZ_branded_fallback" in telemetry:
            stagez_data = telemetry["stageZ_branded_fallback"]
            # Ensure consistent structure
            if isinstance(stagez_data, dict):
                normalized["stageZ_info"] = {
                    "source": stagez_data.get("source", stagez_data.get("fallback_source")),
                    "coverage_class": stagez_data.get("coverage_class", "branded_generic"),
                    "fdc_id": stagez_data.get("fdc_id"),
                    "brand": stagez_data.get("brand")
                }

        # Normalize candidate pool fields (old format had separate counts)
        if "candidate_pool_total" in telemetry and "candidate_pool_size" not in telemetry:
            normalized["telemetry"]["candidate_pool_size"] = telemetry["candidate_pool_total"]

        # Normalize method/form fields
        if "method" not in normalized and "telemetry" in rec:
            normalized["method"] = telemetry.get("method", telemetry.get("cooking_method"))

        return normalized

    def compare_with_baseline(self, baseline_path: str) -> Dict[str, Any]:
        """
        Compare current results with baseline using normalized records.

        Phase Z3.1: Enhanced comparison with schema-aware normalization.

        Args:
            baseline_path: Path to baseline results

        Returns:
            Dict with comparison metrics and deltas
        """
        baseline_analyzer = BatchResultsAnalyzer(baseline_path, verbose=False)

        # Normalize both datasets
        current_items_normalized = [self.normalize_record(item) for item in self.items]
        baseline_items_normalized = [self.normalize_record(item) for item in baseline_analyzer.items]

        # Analyze both
        current_misses = self.analyze_misses()
        baseline_misses = baseline_analyzer.analyze_misses()

        current_stage_dist = self.analyze_stage_distribution()
        baseline_stage_dist = baseline_analyzer.analyze_stage_distribution()

        # Calculate deltas
        delta_unique_misses = current_misses["unique_foods"] - baseline_misses["unique_foods"]
        delta_miss_rate = (current_misses["miss_rate"] - baseline_misses["miss_rate"]) * 100

        # Stage Z comparison
        current_stagez = sum(1 for item in current_items_normalized
                            if item.get("alignment_stage") == "stageZ_branded_fallback")
        baseline_stagez = sum(1 for item in baseline_items_normalized
                             if item.get("alignment_stage") == "stageZ_branded_fallback")

        delta_stagez = current_stagez - baseline_stagez
        delta_stagez_pct = (current_stagez / len(current_items_normalized) * 100) - \
                          (baseline_stagez / len(baseline_items_normalized) * 100)

        return {
            "baseline": {
                "total_items": len(baseline_items_normalized),
                "unique_misses": baseline_misses["unique_foods"],
                "miss_rate": baseline_misses["miss_rate"] * 100,
                "stagez_usage": baseline_stagez
            },
            "current": {
                "total_items": len(current_items_normalized),
                "unique_misses": current_misses["unique_foods"],
                "miss_rate": current_misses["miss_rate"] * 100,
                "stagez_usage": current_stagez
            },
            "deltas": {
                "unique_misses": delta_unique_misses,
                "miss_rate_pct": delta_miss_rate,
                "stagez_usage": delta_stagez,
                "stagez_pct": delta_stagez_pct
            }
        }

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
        print("COMPARISON WITH BASELINE (Phase Z3.1 Enhanced)")
        print("=" * 80)

        comparison = analyzer.compare_with_baseline(args.compare)

        baseline = comparison["baseline"]
        current = comparison["current"]
        deltas = comparison["deltas"]

        print(f"Baseline:")
        print(f"  Total items: {baseline['total_items']}")
        print(f"  Unique misses: {baseline['unique_misses']}")
        print(f"  Miss rate: {baseline['miss_rate']:.1f}%")
        print(f"  Stage Z usage: {baseline['stagez_usage']}")
        print()

        print(f"Current:")
        print(f"  Total items: {current['total_items']}")
        print(f"  Unique misses: {current['unique_misses']}")
        print(f"  Miss rate: {current['miss_rate']:.1f}%")
        print(f"  Stage Z usage: {current['stagez_usage']}")
        print()

        print(f"Deltas:")
        delta_unique = deltas['unique_misses']
        delta_miss = deltas['miss_rate_pct']
        delta_stagez = deltas['stagez_usage']
        delta_stagez_pct = deltas['stagez_pct']

        # Color-coded deltas
        unique_symbol = "✅" if delta_unique < 0 else ("⚠️" if delta_unique == 0 else "❌")
        miss_symbol = "✅" if delta_miss < 0 else ("⚠️" if delta_miss == 0 else "❌")
        stagez_symbol = "✅" if delta_stagez > 0 else ("⚠️" if delta_stagez == 0 else "❌")

        print(f"  Unique misses: {delta_unique:+d} {unique_symbol}")
        print(f"  Miss rate: {delta_miss:+.1f}% {miss_symbol}")
        print(f"  Stage Z usage: {delta_stagez:+d} ({delta_stagez_pct:+.1f}%) {stagez_symbol}")

        # Overall assessment
        if delta_unique < 0 and delta_stagez > 0:
            print("\n✅ IMPROVEMENT: Reduced misses and increased Stage Z coverage!")
        elif delta_unique < 0:
            print("\n✅ IMPROVEMENT: Reduced misses")
        elif delta_stagez > 0:
            print("\n⚠️ MIXED: Increased Stage Z but misses not reduced")
        else:
            print(f"\n❌ REGRESSION: Misses increased or no improvement")


if __name__ == "__main__":
    main()
