"""
Advanced OpenAI adapter with two-pass detection workflow and FDC database integration.
"""
import os
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from openai import AsyncOpenAI

from ..core.advanced_schema import MEAL_ESTIMATE_SCHEMA, DETECTION_SCHEMA
from ..core.advanced_prompts import (
    SYSTEM_PROMPT_ADVANCED,
    SYSTEM_PROMPT_DETECTION,
    get_detection_prompt,
    get_full_estimation_prompt,
    get_review_prompt
)
from .fdc_database import FDCDatabase

load_dotenv(override=True)


class OpenAIAdvancedAdapter:
    """
    Advanced OpenAI adapter with:
    - Two-pass detection workflow (detect → lookup → compute)
    - FDC database integration
    - Uncertainty quantification
    - Structured output via JSON Schema
    """

    def __init__(
        self,
        model: str = "gpt-5",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        use_two_pass: bool = True
    ):
        """
        Initialize advanced adapter.

        Args:
            model: OpenAI model name
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            use_two_pass: Use two-pass workflow (detect → lookup → compute)
        """
        # Load API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key.startswith("your_"):
            raise ValueError("OPENAI_API_KEY not properly set in environment")

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.use_two_pass = use_two_pass

        # Initialize FDC database (optional)
        try:
            self.db = FDCDatabase()
            self.db_available = True
        except ValueError:
            self.db = None
            self.db_available = False
            print("[WARNING] FDC database not configured. Two-pass workflow unavailable.")

    async def infer_single_pass(
        self,
        image_path: Path,
        plate_diameter_cm: float = 27,
        angle_deg: int = 30,
        region: str = "USA",
        include_micros: bool = False
    ) -> Dict[str, Any]:
        """
        Single-pass inference: full estimation in one API call.

        Args:
            image_path: Path to meal image
            plate_diameter_cm: Plate diameter for scale
            angle_deg: Camera viewing angle
            region: Geographic region for cuisine assumptions
            include_micros: Include micronutrients in output

        Returns:
            MealEstimate dict
        """
        # Encode image
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        mime_type = "image/jpeg"
        if image_path.suffix.lower() == ".png":
            mime_type = "image/png"

        # Build user prompt
        user_prompt = get_full_estimation_prompt(
            plate_diameter_cm=plate_diameter_cm,
            angle_deg=angle_deg,
            region=region
        )

        # Determine API parameters
        is_gpt5 = self.model.startswith("gpt-5")

        if is_gpt5:
            # GPT-5 Responses API
            response = await self.client.responses.create(
                model=self.model,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": SYSTEM_PROMPT_ADVANCED},
                        {"type": "input_text", "text": user_prompt},
                        {"type": "input_image", "image_url": f"data:{mime_type};base64,{image_data}"}
                    ]
                }],
                response_format={
                    "type": "json_schema",
                    "json_schema": MEAL_ESTIMATE_SCHEMA
                }
            )
            content = response.output_text
        else:
            # Standard Chat Completions API
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT_ADVANCED},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_data}"}
                        }
                    ]
                }
            ]

            api_params = {
                "model": self.model,
                "messages": messages,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": MEAL_ESTIMATE_SCHEMA
                }
            }

            if not self.model.startswith("o1"):
                api_params["temperature"] = self.temperature

            response = await self.client.chat.completions.create(**api_params)
            content = response.choices[0].message.content

        # Parse JSON
        import json
        result = json.loads(content)

        # Add metadata
        result["_metadata"] = {
            "model": self.model,
            "workflow": "single_pass",
            "db_integrated": False
        }

        return result

    async def infer_two_pass(
        self,
        image_path: Path,
        plate_diameter_cm: float = 27,
        angle_deg: int = 30,
        region: str = "USA",
        include_micros: bool = False
    ) -> Dict[str, Any]:
        """
        Two-pass inference:
        Pass A: Detect items + estimate portions (vision-only)
        Database: Lookup nutrition from FDC
        Pass B: Review + adjust (optional)

        Args:
            image_path: Path to meal image
            plate_diameter_cm: Plate diameter for scale
            angle_deg: Camera viewing angle
            region: Geographic region
            include_micros: Include micronutrients

        Returns:
            MealEstimate dict with database-computed nutrition
        """
        if not self.db_available:
            raise ValueError("FDC database not available. Cannot run two-pass workflow.")

        # --- Pass A: Detection ---
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        mime_type = "image/jpeg"
        if image_path.suffix.lower() == ".png":
            mime_type = "image/png"

        user_prompt = get_detection_prompt(
            plate_diameter_cm=plate_diameter_cm,
            angle_deg=angle_deg,
            region=region
        )

        is_gpt5 = self.model.startswith("gpt-5")

        if is_gpt5:
            response = await self.client.responses.create(
                model=self.model,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": SYSTEM_PROMPT_DETECTION},
                        {"type": "input_text", "text": user_prompt},
                        {"type": "input_image", "image_url": f"data:{mime_type};base64,{image_data}"}
                    ]
                }],
                response_format={
                    "type": "json_schema",
                    "json_schema": DETECTION_SCHEMA
                }
            )
            detection_content = response.output_text
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT_DETECTION},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}}
                    ]
                }
            ]

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_schema", "json_schema": DETECTION_SCHEMA}
            )
            detection_content = response.choices[0].message.content

        import json
        detection = json.loads(detection_content)

        # --- Database Lookup & Compute ---
        enriched_items = []

        with self.db:
            for item in detection["items"]:
                # Search FDC database
                candidates = self.db.search_foods(
                    query=item["name"],
                    limit=3,
                    data_types=["foundation_food", "sr_legacy_food"]
                )

                if not candidates:
                    # No match found
                    enriched_items.append({
                        "name": item["name"],
                        "portion_g": item["portion_estimate_g"],
                        "fdc_id": None,
                        "fdc_name": "NOT_FOUND",
                        "calories_kcal": 0,
                        "protein_g": 0,
                        "carbs_g": 0,
                        "fat_g": 0,
                        "confidence": item["confidence"]
                    })
                    continue

                # Use best match
                best_match = candidates[0]
                fdc_id = str(best_match["fdc_id"])

                # Compute nutrition
                nutrition = self.db.compute_nutrition(
                    fdc_id=fdc_id,
                    portion_g=item["portion_estimate_g"]
                )

                enriched_items.append({
                    "name": item["name"],
                    "portion_g": item["portion_estimate_g"],
                    "fdc_id": fdc_id,
                    "fdc_name": best_match["name"],
                    "fdc_data_type": best_match["data_type"],
                    "calories_kcal": nutrition["calories"],
                    "protein_g": nutrition["protein_g"],
                    "carbs_g": nutrition["carbs_g"],
                    "fat_g": nutrition["fat_g"],
                    "calcium_mg": nutrition["calcium_mg"],
                    "iron_mg": nutrition["iron_mg"],
                    "magnesium_mg": nutrition["magnesium_mg"],
                    "potassium_mg": nutrition["potassium_mg"],
                    "sodium_mg": nutrition["sodium_mg"],
                    "vitamin_d_ug": nutrition["vitamin_d_ug"],
                    "vitamin_b12_ug": nutrition["vitamin_b12_ug"],
                    "confidence": item["confidence"],
                    "all_candidates": [
                        {
                            "fdc_id": str(c["fdc_id"]),
                            "match_name": c["name"],
                            "match_score": c.get("match_score", 0)
                        }
                        for c in candidates
                    ]
                })

        # Compute totals
        totals = {
            "mass_g": sum(item["portion_g"] for item in enriched_items),
            "calories": sum(item["calories_kcal"] for item in enriched_items),
            "protein_g": sum(item["protein_g"] for item in enriched_items),
            "carbs_g": sum(item["carbs_g"] for item in enriched_items),
            "fat_g": sum(item["fat_g"] for item in enriched_items),
        }

        if include_micros:
            totals.update({
                "calcium_mg": sum(item.get("calcium_mg", 0) for item in enriched_items),
                "iron_mg": sum(item.get("iron_mg", 0) for item in enriched_items),
                "magnesium_mg": sum(item.get("magnesium_mg", 0) for item in enriched_items),
                "potassium_mg": sum(item.get("potassium_mg", 0) for item in enriched_items),
                "sodium_mg": sum(item.get("sodium_mg", 0) for item in enriched_items),
                "vitamin_d_ug": sum(item.get("vitamin_d_ug", 0) for item in enriched_items),
                "vitamin_b12_ug": sum(item.get("vitamin_b12_ug", 0) for item in enriched_items),
            })

        # Build final result
        result = {
            "items": [
                {
                    "name": item["name"],
                    "fdc_candidates": item["all_candidates"],
                    "portion_estimate_g": item["portion_g"],
                    "macros": {
                        "protein_g": item["protein_g"],
                        "carbs_g": item["carbs_g"],
                        "fat_g": item["fat_g"]
                    },
                    "calories_kcal": item["calories_kcal"],
                    "confidence": item["confidence"]
                }
                for item in enriched_items
            ],
            "totals": totals,
            "uncertainty": {
                "kcal_low": totals["calories"] * 0.8,  # Conservative 20% uncertainty
                "kcal_high": totals["calories"] * 1.2,
                "mass_low_g": totals["mass_g"] * 0.8,
                "mass_high_g": totals["mass_g"] * 1.2
            },
            "notes": detection.get("context", {}),
            "_metadata": {
                "model": self.model,
                "workflow": "two_pass",
                "db_integrated": True,
                "detection": detection
            }
        }

        return result

    async def infer(
        self,
        image_path: Path,
        prompt: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Main inference method. Routes to single-pass or two-pass workflow.

        Args:
            image_path: Path to meal image
            prompt: Optional custom prompt (overrides defaults)
            **kwargs: Additional arguments

        Returns:
            MealEstimate dict
        """
        if self.use_two_pass and self.db_available:
            return await self.infer_two_pass(image_path, **kwargs)
        else:
            return await self.infer_single_pass(image_path, **kwargs)
