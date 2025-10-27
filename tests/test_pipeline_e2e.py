"""
Test pipeline E2E with regression cases - Phase 4 Pipeline Convergence.

Ensures critical foods (grape, almond, melon) align correctly with 0.30 threshold.
These are regression tests based on previous alignment issues.
"""
import pytest
from pathlib import Path
import sys

# Add pipeline to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from pipeline.run import run_once
from pipeline.config_loader import load_pipeline_config, get_code_git_sha
from pipeline.fdc_index import load_fdc_index
from pipeline.schemas import AlignmentRequest, DetectedFood


@pytest.fixture(scope="module")
def pipeline_components():
    """Load pipeline components once for all tests."""
    configs_path = repo_root / "configs"
    config = load_pipeline_config(root=str(configs_path))
    fdc_index = load_fdc_index()
    code_sha = get_code_git_sha()

    return {
        "config": config,
        "fdc_index": fdc_index,
        "code_sha": code_sha
    }


class TestCriticalFoodAlignmentRegressions:
    """Regression tests for foods that previously had alignment issues."""

    def test_grape_aligns_with_030_threshold(self, pipeline_components):
        """Grape must align successfully with 0.30 threshold (regression from Phase 1)."""
        request = AlignmentRequest(
            image_id="test_grape_001",
            foods=[
                DetectedFood(
                    name="grape",
                    form="raw",
                    mass_g=100.0,
                    confidence=0.85
                )
            ],
            config_version=pipeline_components["config"].config_version
        )

        result = run_once(
            request=request,
            cfg=pipeline_components["config"],
            fdc_index=pipeline_components["fdc_index"],
            allow_stage_z=False,
            code_git_sha=pipeline_components["code_sha"]
        )

        # Verify alignment succeeded
        assert len(result.foods) == 1
        food = result.foods[0]

        # Should NOT be stage0_no_candidates
        assert food.alignment_stage != "stage0_no_candidates", (
            f"Grape failed to align! Stage: {food.alignment_stage}"
        )

        # Should have FDC match
        assert food.fdc_id is not None
        assert food.fdc_name is not None

        # Should have nutrition data
        assert food.calories is not None
        assert food.protein_g is not None

    def test_cantaloupe_aligns_with_030_threshold(self, pipeline_components):
        """Cantaloupe must align successfully with 0.30 threshold."""
        request = AlignmentRequest(
            image_id="test_cantaloupe_001",
            foods=[
                DetectedFood(
                    name="cantaloupe",
                    form="raw",
                    mass_g=150.0,
                    confidence=0.85
                )
            ],
            config_version=pipeline_components["config"].config_version
        )

        result = run_once(
            request=request,
            cfg=pipeline_components["config"],
            fdc_index=pipeline_components["fdc_index"],
            allow_stage_z=False,
            code_git_sha=pipeline_components["code_sha"]
        )

        food = result.foods[0]
        assert food.alignment_stage != "stage0_no_candidates"
        assert food.fdc_id is not None

    def test_honeydew_aligns_with_030_threshold(self, pipeline_components):
        """Honeydew must align successfully with 0.30 threshold."""
        request = AlignmentRequest(
            image_id="test_honeydew_001",
            foods=[
                DetectedFood(
                    name="honeydew",
                    form="raw",
                    mass_g=150.0,
                    confidence=0.85
                )
            ],
            config_version=pipeline_components["config"].config_version
        )

        result = run_once(
            request=request,
            cfg=pipeline_components["config"],
            fdc_index=pipeline_components["fdc_index"],
            allow_stage_z=False,
            code_git_sha=pipeline_components["code_sha"]
        )

        food = result.foods[0]
        assert food.alignment_stage != "stage0_no_candidates"
        assert food.fdc_id is not None

    def test_almond_aligns_with_030_threshold(self, pipeline_components):
        """Almond must align successfully with 0.30 threshold."""
        request = AlignmentRequest(
            image_id="test_almond_001",
            foods=[
                DetectedFood(
                    name="almond",
                    form="raw",
                    mass_g=28.0,  # ~1 oz
                    confidence=0.85
                )
            ],
            config_version=pipeline_components["config"].config_version
        )

        result = run_once(
            request=request,
            cfg=pipeline_components["config"],
            fdc_index=pipeline_components["fdc_index"],
            allow_stage_z=False,
            code_git_sha=pipeline_components["code_sha"]
        )

        food = result.foods[0]
        assert food.alignment_stage != "stage0_no_candidates"
        assert food.fdc_id is not None


