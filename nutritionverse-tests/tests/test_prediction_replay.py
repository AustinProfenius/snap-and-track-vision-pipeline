"""
Tests for Prediction Replay functionality.

Validates that replay correctly:
- Sets source="prediction_replay"
- Loads and applies feature flags and Stage Z fallbacks
- Includes proper telemetry for misses
"""

import pytest
import json
import tempfile
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from entrypoints.replay_from_predictions import run_replay, load_prediction_file


# Minimal test fixture: 2 predictions with known foods
MINIMAL_FIXTURE = {
    "results": [
        {
            "dish_id": "test_001",
            "prediction": {
                "foods": [
                    {"name": "scrambled eggs", "form": "cooked", "mass_g": 100},
                    {"name": "unknown_food_xyz", "form": "raw", "mass_g": 50}
                ]
            }
        },
        {
            "dish_id": "test_002",
            "prediction": {
                "foods": [
                    {"name": "bacon", "form": "fried", "mass_g": 30},
                    {"name": "broccoli florets", "form": "steamed", "mass_g": 80}
                ]
            }
        }
    ]
}


def test_replay_sets_source_prediction_replay():
    """Test that replay sets source="prediction_replay" in telemetry."""
    # Create temp fixture file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(MINIMAL_FIXTURE, f)
        fixture_path = Path(f.name)

    # Create temp output dir
    with tempfile.TemporaryDirectory() as output_dir:
        output_path = Path(output_dir)

        # Run replay
        manifest = run_replay(
            input_files=[fixture_path],
            output_dir=output_path,
            schema="auto",
            limit=None
        )

        # Load telemetry
        telemetry_file = output_path / "telemetry.jsonl"
        assert telemetry_file.exists(), "Telemetry file should be created"

        telemetry_records = []
        with open(telemetry_file) as f:
            for line in f:
                if line.strip():
                    telemetry_records.append(json.loads(line))

        # Assert all telemetry records have source="prediction_replay"
        assert len(telemetry_records) > 0, "Should have telemetry records"
        for record in telemetry_records:
            assert record.get('source') == 'prediction_replay', \
                f"Telemetry record should have source='prediction_replay', got {record.get('source')}"

    # Cleanup
    fixture_path.unlink()


def test_replay_uses_feature_flags_and_fallbacks():
    """Test that replay loads and uses feature flags and Stage Z fallbacks."""
    # Create temp fixture file with a food that should trigger Stage Z
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(MINIMAL_FIXTURE, f)
        fixture_path = Path(f.name)

    # Create temp output dir
    with tempfile.TemporaryDirectory() as output_dir:
        output_path = Path(output_dir)

        # Run replay
        manifest = run_replay(
            input_files=[fixture_path],
            output_dir=output_path,
            schema="auto",
            limit=None
        )

        # Load telemetry
        telemetry_file = output_path / "telemetry.jsonl"
        telemetry_records = []
        with open(telemetry_file) as f:
            for line in f:
                if line.strip():
                    telemetry_records.append(json.loads(line))

        # Check for Stage Z usage (scrambled eggs or broccoli florets should hit Stage Z)
        stageZ_found = False
        for record in telemetry_records:
            if 'stageZ' in record.get('alignment_stage', ''):
                stageZ_found = True
                break

        assert stageZ_found, \
            "Should find at least one Stage Z match (scrambled eggs or broccoli florets)"

    # Cleanup
    fixture_path.unlink()


