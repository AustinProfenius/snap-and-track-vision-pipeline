"""
FDC Database connector for USDA food lookups.
Connects to Neon PostgreSQL database with food nutrition data.
"""
import os
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


class FDCDatabase:
    """USDA FDC database connector."""

    def __init__(self, connection_url: Optional[str] = None):
        """
        Initialize database connection.

        Args:
            connection_url: PostgreSQL connection URL.
                          If None, uses NEON_CONNECTION_URL from environment.
        """
        self.connection_url = connection_url or os.getenv("NEON_CONNECTION_URL")

        if not self.connection_url:
            raise ValueError(
                "Database connection URL not provided. "
                "Set NEON_CONNECTION_URL environment variable or pass connection_url parameter."
            )

        self.conn = None

    def connect(self):
        """Establish database connection."""
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(
                self.connection_url,
                cursor_factory=RealDictCursor
            )
        return self.conn

    def close(self):
        """Close database connection."""
        if self.conn and not self.conn.closed:
            self.conn.close()

    def search_foods(
        self,
        query: str,
        limit: int = 3,
        data_types: List[str] = ["foundation_food", "sr_legacy_food"]
    ) -> List[Dict[str, Any]]:
        """
        Search for foods matching query string.

        Args:
            query: Search string (food name)
            limit: Maximum number of results
            data_types: FDC data types to include (foundation_food, sr_legacy_food, etc.)

        Returns:
            List of matching food records with nutrition data
        """
        conn = self.connect()
        cursor = conn.cursor()

        # Build search query with data_type filter
        data_type_filter = ",".join([f"'{dt}'" for dt in data_types])

        search_query = f"""
        SELECT
            fdc_id,
            name,
            data_type,
            food_category_description,
            serving_description,
            serving_gram_weight,
            -- Macros (per 100g unless serving_gram_weight specified)
            calories_value,
            protein_value,
            carbohydrates_value,
            total_fat_value,
            fiber_value,
            total_sugars_value,
            -- Micronutrients
            calcium_value,
            iron_value,
            magnesium_value,
            potassium_value,
            sodium_value,
            vitamin_d_value,
            vitamin_b12_value,
            -- Match score
            similarity(name, %s) as match_score
        FROM foods
        WHERE
            data_type IN ({data_type_filter})
            AND name ILIKE %s
        ORDER BY match_score DESC, fdc_id
        LIMIT %s
        """

        search_pattern = f"%{query}%"
        cursor.execute(search_query, (query, search_pattern, limit))

        results = cursor.fetchall()
        cursor.close()

        return [dict(row) for row in results]

    def get_food_by_fdc_id(self, fdc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get food by FDC ID.

        Args:
            fdc_id: FDC database ID

        Returns:
            Food record dict or None if not found
        """
        conn = self.connect()
        cursor = conn.cursor()

        query = """
        SELECT
            fdc_id,
            name,
            data_type,
            food_category_description,
            serving_description,
            serving_gram_weight,
            calories_value,
            protein_value,
            carbohydrates_value,
            total_fat_value,
            fiber_value,
            total_sugars_value,
            calcium_value,
            iron_value,
            magnesium_value,
            potassium_value,
            sodium_value,
            vitamin_d_value,
            vitamin_b12_value
        FROM foods
        WHERE fdc_id = %s
        """

        cursor.execute(query, (fdc_id,))
        result = cursor.fetchone()
        cursor.close()

        return dict(result) if result else None

    def compute_nutrition(
        self,
        fdc_id: str,
        portion_g: float
    ) -> Optional[Dict[str, float]]:
        """
        Compute nutrition for a specific portion.

        Args:
            fdc_id: FDC database ID
            portion_g: Portion size in grams

        Returns:
            Dict with computed nutrition values or None if food not found
        """
        food = self.get_food_by_fdc_id(fdc_id)
        if not food:
            return None

        # Determine scaling factor
        # If serving_gram_weight is specified, values are per serving
        # Otherwise, values are per 100g
        if food.get('serving_gram_weight'):
            scale_factor = portion_g / food['serving_gram_weight']
        else:
            scale_factor = portion_g / 100.0

        return {
            "mass_g": portion_g,
            "calories": (food.get('calories_value', 0) or 0) * scale_factor,
            "protein_g": (food.get('protein_value', 0) or 0) * scale_factor,
            "carbs_g": (food.get('carbohydrates_value', 0) or 0) * scale_factor,
            "fat_g": (food.get('total_fat_value', 0) or 0) * scale_factor,
            "fiber_g": (food.get('fiber_value', 0) or 0) * scale_factor,
            "sugars_g": (food.get('total_sugars_value', 0) or 0) * scale_factor,
            "calcium_mg": (food.get('calcium_value', 0) or 0) * scale_factor,
            "iron_mg": (food.get('iron_value', 0) or 0) * scale_factor,
            "magnesium_mg": (food.get('magnesium_value', 0) or 0) * scale_factor,
            "potassium_mg": (food.get('potassium_value', 0) or 0) * scale_factor,
            "sodium_mg": (food.get('sodium_value', 0) or 0) * scale_factor,
            "vitamin_d_ug": (food.get('vitamin_d_value', 0) or 0) * scale_factor,
            "vitamin_b12_ug": (food.get('vitamin_b12_value', 0) or 0) * scale_factor,
        }

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
