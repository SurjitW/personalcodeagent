"""
OpenRouter Provider implementation with access to diverse frontier & open models.
"""

from __future__ import annotations

import os
from typing import Optional
from llm.providers.openai_provider import OpenAIProvider


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter API Provider."""

    DEFAULT_FREE_MODEL = "qwen/qwen-2.5-coder-32b-instruct:free"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        **kwargs,
    ):
        chosen_model = model or self.DEFAULT_FREE_MODEL
        super().__init__(
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY"),
            model=chosen_model,
            base_url=base_url,
            cost_per_million_input=0.0 if ":free" in chosen_model else 0.50,
            cost_per_million_output=0.0 if ":free" in chosen_model else 1.50,
            **kwargs,
        )
        self.name = "openrouter"


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek API Provider (deepseek-chat, deepseek-reasoner)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "deepseek-coder",
        base_url: str = "https://api.deepseek.com",
        **kwargs,
    ):
        super().__init__(
            api_key=api_key or os.environ.get("DEEPSEEK_API_KEY"),
            model=model,
            base_url=base_url,
            cost_per_million_input=0.14,
            cost_per_million_output=0.28,
            **kwargs,
        )
        self.name = "deepseek"


class QwenProvider(OpenAIProvider):
    """Qwen / DashScope Provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen2.5-coder-32b-instruct",
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        **kwargs,
    ):
        super().__init__(
            api_key=api_key or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY"),
            model=model,
            base_url=base_url,
            cost_per_million_input=0.20,
            cost_per_million_output=0.60,
            **kwargs,
        )
        self.name = "qwen"


class KimiProvider(OpenAIProvider):
    """Moonshot AI / Kimi Provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "moonshot-v1-32k",
        base_url: str = "https://api.moonshot.cn/v1",
        **kwargs,
    ):
        super().__init__(
            api_key=api_key or os.environ.get("MOONSHOT_API_KEY") or os.environ.get("KIMI_API_KEY"),
            model=model,
            base_url=base_url,
            cost_per_million_input=0.60,
            cost_per_million_output=1.20,
            **kwargs,
        )
        self.name = "kimi"