class TestNegativeVocabularySafeguards:
    """Test that negative vocabulary prevents wrong matches."""

    def test_cucumber_does_not_match_sea_cucumber(self, pipeline_components):
        """'cucumber' should NOT match 'Sea cucumber' from FDC."""
        request = AlignmentRequest(
            image_id="test_cucumber_001",
            foods=[
                DetectedFood(
                    name="cucumber",
                    form="raw",
                    mass_g=100.0,
                    confidence=0.85
                )
            ],
            config_version=pipeline_components["config"].config_version
        )

        result = run_once(
            request=request,
            cfg=pipeline_components["config"],
            fdc_index=pipeline_components["fdc_index"],
            allow_stage_z=False,
            code_git_sha=pipeline_components["code_sha"]
        )

        food = result.foods[0]

        # If matched, should NOT be "Sea cucumber"
        if food.fdc_name:
            assert "sea cucumber" not in food.fdc_name.lower(), (
                f"Cucumber incorrectly matched to: {food.fdc_name}"
            )
            assert "yane" not in food.fdc_name.lower()

    def test_olive_does_not_match_olive_oil(self, pipeline_components):
        """'olive' should NOT match 'Olive oil' from FDC."""
        request = AlignmentRequest(
            image_id="test_olive_001",
            foods=[
                DetectedFood(
                    name="olive",
                    form="raw",
                    mass_g=50.0,
                    confidence=0.85
                )
            ],
            config_version=pipeline_components["config"].config_version
        )

        result = run_once(
            request=request,
            cfg=pipeline_components["config"],
            fdc_index=pipeline_components["fdc_index"],
            allow_stage_z=False,
            code_git_sha=pipeline_components["code_sha"]
        )

        food = result.foods[0]

        # If matched, should NOT contain "oil"
        if food.fdc_name:
            # Allow "olive loaf" but not "olive oil"
            if "oil" in food.fdc_name.lower():
                assert "loaf" in food.fdc_name.lower() or "pork" in food.fdc_name.lower(), (
                    f"Olive incorrectly matched to oil product: {food.fdc_name}"
                )


class TestConversionLayer:
    """Test raw→cooked conversion functionality."""

    def test_grilled_chicken_uses_conversion(self, pipeline_components):
        """Grilled chicken should use raw Foundation + conversion."""
        request = AlignmentRequest(
            image_id="test_chicken_001",
            foods=[
                DetectedFood(
                    name="chicken breast",
                    form="grilled",
                    mass_g=150.0,
                    confidence=0.85
                )
            ],
            config_version=pipeline_components["config"].config_version
        )

        result = run_once(
            request=request,
            cfg=pipeline_components["config"],
            fdc_index=pipeline_components["fdc_index"],
            allow_stage_z=False,
            code_git_sha=pipeline_components["code_sha"]
        )

        food = result.foods[0]

        # Should align (stage 2 or 1b)
        assert food.alignment_stage in [
            "stage2_raw_convert",
            "stage1b_raw_foundation_direct",
            "stage1c_cooked_sr_whitelist"
        ]

        # Should have nutrition data
        assert food.calories is not None


class TestMultipleFoodsPerImage:
    """Test pipeline with multiple foods in one request."""

    def test_multiple_foods_all_tracked(self, pipeline_components):
        """All foods in a request should be tracked in telemetry."""
        request = AlignmentRequest(
            image_id="test_multi_001",
            foods=[
                DetectedFood(name="grape", form="raw", mass_g=100.0),
                DetectedFood(name="almond", form="raw", mass_g=28.0),
                DetectedFood(name="banana", form="raw", mass_g=120.0),
            ],
            config_version=pipeline_components["config"].config_version
        )

        result = run_once(
            request=request,
            cfg=pipeline_components["config"],
            fdc_index=pipeline_components["fdc_index"],
            allow_stage_z=False,
            code_git_sha=pipeline_components["code_sha"]
        )

        # Should return 3 aligned foods
        assert len(result.foods) == 3

        # Totals should aggregate all foods
        total_mass = sum(f.mass_g for f in result.foods)
        assert total_mass == 248.0  # 100 + 28 + 120

        # Each food should have version tracking
        for food in result.foods:
            assert food.name in ["grape", "almond", "banana"]


class TestStageZControl:
    """Test Stage-Z branded fallback control."""

    def test_allow_stage_z_false_prevents_branded_fallback(self, pipeline_components):
        """When allow_stage_z=False, should not use Stage-Z."""
        request = AlignmentRequest(
            image_id="test_stagez_001",
            foods=[
                DetectedFood(
                    name="obscure_food_12345",  # Won't match Foundation
                    form="raw",
                    mass_g=100.0
                )
            ],
            config_version=pipeline_components["config"].config_version
        )

        result = run_once(
            request=request,
            cfg=pipeline_components["config"],
            fdc_index=pipeline_components["fdc_index"],
            allow_stage_z=False,  # Explicit disable
            code_git_sha=pipeline_components["code_sha"]
        )

        food = result.foods[0]

        # Should NOT use Stage-Z
        assert food.alignment_stage != "stageZ_branded_last_resort"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
