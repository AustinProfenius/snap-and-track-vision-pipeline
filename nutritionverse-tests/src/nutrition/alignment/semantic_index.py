"""
Phase E1: Semantic Retrieval Prototype

Provides sentence-transformer embeddings + HNSW for semantic similarity search.
Foundation/SR only (8,350 entries, not 1.8M branded) for prototype validation.

Features:
- Lazy-loaded index (only loads when semantic search is enabled)
- HNSW indexing for fast approximate nearest neighbor search
- Energy-filtered results to prevent mismatches
- Runs as Stage 1S (after Stage 1c, before Stage 2)
- SHA256 checksum validation for index integrity
"""
import os
import pickle
import hashlib
import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Any, Dict
import numpy as np


class SemanticIndexBuilder:
    """Builds sentence-transformer embeddings + HNSW index for Foundation/SR entries."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialize builder with sentence transformer model.

        Args:
            model_name: HuggingFace model name for sentence embeddings
        """
        self.model_name = model_name
        self.model = None

    def _load_model(self):
        """Lazy-load sentence-transformer model."""
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(self.model_name)
                if os.getenv('ALIGN_VERBOSE', '0') == '1':
                    print(f"[SEMANTIC_INDEX] Loaded model: {self.model_name}")
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )

    def build(
        self,
        fdc_database,
        output_path: Path,
        data_types: List[str] = ['foundation_food', 'sr_legacy_food']
    ) -> Dict[str, Any]:
        """
        Build semantic index from Foundation/SR entries.

        Args:
            fdc_database: FDC database instance
            output_path: Path to save index files
            data_types: List of data types to index (default: Foundation + SR only)

        Returns:
            Stats dict with counts and timing
        """
        import time
        start_time = time.time()

        self._load_model()

        # Fetch Foundation/SR entries
        if os.getenv('ALIGN_VERBOSE', '0') == '1':
            print(f"[SEMANTIC_INDEX] Fetching Foundation/SR entries from database...")

        entries = []
        for data_type in data_types:
            try:
                # Query database for Foundation/SR entries
                results = fdc_database.query(
                    f"SELECT fdc_id, description, energy_kcal FROM fdc_entries "
                    f"WHERE data_type = '{data_type}'"
                )
                entries.extend(results)
            except Exception as e:
                print(f"[SEMANTIC_INDEX] Error fetching {data_type}: {e}")
                continue

        if not entries:
            raise ValueError("No Foundation/SR entries found in database")

        if os.getenv('ALIGN_VERBOSE', '0') == '1':
            print(f"[SEMANTIC_INDEX] Found {len(entries)} Foundation/SR entries")

        # Extract text and metadata
        fdc_ids = []
        descriptions = []
        energies = []

        for entry in entries:
            if isinstance(entry, dict):
                fdc_ids.append(entry.get('fdc_id'))
                descriptions.append(entry.get('description', ''))
                energies.append(entry.get('energy_kcal'))
            else:
                fdc_ids.append(entry[0])
                descriptions.append(entry[1])
                energies.append(entry[2])

        # Generate embeddings
        if os.getenv('ALIGN_VERBOSE', '0') == '1':
            print(f"[SEMANTIC_INDEX] Generating embeddings for {len(descriptions)} entries...")

        embeddings = self.model.encode(
            descriptions,
            show_progress_bar=True,
            convert_to_numpy=True
        )

        # Build HNSW index
        if os.getenv('ALIGN_VERBOSE', '0') == '1':
            print(f"[SEMANTIC_INDEX] Building HNSW index...")

        try:
            import hnswlib
        except ImportError:
            raise ImportError(
                "hnswlib not installed. Install with: pip install hnswlib"
            )

        # Initialize HNSW index
        dim = embeddings.shape[1]
        num_elements = len(embeddings)

        index = hnswlib.Index(space='cosine', dim=dim)
        index.init_index(max_elements=num_elements, ef_construction=200, M=16)
        index.add_items(embeddings, np.arange(num_elements))
        index.set_ef(50)  # Query-time search quality

        # Save index and metadata
        output_path.mkdir(parents=True, exist_ok=True)

        index_file = output_path / "semantic_index.hnsw"
        metadata_file = output_path / "semantic_metadata.pkl"

        index.save_index(str(index_file))

        # Generate checksums for validation (Phase E1)
        index_checksum = hashlib.sha256(index_file.read_bytes()).hexdigest()

        metadata = {
            'fdc_ids': fdc_ids,
            'descriptions': descriptions,
            'energies': energies,
            'model_name': self.model_name,
            'num_entries': len(fdc_ids),
            'data_types': data_types,
            'embedding_dim': dim,
            'build_timestamp': datetime.datetime.utcnow().isoformat(),
            'index_checksum': index_checksum
        }

        with open(metadata_file, 'wb') as f:
            pickle.dump(metadata, f)

        # Generate metadata checksum after saving
        metadata_checksum = hashlib.sha256(metadata_file.read_bytes()).hexdigest()

        # Update metadata with its own checksum (requires re-saving)
        metadata['metadata_checksum'] = metadata_checksum
        with open(metadata_file, 'wb') as f:
            pickle.dump(metadata, f)

        elapsed_time = time.time() - start_time

        stats = {
            'num_entries': len(fdc_ids),
            'embedding_dim': dim,
            'index_file': str(index_file),
            'metadata_file': str(metadata_file),
            'index_checksum': index_checksum,
            'metadata_checksum': metadata_checksum,
            'build_timestamp': metadata['build_timestamp'],
            'elapsed_time_sec': elapsed_time
        }

        if os.getenv('ALIGN_VERBOSE', '0') == '1':
            print(f"[SEMANTIC_INDEX] Index built successfully:")
            print(f"[SEMANTIC_INDEX]   Entries: {stats['num_entries']}")
            print(f"[SEMANTIC_INDEX]   Dimension: {stats['embedding_dim']}")
            print(f"[SEMANTIC_INDEX]   Time: {elapsed_time:.1f}s")
            print(f"[SEMANTIC_INDEX]   Index: {index_file}")
            print(f"[SEMANTIC_INDEX]   Metadata: {metadata_file}")
            print(f"[SEMANTIC_INDEX]   Checksum: {index_checksum[:16]}...")

        return stats


