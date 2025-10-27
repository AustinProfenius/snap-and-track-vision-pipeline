"""
Result storage and checkpointing utilities.
"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd


class ResultStore:
    """Store and manage evaluation results."""

    def __init__(self, run_dir: Path):
        """
        Initialize result store.

        Args:
            run_dir: Directory to store results
        """
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # File paths
        self.jsonl_path = None
        self.summary_path = None
        self.checkpoint_path = None

    def initialize_run(self, api: str, task: str, start_idx: int, end_idx: int,
                      run_id: Optional[str] = None) -> str:
        """
        Initialize a new run with unique ID.

        Args:
            api: API name
            task: Task name
            start_idx: Start index
            end_idx: End index
            run_id: Optional custom run ID

        Returns:
            Run ID
        """
        if run_id is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_id = f"{timestamp}_{api}_{task}_{start_idx}_{end_idx}"

        # Set up file paths
        self.jsonl_path = self.run_dir / f"{run_id}.jsonl"
        self.summary_path = self.run_dir / f"{run_id}_summary.json"
        self.checkpoint_path = self.run_dir / f"{run_id}_checkpoint.json"

        # Initialize checkpoint
        self._save_checkpoint({
            "run_id": run_id,
            "api": api,
            "task": task,
            "start_idx": start_idx,
            "end_idx": end_idx,
            "last_completed_idx": start_idx - 1,
            "num_completed": 0,
            "num_errors": 0,
            "total_cost": 0.0,
            "started_at": datetime.now().isoformat()
        })

        return run_id

    def append_result(self, result: Dict[str, Any]):
        """
        Append a single result to JSONL file.

        Args:
            result: Result dictionary to append
        """
        with open(self.jsonl_path, 'a') as f:
            f.write(json.dumps(result) + '\n')

    def update_checkpoint(self, updates: Dict[str, Any]):
        """
        Update checkpoint with new values.

        Args:
            updates: Dictionary of fields to update
        """
        checkpoint = self.load_checkpoint()
        checkpoint.update(updates)
        checkpoint["updated_at"] = datetime.now().isoformat()
        self._save_checkpoint(checkpoint)

    def _save_checkpoint(self, checkpoint: Dict[str, Any]):
        """Save checkpoint to file."""
        with open(self.checkpoint_path, 'w') as f:
            json.dump(checkpoint, f, indent=2)

    def load_checkpoint(self) -> Dict[str, Any]:
        """Load checkpoint from file."""
        if not self.checkpoint_path.exists():
            return {}

        with open(self.checkpoint_path) as f:
            return json.load(f)

    def save_summary(self, summary: Dict[str, Any]):
        """
        Save run summary.

        Args:
            summary: Summary dictionary
        """
        with open(self.summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

    def load_results(self) -> List[Dict[str, Any]]:
        """
        Load all results from JSONL file.

        Returns:
            List of result dictionaries
        """
        if not self.jsonl_path or not self.jsonl_path.exists():
            return []

        results = []
        with open(self.jsonl_path) as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))

        return results

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert results to pandas DataFrame.

        Returns:
            DataFrame of results
        """
        results = self.load_results()
        if not results:
            return pd.DataFrame()

        # Flatten nested structures for DataFrame
        flattened = []
        for result in results:
            flat = {
                "dish_id": result.get("dish_id"),
                "index": result.get("index"),
                "image_path": result.get("image_path")
            }

            # Add evaluation metrics
            if "evaluation" in result:
                for key, value in result["evaluation"].items():
                    if not isinstance(value, (dict, list)):
                        flat[f"eval_{key}"] = value

            # Add prediction totals
            if "prediction" in result and "totals" in result["prediction"]:
                totals = result["prediction"]["totals"]
                flat["pred_calories"] = totals.get("calories_kcal")
                flat["pred_protein"] = totals.get("macros_g", {}).get("protein")
                flat["pred_carbs"] = totals.get("macros_g", {}).get("carbs")
                flat["pred_fat"] = totals.get("macros_g", {}).get("fat")

            # Add ground truth totals
            if "ground_truth" in result and "totals" in result["ground_truth"]:
                totals = result["ground_truth"]["totals"]
                flat["true_calories"] = totals.get("calories_kcal")
                flat["true_protein"] = totals.get("macros_g", {}).get("protein")
                flat["true_carbs"] = totals.get("macros_g", {}).get("carbs")
                flat["true_fat"] = totals.get("macros_g", {}).get("fat")

            # Add metadata
            if "metadata" in result:
                flat["model"] = result["metadata"].get("model")
                flat["tokens_total"] = result["metadata"].get("tokens_total")
                flat["cost"] = result["metadata"].get("cost")

            flattened.append(flat)

        return pd.DataFrame(flattened)

    def to_parquet(self, output_path: Optional[Path] = None):
        """
        Save results as Parquet file.

        Args:
            output_path: Optional output path (defaults to run_dir/{run_id}.parquet)
        """
        df = self.to_dataframe()

        if output_path is None:
            output_path = self.run_dir / f"{self.jsonl_path.stem}.parquet"

        df.to_parquet(output_path, index=False)

    @staticmethod
    def find_latest_checkpoint(run_dir: Path, api: str, task: str) -> Optional[Path]:
        """
        Find the latest checkpoint for a given API and task.

        Args:
            run_dir: Run directory
            task: Task name
            api: API name

        Returns:
            Path to checkpoint file, or None if not found
        """
        checkpoint_files = list(Path(run_dir).glob(f"*_{api}_{task}_*_checkpoint.json"))

        if not checkpoint_files:
            return None

        # Sort by modification time
        latest = max(checkpoint_files, key=lambda p: p.stat().st_mtime)

        return latest

    @staticmethod
    def resume_from_checkpoint(checkpoint_path: Path) -> Dict[str, Any]:
        """
        Load checkpoint and return resume information.

        Args:
            checkpoint_path: Path to checkpoint file

        Returns:
            Checkpoint dictionary
        """
        with open(checkpoint_path) as f:
            checkpoint = json.load(f)

        return checkpoint
