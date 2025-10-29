"""
Main runner for nutrition estimation evaluation with rate limiting and resumability.
"""
import asyncio
import argparse
import time
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml
from dotenv import load_dotenv

from .loader import NutritionVerseLoader, load_ids_from_file
from .schema import SchemaMapper
from .prompts import build_user_prompt, SYSTEM_MESSAGE
from .evaluator import NutritionEvaluator, SampleEvaluation
from .store import ResultStore
from ..adapters import OpenAIAdapter, ClaudeAdapter, GeminiAdapter, OllamaAdapter


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, requests_per_second: float):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests per second
        """
        self.rps = requests_per_second
        self.min_interval = 1.0 / requests_per_second if requests_per_second > 0 else 0
        self.last_call = 0

    async def wait(self):
        """Wait if necessary to respect rate limit."""
        if self.min_interval > 0:
            now = time.time()
            time_since_last = now - self.last_call
            if time_since_last < self.min_interval:
                await asyncio.sleep(self.min_interval - time_since_last)
            self.last_call = time.time()


class BudgetTracker:
    """Track API costs and enforce budget caps."""

    def __init__(self, max_budget: float = float('inf')):
        """
        Initialize budget tracker.

        Args:
            max_budget: Maximum budget in USD
        """
        self.max_budget = max_budget
        self.current_cost = 0.0

    def add_cost(self, cost: float):
        """Add cost to tracker."""
        self.current_cost += cost

    def is_over_budget(self) -> bool:
        """Check if over budget."""
        return self.current_cost >= self.max_budget

    def remaining(self) -> float:
        """Get remaining budget."""
        return max(0, self.max_budget - self.current_cost)


class EvaluationRunner:
    """Main runner for evaluation tasks."""

    def __init__(self, config_dir: Path, data_dir: Path, run_dir: Path):
        """
        Initialize runner.

        Args:
            config_dir: Path to configs directory
            data_dir: Path to dataset directory
            run_dir: Path to runs directory
        """
        self.config_dir = Path(config_dir)
        self.data_dir = Path(data_dir)
        self.run_dir = Path(run_dir)

        # Load configs
        with open(self.config_dir / "apis.yaml") as f:
            self.apis_config = yaml.safe_load(f)

        with open(self.config_dir / "tasks.yaml") as f:
            self.tasks_config = yaml.safe_load(f)

        # Initialize loader
        schema_map_path = self.config_dir / "schema_map.yaml"
        self.loader = NutritionVerseLoader(data_dir, schema_map_path)

        # Initialize evaluator
        self.evaluator = NutritionEvaluator()

    def _get_adapter(self, api: str, model: Optional[str] = None):
        """
        Get API adapter instance.

        Args:
            api: API name (openai, claude, gemini, ollama)
            model: Optional model name (uses default if not specified)

        Returns:
            Adapter instance
        """
        api_config = self.apis_config["apis"].get(api)
        if not api_config or not api_config.get("enabled"):
            raise ValueError(f"API '{api}' not found or not enabled")

        model_name = model or api_config["default_model"]
        model_config = api_config["models"].get(model_name, {})

        # Get adapter class
        adapter_map = {
            "openai": OpenAIAdapter,
            "claude": ClaudeAdapter,
            "gemini": GeminiAdapter,
            "ollama": OllamaAdapter
        }

        adapter_class = adapter_map.get(api)
        if not adapter_class:
            raise ValueError(f"Unknown API: {api}")

        # Create adapter with config
        return adapter_class(
            model=model_name,
            temperature=model_config.get("temperature", 0.0),
            max_tokens=model_config.get("max_tokens", 2048)
        )

    async def run_evaluation(
        self,
        api: str,
        task: str,
        start: int = 0,
        end: Optional[int] = None,
        ids_file: Optional[Path] = None,
        limit: Optional[int] = None,
        rps: float = 1.0,
        max_cost: float = float('inf'),
        max_retries: int = 3,
        resume: bool = False,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Run evaluation on a dataset slice.

        Args:
            api: API name
            task: Task name
            start: Start index
            end: End index (None = all)
            ids_file: Optional file with dish IDs
            limit: Maximum number of samples to process
            rps: Requests per second
            max_cost: Maximum budget in USD
            max_retries: Max retries per sample
            resume: Resume from checkpoint
            dry_run: Don't make API calls, just preview

        Returns:
            Summary dictionary
        """
        # Load dataset slice
        if ids_file:
            dish_ids = load_ids_from_file(ids_file)
            items = self.loader.get_by_ids(dish_ids)
        else:
            end = end or len(self.loader)
            items = self.loader.get_slice(start, end)

        # Apply limit
        if limit:
            items = items[:limit]

        if not items:
            print("No items to process")
            return {}

        print(f"\nEvaluation Configuration:")
        print(f"  API: {api}")
        print(f"  Task: {task}")
        print(f"  Samples: {len(items)}")
        print(f"  Range: {items[0].index} to {items[-1].index}")
        print(f"  Rate limit: {rps} req/s")
        print(f"  Budget cap: ${max_cost:.2f}")
        print(f"  Dry run: {dry_run}")

        if dry_run:
            print("\n[DRY RUN] Preview:")
            for i, item in enumerate(items[:5]):
                print(f"  {i}: {item.dish_id} - {item.image_path.name}")
            print(f"  ... ({len(items)} total)")
            return {"dry_run": True}

        # Initialize result store
        store = ResultStore(self.run_dir / "results")

        # Resume or start new
        if resume:
            checkpoint_path = ResultStore.find_latest_checkpoint(
                self.run_dir / "results", api, task
            )
            if checkpoint_path:
                checkpoint = ResultStore.resume_from_checkpoint(checkpoint_path)
                print(f"\nResuming from checkpoint: {checkpoint_path.name}")
                print(f"  Last completed index: {checkpoint['last_completed_idx']}")
                print(f"  Completed: {checkpoint['num_completed']}")
                print(f"  Cost so far: ${checkpoint['total_cost']:.4f}")

                # Filter items to resume from
                last_idx = checkpoint["last_completed_idx"]
                items = [item for item in items if item.index > last_idx]

                store.jsonl_path = self.run_dir / "results" / f"{checkpoint['run_id']}.jsonl"
                store.checkpoint_path = checkpoint_path
                store.summary_path = self.run_dir / "results" / f"{checkpoint['run_id']}_summary.json"

                run_id = checkpoint["run_id"]
            else:
                print("No checkpoint found, starting new run")
                resume = False

        if not resume:
            run_id = store.initialize_run(api, task, items[0].index, items[-1].index)
            print(f"\nStarted new run: {run_id}")

        # Get adapter
        try:
            adapter = self._get_adapter(api)
        except Exception as e:
            print(f"Error initializing adapter: {e}")
            return {"error": str(e)}

        # Initialize tracking
        rate_limiter = RateLimiter(rps)
        budget_tracker = BudgetTracker(max_cost)

        # Load checkpoint values if resuming
        if resume:
            checkpoint = store.load_checkpoint()
            budget_tracker.current_cost = checkpoint.get("total_cost", 0.0)
            num_completed = checkpoint.get("num_completed", 0)
            num_errors = checkpoint.get("num_errors", 0)
        else:
            num_completed = 0
            num_errors = 0

        # Build prompt template
        prompt_template = build_user_prompt(task)

        # Process items
        print(f"\nProcessing {len(items)} items...")
        all_evaluations = []

        for idx, item in enumerate(items):
            # Check budget
            if budget_tracker.is_over_budget():
                print(f"\n[BUDGET] Reached budget cap of ${max_cost:.2f}")
                break

            print(f"\n[{idx+1}/{len(items)}] Processing {item.dish_id} (index {item.index})")
            print(f"  Image: {item.image_path.name}")

            # Rate limiting
            await rate_limiter.wait()

            # Run inference with retries
            prediction = None
            error_msg = None

            for attempt in range(max_retries):
                try:
                    prediction = await adapter.infer(
                        image_path=item.image_path,
                        prompt=prompt_template,
                        system_message=SYSTEM_MESSAGE
                    )

                    # Fill in metadata
                    prediction["dish_id"] = item.dish_id
                    prediction["image_relpath"] = str(item.image_path)

                    # Estimate cost
                    metadata = prediction.get("_metadata", {})
                    tokens_in = metadata.get("tokens_input") or 0
                    tokens_out = metadata.get("tokens_output") or 0
                    cost = adapter.estimate_cost(tokens_in, tokens_out)
                    metadata["cost"] = cost
                    budget_tracker.add_cost(cost)

                    print(f"  Success! Cost: ${cost:.4f}, Total: ${budget_tracker.current_cost:.4f}")
                    break

                except Exception as e:
                    error_msg = str(e)
                    print(f"  Attempt {attempt+1} failed: {error_msg}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff

            # Evaluate
            if prediction:
                evaluation = self.evaluator.evaluate_sample(prediction, item.ground_truth)
                all_evaluations.append(evaluation)

                print(f"  Calories MAE: {evaluation.calories_mae:.1f} kcal" if evaluation.calories_mae else "  No calories eval")

                num_completed += 1
            else:
                # Create error evaluation
                evaluation = SampleEvaluation(
                    dish_id=item.dish_id,
                    index=item.index,
                    error_message=error_msg
                )
                all_evaluations.append(evaluation)
                num_errors += 1

            # Store result
            result = {
                "dish_id": item.dish_id,
                "index": item.index,
                "image_path": str(item.image_path),
                "prediction": prediction,
                "ground_truth": item.ground_truth,
                "evaluation": evaluation.to_dict(),
                "metadata": prediction.get("_metadata") if prediction else None
            }
            store.append_result(result)

            # Update checkpoint
            store.update_checkpoint({
                "last_completed_idx": item.index,
                "num_completed": num_completed,
                "num_errors": num_errors,
                "total_cost": budget_tracker.current_cost
            })

            # Progress update
            if (idx + 1) % 10 == 0:
                print(f"\n--- Progress: {idx+1}/{len(items)} ({num_completed} success, {num_errors} errors) ---")

        # Aggregate results
        print(f"\n\nAggregating results...")
        aggregate_metrics = self.evaluator.aggregate_results(all_evaluations)

        # Create summary
        summary = {
            "run_id": run_id,
            "api": api,
            "task": task,
            "total_samples": len(items),
            "completed": num_completed,
            "errors": num_errors,
            "total_cost": budget_tracker.current_cost,
            "metrics": aggregate_metrics
        }

        # Save summary
        store.save_summary(summary)

        # Print summary
        print(f"\n{'='*60}")
        print(f"EVALUATION SUMMARY")
        print(f"{'='*60}")
        print(f"Run ID: {run_id}")
        print(f"Samples: {num_completed}/{len(items)}")
        print(f"Errors: {num_errors}")
        print(f"Total cost: ${budget_tracker.current_cost:.4f}")
        print(f"\nMetrics:")

        if "calories_mae" in aggregate_metrics:
            print(f"  Calories MAE: {aggregate_metrics['calories_mae']['mean']:.1f} ± {aggregate_metrics['calories_mae']['std']:.1f} kcal")
        if "protein_mae" in aggregate_metrics:
            print(f"  Protein MAE: {aggregate_metrics['protein_mae']['mean']:.1f} ± {aggregate_metrics['protein_mae']['std']:.1f} g")
        if "name_jaccard" in aggregate_metrics:
            print(f"  Name Jaccard: {aggregate_metrics['name_jaccard']['mean']:.3f}")

        print(f"\nResults saved to:")
        print(f"  {store.jsonl_path}")
        print(f"  {store.summary_path}")

        return summary


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run nutrition estimation evaluation")

    # Data and config
    parser.add_argument("--data-dir", type=Path, default="data/nvreal",
                       help="Path to dataset directory")
    parser.add_argument("--config-dir", type=Path, default="configs",
                       help="Path to configs directory")
    parser.add_argument("--run-dir", type=Path, default="runs",
                       help="Path to runs directory")

    # API and task
    parser.add_argument("--api", type=str, required=True,
                       help="API name (openai, claude, gemini, ollama)")
    parser.add_argument("--task", type=str, required=True,
                       help="Task name (dish_totals, itemized, names_only)")

    # Dataset slicing
    parser.add_argument("--start", type=int, default=0,
                       help="Start index")
    parser.add_argument("--end", type=int, default=None,
                       help="End index (None = all)")
    parser.add_argument("--ids-file", type=Path, default=None,
                       help="File with dish IDs (one per line)")
    parser.add_argument("--limit", type=int, default=None,
                       help="Max samples to process")

    # Rate limiting and budget
    parser.add_argument("--rps", type=float, default=1.0,
                       help="Requests per second")
    parser.add_argument("--max-cost", type=float, default=float('inf'),
                       help="Maximum budget in USD")

    # Execution
    parser.add_argument("--max-retries", type=int, default=3,
                       help="Max retries per sample")
    parser.add_argument("--resume", action="store_true",
                       help="Resume from last checkpoint")
    parser.add_argument("--dry-run", action="store_true",
                       help="Preview without API calls")

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Initialize runner
    runner = EvaluationRunner(
        config_dir=args.config_dir,
        data_dir=args.data_dir,
        run_dir=args.run_dir
    )

    # Run evaluation
    try:
        summary = asyncio.run(runner.run_evaluation(
            api=args.api,
            task=args.task,
            start=args.start,
            end=args.end,
            ids_file=args.ids_file,
            limit=args.limit,
            rps=args.rps,
            max_cost=args.max_cost,
            max_retries=args.max_retries,
            resume=args.resume,
            dry_run=args.dry_run
        ))
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Progress saved to checkpoint.")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
