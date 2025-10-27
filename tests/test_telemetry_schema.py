"""
Test telemetry schema invariants - Phase 4 Pipeline Convergence.

Ensures all telemetry events have mandatory version tracking fields.
If these tests fail, the build should fail.
"""
import pytest
import json
from pathlib import Path
import sys

# Add pipeline to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from pipeline.schemas import TelemetryEvent, AlignmentRequest, DetectedFood
from pipeline.config_loader import load_pipeline_config, get_code_git_sha
from pipeline.fdc_index import load_fdc_index
from pipeline.run import run_once


class TestTelemetryMandatoryFields:
    """Test that all telemetry events have required version tracking fields."""

    def test_telemetry_event_schema_has_version_fields(self):
        """TelemetryEvent schema must include version tracking fields."""
        # Check that Pydantic model has required fields
        required_fields = [
            'code_git_sha',
            'config_version',
            'fdc_index_version',
            'config_source'
        ]

        model_fields = TelemetryEvent.model_fields.keys()

        for field in required_fields:
            assert field in model_fields, (
                f"TelemetryEvent schema missing mandatory field: {field}"
            )

    def test_telemetry_event_rejects_missing_version_fields(self):
        """TelemetryEvent should reject events without version tracking."""
        # This should raise ValidationError
        with pytest.raises(Exception):  # Pydantic ValidationError
            TelemetryEvent(
                image_id="test",
                food_idx=0,
                query="grape",
                alignment_stage="stage1b_raw_foundation_direct",
                candidate_pool_size=10,
                foundation_pool_count=10,
                search_variants_tried=["grape"],
                # Missing: code_git_sha, config_version, fdc_index_version, config_source
            )

    def test_pipeline_run_produces_valid_telemetry(self):
        """Pipeline run_once() must produce telemetry with all mandatory fields."""
        # Load pipeline components
        configs_path = repo_root / "configs"
        config = load_pipeline_config(root=str(configs_path))
        fdc_index = load_fdc_index()
        code_sha = get_code_git_sha()

        # Create test request
        request = AlignmentRequest(
            image_id="test_telemetry_001",
            foods=[
                DetectedFood(
                    name="grape",
                    form="raw",
                    mass_g=100.0,
                    confidence=0.85
                )
            ],
            config_version=config.config_version
        )

        # Run pipeline
        result = run_once(
            request=request,
            cfg=config,
            fdc_index=fdc_index,
            allow_stage_z=False,
            code_git_sha=code_sha
        )

        # Verify result has version tracking
        assert result.code_git_sha is not None
        assert result.config_version is not None
        assert result.fdc_index_version is not None

        # Check telemetry file was created
        from glob import glob
        runs_dir = repo_root / "gpt5-context-delivery" / "entrypoints" / "runs"
        telemetry_files = list(runs_dir.glob("*/telemetry.jsonl"))

        if telemetry_files:
            # Read latest telemetry
            latest_telemetry = telemetry_files[-1]
            with open(latest_telemetry) as f:
                for line in f:
                    event = json.loads(line)
                    # Every telemetry event must have version fields
                    assert "code_git_sha" in event
                    assert "config_version" in event
                    assert "fdc_index_version" in event
                    assert "config_source" in event

                    # config_source must be "external" when using pipeline
                    assert event["config_source"] == "external"


class TestTelemetryConfigSourceTracking:
    """Test that config_source correctly distinguishes external vs fallback."""

    def test_external_configs_set_config_source_external(self):
        """When external configs provided, config_source must be 'external'."""
        from nutritionverse_tests.src.nutrition.alignment.align_convert import FDCAlignmentWithConversion

        # With external configs
        engine = FDCAlignmentWithConversion(
            class_thresholds={"grape": 0.30},
            negative_vocab={"grape": ["juice"]},
            feature_flags={"stageZ_branded_fallback": False}
        )

        assert engine.config_source == "external"

    def test_no_configs_sets_config_source_fallback(self):
        """When no external configs provided, config_source must be 'fallback'."""
        from nutritionverse_tests.src.nutrition.alignment.align_convert import FDCAlignmentWithConversion

        # Without external configs (backward compatibility mode)
        import io
        import sys

        # Capture warning output
        captured_output = io.StringIO()
        sys.stdout = captured_output

        engine = FDCAlignmentWithConversion()

        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        assert engine.config_source == "fallback"
        assert "[WARNING]" in output
        assert "hardcoded config defaults" in output


class TestVersionTrackingDeterminism:
    """Test that version strings are deterministic and stable."""

    def test_config_version_is_deterministic(self):
        """Config version should be same for same config files."""
        configs_path = repo_root / "configs"

        # Load config twice
        config1 = load_pipeline_config(root=str(configs_path))
        config2 = load_pipeline_config(root=str(configs_path))

        # Should produce identical fingerprints
        assert config1.config_version == config2.config_version
        assert config1.config_fingerprint == config2.config_fingerprint

    def test_config_version_changes_when_file_changes(self):
        """Config version should change if any config file is modified."""
        import tempfile
        import shutil

        # Create temp copy of configs
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_configs = Path(tmpdir) / "configs"
            shutil.copytree(repo_root / "configs", tmp_configs)

            # Load original
            config_original = load_pipeline_config(root=str(tmp_configs))

            # Modify a config file
            thresholds_file = tmp_configs / "class_thresholds.yml"
            with open(thresholds_file, 'a') as f:
                f.write("\n# Test comment\n")

            # Load modified
            config_modified = load_pipeline_config(root=str(tmp_configs))

            # Fingerprints should differ
            assert config_original.config_fingerprint != config_modified.config_fingerprint

    def test_code_git_sha_is_valid_format(self):
        """Code git SHA should be a valid 12-character hex string."""
        code_sha = get_code_git_sha()

        assert len(code_sha) == 12
        # Should be hexadecimal
        int(code_sha, 16)  # Raises ValueError if not hex


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
