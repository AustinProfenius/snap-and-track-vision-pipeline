"""
Ollama LLaVA adapter for local nutrition estimation.
"""
import os
import base64
from pathlib import Path
from typing import Dict, Any, Optional
import aiohttp

from ..core.prompts import SYSTEM_MESSAGE, parse_json_response


class OllamaAdapter:
    """Adapter for Ollama local vision models (e.g., LLaVA)."""

    def __init__(self, model: str = "llava", temperature: float = 0.0, max_tokens: int = 2048):
        """
        Initialize Ollama adapter.

        Args:
            model: Model name (llava, bakllava, etc.)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
        """
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
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

        # Build prompt with system message
        system_message = kwargs.get("system_message", SYSTEM_MESSAGE)
        full_prompt = f"{system_message}\n\n{prompt}"

        # Ollama API payload
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "images": [image_data],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens
            }
        }

        # Call API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300)  # 5 min timeout
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Ollama API error: {response.status} - {error_text}")

                data = await response.json()

        # Extract response
        content = data.get("response", "")

        # Parse JSON
        result = parse_json_response(content)

        # Attach metadata
        result["_metadata"] = {
            "model": self.model,
            "tokens_input": None,  # Ollama doesn't always provide this
            "tokens_output": None,
            "tokens_total": None
        }

        return result

    def estimate_cost(self, tokens_input: int, tokens_output: int, model: Optional[str] = None) -> float:
        """
        Estimate cost for token usage (always 0 for local models).

        Args:
            tokens_input: Input tokens
            tokens_output: Output tokens
            model: Model name (unused)

        Returns:
            0.0 (local models are free)
        """
        return 0.0
