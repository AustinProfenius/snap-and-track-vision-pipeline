"""
Unit tests for stage1c_switched telemetry persistence.

Tests that stage1c_switched events are correctly captured and persisted to telemetry.jsonl.
"""
import json
import sys
from pathlib import Path

# Add parent dirs to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pipeline.schemas import TelemetryEvent


def test_telemetry_event_schema_includes_stage1c_switched():
    """Test that TelemetryEvent schema includes stage1c_switched field."""
    # Create a telemetry event with stage1c_switched
    event = TelemetryEvent(
        image_id="test_001",
        food_idx=0,
        query="blackberries",
        alignment_stage="stage1b_raw_foundation_direct",
        fdc_id=173946,
        fdc_name="Blackberries raw",
        candidate_pool_size=5,
        foundation_pool_count=5,
        stage1c_switched={"from": "blackberries frozen unsweetened", "to": "blackberries raw"},
        code_git_sha="test_sha",
        config_version="test_config",
        fdc_index_version="test_fdc",
    )

    # Verify the field is present
    assert event.stage1c_switched is not None
    assert event.stage1c_switched["from"] == "blackberries frozen unsweetened"
    assert event.stage1c_switched["to"] == "blackberries raw"

    # Verify JSON serialization preserves the field
    json_str = event.model_dump_json()
    json_data = json.loads(json_str)

    assert "stage1c_switched" in json_data
    assert json_data["stage1c_switched"]["from"] == "blackberries frozen unsweetened"
    assert json_data["stage1c_switched"]["to"] == "blackberries raw"

    print("✓ test_telemetry_event_schema_includes_stage1c_switched passed")


def test_telemetry_event_stage1c_switched_optional():
    """Test that stage1c_switched is optional (None when no switch occurred)."""
    # Create a telemetry event without stage1c_switched
    event = TelemetryEvent(
        image_id="test_002",
        food_idx=1,
        query="broccoli",
        alignment_stage="stage1b_raw_foundation_direct",
        fdc_id=170379,
        fdc_name="Broccoli raw",
        candidate_pool_size=22,
        foundation_pool_count=14,
        stage1c_switched=None,  # No switch occurred
        code_git_sha="test_sha",
        config_version="test_config",
        fdc_index_version="test_fdc",
    )

    # Verify the field is None
    assert event.stage1c_switched is None

    # Verify JSON serialization includes null
    json_str = event.model_dump_json()
    json_data = json.loads(json_str)

    assert "stage1c_switched" in json_data
    assert json_data["stage1c_switched"] is None

    print("✓ test_telemetry_event_stage1c_switched_optional passed")


def test_jsonl_line_format():
    """Test that telemetry events serialize to single-line JSON (JSONL format)."""
    event = TelemetryEvent(
        image_id="test_003",
        food_idx=2,
        query="eggs",
        alignment_stage="stage1b_raw_foundation_direct",
        fdc_id=171287,
        fdc_name="Egg whole raw fresh",
        candidate_pool_size=50,
        foundation_pool_count=36,
        stage1c_switched={"from": "bread egg toasted", "to": "egg whole raw fresh"},
        code_git_sha="test_sha",
        config_version="test_config",
        fdc_index_version="test_fdc",
    )

    # Serialize to JSON
    json_str = event.model_dump_json()

    # Verify it's a single line (no newlines in the middle)
    assert "\n" not in json_str
    assert "\r" not in json_str

    # Verify it's valid JSON
    json_data = json.loads(json_str)
    assert json_data["image_id"] == "test_003"
    assert json_data["stage1c_switched"]["from"] == "bread egg toasted"

    print("✓ test_jsonl_line_format passed")


def test_stage1c_switched_dict_validation():
    """Test that stage1c_switched must be a dict with 'from' and 'to' keys."""
    # Valid dict
    event = TelemetryEvent(
        image_id="test_004",
        food_idx=0,
        query="test",
        alignment_stage="stage1b_raw_foundation_direct",
        candidate_pool_size=0,
        foundation_pool_count=0,
        stage1c_switched={"from": "original", "to": "new"},
        code_git_sha="test_sha",
        config_version="test_config",
        fdc_index_version="test_fdc",
    )
    assert event.stage1c_switched == {"from": "original", "to": "new"}

    # None is valid (optional field)
    event2 = TelemetryEvent(
        image_id="test_005",
        food_idx=0,
        query="test",
        alignment_stage="stage1b_raw_foundation_direct",
        candidate_pool_size=0,
        foundation_pool_count=0,
        stage1c_switched=None,
        code_git_sha="test_sha",
        config_version="test_config",
        fdc_index_version="test_fdc",
    )
    assert event2.stage1c_switched is None

    print("✓ test_stage1c_switched_dict_validation passed")


if __name__ == "__main__":
    print("Running stage1c_switched telemetry persistence tests...")
    print()

    test_telemetry_event_schema_includes_stage1c_switched()
    test_telemetry_event_stage1c_switched_optional()
    test_jsonl_line_format()
    test_stage1c_switched_dict_validation()

    print()
    print("=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
