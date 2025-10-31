"""
Unit tests for Phase E1 Semantic Retrieval Prototype (Stage 1S).

Tests the semantic index builder, searcher, and Stage 1S integration.
Note: These tests require sentence-transformers and hnswlib to be installed.
"""
import pytest
import sys
from pathlib import Path
import tempfile
import shutil

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.nutrition.alignment.semantic_index import SemanticIndexBuilder, SemanticSearcher

# Check if semantic search dependencies are available
try:
    import sentence_transformers
    import hnswlib
    SEMANTIC_DEPS_AVAILABLE = True
except ImportError:
    SEMANTIC_DEPS_AVAILABLE = False


@pytest.fixture
def temp_index_dir():
    """Create temporary directory for test indices."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


def test_semantic_index_builder_initialization():
    """Test that SemanticIndexBuilder initializes correctly."""
    if not SEMANTIC_DEPS_AVAILABLE:
        pytest.skip("sentence-transformers or hnswlib not installed")

    builder = SemanticIndexBuilder()
    assert builder.model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert builder.model is None  # Should be lazy-loaded


def test_semantic_searcher_initialization(temp_index_dir):
    """Test that SemanticSearcher initializes correctly."""
    if not SEMANTIC_DEPS_AVAILABLE:
        pytest.skip("sentence-transformers or hnswlib not installed")

    searcher = SemanticSearcher(temp_index_dir)
    assert searcher.index_path == temp_index_dir
    assert searcher.index is None  # Should be lazy-loaded
    assert searcher.model is None  # Should be lazy-loaded


def test_semantic_search_requires_index(temp_index_dir):
    """Test that semantic search fails gracefully without index."""
    if not SEMANTIC_DEPS_AVAILABLE:
        pytest.skip("sentence-transformers or hnswlib not installed")

    searcher = SemanticSearcher(temp_index_dir)

    # Should raise FileNotFoundError when trying to search without index
    with pytest.raises(FileNotFoundError):
        searcher.search("apple")


def test_semantic_index_builder_requires_database():
    """Test that index builder requires FDC database."""
    if not SEMANTIC_DEPS_AVAILABLE:
        pytest.skip("sentence-transformers or hnswlib not installed")

    builder = SemanticIndexBuilder()

    # Should fail without valid database
    # (We can't easily test this without a real database, so skip)
    pytest.skip("Requires real FDC database for testing")


def test_semantic_search_energy_filtering():
    """Test that semantic search respects energy filters."""
    if not SEMANTIC_DEPS_AVAILABLE:
        pytest.skip("sentence-transformers or hnswlib not installed")

    # This test would require a pre-built index
    # Skip for now as it requires database setup
    pytest.skip("Requires pre-built semantic index for testing")


def test_stage1s_disabled_by_default():
    """Test that Stage 1S is disabled by default (feature flag)."""
    # Import after path setup
    from src.adapters.alignment_adapter import AlignmentEngineAdapter

    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    # Check that semantic search is disabled by default
    feature_flags = adapter.engine._external_feature_flags
    if feature_flags:
        semantic_enabled = feature_flags.get('enable_semantic_search', False)
        assert semantic_enabled is False, \
            "Semantic search should be disabled by default (Phase E1 prototype)"


def test_stage1s_requires_semantic_index():
    """Test that Stage 1S requires semantic index to be loaded."""
    from src.adapters.alignment_adapter import AlignmentEngineAdapter

    adapter = AlignmentEngineAdapter()
    if not adapter.db_available:
        pytest.skip("DB not available")

    # Verify that semantic_searcher is None when not enabled
    assert adapter.engine._semantic_searcher is None, \
        "Semantic searcher should be None when feature is disabled"


def test_semantic_similarity_metadata():
    """Test that semantic matches include similarity metadata."""
    # This test requires Stage 1S to be enabled and a semantic index
    # Skip for now as it requires complex setup
    pytest.skip("Requires semantic search to be enabled with valid index")


def test_semantic_search_top_k_limit():
    """Test that semantic search respects top_k limit."""
    if not SEMANTIC_DEPS_AVAILABLE:
        pytest.skip("sentence-transformers or hnswlib not installed")

    # This test would require a pre-built index
    pytest.skip("Requires pre-built semantic index for testing")


def test_semantic_index_foundation_sr_only():
    """Test that semantic index only indexes Foundation/SR entries (not 1.8M branded)."""
    if not SEMANTIC_DEPS_AVAILABLE:
        pytest.skip("sentence-transformers or hnswlib not installed")

    # This test would verify the index builder only processes Foundation/SR
    # Skip for now as it requires database setup
    pytest.skip("Requires real FDC database for testing")