def test_miss_telemetry_contains_queries_and_reason():
    """Test that miss items have queries_tried and why_no_candidates."""
    # Create temp fixture file with a food that will definitely miss
    miss_fixture = {
        "results": [
            {
                "dish_id": "test_miss",
                "prediction": {
                    "foods": [
                        {"name": "unknown_food_xyz_definitely_not_in_db", "form": "raw", "mass_g": 100}
                    ]
                }
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(miss_fixture, f)
        fixture_path = Path(f.name)

    # Create temp output dir
    with tempfile.TemporaryDirectory() as output_dir:
        output_path = Path(output_dir)

        # Run replay
        manifest = run_replay(
            input_files=[fixture_path],
            output_dir=output_path,
            schema="auto",
            limit=None
        )

        # Load telemetry
        telemetry_file = output_path / "telemetry.jsonl"
        telemetry_records = []
        with open(telemetry_file) as f:
            for line in f:
                if line.strip():
                    telemetry_records.append(json.loads(line))

        # Find miss records
        miss_records = [r for r in telemetry_records
                       if r.get('alignment_stage') == 'stage0_no_candidates']

        assert len(miss_records) > 0, "Should have at least one miss record"

        # Check miss telemetry contains required fields
        for miss in miss_records:
            # Check for normalized_key or variant_chosen
            assert 'variant_chosen' in miss or 'normalized_key' in miss, \
                "Miss record should have variant_chosen or normalized_key"

            # Check for search_variants_tried
            assert 'search_variants_tried' in miss, \
                "Miss record should have search_variants_tried"

            # Check candidate pool info
            assert 'candidate_pool_size' in miss, \
                "Miss record should have candidate_pool_size"

    # Cleanup
    fixture_path.unlink()


def test_schema_detection():
    """Test that schema auto-detection works for V1 format."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(MINIMAL_FIXTURE, f)
        fixture_path = Path(f.name)

    # Load with auto-detection
    schema, predictions = load_prediction_file(fixture_path, schema="auto")

    assert schema == "v1", f"Should detect v1 schema, got {schema}"
    assert len(predictions) == 2, f"Should have 2 predictions, got {len(predictions)}"

    # Check prediction structure
    for pred in predictions:
        assert 'prediction_id' in pred, "Prediction should have prediction_id"
        assert 'prediction_hash' in pred, "Prediction should have prediction_hash"
        assert 'foods' in pred, "Prediction should have foods array"
        assert 'input_schema_version' in pred, "Prediction should have input_schema_version"

    # Cleanup
    fixture_path.unlink()


def test_roasted_veg_attempts_stageZ():
    """
    Phase Z3.2: Test that roasted vegetables trigger Stage Z attempts.

    Validates:
    - Roasted vegetables (brussels sprouts, cauliflower) attempt Stage Z
    - attempted_stages includes "stageZ_branded_fallback"
    - No early returns with empty attempted_stages
    """
    # Create fixture with roasted vegetables
    roasted_veg_fixture = {
        "results": [
            {
                "dish_id": "test_roasted_001",
                "prediction": {
                    "foods": [
                        {"name": "brussels sprouts roasted", "form": "roasted", "mass_g": 90}
                    ]
                }
            },
            {
                "dish_id": "test_roasted_002",
                "prediction": {
                    "foods": [
                        {"name": "cauliflower roasted", "form": "roasted", "mass_g": 85}
                    ]
                }
            },
            {
                "dish_id": "test_roasted_003",
                "prediction": {
                    "foods": [
                        {"name": "roasted brussels sprouts", "form": "roasted", "mass_g": 100}
                    ]
                }
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(roasted_veg_fixture, f)
        fixture_path = Path(f.name)

    # Create temp output dir
    with tempfile.TemporaryDirectory() as output_dir:
        output_path = Path(output_dir)

        # Run replay
        manifest = run_replay(
            input_files=[fixture_path],
            output_dir=output_path,
            schema="auto",
            limit=None
        )

        # Load telemetry
        telemetry_file = output_path / "telemetry.jsonl"
        telemetry_records = []
        with open(telemetry_file) as f:
            for line in f:
                if line.strip():
                    telemetry_records.append(json.loads(line))

        # Validate: All roasted veg records should have attempted_stages
        assert len(telemetry_records) == 3, f"Expected 3 telemetry records, got {len(telemetry_records)}"

        for record in telemetry_records:
            # Check for attempted_stages field
            attempted_stages = record.get('attempted_stages', [])
            assert isinstance(attempted_stages, list), \
                f"attempted_stages should be a list, got {type(attempted_stages)}"

            # Should not be empty (no early returns)
            assert len(attempted_stages) > 0, \
                f"Roasted veg should attempt at least one stage. Got empty attempted_stages for: {record.get('food_name')}"

            # Should attempt Stage Z (either hit or tried)
            alignment_stage = record.get('alignment_stage', '')
            has_stageZ = (
                alignment_stage == 'stageZ_branded_fallback' or
                'stageZ_branded_fallback' in attempted_stages
            )
            assert has_stageZ, \
                f"Roasted veg should attempt Stage Z. Got alignment_stage={alignment_stage}, attempted_stages={attempted_stages}"

        # Count Stage Z hits (should have at least one)
        stageZ_hits = sum(1 for r in telemetry_records
                         if r.get('alignment_stage') == 'stageZ_branded_fallback')
        assert stageZ_hits > 0, \
            f"At least one roasted veg should match Stage Z. Got {stageZ_hits} hits out of {len(telemetry_records)}"

        print(f"✓ Roasted veg test passed: {stageZ_hits}/{len(telemetry_records)} Stage Z hits")

    # Cleanup
    fixture_path.unlink()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
