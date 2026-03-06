"""
Prompt Processing Pipeline.
Coordinates language detection, translation, enhancement, and image generation.
Implements strict intent preservation rules for prompt enhancement.
"""

import time
import re
from typing import Dict, Any, Optional
from enum import Enum

from fast_langdetect import detect

from .config import settings, EnhancementLevel
from .schemas import (
    LanguageDetectionResult,
    PromptProcessingResult,
    GenerateImageRequest,
    GenerateImageResponse,
    ImageGenerationResult,
)
from .providers import get_text_provider, ProviderResponse
from .image_gateway import get_image_provider, ImageGenerationResponse
from .logger import app_logger, log_processing_step, get_request_logger


class ProcessingStage(str, Enum):
    """Stages in the processing pipeline."""

    LANGUAGE_DETECTION = "language_detection"
    TRANSLATION = "translation"
    ENHANCEMENT = "enhancement"
    IMAGE_GENERATION = "image_generation"
    COMPLETION = "completion"


def _offline_language_fallback(text: str) -> LanguageDetectionResult:
    """Offline-safe language fallback to avoid crashes in restricted environments."""
    arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    if arabic_chars > max(1, len(text) // 5):
        return LanguageDetectionResult(language="ar", confidence=0.35, language_name="Arabic")
    return LanguageDetectionResult(language="en", confidence=0.2, language_name="English")


class PromptEnhancer:
    """Handles prompt enhancement with strict intent preservation rules."""

    def __init__(self):
        self.logger = app_logger.bind(component="prompt_enhancer")
        self.enhancement_prompts = {
            EnhancementLevel.LOW: (
                "Enhance this image generation prompt by slightly improving lighting, composition, "
                "and visual clarity. Keep the core subject and artistic intent completely unchanged. "
                "Only make minimal improvements to visual quality."
            ),
            EnhancementLevel.MEDIUM: (
                "Enhance this image generation prompt by improving lighting, composition, "
                "and visual clarity while maintaining the exact same subject and artistic intent. "
                "Focus on making the image more visually appealing without adding new elements "
                "or changing the core meaning."
            ),
            EnhancementLevel.HIGH: (
                "Enhance this image generation prompt by significantly improving lighting, composition, "
                "realism, and visual clarity. Maintain the exact same subject, style, and artistic intent. "
                "Make the image more professional and visually compelling while preserving all original elements "
                "and creative vision."
            ),
        }

    async def enhance_prompt(
        self,
        prompt: str,
        level: EnhancementLevel = EnhancementLevel.MEDIUM,
        detected_language: Optional[str] = None,
    ) -> str:
        start_time = time.time()
        request_logger = get_request_logger()

        try:
            enhancement_instruction = self.enhancement_prompts.get(
                level, self.enhancement_prompts[EnhancementLevel.MEDIUM]
            )
            if detected_language:
                enhancement_instruction += f"\n\nNote: Original prompt was in {detected_language} language."

            provider = await get_text_provider()
            response: ProviderResponse = await provider.generate_text(
                prompt=prompt,
                system_prompt=settings.enhancement_system_prompt + "\n\n" + enhancement_instruction,
                max_tokens=500,
                temperature=0.4,
            )

            enhanced_prompt = response.content.strip()
            validation_result = self._validate_enhancement(prompt, enhanced_prompt)
            if not validation_result["valid"]:
                request_logger.warning(
                    "Enhancement failed validation, using original prompt",
                    extra={"validation_errors": validation_result["errors"]},
                )
                enhanced_prompt = prompt

            processing_time = time.time() - start_time
            log_processing_step(
                "prompt_enhancement",
                processing_time,
                success=True,
                enhancement_level=level.value,
                validation_passed=validation_result["valid"],
            )
            return enhanced_prompt
        except Exception as e:
            processing_time = time.time() - start_time
            log_processing_step("prompt_enhancement", processing_time, success=False, error=str(e))
            request_logger.error(f"Prompt enhancement failed: {str(e)}")
            return prompt

    def _validate_enhancement(self, original_prompt: str, enhanced_prompt: str) -> Dict[str, Any]:
        result = {"valid": True, "errors": []}
        original_words = set(re.findall(r"\b\w+\b", original_prompt.lower()))
        enhanced_words = set(re.findall(r"\b\w+\b", enhanced_prompt.lower()))

        new_words = enhanced_words - original_words
        suspicious_words = [
            "person",
            "man",
            "woman",
            "child",
            "animal",
            "car",
            "building",
            "tree",
            "flower",
            "water",
            "sky",
            "mountain",
            "ocean",
            "beach",
            "city",
            "house",
            "dog",
            "cat",
        ]
        for word in new_words:
            if word in suspicious_words and len(word) > 3:
                result["valid"] = False
                result["errors"].append(f"Potentially added new object: {word}")

        if len(enhanced_prompt) > len(original_prompt) * 2:
            result["valid"] = False
            result["errors"].append("Enhanced prompt is significantly longer than original")

        return result


class TranslationPipeline:
    """Main pipeline for translation, enhancement, and image generation."""

    def __init__(self):
        self.logger = app_logger.bind(component="translation_pipeline")
        self.prompt_enhancer = PromptEnhancer()

    async def detect_language(self, text: str) -> LanguageDetectionResult:
        start_time = time.time()
        request_logger = get_request_logger()

        try:
            detection = detect(text)
            if isinstance(detection, dict):
                language_code = detection.get("lang", "en")
                confidence = float(detection.get("score", 0.0))
            else:
                language_code = getattr(detection, "lang", "en")
                confidence = float(getattr(detection, "score", 0.0))

            language_names = {
                "en": "English",
                "es": "Spanish",
                "fr": "French",
                "de": "German",
                "it": "Italian",
                "pt": "Portuguese",
                "ru": "Russian",
                "zh": "Chinese",
                "ja": "Japanese",
                "ko": "Korean",
                "ar": "Arabic",
            }
            result = LanguageDetectionResult(
                language=language_code,
                confidence=confidence,
                language_name=language_names.get(language_code, language_code.upper()),
            )
            log_processing_step(
                "language_detection",
                time.time() - start_time,
                success=True,
                detected_language=language_code,
                confidence=confidence,
            )
            return result
        except Exception as e:
            fallback = _offline_language_fallback(text)
            log_processing_step(
                "language_detection",
                time.time() - start_time,
                success=False,
                error=str(e),
                fallback_language=fallback.language,
            )
            request_logger.warning(f"Language detection failed, using fallback: {str(e)}")
            return fallback

    async def translate_prompt(self, prompt: str, source_language: str, target_language: str = "en") -> str:
        start_time = time.time()
        request_logger = get_request_logger()

        try:
            if source_language.lower() == target_language.lower():
                return prompt

            provider = await get_text_provider()
            system_prompt = (
                f"You are a professional translator. Translate the following text from {source_language} to {target_language}. "
                "Maintain the exact same meaning, tone, and style. Do not add or remove any content. "
                "Only return the translated text, nothing else."
            )
            response: ProviderResponse = await provider.generate_text(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=1000,
                temperature=0.1,
            )
            translated_prompt = response.content.strip()
            log_processing_step("translation", time.time() - start_time, success=True)
            return translated_prompt
        except Exception as e:
            log_processing_step("translation", time.time() - start_time, success=False, error=str(e))
            request_logger.error(f"Translation failed: {str(e)}")
            return prompt

    async def process_prompt(self, request: GenerateImageRequest, request_id: str) -> PromptProcessingResult:
        language_detection = await self.detect_language(request.prompt)
        translated_prompt = await self.translate_prompt(request.prompt, language_detection.language, "en")

        enhanced_prompt = None
        enhancement_applied = False
        enhancement_level = None
        if request.enhance:
            enhancement_level = request.enhancement_level or settings.default_enhancement_level
            enhanced_prompt = await self.prompt_enhancer.enhance_prompt(
                translated_prompt,
                level=enhancement_level,
                detected_language=language_detection.language_name,
            )
            enhancement_applied = True

        return PromptProcessingResult(
            original_prompt=request.prompt,
            detected_language=language_detection,
            translated_prompt=translated_prompt,
            enhanced_prompt=enhanced_prompt if enhancement_applied else None,
            enhancement_applied=enhancement_applied,
            enhancement_level=enhancement_level if enhancement_applied else None,
        )

    async def generate_image(self, prompt: str, request: GenerateImageRequest, request_id: str) -> ImageGenerationResult:
        provider_config = {}
        if request.image_provider:
            provider_config["provider"] = request.image_provider.value
        if request.image_model:
            provider_config["model"] = request.image_model
        if request.image_size:
            provider_config["size"] = request.image_size

        provider = await get_image_provider(custom_config=provider_config)
        response: ImageGenerationResponse = await provider.generate_image(
            prompt=prompt,
            model=request.image_model,
            size=request.image_size,
        )
        return ImageGenerationResult(
            image_url=response.image_url,
            image_data=response.image_data,
            model_used=response.model,
            provider_used=response.provider,
            generation_time=response.processing_time,
        )

    async def process_request(self, request: GenerateImageRequest, request_id: str) -> GenerateImageResponse:
        total_start_time = time.time()
        request_logger = get_request_logger(request_id)

        prompt_result = await self.process_prompt(request, request_id)
        final_prompt = (
            prompt_result.enhanced_prompt
            if prompt_result.enhancement_applied and prompt_result.enhanced_prompt
            else prompt_result.translated_prompt
        )
        request_logger.info("Using prompt for image generation", extra={"enhanced": prompt_result.enhancement_applied})

        image_result = await self.generate_image(final_prompt, request, request_id)
        return GenerateImageResponse(
            request_id=request_id,
            original_prompt=prompt_result.original_prompt,
            detected_language=prompt_result.detected_language,
            translated_prompt=prompt_result.translated_prompt,
            enhanced_prompt=prompt_result.enhanced_prompt,
            enhancement_applied=prompt_result.enhancement_applied,
            enhancement_level=prompt_result.enhancement_level,
            image_result=image_result,
            providers_used={"text": settings.text_provider.value, "image": settings.image_provider.value},
            processing_time=time.time() - total_start_time,
            metadata=request.metadata,
        )


translation_pipeline = TranslationPipeline()
