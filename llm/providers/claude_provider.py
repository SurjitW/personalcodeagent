"""
Claude (Anthropic) Provider implementation.
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


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API Provider (Claude 3.5 Sonnet, Haiku, etc.)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        base_url: str = "https://api.anthropic.com/v1",
        **kwargs,
    ):
        super().__init__(
            name="claude",
            model=model,
            api_key=api_key,
            base_url=base_url,
            cost_per_million_input=3.00,
            cost_per_million_output=15.00,
            **kwargs,
        )

    def _sync_request(self, payload: Dict[str, Any]) -> str:
        url = f"{self.base_url.rstrip('/')}/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))

        usage = result.get("usage", {})
        prompt_tokens = usage.get("input_tokens", self.estimate_tokens(str(payload)))
        completion_tokens = usage.get("output_tokens", 0)

        content_list = result.get("content", [])
        text_parts = [c.get("text", "") for c in content_list if c.get("type") == "text"]
        full_text = "\n".join(text_parts)

        if not completion_tokens:
            completion_tokens = self.estimate_tokens(full_text)

        self.record_usage(prompt_tokens, completion_tokens)
        return full_text

    async def generate(self, prompt: str, context: str = "") -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if context:
            payload["system"] = context

        try:
            return await asyncio.to_thread(self._sync_request, payload)
        except Exception as e:
            logger.error(f"Claude generate failed: {e}")
            raise RuntimeError(f"Claude error ({self.model}): {e}") from e
