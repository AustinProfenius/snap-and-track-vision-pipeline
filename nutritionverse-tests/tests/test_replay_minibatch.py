"""
Phase Z3.1: Fast deterministic replay test for CI.

Tests the prediction replay system with a small 15-food minibatch to ensure:
- Stage Z usage > 0
- Miss rate < 35%
- Completes in < 30s

This test validates core alignment functionality without requiring full 630-image replay.
"""
import subprocess
import json
import time
from pathlib import Path


def test_replay_minibatch():
    """
    Phase Z3.1: Fast deterministic replay test for CI.

    Validates:
    - Stage Z usage > 0
    - Miss rate < 35%
    - Completes in < 30s
    """
    # Paths
    test_dir = Path(__file__).parent
    project_root = test_dir.parent
    fixture_path = project_root / "fixtures" / "replay_minibatch.json"
    output_dir = Path("/tmp/test_replay_minibatch")

    # Ensure fixture exists
    assert fixture_path.exists(), f"Fixture not found: {fixture_path}"

    # Clean output directory
    if output_dir.exists():
        import shutil
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run replay with timeout
    cmd = [
        "python",
        str(project_root / "entrypoints" / "replay_from_predictions.py"),
        "--in", str(fixture_path),
        "--out", str(output_dir),
        "--config-dir", str(project_root.parent / "configs")
    ]

    print(f"Running minibatch replay: {' '.join(cmd)}")
    start_time = time.time()

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(project_root)
    )

    elapsed_time = time.time() - start_time

    # Check replay succeeded
    assert result.returncode == 0, f"Replay failed with exit code {result.returncode}:\n{result.stderr}"

    # Check runtime < 30s
    assert elapsed_time < 30, f"Replay took {elapsed_time:.1f}s (expected <30s)"

    # Load results
    results_file = output_dir / "results.jsonl"
    assert results_file.exists(), f"No results.jsonl generated at {results_file}"

    predictions = []
    with open(results_file) as f:
        for line in f:
            if line.strip():
                predictions.append(json.loads(line))

    # Validate we got 5 predictions (one per image)
    assert len(predictions) == 5, f"Expected 5 predictions, got {len(predictions)}"

    # Flatten foods from all predictions
    all_foods = []
    for pred in predictions:
        foods = pred.get("foods", [])
        all_foods.extend(foods)

    # Validate we got 15 foods (5 images × 3 foods each)
    total = len(all_foods)
    assert total == 15, f"Expected 15 foods, got {total}"

    # Count Stage Z usage and misses
    stagez_count = 0
    miss_count = 0

    for food in all_foods:
        alignment_stage = food.get("alignment_stage", "unknown")

        if alignment_stage == "stageZ_branded_fallback":
            stagez_count += 1
        elif alignment_stage == "stage0_no_candidates":
            miss_count += 1

    # Calculate percentages
    stagez_usage = (stagez_count / total) * 100 if total > 0 else 0
    miss_rate = (miss_count / total) * 100 if total > 0 else 0

    # Assertions - Phase Z3.2.1: Tightened thresholds after roasted veg resolution
    assert stagez_usage >= 18.0, f"Stage Z usage {stagez_usage:.1f}% below 18% target"
    assert miss_rate <= 35.0, f"Miss rate {miss_rate:.1f}% exceeds 35% threshold"

    # Print results
    print(f"✓ Mini-replay validation passed:")
    print(f"  Runtime: {elapsed_time:.1f}s")
    print(f"  Total foods: {total}")
    print(f"  Stage Z usage: {stagez_count} ({stagez_usage:.1f}%)")
    print(f"  Miss rate: {miss_count} ({miss_rate:.1f}%)")
    print(f"  Results directory: {output_dir}")


if __name__ == "__main__":
    test_replay_minibatch()
