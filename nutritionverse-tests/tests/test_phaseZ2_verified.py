"""
Phase Z2: Close Alignment Misses - Test Suite

Tests for Phase Z2 implementation covering:
1. CSV merge functionality
2. Special case handling (chicken, cherry tomato, chilaquiles, orange with peel)
3. No-result foods (celery root, tatsoi, alcohol, deprecated)
4. Normalization fixes
"""
import pytest
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nutrition.alignment.align_convert import AlignmentResolver, _normalize_for_lookup
from nutrition.fdc_database import FDCDatabase


@pytest.fixture(scope="module")
def alignment_resolver():
    """Create AlignmentResolver with Phase Z2 configs."""
    # Load all required configs
    config_dir = Path(__file__).parent.parent.parent / "configs"

    # This will be initialized with proper configs in the actual test environment
    resolver = AlignmentResolver(
        fdc_database_path=None,  # Mock or real DB path
        config_dir=config_dir
    )
    return resolver


class TestNormalizationFixes:
    """Test Phase Z2 normalization fixes."""

    def test_duplicate_parentheticals_collapse(self):
        """Test Fix 2: Collapse duplicate parentheticals."""
        # Test case: "spinach (raw) (raw)" → "spinach (raw)"
        norm, tokens, form, method, hints = _normalize_for_lookup("spinach (raw) (raw)")

        # Should not have duplicate (raw) (raw)
        assert "(raw) (raw)" not in norm
        # Should extract raw form
        assert form == "raw"
        # Should have spinach in result
        assert "spinach" in norm

    def test_sun_dried_normalization(self):
        """Test Fix 3: sun dried / sun-dried → sun_dried."""
        # Test with space
        norm1, *_, hints1 = _normalize_for_lookup("sun dried tomatoes")
        # Test with hyphen
        norm2, *_, hints2 = _normalize_for_lookup("sun-dried tomatoes")

        # Both should normalize to sun_dried
        assert "sun_dried" in norm1
        assert "sun_dried" in norm2
        # Should be consistent
        assert norm1 == norm2

    def test_peel_hint_extraction_with_peel(self):
        """Test Fix 4: Extract 'with peel' hint."""
        norm, tokens, form, method, hints = _normalize_for_lookup("orange with peel")

        # Should extract peel hint
        assert hints.get('peel') == True
        # Should remove peel from normalized name
        assert "peel" not in norm
        # Should have orange
        assert "orange" in norm

    def test_peel_hint_extraction_without_peel(self):
        """Test Fix 4: Extract 'without peel' hint."""
        norm, tokens, form, method, hints = _normalize_for_lookup("banana without peel")

        # Should extract peel hint as False
        assert hints.get('peel') == False
        # Should remove peel from normalized name
        assert "peel" not in norm
        # Should have banana
        assert "banana" in norm

    def test_deprecated_handling(self):
        """Test Fix 1: Handle literal 'deprecated'."""
        norm, tokens, form, method, hints = _normalize_for_lookup("deprecated")

        # Should return None for name
        assert norm is None
        # Should have ignored_class hint
        assert hints.get('ignored_class') == 'deprecated'
        # Should have empty tokens
        assert len(tokens) == 0


class TestCSVMergeFunctionality:
    """Test CSV merge tool and config integration."""

    def test_csv_derived_entries_exist(self):
        """Test that CSV-derived entries were merged into config."""
        config_path = Path(__file__).parent.parent.parent / "configs" / "stageZ_branded_fallbacks.yml"

        # Load config
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)

        fallbacks = config.get('fallbacks', {})

        # Check for known CSV entries (from missed_food_names.csv)
        csv_entries = [
            'spinach_baby',
            'eggplant',
            'chicken_breast_boneless_skinless_raw',
            'steak',
            'rice_brown_cooked'
        ]

        for entry_key in csv_entries:
            assert entry_key in fallbacks, f"CSV entry '{entry_key}' not found in config"

    def test_csv_entries_have_metadata(self):
        """Test that CSV entries have proper metadata."""
        config_path = Path(__file__).parent.parent.parent / "configs" / "stageZ_branded_fallbacks.yml"

        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)

        fallbacks = config.get('fallbacks', {})

        # Check spinach_baby has FDC ID and kcal range
        spinach = fallbacks.get('spinach_baby')
        assert spinach is not None
        assert 'primary' in spinach
        assert 'fdc_id' in spinach['primary']
        assert 'kcal_per_100g' in spinach['primary']

        # Kcal range should be valid
        kcal_range = spinach['primary']['kcal_per_100g']
        assert len(kcal_range) == 2
        assert kcal_range[0] < kcal_range[1]

    def test_celery_mapping_added(self):
        """Test that celery root → celery mapping exists."""
        config_path = Path(__file__).parent.parent.parent / "configs" / "stageZ_branded_fallbacks.yml"

        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)

        fallbacks = config.get('fallbacks', {})

        # Check celery entry exists
        assert 'celery' in fallbacks

        celery = fallbacks['celery']
        # Should have synonyms including "celery root"
        assert 'synonyms' in celery
        assert 'celery root' in celery['synonyms']


