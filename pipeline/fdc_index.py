"""
FDC database wrapper with deterministic version tracking.

Wraps existing FDCDatabase adapter and computes content hash for drift detection.
"""
import os
import hashlib
import json
from typing import List, Dict, Any
from pathlib import Path
import sys

# Add nutritionverse-tests to path to import FDCDatabase
nutritionverse_path = Path(__file__).parent.parent / "nutritionverse-tests"
if str(nutritionverse_path) not in sys.path:
    sys.path.insert(0, str(nutritionverse_path))

from src.adapters.fdc_database import FDCDatabase


class FDCIndex:
    """
    FDC database wrapper with versioning for reproducibility.

    Attributes:
        adapter: FDCDatabase instance for querying
        version: Deterministic version string (fdc@<hash>)
    """

    def __init__(self, adapter: FDCDatabase, version: str):
        self.adapter = adapter
        self.version = version

    def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Search FDC database for matching foods.

        Args:
            query: Search term (food name)
            **kwargs: Additional search parameters (limit, data_types, etc.)

        Returns:
            List of matching FDC entries
        """
        return self.adapter.search_foods(query, **kwargs)


def _compute_fdc_version(adapter: FDCDatabase) -> str:
    """
    Compute deterministic FDC index version via content hash.

    Strategy:
    1. Query representative sample from each data type
    2. Hash concatenation of fdc_id, name, data_type, macros
    3. Return fdc@<hash[:12]>

    This ensures identical database contents → identical version string.

    Args:
        adapter: FDCDatabase instance

    Returns:
        Version string like "fdc@a1b2c3d4e5f6"
    """
    try:
        adapter.connect()

        # Query sample entries from each data type for fingerprinting
        # Use deterministic ordering (ORDER BY fdc_id) and limited sample
        conn = adapter.conn
        cursor = conn.cursor()

        # Get counts per data type + sample of first 100 from each
        query = """
        WITH samples AS (
            SELECT fdc_id, name, data_type, calories_value, protein_value, total_fat_value, carbohydrates_value
            FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY data_type ORDER BY fdc_id) as rn
                FROM foods
                WHERE data_type IN ('foundation_food', 'sr_legacy_food', 'branded_food')
            ) ranked
            WHERE rn <= 100
            ORDER BY data_type, fdc_id
        )
        SELECT * FROM samples;
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        # Build deterministic fingerprint from sample
        fingerprint_data = []
        for row in rows:
            fingerprint_data.append({
                'fdc_id': row['fdc_id'],
                'name': row['name'],
                'data_type': row['data_type'],
                'energy_kcal': row['energy_kcal'],
                'protein_g': row['protein_g'],
                'fat_g': row['fat_g'],
                'carb_g': row['carb_g'],
            })

        # Hash the fingerprint data
        blob = json.dumps(fingerprint_data, sort_keys=True).encode('utf-8')
        hash_hex = hashlib.sha256(blob).hexdigest()[:12]

        cursor.close()

        return f"fdc@{hash_hex}"

    except Exception as e:
        # Fallback: use environment variable or "unknown"
        print(f"[WARNING] Could not compute FDC version from database: {e}")
        print("[WARNING] Using fallback FDC version")
        return os.getenv("FDC_INDEX_VERSION", "fdc@unknown")


def load_fdc_index(connection_url: str = None) -> FDCIndex:
    """
    Load FDC database and compute deterministic version.

    Args:
        connection_url: PostgreSQL DSN (default: read from NEON_CONNECTION_URL env)

    Returns:
        FDCIndex wrapper with versioned adapter

    Raises:
        ValueError: If connection URL not provided

    Example:
        >>> fdc = load_fdc_index()
        >>> results = fdc.search("chicken")
        >>> print(f"Using FDC version: {fdc.version}")
    """
    adapter = FDCDatabase(connection_url=connection_url)
    version = _compute_fdc_version(adapter)

    print(f"[FDC INDEX] Loaded FDC database: {version}")

    return FDCIndex(adapter, version)
