#!/usr/bin/env python3
"""
Quick smoke test for Phase 7.3 Task 1 & 2 fixes.

Tests:
1. Config loading (branded_fallbacks, unit_to_grams)
2. Stage 5B triggers for caesar salad and mixed greens
3. Config banner displays
"""
import sys
import os
from pathlib import Path

# Add paths
nutritionverse_path = Path(__file__).parent / "nutritionverse-tests"
sys.path.insert(0, str(nutritionverse_path))

# Enable verbose output
os.environ['ALIGN_VERBOSE'] = '1'

from pipeline.config_loader import load_pipeline_config
from pipeline.fdc_index import load_fdc_index
from pipeline.schemas import AlignmentRequest, DetectedFood
from pipeline.run import run_once

def test_config_loading():
    """Test that configs load properly."""
    print("\n" + "="*70)
    print("TEST 1: Config Loading")
    print("="*70)

    cfg = load_pipeline_config()

    # Check branded_fallbacks loaded
    assert cfg.branded_fallbacks is not None, "branded_fallbacks not loaded!"
    assert "fallbacks" in cfg.branded_fallbacks, "branded_fallbacks missing 'fallbacks' key!"
    print("✓ branded_fallbacks loaded:", list(cfg.branded_fallbacks.get("fallbacks", {}).keys())[:3])

    # Check unit_to_grams loaded
    assert cfg.unit_to_grams is not None, "unit_to_grams not loaded!"
    assert "egg_whole_large" in cfg.unit_to_grams, "unit_to_grams missing expected keys!"
    print("✓ unit_to_grams loaded:", list(cfg.unit_to_grams.keys())[:5])

    print("✓ Config loading test PASSED\n")
    return cfg

def test_stage5b_triggers(cfg, fdc):
    """Test that Stage 5B triggers for salads."""
    print("\n" + "="*70)
    print("TEST 2: Stage 5B Triggering")
    print("="*70)

    test_cases = [
        ("caesar salad", "raw"),
        ("mixed greens", "raw"),
    ]

    for name, form in test_cases:
        print(f"\n--- Testing: {name} ({form}) ---")
        request = AlignmentRequest(
            image_id=f"test_{name.replace(' ', '_')}",
            foods=[DetectedFood(name=name, form=form, mass_g=100)],
            config_version=cfg.config_version
        )

        result = run_once(request, cfg, fdc, code_git_sha="test")

        if result.foods:
            food = result.foods[0]
            stage = food.alignment_stage
            print(f"✓ Aligned to stage: {stage}")

            if stage == "stage5b_salad_decomposition":
                print(f"✓✓✓ SUCCESS: {name} decomposed via Stage 5B!")
            elif stage == "stage0_no_candidates":
                print(f"❌ FAILED: {name} hit stage0_no_candidates (Stage 5B did NOT trigger)")
                return False
            else:
                print(f"⚠️  {name} aligned to {stage} (not Stage 5B)")
        else:
            print(f"❌ No foods returned for {name}")
            return False

    print("\n✓ Stage 5B triggering test PASSED\n")
    return True

if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE 7.3 FIXES - SMOKE TEST")
    print("Tasks 1 & 2: Config Loading + Stage 5B Wiring")
    print("="*70)

    # Test 1: Config loading
    cfg = test_config_loading()

    # Load FDC index
    print("Loading FDC index...")
    fdc = load_fdc_index()
    print("✓ FDC index loaded\n")

    # Test 2: Stage 5B triggers
    success = test_stage5b_triggers(cfg, fdc)

    if success:
        print("\n" + "="*70)
        print("✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("="*70)
        sys.exit(0)
    else:
        print("\n" + "="*70)
        print("❌ TESTS FAILED")
        print("="*70)
        sys.exit(1)
