"""
Google Gemini Provider implementation via REST API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini API Provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-1.5-pro",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        **kwargs,
    ):
        super().__init__(
            name="gemini",
            model=model,
            api_key=api_key,
            base_url=base_url,
            cost_per_million_input=1.25,
            cost_per_million_output=5.00,
            **kwargs,
        )

    def _sync_request(self, payload: Dict[str, Any]) -> str:
        model_name = self.model
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"

        url = f"{self.base_url.rstrip('/')}/{model_name}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))

        usage = result.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", self.estimate_tokens(str(payload)))
        completion_tokens = usage.get("candidatesTokenCount", 0)

        candidates = result.get("candidates", [])
        if not candidates:
            return ""

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)

        if not completion_tokens:
            completion_tokens = self.estimate_tokens(text)

        self.record_usage(prompt_tokens, completion_tokens)
        return text

    async def generate(self, prompt: str, context: str = "") -> str:
        contents = []
        if context:
            contents.append({"role": "user", "parts": [{"text": f"System Context:\n{context}"}]})
            contents.append({"role": "model", "parts": [{"text": "Acknowledged."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
            },
        }

        try:
            return await asyncio.to_thread(self._sync_request, payload)
        except Exception as e:
            logger.error(f"Gemini generate failed: {e}")
            raise RuntimeError(f"Gemini error ({self.model}): {e}") from e
