"""
Anthropic Claude adapter for nutrition estimation.
"""
import os
import base64
from pathlib import Path
from typing import Dict, Any, Optional

from anthropic import AsyncAnthropic

from ..core.prompts import SYSTEM_MESSAGE, parse_json_response


class ClaudeAdapter:
    """Adapter for Anthropic Claude vision models."""

    def __init__(self, model: str = "claude-3-5-sonnet-20241022", temperature: float = 0.0, max_tokens: int = 4096):
        """
        Initialize Claude adapter.

        Args:
            model: Model name (claude-3-7-sonnet, claude-3-5-sonnet, etc.)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

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
        # Encode image as base64
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # Determine image MIME type
        ext = image_path.suffix.lower()
        mime_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp"
        }.get(ext, "image/jpeg")

        # Build messages
        system_message = kwargs.get("system_message", SYSTEM_MESSAGE)

        # Claude format: system is separate parameter
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": image_data
                        }
                    },
                    {"type": "text", "text": prompt}
                ]
            }
        ]

        # Call API
        response = await self.client.messages.create(
            model=self.model,
            system=system_message,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        # Extract response
        content = response.content[0].text

        # Parse JSON
        result = parse_json_response(content)

        # Attach metadata
        result["_metadata"] = {
            "model": self.model,
            "tokens_input": response.usage.input_tokens,
            "tokens_output": response.usage.output_tokens,
            "tokens_total": response.usage.input_tokens + response.usage.output_tokens
        }

        return result

    def estimate_cost(self, tokens_input: int, tokens_output: int, model: Optional[str] = None) -> float:
        """
        Estimate cost for token usage.

        Args:
            tokens_input: Input tokens
            tokens_output: Output tokens
            model: Model name (uses self.model if not provided)

        Returns:
            Estimated cost in USD
        """
        model = model or self.model

        # Pricing as of Jan 2025 (per 1K tokens)
        pricing = {
            "claude-3-7-sonnet-20250219": {"input": 0.003, "output": 0.015},
            "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015}
        }

        # Default pricing for unknown models
        default_pricing = {"input": 0.003, "output": 0.015}

        model_pricing = pricing.get(model, default_pricing)

        cost_input = (tokens_input / 1000) * model_pricing["input"]
        cost_output = (tokens_output / 1000) * model_pricing["output"]

        return cost_input + cost_output
