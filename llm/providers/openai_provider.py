"""
OpenAI Provider implementation supporting chat completions API.
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


class OpenAIProvider(LLMProvider):
    """OpenAI API Provider (GPT-4o, GPT-4, etc.)"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
        **kwargs,
    ):
        super().__init__(
            name="openai",
            model=model,
            api_key=api_key,
            base_url=base_url,
            cost_per_million_input=kwargs.pop("cost_per_million_input", 2.50),
            cost_per_million_output=kwargs.pop("cost_per_million_output", 10.00),
            **kwargs,
        )

    def _sync_request(self, payload: Dict[str, Any]) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))

        usage = result.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        if not prompt_tokens:
            prompt_tokens = self.estimate_tokens(str(payload))
        if not completion_tokens:
            resp_text = result["choices"][0]["message"].get("content", "")
            completion_tokens = self.estimate_tokens(resp_text)

        self.record_usage(prompt_tokens, completion_tokens)
        return result["choices"][0]["message"].get("content", "")

    async def generate(self, prompt: str, context: str = "") -> str:
        messages = []
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        try:
            return await asyncio.to_thread(self._sync_request, payload)
        except Exception as e:
            logger.error(f"OpenAI generate failed: {e}")
            raise RuntimeError(f"OpenAI error ({self.model}): {e}") from e