class SemanticSearcher:
    """Lazy-loaded semantic searcher with HNSW index."""

    def __init__(self, index_path: Path):
        """
        Initialize searcher (index loaded lazily on first search).

        Args:
            index_path: Path to directory containing index files
        """
        self.index_path = Path(index_path)
        self.index = None
        self.metadata = None
        self.model = None
        self.model_name = None

    def _load_index(self):
        """Lazy-load HNSW index and metadata."""
        if self.index is not None:
            return  # Already loaded

        index_file = self.index_path / "semantic_index.hnsw"
        metadata_file = self.index_path / "semantic_metadata.pkl"

        if not index_file.exists() or not metadata_file.exists():
            raise FileNotFoundError(
                f"Semantic index not found at {self.index_path}. "
                f"Build index first using SemanticIndexBuilder."
            )

        # Load metadata
        with open(metadata_file, 'rb') as f:
            self.metadata = pickle.load(f)

        # Validate checksums if present (Phase E1)
        if 'index_checksum' in self.metadata:
            actual_index_checksum = hashlib.sha256(index_file.read_bytes()).hexdigest()
            expected_index_checksum = self.metadata['index_checksum']
            if actual_index_checksum != expected_index_checksum:
                raise ValueError(
                    f"Index checksum mismatch! Expected {expected_index_checksum[:16]}..., "
                    f"got {actual_index_checksum[:16]}.... Index may be corrupted."
                )

            if os.getenv('ALIGN_VERBOSE', '0') == '1':
                print(f"[SEMANTIC_SEARCH] Index checksum validated: {expected_index_checksum[:16]}...")

        self.model_name = self.metadata['model_name']

        # Load HNSW index
        try:
            import hnswlib
        except ImportError:
            raise ImportError(
                "hnswlib not installed. Install with: pip install hnswlib"
            )

        dim = self.metadata['embedding_dim']
        self.index = hnswlib.Index(space='cosine', dim=dim)
        self.index.load_index(str(index_file), max_elements=self.metadata['num_entries'])

        if os.getenv('ALIGN_VERBOSE', '0') == '1':
            build_time = self.metadata.get('build_timestamp', 'unknown')
            print(f"[SEMANTIC_SEARCH] Loaded index: {self.metadata['num_entries']} entries (built: {build_time})")

    def _load_model(self):
        """Lazy-load sentence-transformer model."""
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(self.model_name)
                if os.getenv('ALIGN_VERBOSE', '0') == '1':
                    print(f"[SEMANTIC_SEARCH] Loaded model: {self.model_name}")
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )

    def search(
        self,
        query: str,
        top_k: int = 10,
        energy_filter: Optional[Tuple[float, float]] = None
    ) -> List[Tuple[int, float, str, float]]:
        """
        Search for semantically similar entries.

        Args:
            query: Query string (food name)
            top_k: Number of results to return
            energy_filter: Optional (min_kcal, max_kcal) tuple to filter results

        Returns:
            List of (fdc_id, similarity_score, description, energy_kcal) tuples
        """
        # Lazy-load index and model
        self._load_index()
        self._load_model()

        # Generate query embedding
        query_embedding = self.model.encode([query], convert_to_numpy=True)[0]

        # Search HNSW index (retrieve more if filtering by energy)
        search_k = top_k * 5 if energy_filter else top_k
        labels, distances = self.index.knn_query(query_embedding, k=search_k)

        # Convert distances to similarity scores (cosine similarity = 1 - distance)
        similarities = 1.0 - distances[0]

        # Build results
        results = []
        for idx, similarity in zip(labels[0], similarities):
            fdc_id = self.metadata['fdc_ids'][idx]
            description = self.metadata['descriptions'][idx]
            energy = self.metadata['energies'][idx]

            # Apply energy filter if provided
            if energy_filter:
                min_kcal, max_kcal = energy_filter
                if energy is None or not (min_kcal <= energy <= max_kcal):
                    continue

            results.append((fdc_id, float(similarity), description, energy))

            if len(results) >= top_k:
                break

        return results

    def __repr__(self) -> str:
        if self.metadata:
            return f"SemanticSearcher(entries={self.metadata['num_entries']}, loaded=True)"
        else:
            return f"SemanticSearcher(path={self.index_path}, loaded=False)"
