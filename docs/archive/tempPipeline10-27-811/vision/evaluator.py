"""
Evaluation metrics for nutrition estimation.
"""
import re
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict
import numpy as np


@dataclass
class MetricScores:
    """Container for metric scores."""
    mae: Optional[float] = None
    mape: Optional[float] = None
    rmse: Optional[float] = None
    coverage: Optional[float] = None  # % of predictions with valid values
    accuracy: Optional[float] = None  # For categorical/name matching
    jaccard: Optional[float] = None  # For set similarity


@dataclass
class SampleEvaluation:
    """Evaluation results for a single sample."""
    dish_id: str
    index: int

    # Totals metrics
    calories_mae: Optional[float] = None
    calories_mape: Optional[float] = None
    protein_mae: Optional[float] = None
    protein_mape: Optional[float] = None
    carbs_mae: Optional[float] = None
    carbs_mape: Optional[float] = None
    fat_mae: Optional[float] = None
    fat_mape: Optional[float] = None
    mass_mae: Optional[float] = None
    mass_mape: Optional[float] = None

    # Food name matching
    name_jaccard: Optional[float] = None
    name_precision: Optional[float] = None
    name_recall: Optional[float] = None

    # Per-item metrics (if itemized)
    avg_item_calories_mae: Optional[float] = None
    avg_item_protein_mae: Optional[float] = None

    # Metadata
    num_foods_predicted: int = 0
    num_foods_truth: int = 0
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class NutritionEvaluator:
    """Evaluator for nutrition estimation tasks."""

    def __init__(self, synonym_map: Optional[Dict[str, List[str]]] = None):
        """
        Initialize evaluator.

        Args:
            synonym_map: Optional mapping of canonical names to synonyms
                        e.g., {"chicken breast": ["chicken", "grilled chicken"]}
        """
        self.synonym_map = synonym_map or {}

        # Build reverse lookup
        self.canonical_map = {}
        for canonical, synonyms in self.synonym_map.items():
            for syn in synonyms:
                self.canonical_map[self._normalize_name(syn)] = canonical

    def evaluate_sample(self, prediction: Dict[str, Any], ground_truth: Dict[str, Any]) -> SampleEvaluation:
        """
        Evaluate a single prediction against ground truth.

        Args:
            prediction: Model prediction (uniform schema)
            ground_truth: Ground truth annotation (uniform schema)

        Returns:
            SampleEvaluation with computed metrics
        """
        eval_result = SampleEvaluation(
            dish_id=ground_truth.get("dish_id", "unknown"),
            index=ground_truth.get("index", -1)
        )

        try:
            # Evaluate totals
            pred_totals = prediction.get("totals", {})
            true_totals = ground_truth.get("totals", {})

            eval_result.calories_mae, eval_result.calories_mape = self._compute_mae_mape(
                pred_totals.get("calories_kcal", 0),
                true_totals.get("calories_kcal", 0)
            )

            pred_macros = pred_totals.get("macros_g", {})
            true_macros = true_totals.get("macros_g", {})

            eval_result.protein_mae, eval_result.protein_mape = self._compute_mae_mape(
                pred_macros.get("protein", 0),
                true_macros.get("protein", 0)
            )

            eval_result.carbs_mae, eval_result.carbs_mape = self._compute_mae_mape(
                pred_macros.get("carbs", 0),
                true_macros.get("carbs", 0)
            )

            eval_result.fat_mae, eval_result.fat_mape = self._compute_mae_mape(
                pred_macros.get("fat", 0),
                true_macros.get("fat", 0)
            )

            eval_result.mass_mae, eval_result.mass_mape = self._compute_mae_mape(
                pred_totals.get("mass_g", 0),
                true_totals.get("mass_g", 0)
            )

            # Evaluate food names
            pred_foods = prediction.get("foods", [])
            true_foods = ground_truth.get("foods", [])

            eval_result.num_foods_predicted = len(pred_foods)
            eval_result.num_foods_truth = len(true_foods)

            pred_names = [self._normalize_name(f.get("name", "")) for f in pred_foods]
            true_names = [self._normalize_name(f.get("name", "")) for f in true_foods]

            # Map to canonical names
            pred_names_canonical = [self._to_canonical(n) for n in pred_names if n]
            true_names_canonical = [self._to_canonical(n) for n in true_names if n]

            eval_result.name_jaccard = self._jaccard_similarity(
                set(pred_names_canonical),
                set(true_names_canonical)
            )

            eval_result.name_precision, eval_result.name_recall = self._precision_recall(
                set(pred_names_canonical),
                set(true_names_canonical)
            )

            # Per-item metrics (if itemized task)
            if pred_foods and true_foods:
                item_cals_errors = []
                item_prot_errors = []

                # Simple matching: pair by order (or could use name matching)
                for pred_food, true_food in zip(pred_foods, true_foods):
                    pred_cal = pred_food.get("calories_kcal", 0)
                    true_cal = true_food.get("calories_kcal", 0)
                    if true_cal > 0:
                        item_cals_errors.append(abs(pred_cal - true_cal))

                    pred_prot = pred_food.get("macros_g", {}).get("protein", 0)
                    true_prot = true_food.get("macros_g", {}).get("protein", 0)
                    if true_prot > 0:
                        item_prot_errors.append(abs(pred_prot - true_prot))

                if item_cals_errors:
                    eval_result.avg_item_calories_mae = np.mean(item_cals_errors)
                if item_prot_errors:
                    eval_result.avg_item_protein_mae = np.mean(item_prot_errors)

        except Exception as e:
            eval_result.error_message = str(e)

        return eval_result

    def aggregate_results(self, evaluations: List[SampleEvaluation]) -> Dict[str, Any]:
        """
        Aggregate results across multiple samples.

        Args:
            evaluations: List of sample evaluations

        Returns:
            Dictionary of aggregate statistics
        """
        if not evaluations:
            return {}

        # Filter out errors
        valid_evals = [e for e in evaluations if e.error_message is None]

        if not valid_evals:
            return {"error": "No valid evaluations", "total_samples": len(evaluations)}

        # Aggregate metrics
        metrics = {}

        # Totals metrics
        for field in ["calories", "protein", "carbs", "fat", "mass"]:
            mae_values = [getattr(e, f"{field}_mae") for e in valid_evals
                         if getattr(e, f"{field}_mae") is not None]
            mape_values = [getattr(e, f"{field}_mape") for e in valid_evals
                          if getattr(e, f"{field}_mape") is not None]

            if mae_values:
                metrics[f"{field}_mae"] = {
                    "mean": np.mean(mae_values),
                    "median": np.median(mae_values),
                    "std": np.std(mae_values),
                    "min": np.min(mae_values),
                    "max": np.max(mae_values)
                }

            if mape_values:
                metrics[f"{field}_mape"] = {
                    "mean": np.mean(mape_values),
                    "median": np.median(mape_values),
                    "std": np.std(mape_values),
                    "min": np.min(mape_values),
                    "max": np.max(mape_values)
                }

        # Name matching metrics
        jaccard_values = [e.name_jaccard for e in valid_evals if e.name_jaccard is not None]
        if jaccard_values:
            metrics["name_jaccard"] = {
                "mean": np.mean(jaccard_values),
                "median": np.median(jaccard_values),
                "std": np.std(jaccard_values)
            }

        precision_values = [e.name_precision for e in valid_evals if e.name_precision is not None]
        recall_values = [e.name_recall for e in valid_evals if e.name_recall is not None]

        if precision_values:
            metrics["name_precision"] = {"mean": np.mean(precision_values)}
        if recall_values:
            metrics["name_recall"] = {"mean": np.mean(recall_values)}

        # Coverage
        metrics["coverage"] = {
            "total_samples": len(evaluations),
            "valid_samples": len(valid_evals),
            "error_samples": len(evaluations) - len(valid_evals),
            "success_rate": len(valid_evals) / len(evaluations) if evaluations else 0
        }

        return metrics

    @staticmethod
    def _compute_mae_mape(predicted: float, actual: float) -> Tuple[Optional[float], Optional[float]]:
        """
        Compute MAE and MAPE for a single value.

        Args:
            predicted: Predicted value
            actual: Actual value

        Returns:
            Tuple of (MAE, MAPE)
        """
        if actual == 0:
            return None, None

        mae = abs(predicted - actual)
        mape = (mae / actual) * 100

        return mae, mape

    @staticmethod
    def _normalize_name(name: str) -> str:
        """
        Normalize food name for matching.

        Args:
            name: Raw food name

        Returns:
            Normalized name (lowercase, no extra spaces, singular)
        """
        if not name:
            return ""

        # Lowercase
        name = name.lower().strip()

        # Remove extra whitespace
        name = re.sub(r'\s+', ' ', name)

        # Simple singularization (remove trailing 's')
        # More sophisticated would use inflect library
        if name.endswith('s') and len(name) > 3:
            name = name[:-1]

        return name

    def _to_canonical(self, name: str) -> str:
        """
        Map name to canonical form using synonym map.

        Args:
            name: Normalized name

        Returns:
            Canonical name
        """
        return self.canonical_map.get(name, name)

    @staticmethod
    def _jaccard_similarity(set1: set, set2: set) -> float:
        """
        Compute Jaccard similarity between two sets.

        Args:
            set1: First set
            set2: Second set

        Returns:
            Jaccard index (0 to 1)
        """
        if not set1 and not set2:
            return 1.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _precision_recall(predicted: set, actual: set) -> Tuple[float, float]:
        """
        Compute precision and recall for set matching.

        Args:
            predicted: Predicted set
            actual: Actual set

        Returns:
            Tuple of (precision, recall)
        """
        if not predicted and not actual:
            return 1.0, 1.0

        true_positives = len(predicted & actual)

        precision = true_positives / len(predicted) if predicted else 0.0
        recall = true_positives / len(actual) if actual else 0.0

        return precision, recall


def create_calibration_data(evaluations: List[SampleEvaluation],
                            ground_truths: List[Dict[str, Any]],
                            predictions: List[Dict[str, Any]],
                            field: str = "calories_kcal") -> Dict[str, List]:
    """
    Create calibration plot data (predicted vs actual).

    Args:
        evaluations: List of sample evaluations
        ground_truths: List of ground truth annotations
        predictions: List of predictions
        field: Field to plot (e.g., "calories_kcal")

    Returns:
        Dictionary with 'predicted' and 'actual' lists
    """
    predicted = []
    actual = []

    for pred, truth in zip(predictions, ground_truths):
        pred_val = pred.get("totals", {}).get(field, 0)
        true_val = truth.get("totals", {}).get(field, 0)

        if pred_val > 0 and true_val > 0:
            predicted.append(pred_val)
            actual.append(true_val)

    return {"predicted": predicted, "actual": actual}