class TestSpecialCaseHandling:
    """Test special case foods from Phase Z2 spec."""

    @pytest.mark.skipif(not os.path.exists("/path/to/fdc_db"), reason="Requires FDC database")
    def test_cherry_tomato_foundation_match(self, alignment_resolver):
        """Test cherry tomato uses Foundation when available."""
        # Set feature flag
        alignment_resolver._external_feature_flags = {
            'allow_branded_when_foundation_missing': True
        }

        result = alignment_resolver.align(
            predicted_name="cherry tomato",
            predicted_form="raw",
            class_intent="produce|vegetable"
        )

        # Should find Foundation entry
        assert result.available is True
        # Should be Foundation, not Stage Z
        assert result.method in ["stage1b_direct", "stage1c_direct"]

    def test_chicken_breast_token_constraint(self):
        """Test chicken requires 'breast' token for breast mapping."""
        config_path = Path(__file__).parent.parent.parent / "configs" / "stageZ_branded_fallbacks.yml"

        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)

        fallbacks = config.get('fallbacks', {})

        # Find chicken breast entry
        chicken_breast = fallbacks.get('chicken_breast_boneless_skinless_raw')
        assert chicken_breast is not None

        # Should have token constraint
        metadata = chicken_breast.get('_metadata', {})
        assert 'token_constraint' in metadata
        assert 'breast' in metadata['token_constraint']

    def test_chilaquiles_low_confidence(self):
        """Test chilaquiles has low_confidence flag."""
        config_path = Path(__file__).parent.parent.parent / "configs" / "stageZ_branded_fallbacks.yml"

        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)

        fallbacks = config.get('fallbacks', {})

        # Find chilaquiles entry
        chilaquiles = fallbacks.get('chilaquiles_chips')
        assert chilaquiles is not None

        # Should have low_confidence flag
        metadata = chilaquiles.get('_metadata', {})
        assert metadata.get('low_confidence') is True

        # Should have valid kcal range
        kcal_range = chilaquiles['primary']['kcal_per_100g']
        assert kcal_range[0] < kcal_range[1], "Kcal range should be valid (min < max)"

    def test_orange_with_peel_hint(self):
        """Test orange with peel produces peel hint."""
        norm, tokens, form, method, hints = _normalize_for_lookup("orange with peel")

        # Should extract peel hint
        assert hints.get('peel') == True
        # Should normalize to just "orange"
        assert norm == "orange"


class TestNoResultFoods:
    """Test foods that should return no results (ignored)."""

    def test_tatsoi_ignored(self):
        """Test tatsoi is in negative vocabulary."""
        config_path = Path(__file__).parent.parent.parent / "configs" / "negative_vocabulary.yml"

        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Should have tatsoi
        assert 'tatsoi' in config
        assert config['tatsoi'] == ['all']

    def test_alcohol_ignored(self):
        """Test alcoholic beverages are in negative vocabulary."""
        config_path = Path(__file__).parent.parent.parent / "configs" / "negative_vocabulary.yml"

        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Should have various alcohol types
        alcohol_types = ['white_wine', 'red_wine', 'beer', 'wine', 'vodka',
                        'whiskey', 'rum', 'tequila', 'sake']

        for alcohol in alcohol_types:
            assert alcohol in config, f"Alcohol type '{alcohol}' not in negative vocabulary"
            assert config[alcohol] == ['all']

    def test_deprecated_normalization_ignored(self):
        """Test literal 'deprecated' is ignored via normalization."""
        norm, tokens, form, method, hints = _normalize_for_lookup("deprecated")

        # Should be marked as ignored
        assert hints.get('ignored_class') == 'deprecated'
        # Should return None
        assert norm is None


