"""
Auto-detect prediction schema version and return appropriate parser.
"""

from typing import Dict, Any, Optional
from .prediction_schema_v1 import PredictionSchemaV1Parser
from .prediction_schema_v2 import PredictionSchemaV2Parser


def detect_schema(data: Dict[str, Any]) -> str:
    """
    Auto-detect schema version from data.

    Args:
        data: Loaded JSON data

    Returns:
        Schema version string ("v1", "v2", or "unknown")
    """
    # Try V2 first (future format)
    if PredictionSchemaV2Parser.can_parse(data):
        return "v2"

    # Try V1 (current format)
    if PredictionSchemaV1Parser.can_parse(data):
        return "v1"

    return "unknown"


def get_parser(schema_version: str):
    """
    Get parser class for schema version.

    Args:
        schema_version: Schema version string ("auto", "v1", "v2")

    Returns:
        Parser class

    Raises:
        ValueError: If schema version is unknown
    """
    if schema_version == "auto":
        # Auto-detection will happen at parse time
        return None

    parsers = {
        "v1": PredictionSchemaV1Parser,
        "v2": PredictionSchemaV2Parser
    }

    if schema_version not in parsers:
        raise ValueError(f"Unknown schema version: {schema_version}")

    return parsers[schema_version]
