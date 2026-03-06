"""
LLM Provider Abstraction Layer.
Defines interfaces and implementations for text LLM providers with configuration-based switching.
"""

import os
import time
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum

import httpx
from pydantic import BaseModel, Field, field_validator

from .config import settings
from .logger import app_logger, log_processing_step


class ProviderType(str, Enum):
    """Supported provider types."""

    OPENAI = "openai"
    QWEN = "qwen"
    DEEPSEEK = "deepseek"
    CUSTOM = "custom"


class ProviderConfig(BaseModel):
    """Configuration for an LLM provider."""

    provider: ProviderType = Field(..., description="Provider type")
    api_key: str = Field(..., description="API key", min_length=1)
    base_url: Optional[str] = Field(default=None, description="Custom base URL")
    model: str = Field(..., description="Model name to use")
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    timeout: float = Field(default=30.0, ge=1.0, le=300.0)
    max_tokens: int = Field(default=1000, ge=1, le=4096)
    system_prompt: Optional[str] = Field(default=None)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://")
        return v


class ProviderResponse(BaseModel):
    """Standardized response from LLM providers."""

    content: str
    provider: str
    model: str
    usage: Dict[str, Any] = Field(default_factory=dict)
    processing_time: float


class ProviderRegistry:
    """Keeps track of provider instances for graceful shutdown."""

    def __init__(self):
        self._providers = set()
        self._lock = asyncio.Lock()

    async def register(self, provider: Any):
        async with self._lock:
            self._providers.add(provider)

    async def close_all(self):
        async with self._lock:
            providers = list(self._providers)
            self._providers.clear()

        if not providers:
            return

        await asyncio.gather(*(p.close() for p in providers), return_exceptions=True)


provider_registry = ProviderRegistry()


class BaseTextProvider(ABC):
    """Abstract base class for text LLM providers."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.logger = app_logger.bind(provider=config.provider.value)
        self.client = httpx.AsyncClient(timeout=config.timeout, follow_redirects=True)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(provider_registry.register(self))
        except RuntimeError:
            pass

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> ProviderResponse:
        pass

    async def close(self):
        await self.client.aclose()

    def _get_temperature(self, override: Optional[float] = None) -> float:
        return override if override is not None else self.config.temperature

    def _get_max_tokens(self, override: Optional[int] = None) -> int:
        return override if override is not None else self.config.max_tokens

    def _get_system_prompt(self, override: Optional[str] = None) -> str:
        return override if override is not None else (self.config.system_prompt or "")


class OpenAIProvider(BaseTextProvider):
    """OpenAI-compatible provider implementation."""

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> ProviderResponse:
        start_time = time.time()

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": self._get_system_prompt(system_prompt)},
                {"role": "user", "content": prompt},
            ],
            "temperature": self._get_temperature(temperature),
            "max_tokens": self._get_max_tokens(max_tokens),
            "response_format": {"type": "text"},
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        if self.config.provider == ProviderType.OPENAI:
            org = os.getenv("OPENAI_ORGANIZATION")
            if org:
                headers["OpenAI-Organization"] = org

        base_url = self.config.base_url or "https://api.openai.com/v1"
        url = f"{base_url}/chat/completions"

        try:
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            content = response_data["choices"][0]["message"]["content"].strip()
            usage = response_data.get("usage", {})
            processing_time = time.time() - start_time

            log_processing_step(
                "openai_generate",
                processing_time,
                success=True,
                model=self.config.model,
                tokens_used=usage.get("total_tokens", 0),
            )

            return ProviderResponse(
                content=content,
                provider=self.config.provider.value,
                model=self.config.model,
                usage=usage,
                processing_time=processing_time,
            )
        except Exception as e:
            processing_time = time.time() - start_time
            log_processing_step("openai_generate", processing_time, success=False, error=str(e))
            self.logger.error(f"OpenAI request failed: {str(e)}")
            raise


class TextProviderFactory:
    """Factory class for creating text LLM providers."""

    @staticmethod
    def create_provider(config: ProviderConfig) -> BaseTextProvider:
        provider_map = {
            ProviderType.OPENAI: OpenAIProvider,
            ProviderType.QWEN: OpenAIProvider,
            ProviderType.DEEPSEEK: OpenAIProvider,
            ProviderType.CUSTOM: OpenAIProvider,
        }
        provider_class = provider_map.get(config.provider)
        if not provider_class:
            raise ValueError(f"Unsupported provider type: {config.provider}")
        return provider_class(config)


async def get_text_provider(
    provider_type: Optional[ProviderType] = None,
    custom_config: Optional[Dict[str, Any]] = None,
) -> BaseTextProvider:
    provider_config = settings.get_provider_config("text")

    if provider_type:
        provider_config["provider"] = provider_type.value
    if custom_config:
        provider_config.update(custom_config)

    config = ProviderConfig(**provider_config)
    provider = TextProviderFactory.create_provider(config)
    await provider_registry.register(provider)
    return provider


async def close_all_providers():
    """Close all tracked provider client connections."""
    await provider_registry.close_all()
