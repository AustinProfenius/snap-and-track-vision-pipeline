"""
Schema V2 Parser - Future/alternative prediction formats

This parser handles JSONL-style predictions or alternative batch formats.
Currently a placeholder that delegates to V1 for forward compatibility.
"""

from typing import List, Dict, Any, Iterator
from .prediction_schema_v1 import PredictionSchemaV1Parser


class PredictionSchemaV2Parser:
    """Parser for V2 prediction schema (future format)."""

    SCHEMA_VERSION = "v2"

    @staticmethod
    def can_parse(data: Dict[str, Any]) -> bool:
        """
        Check if data matches V2 schema.

        Args:
            data: Loaded JSON data

        Returns:
            True if data matches V2 schema
        """
        # V2 would have different structure
        # For now, return False (delegate to V1)
        return False

    @staticmethod
    def parse(data: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """
        Parse V2 format.

        Args:
            data: Loaded JSON data

        Yields:
            Normalized prediction dicts
        """
        # Future implementation
        # For now, empty (V1 handles current format)
        return iter([])
