"""
Multi-LLM Router with fallback chain, retry policy, and usage/cost aggregation.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from llm.provider import LLMProvider
from llm.providers import (
    ClaudeProvider,
    DeepSeekProvider,
    GeminiProvider,
    KimiProvider,
    MockProvider,
    OpenAIProvider,
    OpenRouterProvider,
    QwenProvider,
)

logger = logging.getLogger(__name__)


class LLMRouter:
    """
    Intelligent Router coordinating LLM providers with automatic fallback chains,
    cost/token tracking aggregation, and provider switching.
    """

    def __init__(
        self,
        primary_name: str = "mock",
        fallback_names: Optional[List[str]] = None,
        providers: Optional[Dict[str, LLMProvider]] = None,
        temperature: float = 0.2,
        max_retries: int = 2,
    ):
        self.temperature = temperature
        self.max_retries = max_retries
        self.providers: Dict[str, LLMProvider] = providers or {}
        self.primary_name = primary_name
        self.fallback_names = fallback_names or []
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        """Register default providers if not already configured."""
        if "mock" not in self.providers:
            self.providers["mock"] = MockProvider()
        if "openai" not in self.providers:
            self.providers["openai"] = OpenAIProvider(temperature=self.temperature)
        if "claude" not in self.providers:
            self.providers["claude"] = ClaudeProvider(temperature=self.temperature)
        if "gemini" not in self.providers:
            self.providers["gemini"] = GeminiProvider(temperature=self.temperature)
        if "openrouter" not in self.providers:
            self.providers["openrouter"] = OpenRouterProvider(temperature=self.temperature)
        if "deepseek" not in self.providers:
            self.providers["deepseek"] = DeepSeekProvider(temperature=self.temperature)
        if "qwen" not in self.providers:
            self.providers["qwen"] = QwenProvider(temperature=self.temperature)
        if "kimi" not in self.providers:
            self.providers["kimi"] = KimiProvider(temperature=self.temperature)

    def register_provider(self, name: str, provider: LLMProvider) -> None:
        self.providers[name] = provider

    def get_provider(self, name: str) -> Optional[LLMProvider]:
        return self.providers.get(name)

    async def generate(
        self,
        prompt: str,
        context: str = "",
        preferred_provider: Optional[str] = None,
    ) -> str:
        """
        Attempt generation using preferred or primary provider, cascading to fallback providers on failure.
        """
        chain = []
        if preferred_provider and preferred_provider in self.providers:
            chain.append(preferred_provider)
        if self.primary_name in self.providers and self.primary_name not in chain:
            chain.append(self.primary_name)
        for fb in self.fallback_names:
            if fb in self.providers and fb not in chain:
                chain.append(fb)
        # Always allow mock fallback as safety net if nothing else succeeds
        if "mock" in self.providers and "mock" not in chain:
            chain.append("mock")

        last_error = None
        for prov_name in chain:
            prov = self.providers[prov_name]
            for attempt in range(self.max_retries + 1):
                try:
                    logger.info(f"Attempting generation with provider '{prov_name}' (model: {prov.model})")
                    return await prov.generate(prompt, context)
                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"Provider '{prov_name}' failed attempt {attempt + 1}/{self.max_retries + 1}: {e}"
                    )
                    await asyncio.sleep(0.5 * (attempt + 1))

        # If all fail, raise the last encountered error or a clear runtime error
        raise RuntimeError(f"All LLM providers in chain {chain} failed. Last error: {last_error}")

    def get_aggregated_stats(self) -> Dict[str, Any]:
        """Aggregate token and cost metrics across all active providers."""
        total_prompt = 0
        total_completion = 0
        total_tokens = 0
        total_cost = 0.0
        provider_breakdown = {}

        for name, prov in self.providers.items():
            stats = prov.get_stats()
            total_prompt += stats["prompt_tokens"]
            total_completion += stats["completion_tokens"]
            total_tokens += stats["total_tokens"]
            total_cost += stats["estimated_cost_usd"]
            if stats["total_calls"] > 0:
                provider_breakdown[name] = stats

        return {
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_tokens,
            "total_estimated_cost_usd": round(total_cost, 6),
            "providers": provider_breakdown,
        }