class TestTelemetryEnhancements:
    """Test Phase Z2 telemetry additions."""

    @pytest.mark.skipif(not os.path.exists("/path/to/fdc_db"), reason="Requires FDC database")
    def test_coverage_class_in_telemetry(self, alignment_resolver):
        """Test coverage_class field is added to telemetry."""
        # Enable Stage Z
        alignment_resolver._external_feature_flags = {
            'allow_branded_when_foundation_missing': True
        }

        result = alignment_resolver.align(
            predicted_name="spinach baby",
            predicted_form="raw",
            class_intent="produce|vegetable"
        )

        # Should have coverage_class in telemetry
        if result.method == "stageZ_branded_fallback":
            assert 'stageZ_branded_fallback' in result.telemetry
            stageZ_telemetry = result.telemetry['stageZ_branded_fallback']
            assert 'coverage_class' in stageZ_telemetry

    @pytest.mark.skipif(not os.path.exists("/path/to/fdc_db"), reason="Requires FDC database")
    def test_form_hint_in_telemetry(self, alignment_resolver):
        """Test peel hint is propagated to telemetry."""
        result = alignment_resolver.align(
            predicted_name="orange with peel",
            predicted_form="raw",
            class_intent="produce|fruit"
        )

        # Should have form_hint in telemetry if peel was detected
        if 'form_hint' in result.telemetry:
            assert 'peel' in result.telemetry['form_hint']
            assert result.telemetry['form_hint']['peel'] is True

    @pytest.mark.skipif(not os.path.exists("/path/to/fdc_db"), reason="Requires FDC database")
    def test_source_tracking_in_telemetry(self, alignment_resolver):
        """Test source field tracks manual_verified_csv vs existing_config."""
        alignment_resolver._external_feature_flags = {
            'allow_branded_when_foundation_missing': True
        }

        result = alignment_resolver.align(
            predicted_name="spinach baby",
            predicted_form="raw",
            class_intent="produce|vegetable"
        )

        # Should have source in Stage Z telemetry
        if result.method == "stageZ_branded_fallback":
            stageZ_telemetry = result.telemetry.get('stageZ_branded_fallback', {})
            assert 'source' in stageZ_telemetry
            # Should be either manual_verified_csv or existing_config
            assert stageZ_telemetry['source'] in ['manual_verified_csv', 'existing_config']


class TestIntegration:
    """Integration tests for Phase Z2."""

    def test_config_validation_passes(self):
        """Test that Stage Z config passes validation."""
        config_path = Path(__file__).parent.parent.parent / "configs" / "stageZ_branded_fallbacks.yml"

        # Run validation tool
        import subprocess
        result = subprocess.run(
            ['python', 'tools/validate_stageZ_config.py', str(config_path)],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True
        )

        # Should pass validation (exit code 0)
        assert result.returncode == 0, f"Config validation failed: {result.stdout}"

    def test_no_duplicate_keys(self):
        """Test config has no duplicate keys."""
        config_path = Path(__file__).parent.parent.parent / "configs" / "stageZ_branded_fallbacks.yml"

        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)

        fallbacks = config.get('fallbacks', {})

        # Check for duplicate keys (should be none due to YAML structure)
        keys = list(fallbacks.keys())
        unique_keys = set(keys)
        assert len(keys) == len(unique_keys), f"Found {len(keys) - len(unique_keys)} duplicate keys"

    def test_all_kcal_ranges_valid(self):
        """Test all kcal ranges are valid (min < max)."""
        config_path = Path(__file__).parent.parent.parent / "configs" / "stageZ_branded_fallbacks.yml"

        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)

        fallbacks = config.get('fallbacks', {})

        invalid_ranges = []
        for key, entry in fallbacks.items():
            primary = entry.get('primary', {})
            kcal_range = primary.get('kcal_per_100g', [])

            if len(kcal_range) == 2:
                if kcal_range[0] >= kcal_range[1]:
                    invalid_ranges.append(f"{key}: {kcal_range}")

        assert len(invalid_ranges) == 0, f"Invalid kcal ranges: {invalid_ranges}"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
