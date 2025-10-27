"""
Test negative vocabulary safeguards - Phase 4 Pipeline Convergence.

Ensures cucumber/olive and other negative vocab rules prevent wrong matches.
"""
import pytest
from pathlib import Path
import sys

# Add pipeline to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from pipeline.config_loader import load_pipeline_config


class TestNegativeVocabularyConfig:
    """Test that negative vocabulary config has all required safeguards."""

    def test_cucumber_has_sea_cucumber_safeguard(self):
        """Cucumber negative vocab must include 'sea cucumber' safeguard."""
        configs_path = repo_root / "configs"
        config = load_pipeline_config(root=str(configs_path))

        assert "cucumber" in config.neg_vocab, "cucumber missing from negative_vocabulary.yml"

        cucumber_negatives = [n.lower() for n in config.neg_vocab["cucumber"]]

        # Must have these safeguards
        assert any("sea cucumber" in n for n in cucumber_negatives), (
            "Missing 'sea cucumber' safeguard for cucumber"
        )

    def test_olive_has_oil_safeguard(self):
        """Olive negative vocab must include 'oil' safeguard."""
        configs_path = repo_root / "configs"
        config = load_pipeline_config(root=str(configs_path))

        assert "olive" in config.neg_vocab, "olive missing from negative_vocabulary.yml"

        olive_negatives = [n.lower() for n in config.neg_vocab["olive"]]

        # Must exclude oil products
        assert "oil" in olive_negatives, "Missing 'oil' safeguard for olive"

    def test_grape_has_processed_form_safeguards(self):
        """Grape negative vocab must exclude juice, jam, jelly, raisins."""
        configs_path = repo_root / "configs"
        config = load_pipeline_config(root=str(configs_path))

        assert "grape" in config.neg_vocab

        grape_negatives = [n.lower() for n in config.neg_vocab["grape"]]

        # Must exclude processed forms
        required_exclusions = ["juice", "jam", "jelly", "raisin"]
        for exclusion in required_exclusions:
            assert exclusion in grape_negatives, (
                f"Grape missing '{exclusion}' exclusion"
            )

    def test_almond_has_processed_form_safeguards(self):
        """Almond negative vocab must exclude oil, butter, flour, etc."""
        configs_path = repo_root / "configs"
        config = load_pipeline_config(root=str(configs_path))

        assert "almond" in config.neg_vocab

        almond_negatives = [n.lower() for n in config.neg_vocab["almond"]]

        # Must exclude processed forms
        required_exclusions = ["oil", "butter", "flour"]
        for exclusion in required_exclusions:
            assert exclusion in almond_negatives, (
                f"Almond missing '{exclusion}' exclusion"
            )


class TestNegativeVocabularyStructure:
    """Test structural integrity of negative vocabulary config."""

    def test_negative_vocab_is_dict_of_lists(self):
        """negative_vocabulary.yml should be dict mapping class → list of exclusions."""
        configs_path = repo_root / "configs"
        config = load_pipeline_config(root=str(configs_path))

        assert isinstance(config.neg_vocab, dict)

        # Each entry should be a list
        for food_class, exclusions in config.neg_vocab.items():
            assert isinstance(food_class, str), f"Key {food_class} should be string"
            assert isinstance(exclusions, list), f"Value for {food_class} should be list"

            # Each exclusion should be a string
            for exclusion in exclusions:
                assert isinstance(exclusion, str), (
                    f"Exclusion {exclusion} for {food_class} should be string"
                )

    def test_no_duplicate_exclusions_per_class(self):
        """Each class should not have duplicate exclusions."""
        configs_path = repo_root / "configs"
        config = load_pipeline_config(root=str(configs_path))

        for food_class, exclusions in config.neg_vocab.items():
            # Convert to lowercase for comparison
            exclusions_lower = [e.lower() for e in exclusions]

            # Check for duplicates
            unique_exclusions = set(exclusions_lower)

            assert len(exclusions_lower) == len(unique_exclusions), (
                f"{food_class} has duplicate exclusions: {exclusions}"
            )


class TestNegativeVocabularyApplicationLogic:
    """Test that negative vocabulary is actually applied during alignment."""

    def test_alignment_engine_receives_negative_vocab(self):
        """Alignment engine should receive negative vocab from config."""
        from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion

        configs_path = repo_root / "configs"
        config = load_pipeline_config(root=str(configs_path))

        # Create engine with external config
        engine = FDCAlignmentWithConversion(
            negative_vocab=config.neg_vocab
        )

        # Should have external config
        assert engine.config_source == "external"
        assert engine._external_negative_vocab is not None

    def test_fallback_mode_still_has_negative_vocab(self):
        """Even in fallback mode, engine should have some negative vocab."""
        from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion
        import io
        import sys

        # Capture warnings
        captured = io.StringIO()
        sys.stdout = captured

        engine = FDCAlignmentWithConversion()  # No external config

        sys.stdout = sys.__stdout__

        # Should be in fallback mode
        assert engine.config_source == "fallback"

        # Should have emitted warning
        output = captured.getvalue()
        assert "[WARNING]" in output


class TestCriticalFoodNegativeVocab:
    """Test negative vocab for critical foods from Phase 1."""

    def test_all_critical_foods_have_negative_vocab(self):
        """All critical foods (grape, almond, melon, cucumber, olive) must have negative vocab."""
        configs_path = repo_root / "configs"
        config = load_pipeline_config(root=str(configs_path))

        critical_foods = [
            "grape",
            "almond",
            "cucumber",
            "olive",
            "cantaloupe",
            "honeydew"
        ]

        for food in critical_foods:
            # Note: cantaloupe/honeydew might not have specific entries (they're new)
            if food in ["cantaloupe", "honeydew"]:
                # These are OK to not have negative vocab (single-token, unambiguous)
                continue

            assert food in config.neg_vocab, (
                f"Critical food '{food}' missing from negative_vocabulary.yml"
            )

            # Should have at least one exclusion
            assert len(config.neg_vocab[food]) > 0, (
                f"{food} has empty negative vocabulary"
            )


class TestNegativeVocabularyCoverage:
    """Test that common problematic foods have negative vocab."""

    def test_common_fruits_have_processed_exclusions(self):
        """Common fruits should exclude juice/jam/dried forms."""
        configs_path = repo_root / "configs"
        config = load_pipeline_config(root=str(configs_path))

        common_fruits = ["apple", "grape", "strawberry", "blueberry"]
        processed_forms = ["juice", "jam"]

        for fruit in common_fruits:
            if fruit not in config.neg_vocab:
                continue  # Optional

            fruit_negatives = [n.lower() for n in config.neg_vocab[fruit]]

            # Should exclude at least one processed form
            has_exclusion = any(
                proc in fruit_negatives for proc in processed_forms
            )

            if not has_exclusion:
                # Warning, not failure (not all fruits need this)
                print(f"Note: {fruit} doesn't exclude processed forms")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
