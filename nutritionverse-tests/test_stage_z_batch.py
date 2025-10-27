"""
Batch validation test for Stage Z implementation.

Tests catalog gap foods (bell peppers, herbs, uncommon produce) that should
trigger Stage Z fallback and validates telemetry tracking.
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from src.adapters.fdc_alignment_v2 import FDCAlignmentEngineV2
from src.config.feature_flags import FLAGS


def test_stage_z_batch_validation():
    """Test Stage Z with catalog gap foods."""
    print("=" * 80)
    print("STAGE Z BATCH VALIDATION TEST")
    print("=" * 80)
    print(f"Feature Flag Status: stageZ_branded_fallback = {FLAGS.stageZ_branded_fallback}")
    print()

    engine = FDCAlignmentEngineV2()

    if not engine.db_available:
        print("❌ Database not available")
        return

    # Test cases designed to trigger Stage Z (catalog gaps)
    test_cases = [
        # Raw vegetables (common catalog gaps)
        {
            "name": "green bell pepper",
            "calories": 24,
            "mass_g": 100,
            "expected_stage": "stageZ_branded_last_resort",
            "description": "Catalog gap - should trigger Stage Z",
        },
        {
            "name": "red bell pepper",
            "calories": 31,
            "mass_g": 100,
            "expected_stage": "stageZ_branded_last_resort",
            "description": "Catalog gap - should trigger Stage Z",
        },
        {
            "name": "fresh cilantro",
            "calories": 23,
            "mass_g": 100,
            "expected_stage": "stageZ_branded_last_resort",
            "description": "Fresh herb - catalog gap",
        },
        {
            "name": "fresh basil",
            "calories": 23,
            "mass_g": 100,
            "expected_stage": "stageZ_branded_last_resort",
            "description": "Fresh herb - catalog gap",
        },
        {
            "name": "fresh parsley",
            "calories": 36,
            "mass_g": 100,
            "expected_stage": "stageZ_branded_last_resort",
            "description": "Fresh herb - catalog gap",
        },
        {
            "name": "scallions",
            "calories": 32,
            "mass_g": 100,
            "expected_stage": "stageZ_branded_last_resort",
            "description": "Regional synonym test (green onion)",
        },
        {
            "name": "zucchini",
            "calories": 17,
            "mass_g": 100,
            "expected_stage": None,  # May find in Foundation/SR
            "description": "May have Foundation entry",
        },
        # Foods that should NOT trigger Stage Z (have good Foundation/SR matches)
        {
            "name": "cooked white rice",
            "calories": 130,
            "mass_g": 100,
            "expected_stage": "stage2_raw_convert",
            "description": "Should match Foundation rice",
        },
        {
            "name": "grilled chicken breast",
            "calories": 165,
            "mass_g": 100,
            "expected_stage": "stage1_cooked_exact",
            "description": "Should match Foundation chicken",
        },
        {
            "name": "raw almonds",
            "calories": 164,
            "mass_g": 28,
            "expected_stage": "stage1_cooked_exact",  # Almonds are considered "cooked" (dried)
            "description": "Should match SR legacy nuts",
        },
    ]

    results = []
    stage_z_matches = []

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'=' * 80}")
        print(f"TEST {i}: {test['name']}")
        print(f"  {test['description']}")
        print(f"  Predicted: {test['mass_g']}g, {test['calories']} kcal")
        if test['expected_stage']:
            print(f"  Expected Stage: {test['expected_stage']}")
        print("=" * 80)

        # Build predicted food dict
        predicted_food = {
            "mass_g": test["mass_g"],
            "calories": test["calories"]
        }

        # Run alignment
        alignment = engine.align_predicted_food(test["name"], predicted_food)

        if alignment:
            matched_name = alignment["matched_name"]
            nutrition = alignment["nutrition"]
            stage = alignment.get("alignment_stage", "unknown")

            print(f"\n✅ MATCHED: {matched_name}")
            print(f"   FDC ID: {alignment['fdc_id']}")
            print(f"   Data Type: {alignment['data_type']}")
            print(f"   Stage: {stage}")
            print(f"   Confidence: {alignment['confidence']:.2f}")
            print(f"   Score: {alignment['score']:.2f}")
            print(f"\n   Computed Nutrition:")
            print(f"     Mass: {nutrition['mass_g']:.1f}g")
            print(f"     Calories: {nutrition['calories']:.1f} kcal")
            print(f"     Protein: {nutrition['protein_g']:.1f}g")
            print(f"     Carbs: {nutrition['carbs_g']:.1f}g")
            print(f"     Fat: {nutrition['fat_g']:.1f}g")

            # Track Stage Z matches
            if stage == "stageZ_branded_last_resort":
                print(f"\n   🎯 STAGE Z TRIGGERED!")
                stage_z_matches.append({
                    "input": test["name"],
                    "matched": matched_name,
                    "fdc_id": alignment["fdc_id"],
                    "confidence": alignment["confidence"],
                    "score": alignment["score"],
                })

            # Check stage expectations
            if test['expected_stage']:
                if stage == test['expected_stage']:
                    print(f"   ✓ Expected stage matched: {stage}")
                    results.append(("PASS", test["name"], stage))
                else:
                    print(f"   ⚠️  Stage mismatch: got {stage}, expected {test['expected_stage']}")
                    results.append(("WARN", test["name"], stage))
            else:
                print(f"   ℹ️  Stage: {stage} (no expectation set)")
                results.append(("INFO", test["name"], stage))

            # Sanity checks
            mass_ratio = nutrition['mass_g'] / test['mass_g']
            if mass_ratio < 0.95 or mass_ratio > 1.05:
                print(f"   ⚠️  WARNING: Mass ratio {mass_ratio:.2f}x (expected ~1.0)")

            cal_ratio = nutrition['calories'] / test['calories']
            if abs(cal_ratio - 1.0) > 0.15:  # Allow 15% variance
                print(f"   ⚠️  WARNING: Calorie variance {((cal_ratio - 1.0) * 100):.1f}%")

        else:
            print(f"\n❌ NO MATCH FOUND")
            results.append(("FAIL", test["name"], "No match"))

    # Print telemetry
    print(f"\n\n{'=' * 80}")
    print("STAGE Z TELEMETRY")
    print("=" * 80)

    # Access telemetry from conversion_engine (if available)
    if hasattr(engine, 'conversion_engine') and engine.conversion_engine:
        telemetry = engine.conversion_engine.telemetry
        print(f"\nStage Z Metrics:")
        print(f"  Attempts: {telemetry.get('stageZ_attempts', 0)}")
        print(f"  Passes: {telemetry.get('stageZ_passes', 0)}")
        print(f"\nRejection Reasons:")
        print(f"  Energy band: {telemetry.get('stageZ_reject_energy_band', 0)}")
        print(f"  Macro gates: {telemetry.get('stageZ_reject_macro_gates', 0)}")
        print(f"  Ingredients: {telemetry.get('stageZ_reject_ingredients', 0)}")
        print(f"  Processing: {telemetry.get('stageZ_reject_processing', 0)}")
        print(f"  Score floor: {telemetry.get('stageZ_reject_score_floor', 0)}")

        if telemetry.get('stageZ_top_rejected'):
            print(f"\nTop Rejected Candidates:")
            for item in telemetry['stageZ_top_rejected'][:5]:
                print(f"  - {item}")
    else:
        print("\n⚠️  Conversion engine not initialized - cannot access Stage Z telemetry")
        print(f"   Has conversion_engine: {hasattr(engine, 'conversion_engine')}")
        print(f"   Conversion enabled: {engine.conversion_enabled if hasattr(engine, 'conversion_enabled') else 'unknown'}")

    # Summary
    print(f"\n\n{'=' * 80}")
    print("SUMMARY")
    print("=" * 80)

    passed = sum(1 for r in results if r[0] == "PASS")
    warned = sum(1 for r in results if r[0] == "WARN")
    failed = sum(1 for r in results if r[0] == "FAIL")
    info = sum(1 for r in results if r[0] == "INFO")

    print(f"Total: {len(results)} tests")
    print(f"  ✓ Passed: {passed}")
    print(f"  ⚠  Warnings: {warned}")
    print(f"  ✗ Failed: {failed}")
    print(f"  ℹ️  Info: {info}")
    print(f"\n🎯 Stage Z Matches: {len(stage_z_matches)}")

    if stage_z_matches:
        print("\nStage Z Match Details:")
        for match in stage_z_matches:
            print(f"  • {match['input']} → {match['matched']}")
            print(f"    FDC: {match['fdc_id']}, Score: {match['score']:.2f}, Confidence: {match['confidence']:.2f}")

    print("\nDetailed Results:")
    for status, name, info in results:
        symbol = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗", "INFO": "ℹ"}[status]
        print(f"  {symbol} {name} → {info}")

    # Stage Z validation
    print(f"\n{'=' * 80}")
    print("STAGE Z VALIDATION")
    print("=" * 80)

    if len(stage_z_matches) >= 3:
        print(f"✅ Stage Z is working! Captured {len(stage_z_matches)} catalog gap matches")
    elif len(stage_z_matches) > 0:
        print(f"⚠️  Stage Z triggered {len(stage_z_matches)} times (expected 3-6 for catalog gaps)")
    else:
        print(f"❌ Stage Z never triggered - check if feature flag is enabled")
        print(f"   Current flag status: {FLAGS.stageZ_branded_fallback}")

    if failed == 0:
        print(f"\n🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
    else:
        print(f"\n⚠️  {failed} tests had no match")


if __name__ == "__main__":
    test_stage_z_batch_validation()
