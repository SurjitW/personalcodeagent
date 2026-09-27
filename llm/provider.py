"""
Multi-LLM Provider Abstraction Layer
Defines the base interface for LLM integrations, tracking usage, costs, and context.
"""

from __future__ import annotations

import abc
import asyncio
from dataclasses import dataclass, field
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Usage metrics for LLM calls."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    def add(self, prompt: int, completion: int, cost: float = 0.0) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += (prompt + completion)
        self.estimated_cost_usd += cost


class LLMProvider(abc.ABC):
    """
    Abstract Base Class for all LLM model providers.
    Every provider implements generate(prompt, context) and tracks tokens and cost.
    """

    def __init__(
        self,
        name: str,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        cost_per_million_input: float = 0.50,
        cost_per_million_output: float = 1.50,
    ):
        self.name = name
        self.model = model
        self.api_key = api_key or os.environ.get(f"{name.upper()}_API_KEY", "")
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.cost_per_million_input = cost_per_million_input
        self.cost_per_million_output = cost_per_million_output
        self.usage = TokenUsage()
        self.call_history: List[Dict[str, Any]] = []

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        input_cost = (prompt_tokens / 1_000_000.0) * self.cost_per_million_input
        output_cost = (completion_tokens / 1_000_000.0) * self.cost_per_million_output
        return round(input_cost + output_cost, 6)

    def estimate_tokens(self, text: str) -> int:
        """Heuristic token estimation: ~4 chars per token."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def record_usage(self, prompt_tokens: int, completion_tokens: int) -> float:
        cost = self.calculate_cost(prompt_tokens, completion_tokens)
        self.usage.add(prompt_tokens, completion_tokens, cost)
        return cost

    @abc.abstractmethod
    async def generate(self, prompt: str, context: str = "") -> str:
        """
        Generate completion for a given prompt and context.
        Must be implemented by concrete providers.
        """
        raise NotImplementedError

    def get_stats(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "model": self.model,
            "prompt_tokens": self.usage.prompt_tokens,
            "completion_tokens": self.usage.completion_tokens,
            "total_tokens": self.usage.total_tokens,
            "estimated_cost_usd": self.usage.estimated_cost_usd,
            "total_calls": len(self.call_history),
        }
