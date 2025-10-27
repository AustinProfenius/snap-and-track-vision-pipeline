"""
Test config loader stability and determinism - Phase 4 Pipeline Convergence.

Ensures config fingerprinting is stable and deterministic.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
import sys
import yaml
import json

# Add pipeline to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from pipeline.config_loader import load_pipeline_config, get_code_git_sha


class TestConfigFingerprinting:
    """Test that config fingerprinting is deterministic and stable."""

    def test_config_loads_successfully(self):
        """Config loader should load all required config files."""
        configs_path = repo_root / "configs"
        config = load_pipeline_config(root=str(configs_path))

        # Verify all config sections loaded
        assert config.thresholds is not None
        assert config.neg_vocab is not None
        assert config.variants is not None
        assert config.conversions is not None
        assert config.feature_flags is not None
        assert config.energy_bands is not None
        assert config.proxy_rules is not None

        # Verify version tracking
        assert config.config_version is not None
        assert config.config_fingerprint is not None
        assert config.config_version.startswith("configs@")

    def test_fingerprint_is_deterministic(self):
        """Same config files should produce same fingerprint."""
        configs_path = repo_root / "configs"

        # Load config multiple times
        config1 = load_pipeline_config(root=str(configs_path))
        config2 = load_pipeline_config(root=str(configs_path))
        config3 = load_pipeline_config(root=str(configs_path))

        # All should have identical fingerprints
        assert config1.config_fingerprint == config2.config_fingerprint
        assert config2.config_fingerprint == config3.config_fingerprint
        assert config1.config_version == config2.config_version

    def test_fingerprint_changes_on_threshold_change(self):
        """Changing class_thresholds.yml should change fingerprint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_configs = Path(tmpdir) / "configs"
            shutil.copytree(repo_root / "configs", tmp_configs)

            # Load original
            config_original = load_pipeline_config(root=str(tmp_configs))

            # Modify thresholds
            thresholds_file = tmp_configs / "class_thresholds.yml"
            with open(thresholds_file) as f:
                thresholds = yaml.safe_load(f)

            thresholds["grape"] = 0.25  # Change from 0.30
            with open(thresholds_file, 'w') as f:
                yaml.dump(thresholds, f)

            # Load modified
            config_modified = load_pipeline_config(root=str(tmp_configs))

            # Fingerprints must differ
            assert config_original.config_fingerprint != config_modified.config_fingerprint
            assert config_original.config_version != config_modified.config_version

    def test_fingerprint_changes_on_vocab_change(self):
        """Changing negative_vocabulary.yml should change fingerprint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_configs = Path(tmpdir) / "configs"
            shutil.copytree(repo_root / "configs", tmp_configs)

            # Load original
            config_original = load_pipeline_config(root=str(tmp_configs))

            # Modify vocab
            vocab_file = tmp_configs / "negative_vocabulary.yml"
            with open(vocab_file) as f:
                vocab = yaml.safe_load(f)

            vocab["grape"].append("wine")  # Add new negative
            with open(vocab_file, 'w') as f:
                yaml.dump(vocab, f)

            # Load modified
            config_modified = load_pipeline_config(root=str(tmp_configs))

            # Fingerprints must differ
            assert config_original.config_fingerprint != config_modified.config_fingerprint

    def test_fingerprint_stable_with_comment_changes(self):
        """YAML comments should NOT change fingerprint (only data matters)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_configs = Path(tmpdir) / "configs"
            shutil.copytree(repo_root / "configs", tmp_configs)

            # Load original
            config_original = load_pipeline_config(root=str(tmp_configs))

            # Add comment (data unchanged)
            thresholds_file = tmp_configs / "class_thresholds.yml"
            with open(thresholds_file) as f:
                content = f.read()

            with open(thresholds_file, 'w') as f:
                f.write("# New comment\n" + content)

            # Load modified
            config_modified = load_pipeline_config(root=str(tmp_configs))

            # Fingerprints should be SAME (comments don't affect data)
            assert config_original.config_fingerprint == config_modified.config_fingerprint


class TestConfigValues:
    """Test that configs contain expected values from Phase 1."""

    def test_class_thresholds_has_critical_overrides(self):
        """Critical single-token foods must have lowered thresholds."""
        configs_path = repo_root / "configs"
        config = load_pipeline_config(root=str(configs_path))

        # Phase 1 requirement: These foods need 0.30 threshold
        critical_foods = ["grape", "cantaloupe", "honeydew", "almond"]

        for food in critical_foods:
            assert food in config.thresholds, f"{food} missing from class_thresholds"
            assert config.thresholds[food] == 0.30, (
                f"{food} threshold should be 0.30, got {config.thresholds[food]}"
            )

        # Olive and tomato: 0.35 threshold
        assert config.thresholds["olive"] == 0.35
        assert config.thresholds["tomato"] == 0.35

    def test_negative_vocab_has_cucumber_safeguards(self):
        """Cucumber must exclude 'sea cucumber' (Phase 1 enhancement)."""
        configs_path = repo_root / "configs"
        config = load_pipeline_config(root=str(configs_path))

        assert "cucumber" in config.neg_vocab
        cucumber_negatives = [n.lower() for n in config.neg_vocab["cucumber"]]

        # Must have sea cucumber safeguards
        assert any("sea cucumber" in n for n in cucumber_negatives)

    def test_negative_vocab_has_olive_safeguards(self):
        """Olive must exclude 'oil' (Phase 1 enhancement)."""
        configs_path = repo_root / "configs"
        config = load_pipeline_config(root=str(configs_path))

        assert "olive" in config.neg_vocab
        olive_negatives = [n.lower() for n in config.neg_vocab["olive"]]

        # Must exclude olive oil
        assert "oil" in olive_negatives

    def test_feature_flags_has_stage_z_default(self):
        """stageZ_branded_fallback must default to false."""
        configs_path = repo_root / "configs"
        config = load_pipeline_config(root=str(configs_path))

        assert "stageZ_branded_fallback" in config.feature_flags
        assert config.feature_flags["stageZ_branded_fallback"] is False


class TestConfigLoaderErrorHandling:
    """Test that config loader handles errors gracefully."""

    def test_missing_config_directory_raises_error(self):
        """Should raise clear error if configs/ directory doesn't exist."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_pipeline_config(root="/nonexistent/configs")

        assert "config file not found" in str(exc_info.value).lower()

    def test_malformed_yaml_raises_error(self):
        """Should raise clear error if YAML is malformed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_configs = Path(tmpdir) / "configs"
            tmp_configs.mkdir()

            # Create malformed YAML
            bad_yaml = tmp_configs / "class_thresholds.yml"
            with open(bad_yaml, 'w') as f:
                f.write("grape: [\nunclosed bracket")

            with pytest.raises(Exception):  # yaml.YAMLError
                load_pipeline_config(root=str(tmp_configs))


class TestCodeGitSha:
    """Test code git SHA generation."""

    def test_code_git_sha_is_valid(self):
        """Code SHA should be a valid 12-char hex string."""
        code_sha = get_code_git_sha()

        assert isinstance(code_sha, str)
        assert len(code_sha) == 12
        # Should be hexadecimal
        int(code_sha, 16)  # Raises ValueError if not hex

    def test_code_git_sha_is_consistent(self):
        """Code SHA should be consistent within same session."""
        sha1 = get_code_git_sha()
        sha2 = get_code_git_sha()

        assert sha1 == sha2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
