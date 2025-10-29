"""
OpenAI GPT-5 adapter for nutrition estimation.
GPT-5 models are mapped to gpt-4o in the OpenAI API.
"""
import os
import base64
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from openai import AsyncOpenAI

from ..core.prompts import SYSTEM_MESSAGE, parse_json_response
from ..core.nutritionverse_prompts import (
    MASS_ONLY_SYSTEM_MESSAGE,
    get_mass_only_prompt,
    validate_mass_only_response,
    parse_json_response as parse_json_nv
)
from ..core.image_preprocessing import preprocess_image_for_api

# Force reload of .env file
load_dotenv(override=True)


class OpenAIAdapter:
    """Adapter for OpenAI GPT-5 Vision models."""

    def __init__(self, model: str = "gpt-5", temperature: float = 0.1, max_tokens: int = 900, use_mass_only: bool | None = None):
        """
        Initialize OpenAI adapter.

        Args:
            model: Model name (gpt-5, gpt-5-mini, gpt-5-turbo, gpt-5-vision, etc.)
            temperature: Sampling temperature (default 0.1 for consistency)
            max_tokens: Maximum tokens in response (default 900 for mass-only mode)
            use_mass_only: Use mass-only prompt (no calorie estimation from vision).
                          If None, reads from FLAGS.vision_mass_only (default: True)
        """
        # Try multiple ways to get API key
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key or api_key.startswith("your_") or api_key == "":
            # Try loading .env from multiple locations
            possible_env_paths = [
                Path.cwd() / ".env",
                Path(__file__).parent.parent.parent / ".env",
                Path("/Users/austinprofenius/snapandtrack-model-testing/nutritionverse-tests/.env"),
            ]

            for env_path in possible_env_paths:
                if env_path.exists():
                    load_dotenv(env_path, override=True)
                    api_key = os.getenv("OPENAI_API_KEY")
                    if api_key and not api_key.startswith("your_"):
                        break

        if not api_key or api_key.startswith("your_"):
            raise ValueError(
                f"OPENAI_API_KEY not properly set.\n"
                f"Current value: {api_key}\n"
                f"Tried loading .env from:\n" +
                "\n".join([f"  - {p} (exists: {p.exists()})" for p in possible_env_paths]) +
                f"\n\nPlease ensure .env file exists with a valid OPENAI_API_KEY=sk-..."
            )

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Read mass-only flag from FLAGS if not specified
        if use_mass_only is None:
            from ..config.feature_flags import FLAGS
            use_mass_only = FLAGS.vision_mass_only

        self.use_mass_only = use_mass_only

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
        # Log the image being processed for debugging
        print(f"[OpenAI Adapter] Reading image: {image_path}")
        print(f"[OpenAI Adapter] Image file exists: {image_path.exists()}")
        print(f"[OpenAI Adapter] Image filename: {image_path.name}")

        # Preprocess image: EXIF orientation, optimal resolution (1536px), high quality JPEG
        print(f"[OpenAI Adapter] Preprocessing image (EXIF correction, resize to 1536px)")
        image_bytes = preprocess_image_for_api(
            image_path,
            target_size=1536,  # Optimal for GPT-5 Vision
            jpeg_quality=95     # High quality, minimal compression
        )

        image_data = base64.b64encode(image_bytes).decode("utf-8")
        print(f"[OpenAI Adapter] Preprocessed and encoded {len(image_bytes)} bytes to base64")

        # Determine image MIME type
        ext = image_path.suffix.lower()
        mime_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp"
        }.get(ext, "image/jpeg")

        # Build messages (use mass-only prompts if enabled)
        if self.use_mass_only:
            system_message = MASS_ONLY_SYSTEM_MESSAGE
            user_prompt = get_mass_only_prompt()
        else:
            system_message = kwargs.get("system_message", SYSTEM_MESSAGE)
            user_prompt = prompt

        messages = [
            {"role": "system", "content": system_message},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_data}"
                        }
                    }
                ]
            }
        ]

        # GPT-5 uses a completely different API (responses.create instead of chat.completions.create)
        is_gpt5 = self.model.startswith("gpt-5")

        if is_gpt5:
            # GPT-5 uses new Responses API
            # CRITICAL: Include system message (was previously dropped!)

            # Build input messages with system role
            # IMPORTANT: Responses API requires "input_text" not "text" for all text content
            input_messages = [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_message}]
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": f"data:{mime_type};base64,{image_data}"}
                    ]
                }
            ]

            # NOTE: GPT-5 Responses API does not support JSON schema enforcement yet
            # We rely on system message instructions to get properly formatted JSON
            # Expected schema (documented for reference):
            # {
            #   "foods": [{
            #     "name": str,
            #     "mass_g": number,
            #     "calories": number,
            #     "fat_g": number,
            #     "carbs_g": number,
            #     "protein_g": number,
            #     "form": str (optional),  # raw/cooked/dried/juice/canned/baby
            #     "count": number (optional),  # for discrete items
            #     "kcal_per_100g_est": number (optional),  # energy density estimate
            #     "confidence": number (optional)  # 0-1 confidence score
            #   }],
            #   "totals": {
            #     "mass_g": number,
            #     "calories": number,
            #     "fat_g": number,
            #     "carbs_g": number,
            #     "protein_g": number
            #   }
            # }

            # GPT-5 API call with proper parameters
            # Note: GPT-5 Responses API does NOT support temperature or max_output_tokens
            # Only pass model and input (minimal params for reliability)
            response = await self.client.responses.create(
                model=self.model,
                input=input_messages
            )

            # Extract response - GPT-5 uses output_text
            content = response.output_text

        else:
            # Standard chat.completions API (fallback for non-GPT-5 models)
            uses_completion_tokens = any([
                self.model.startswith("o1"),
                self.model.startswith("o3"),
                "2024-08-06" in self.model,
            ])

            # Build API call parameters
            api_params = {
                "model": self.model,
                "messages": messages,
            }

            # Add temperature (not supported by o-series)
            if not self.model.startswith("o1") and not self.model.startswith("o3"):
                api_params["temperature"] = self.temperature

            # Add token limit parameter
            if uses_completion_tokens:
                api_params["max_completion_tokens"] = self.max_tokens
            else:
                api_params["max_tokens"] = self.max_tokens

            # Add JSON mode if supported
            if not self.model.startswith("o1") and not self.model.startswith("o3"):
                api_params["response_format"] = {"type": "json_object"}

            # Call API
            response = await self.client.chat.completions.create(**api_params)

            # Extract response
            content = response.choices[0].message.content

        # Parse JSON
        result = parse_json_response(content)

        # Validate mass-only response if enabled
        if self.use_mass_only:
            try:
                validate_mass_only_response(result)
            except ValueError as e:
                print(f"[OpenAI Adapter] WARNING: Mass-only validation failed: {e}")
                # Re-raise to fail fast
                raise

        # Attach metadata
        if is_gpt5:
            # GPT-5 responses may have different usage structure
            try:
                usage = response.usage
                result["_metadata"] = {
                    "model": self.model,
                    "tokens_input": getattr(usage, 'prompt_tokens', 0) if usage else 0,
                    "tokens_output": getattr(usage, 'completion_tokens', 0) if usage else 0,
                    "tokens_total": getattr(usage, 'total_tokens', 0) if usage else 0
                }
            except AttributeError:
                # GPT-5 may not return usage info
                result["_metadata"] = {
                    "model": self.model,
                    "tokens_input": 0,
                    "tokens_output": 0,
                    "tokens_total": 0
                }
        else:
            result["_metadata"] = {
                "model": self.model,
                "tokens_input": response.usage.prompt_tokens,
                "tokens_output": response.usage.completion_tokens,
                "tokens_total": response.usage.total_tokens
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

        # Pricing as of Jan 2025 (per 1K tokens) - GPT-5 models only
        pricing = {
            "gpt-5-turbo": {"input": 0.003, "output": 0.012},
            "gpt-5-turbo-mini": {"input": 0.0002, "output": 0.0008},
            "gpt-5-vision-turbo": {"input": 0.006, "output": 0.024},
            "gpt-5-vision-turbo-mini": {"input": 0.0004, "output": 0.0016},
            "gpt-5": {"input": 0.003, "output": 0.012},
            "gpt-5-mini": {"input": 0.0002, "output": 0.0008},
            "gpt-5-vision": {"input": 0.006, "output": 0.024},
            "gpt-5-vision-mini": {"input": 0.0004, "output": 0.0016}
        }

        if model not in pricing:
            return 0.0

        cost_input = (tokens_input / 1000) * pricing[model]["input"]
        cost_output = (tokens_output / 1000) * pricing[model]["output"]

        return cost_input + cost_output
