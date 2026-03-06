"""
Image Generation Gateway.
Abstraction layer for image generation providers with configuration-based switching.
"""

import os
import time
from typing import Dict, Any, Optional, Literal
from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel, Field, field_validator

from .config import settings
from .logger import app_logger, log_processing_step
from .providers import ProviderType, provider_registry


class ImageProviderConfig(BaseModel):
    """Configuration for image generation providers."""

    provider: ProviderType
    api_key: str = Field(..., min_length=1)
    base_url: Optional[str] = None
    model: str
    size: Literal["256x256", "512x512", "1024x1024", "1024x1792", "1792x1024"] = "1024x1024"
    timeout: float = Field(default=60.0, ge=1.0, le=300.0)
    quality: Literal["standard", "hd"] = "standard"
    style: Optional[Literal["vivid", "natural"]] = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://")
        return v


class ImageGenerationResponse(BaseModel):
    """Standardized response from image generation providers."""

    image_url: str
    image_data: Optional[str] = None
    provider: str
    model: str
    size: str
    usage: Dict[str, Any] = Field(default_factory=dict)
    processing_time: float


class BaseImageProvider(ABC):
    """Abstract base class for image generation providers."""

    def __init__(self, config: ImageProviderConfig):
        self.config = config
        self.logger = app_logger.bind(provider=config.provider.value)
        self.client = httpx.AsyncClient(timeout=config.timeout, follow_redirects=True)

    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        model: Optional[str] = None,
        size: Optional[str] = None,
        **kwargs,
    ) -> ImageGenerationResponse:
        pass

    async def close(self):
        await self.client.aclose()


class OpenAIImageProvider(BaseImageProvider):
    """OpenAI DALL-E image generation provider."""

    async def generate_image(
        self,
        prompt: str,
        model: Optional[str] = None,
        size: Optional[str] = None,
        **kwargs,
    ) -> ImageGenerationResponse:
        start_time = time.time()

        payload = {
            "model": model or self.config.model,
            "prompt": prompt,
            "n": 1,
            "size": size or self.config.size,
            "response_format": "url",
            "quality": kwargs.get("quality", self.config.quality),
        }

        if self.config.style and (model or self.config.model) == "dall-e-3":
            payload["style"] = self.config.style

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        if settings.app_env == "production":
            org = os.getenv("OPENAI_ORGANIZATION")
            if org:
                headers["OpenAI-Organization"] = org

        base_url = self.config.base_url or "https://api.openai.com/v1"
        url = f"{base_url}/images/generations"

        try:
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            image_data = response_data["data"][0]
            image_url = image_data.get("url")
            b64_json = image_data.get("b64_json")
            processing_time = time.time() - start_time

            log_processing_step(
                "openai_image_generate",
                processing_time,
                success=True,
                model=model or self.config.model,
                size=size or self.config.size,
            )

            return ImageGenerationResponse(
                image_url=image_url,
                image_data=b64_json,
                provider=self.config.provider.value,
                model=model or self.config.model,
                size=size or self.config.size,
                usage={"prompt_tokens": len(prompt.split())},
                processing_time=processing_time,
            )
        except Exception as e:
            processing_time = time.time() - start_time
            log_processing_step("openai_image_generate", processing_time, success=False, error=str(e))
            self.logger.error(f"OpenAI image generation failed: {str(e)}")
            raise


class ImageProviderFactory:
    """Factory class for creating image generation providers."""

    @staticmethod
    def create_provider(config: ImageProviderConfig) -> BaseImageProvider:
        provider_map = {ProviderType.OPENAI: OpenAIImageProvider}
        provider_class = provider_map.get(config.provider)
        if not provider_class:
            raise ValueError(f"Unsupported image provider type: {config.provider}")
        return provider_class(config)


async def get_image_provider(
    provider_type: Optional[ProviderType] = None,
    custom_config: Optional[Dict[str, Any]] = None,
) -> BaseImageProvider:
    provider_config = settings.get_provider_config("image")

    if provider_type:
        provider_config["provider"] = provider_type.value
    if custom_config:
        provider_config.update(custom_config)

    config = ImageProviderConfig(**provider_config)
    provider = ImageProviderFactory.create_provider(config)
    await provider_registry.register(provider)
    return provider
