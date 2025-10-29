"""
Unit tests for Stage 1c raw-first preference logic.

These tests do NOT require a database connection and can run in CI.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.nutrition.alignment.align_convert import _prefer_raw_stage1c


class MockEntry:
    """Mock FdcEntry for testing without database."""
    def __init__(self, name: str):
        self.name = name


def test_stage1c_switches_to_raw():
    """Test that Stage 1c switches from processed (bread) to raw alternative."""
    picked = MockEntry("Bread egg toasted")
    candidates = [
        MockEntry("Bread egg toasted"),
        MockEntry("Egg whole raw fresh"),
        MockEntry("Egg yolk frozen")
    ]
    cfg = {
        "stage1c_processed_penalties": ["bread", "toast", "frozen"],
        "stage1c_raw_synonyms": ["raw", "fresh"]
    }

    result = _prefer_raw_stage1c("eggs", picked, candidates, cfg=cfg)

    # Should switch to raw alternative
    assert getattr(result, "name", "") == "Egg whole raw fresh", \
        f"Expected 'Egg whole raw fresh', got '{getattr(result, 'name', '')}'"


def test_stage1c_keeps_when_no_raw():
    """Test that Stage 1c keeps original when no raw alternative exists."""
    picked = MockEntry("Blackberries frozen")
    candidates = [MockEntry("Blackberries frozen")]
    cfg = {
        "stage1c_processed_penalties": ["frozen"],
        "stage1c_raw_synonyms": ["raw", "fresh"]
    }

    result = _prefer_raw_stage1c("blackberries", picked, candidates, cfg=cfg)

    # Should keep original since no raw alternative
    assert getattr(result, "name", "") == "Blackberries frozen", \
        f"Expected 'Blackberries frozen', got '{getattr(result, 'name', '')}'"


def test_stage1c_handles_dict_candidates():
    """Test that Stage 1c works with dict candidates (not just FdcEntry)."""
    picked = {"name": "Oil olive salad or cooking"}
    candidates = [
        {"name": "Oil olive salad or cooking"},
        {"name": "Olives ripe canned raw"}
    ]
    cfg = {
        "stage1c_processed_penalties": ["oil", "fried"],
        "stage1c_raw_synonyms": ["raw", "fresh"]
    }

    result = _prefer_raw_stage1c("olives", picked, candidates, cfg=cfg)

    # Should switch to raw alternative
    assert result.get("name", "") == "Olives ripe canned raw", \
        f"Expected 'Olives ripe canned raw', got '{result.get('name', '')}'"


def test_stage1c_keeps_already_raw():
    """Test that Stage 1c keeps foods that are already raw."""
    picked = MockEntry("Broccoli raw")
    candidates = [
        MockEntry("Broccoli raw"),
        MockEntry("Broccoli frozen"),
        MockEntry("Soup broccoli cheese")
    ]
    cfg = {
        "stage1c_processed_penalties": ["frozen", "soup", "cheese"],
        "stage1c_raw_synonyms": ["raw", "fresh"]
    }

    result = _prefer_raw_stage1c("broccoli", picked, candidates, cfg=cfg)

    # Should keep original since it's already raw
    assert getattr(result, "name", "") == "Broccoli raw", \
        f"Expected 'Broccoli raw', got '{getattr(result, 'name', '')}'"


def test_stage1c_uses_defaults_when_no_config():
    """Test that Stage 1c uses hardcoded defaults when config is missing."""
    picked = MockEntry("Avocado oil")
    candidates = [
        MockEntry("Avocado oil"),
        MockEntry("Avocados raw Florida")
    ]

    # No config provided - should use defaults
    result = _prefer_raw_stage1c("avocado", picked, candidates, cfg=None)

    # Should switch to raw using default lists
    assert getattr(result, "name", "") == "Avocados raw Florida", \
        f"Expected 'Avocados raw Florida', got '{getattr(result, 'name', '')}'"


def test_stage1c_never_throws():
    """Test that Stage 1c never throws exceptions (defensive programming)."""
    # Try with invalid inputs
    picked = None
    candidates = None
    cfg = None

    result = _prefer_raw_stage1c("test", picked, candidates, cfg=cfg)

    # Should return None without throwing
    assert result is None, f"Expected None, got '{result}'"

    # Try with empty candidates
    picked = MockEntry("Test food")
    candidates = []

    result = _prefer_raw_stage1c("test", picked, candidates, cfg=cfg)

    # Should return original without throwing
    assert getattr(result, "name", "") == "Test food"


if __name__ == "__main__":
    # Run tests
    print("Running Stage 1c unit tests...")

    test_stage1c_switches_to_raw()
    print("✓ test_stage1c_switches_to_raw passed")

    test_stage1c_keeps_when_no_raw()
    print("✓ test_stage1c_keeps_when_no_raw passed")

    test_stage1c_handles_dict_candidates()
    print("✓ test_stage1c_handles_dict_candidates passed")

    test_stage1c_keeps_already_raw()
    print("✓ test_stage1c_keeps_already_raw passed")

    test_stage1c_uses_defaults_when_no_config()
    print("✓ test_stage1c_uses_defaults_when_no_config passed")

    test_stage1c_never_throws()
    print("✓ test_stage1c_never_throws passed")

    print("\n✅ All Stage 1c unit tests passed!")
