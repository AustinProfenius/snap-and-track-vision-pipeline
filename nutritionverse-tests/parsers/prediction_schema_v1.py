"""
Schema V1 Parser - Current GPT-5 batch format

Schema:
{
  "timestamp": "...",
  "model": "gpt-5",
  "results": [
    {
      "dish_id": "...",
      "prediction": {
        "foods": [
          {"name": "...", "form": "...", "mass_g": N, ...}
        ]
      }
    }
  ]
}
"""

from typing import List, Dict, Any, Iterator
import hashlib
import json


class PredictionSchemaV1Parser:
    """Parser for V1 prediction schema (GPT-5 batch format)."""

    SCHEMA_VERSION = "v1"

    @staticmethod
    def can_parse(data: Dict[str, Any]) -> bool:
        """
        Check if data matches V1 schema.

        Args:
            data: Loaded JSON data

        Returns:
            True if data matches V1 schema
        """
        if not isinstance(data, dict):
            return False

        # V1 has 'results' array with 'prediction' objects
        if 'results' not in data:
            return False

        results = data['results']
        if not isinstance(results, list) or len(results) == 0:
            return False

        # Check first result has prediction with foods
        first = results[0]
        return (
            isinstance(first, dict) and
            'prediction' in first and
            isinstance(first['prediction'], dict) and
            'foods' in first['prediction']
        )

    @staticmethod
    def parse(data: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """
        Parse V1 format and yield normalized prediction dicts.

        Args:
            data: Loaded JSON data

        Yields:
            Normalized prediction dicts with:
            - prediction_id: Stable identifier
            - prediction_hash: Hash of foods array
            - foods: List of food dicts
            - metadata: Original metadata
        """
        results = data.get('results', [])

        for idx, result in enumerate(results):
            prediction = result.get('prediction', {})
            foods = prediction.get('foods', [])

            # Generate stable prediction ID
            dish_id = result.get('dish_id', f'prediction_{idx}')
            prediction_id = f"v1_{dish_id}"

            # Hash the foods array for change detection
            foods_json = json.dumps(foods, sort_keys=True)
            prediction_hash = hashlib.md5(foods_json.encode()).hexdigest()

            yield {
                'prediction_id': prediction_id,
                'prediction_hash': prediction_hash,
                'input_schema_version': 'v1',
                'foods': foods,
                'metadata': {
                    'dish_id': dish_id,
                    'image_filename': result.get('image_filename'),
                    'model': prediction.get('_metadata', {}).get('model', data.get('model')),
                    'original_index': idx
                }
            }
