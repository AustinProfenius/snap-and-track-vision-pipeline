"""
Direct Stage Z validation test using FDCAlignmentWithConversion.

Tests Stage Z by directly calling the 5-stage alignment engine (bypassing V2 wrapper).
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion
from src.adapters.fdc_database import FDCDatabase
from src.config.feature_flags import FLAGS


def get_fdc_candidates(food_name: str, db_url: str):
    """Get FDC candidates from database for testing."""
    candidates = []

    with FDCDatabase(db_url) as db:
        # Search for candidates matching the food name
        # Simplified search - just get branded foods with name overlap
        words = food_name.lower().split()

        # Try to find candidates (simple keyword search)
        for word in words:
            if len(word) < 3:  # Skip short words
                continue

            query = """
                SELECT
                    fdc_id,
                    description as name,
                    data_type,
                    energy as kcal_100g,
                    protein as protein_100g,
                    carbohydrate as carbs_100g,
                    fat as fat_100g,
                    ingredients
                FROM fdc_food
                WHERE LOWER(description) LIKE %s
                AND data_type = 'branded_food'
                LIMIT 50
            """

            with db.connection.cursor() as cur:
                cur.execute(query, (f'%{word}%',))
                rows = cur.fetchall()

                for row in rows:
                    candidates.append({
                        "fdc_id": row[0],
                        "name": row[1],
                        "source": "branded",
                        "kcal_100g": row[3],
                        "protein_100g": row[4],
                        "carbs_100g": row[5],
                        "fat_100g": row[6],
                        "ingredients": row[7],
                        "form": "raw",  # Default
                        "method": "raw",  # Default
                    })

            if candidates:
                break  # Found some candidates

    return candidates


def test_stage_z_direct():
    """Test Stage Z directly with FDCAlignmentWithConversion."""
    print("=" * 80)
    print("STAGE Z DIRECT TEST")
    print("=" * 80)
    print(f"Feature Flag: stageZ_branded_fallback = {FLAGS.stageZ_branded_fallback}")
    print()

    # Initialize alignment engine
    engine = FDCAlignmentWithConversion()

    # Get database URL
    import os
    db_url = os.getenv("NEON_CONNECTION_URL")
    if not db_url:
        print("❌ NEON_CONNECTION_URL not set")
        return

    # Test cases designed to trigger Stage Z
    test_cases = [
        {
            "name": "bell pepper",
            "form": "raw",
            "kcal_100g": 26.0,
            "expected_stage": "stageZ_branded_last_resort",
            "description": "Catalog gap - should trigger Stage Z",
        },
        {
            "name": "cilantro",
            "form": "raw",
            "kcal_100g": 23.0,
            "expected_stage": "stageZ_branded_last_resort",
            "description": "Fresh herb - catalog gap",
        },
        {
            "name": "basil",
            "form": "raw",
            "kcal_100g": 23.0,
            "expected_stage": "stageZ_branded_last_resort",
            "description": "Fresh herb - catalog gap",
        },
        {
            "name": "parsley",
            "form": "raw",
            "kcal_100g": 36.0,
            "expected_stage": "stageZ_branded_last_resort",
            "description": "Fresh herb - catalog gap",
        },
    ]

    results = []
    stage_z_matches = []

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'=' * 80}")
        print(f"TEST {i}: {test['name']}")
        print(f"  {test['description']}")
        print(f"  Form: {test['form']}, Energy: {test['kcal_100g']} kcal/100g")
        if test['expected_stage']:
            print(f"  Expected Stage: {test['expected_stage']}")
        print("=" * 80)

        # Get FDC candidates from database
        try:
            candidates = get_fdc_candidates(test["name"], db_url)
            print(f"\n  Found {len(candidates)} branded candidates in database")

            if not candidates:
                print(f"  ⚠️  No candidates found - skipping")
                results.append(("SKIP", test["name"], "No candidates"))
                continue

            # Show sample candidates
            print(f"  Sample candidates:")
            for cand in candidates[:5]:
                print(f"    - {cand['name'][:60]} ({cand['kcal_100g']:.1f} kcal)")

            # Run alignment
            alignment_result = engine.align_food_item(
                predicted_name=test["name"],
                predicted_form=test["form"],
                predicted_kcal_100g=test["kcal_100g"],
                fdc_candidates=candidates,
                confidence=0.70  # Medium-low confidence to allow Stage Z
            )

            if alignment_result.fdc_id:
                print(f"\n  ✅ MATCHED: {alignment_result.name}")
                print(f"     FDC ID: {alignment_result.fdc_id}")
                print(f"     Source: {alignment_result.source}")
                print(f"     Stage: {alignment_result.alignment_stage}")
                print(f"     Confidence: {alignment_result.confidence:.2f}")
                print(f"     Score: {alignment_result.match_score:.2f}")
                print(f"     Energy: {alignment_result.kcal_100g:.1f} kcal/100g")
                print(f"     Macros: P{alignment_result.protein_100g:.1f}g C{alignment_result.carbs_100g:.1f}g F{alignment_result.fat_100g:.1f}g")

                # Track Stage Z matches
                stage = alignment_result.alignment_stage
                if stage == "stageZ_branded_last_resort":
                    print(f"\n     🎯 STAGE Z TRIGGERED!")
                    stage_z_matches.append({
                        "input": test["name"],
                        "matched": alignment_result.name,
                        "fdc_id": alignment_result.fdc_id,
                        "confidence": alignment_result.confidence,
                        "score": alignment_result.match_score,
                    })

                # Check stage expectations
                if test['expected_stage']:
                    if stage == test['expected_stage']:
                        print(f"     ✓ Expected stage matched")
                        results.append(("PASS", test["name"], stage))
                    else:
                        print(f"     ⚠️  Stage mismatch: got {stage}, expected {test['expected_stage']}")
                        results.append(("WARN", test["name"], stage))
                else:
                    results.append(("INFO", test["name"], stage))

            else:
                print(f"\n  ❌ NO MATCH FOUND")
                results.append(("FAIL", test["name"], "No match"))

        except Exception as e:
            print(f"\n  ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append(("ERROR", test["name"], str(e)))

    # Print telemetry
    print(f"\n\n{'=' * 80}")
    print("STAGE Z TELEMETRY")
    print("=" * 80)

    telemetry = engine.telemetry
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
        for item in telemetry['stageZ_top_rejected'][:10]:
            print(f"  - {item}")

    # Summary
    print(f"\n\n{'=' * 80}")
    print("SUMMARY")
    print("=" * 80)

    passed = sum(1 for r in results if r[0] == "PASS")
    warned = sum(1 for r in results if r[0] == "WARN")
    failed = sum(1 for r in results if r[0] == "FAIL")
    skipped = sum(1 for r in results if r[0] == "SKIP")
    errors = sum(1 for r in results if r[0] == "ERROR")

    print(f"Total: {len(results)} tests")
    print(f"  ✓ Passed: {passed}")
    print(f"  ⚠  Warnings: {warned}")
    print(f"  ✗ Failed: {failed}")
    print(f"  ⊘ Skipped: {skipped}")
    print(f"  ⚠ Errors: {errors}")
    print(f"\n🎯 Stage Z Matches: {len(stage_z_matches)}")

    if stage_z_matches:
        print("\nStage Z Match Details:")
        for match in stage_z_matches:
            print(f"  • {match['input']} → {match['matched'][:60]}")
            print(f"    FDC: {match['fdc_id']}, Score: {match['score']:.2f}, Confidence: {match['confidence']:.2f}")

    print("\nDetailed Results:")
    for status, name, info in results:
        symbol = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗", "SKIP": "⊘", "ERROR": "⚠", "INFO": "ℹ"}[status]
        print(f"  {symbol} {name} → {info}")

    # Stage Z validation
    print(f"\n{'=' * 80}")
    print("STAGE Z VALIDATION")
    print("=" * 80)

    if len(stage_z_matches) >= 2:
        print(f"✅ Stage Z is working! Captured {len(stage_z_matches)} catalog gap matches")
    elif len(stage_z_matches) > 0:
        print(f"⚠️  Stage Z triggered {len(stage_z_matches)} times (expected 2-4 for catalog gaps)")
    else:
        print(f"⚠️  Stage Z never triggered")
        print(f"   Possible reasons:")
        print(f"   - Feature flag disabled: {not FLAGS.stageZ_branded_fallback}")
        print(f"   - Earlier stages (1-4) found matches")
        print(f"   - No candidates passed Stage Z gates")
        print(f"   - No suitable branded candidates in database")

    if failed == 0 and errors == 0:
        print(f"\n🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
    else:
        print(f"\n⚠️  {failed + errors} tests had issues")


if __name__ == "__main__":
    test_stage_z_direct()
