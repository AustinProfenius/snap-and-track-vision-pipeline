"""
Google Gemini adapter for nutrition estimation.
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from ..core.prompts import SYSTEM_MESSAGE, parse_json_response


class GeminiAdapter:
    """Adapter for Google Gemini vision models."""

    def __init__(self, model: str = "gemini-1.5-flash", temperature: float = 0.0, max_tokens: int = 2048):
        """
        Initialize Gemini adapter.

        Args:
            model: Model name (gemini-1.5-flash, gemini-1.5-pro)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
        """
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        genai.configure(api_key=api_key)

        self.model_name = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Configure model
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "response_mime_type": "application/json"  # JSON mode
        }

        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        self.model = genai.GenerativeModel(
            model_name=model,
            generation_config=generation_config,
            safety_settings=safety_settings
        )

    async def infer(self, image_path: Path, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Run inference on an image with a prompt.

        Args:
            image_path: Path to image file
            prompt: User prompt text
            **kwargs: Additional arguments (supports 'system_message')

        Returns:
            Parsed JSON response

        Raises:
            Exception: If inference fails
        """
        # Load image
        with open(image_path, "rb") as f:
            image_data = f.read()

        # Determine MIME type
        ext = image_path.suffix.lower()
        mime_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp"
        }.get(ext, "image/jpeg")

        # Gemini image format
        image_part = {
            "mime_type": mime_type,
            "data": image_data
        }

        # Build prompt with system message
        system_message = kwargs.get("system_message", SYSTEM_MESSAGE)
        full_prompt = f"{system_message}\n\n{prompt}"

        # Call API (using generate_content_async for async)
        response = await self.model.generate_content_async([full_prompt, image_part])

        # Extract response
        content = response.text

        # Parse JSON
        result = parse_json_response(content)

        # Attach metadata (Gemini doesn't provide token counts in same way)
        result["_metadata"] = {
            "model": self.model_name,
            "tokens_input": None,  # Gemini API doesn't expose this easily
            "tokens_output": None,
            "tokens_total": None
        }

        return result

    def estimate_cost(self, tokens_input: int, tokens_output: int, model: Optional[str] = None) -> float:
        """
        Estimate cost for token usage.

        Args:
            tokens_input: Input tokens
            tokens_output: Output tokens
            model: Model name (uses self.model_name if not provided)

        Returns:
            Estimated cost in USD
        """
        model = model or self.model_name

        # Pricing as of Jan 2025 (per 1K tokens)
        pricing = {
            "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
            "gemini-1.5-pro": {"input": 0.00125, "output": 0.005}
        }

        if model not in pricing:
            return 0.0

        cost_input = (tokens_input / 1000) * pricing[model]["input"]
        cost_output = (tokens_output / 1000) * pricing[model]["output"]

        return cost_input + cost_output
