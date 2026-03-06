"""
TRANSLai - Multilingual Prompt Translation & Enhancement Middleware.
FastAPI application entry point with comprehensive error handling and observability.
"""

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .logger import app_logger, RequestIDMiddleware, get_request_logger, setup_exception_logging
from .schemas import GenerateImageRequest, GenerateImageResponse, ErrorResponse
from .pipeline import translation_pipeline
from .providers import close_all_providers
from .auth import require_api_key
from .rate_limit import RateLimitMiddleware, rate_limiter

setup_exception_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    app_logger.info("🚀 TRANSLai application starting up...")
    app_logger.info(f"Environment: {settings.app_env}")
    app_logger.info(f"Version: {settings.app_version}")
    app_logger.info(f"Auth enabled: {settings.auth_enabled}")

    yield

    app_logger.info("🛑 TRANSLai application shutting down...")
    await close_all_providers()
    await rate_limiter.close()
    app_logger.info("🔌 All provider and rate-limiter connections closed")


app = FastAPI(
    title="TRANSLai",
    description="Multilingual Prompt Translation & Enhancement Middleware for Image Generation Models",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
    openapi_url="/api/openapi.json" if settings.debug else None,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(RateLimitMiddleware)

if settings.app_env == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.app_env,
        "version": settings.app_version,
        "timestamp": time.time(),
    }


@app.get("/api/config")
async def get_config(_: str = Depends(require_api_key)):
    """Get application configuration (protected)."""
    return {
        "text_provider": settings.text_provider,
        "image_provider": settings.image_provider,
        "enhancement_enabled": True,
        "max_prompt_length": settings.max_prompt_length,
        "environment": settings.app_env,
        "version": settings.app_version,
    }


@app.post("/api/v1/generate", response_model=GenerateImageResponse)
async def generate_image(
    request: GenerateImageRequest,
    req: Request,
    _: str = Depends(require_api_key),
):
    """Generate image from multilingual prompt."""
    request_id = req.headers.get("X-Request-ID", str(uuid.uuid4()))
    request_logger = get_request_logger(request_id)

    if len(request.prompt) > settings.max_prompt_length:
        error_response = ErrorResponse(
            error=f"Prompt exceeds maximum length of {settings.max_prompt_length} characters",
            code="INVALID_PROMPT_LENGTH",
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_response.model_dump(mode="json"))

    request_logger.info(
        "Processing image generation request",
        extra={
            "prompt_preview": request.prompt[:100] + "..." if len(request.prompt) > 100 else request.prompt,
            "enhance": request.enhance,
        },
    )

    try:
        return await translation_pipeline.process_request(request, request_id)
    except HTTPException:
        raise
    except Exception as e:
        request_logger.error("Unexpected error during image generation", extra={"error": str(e)})
        error_response = ErrorResponse(
            error="Failed to generate image",
            code="IMAGE_GENERATION_FAILED",
            details={"message": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response.model_dump(mode="json"),
        )


@app.get("/api/v1/user")
async def get_user_profile(_: str = Depends(require_api_key)):
    """Protected user placeholder endpoint."""
    return {"message": "User endpoint is protected and available", "version": settings.app_version}


@app.get("/api/v1/memory")
async def get_memory_state(_: str = Depends(require_api_key)):
    """Protected memory placeholder endpoint."""
    return {"message": "Memory endpoint is protected and available", "version": settings.app_version}


@app.get("/api/v1/providers/text")
async def get_text_providers(_: str = Depends(require_api_key)):
    """Get available text LLM providers."""
    return {
        "providers": [
            {"name": "OpenAI", "value": "openai"},
            {"name": "Qwen", "value": "qwen"},
            {"name": "DeepSeek", "value": "deepseek"},
            {"name": "Custom", "value": "custom"},
        ]
    }


@app.get("/api/v1/providers/image")
async def get_image_providers(_: str = Depends(require_api_key)):
    """Get available image generation providers."""
    return {
        "providers": [
            {"name": "OpenAI DALL-E", "value": "openai"},
            {"name": "Stability AI", "value": "stability"},
            {"name": "Custom", "value": "custom"},
        ]
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with standardized response."""
    request_logger = get_request_logger(request.headers.get("X-Request-ID"))

    error_response = ErrorResponse(
        error=exc.detail.get("error", "Unknown error") if isinstance(exc.detail, dict) else str(exc.detail),
        code=exc.detail.get("code", "UNKNOWN_ERROR") if isinstance(exc.detail, dict) else "HTTP_ERROR",
        details=exc.detail.get("details", {}) if isinstance(exc.detail, dict) else {"status_code": exc.status_code},
    )

    request_logger.warning(
        "HTTP exception occurred",
        extra={"status_code": exc.status_code, "error": error_response.error, "code": error_response.code},
    )
    return JSONResponse(status_code=exc.status_code, content=error_response.model_dump(mode="json"))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions globally."""
    request_logger = get_request_logger(request.headers.get("X-Request-ID"))

    error_response = ErrorResponse(
        error="Internal server error",
        code="INTERNAL_ERROR",
        details={"message": str(exc), "type": type(exc).__name__},
    )

    request_logger.critical(
        "Unhandled exception occurred",
        extra={"error": str(exc), "error_type": type(exc).__name__, "path": request.url.path},
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=error_response.model_dump(mode="json"))


if __name__ == "__main__":
    import uvicorn

    app_logger.info("Starting TRANSLai server...")
    uvicorn.run(
        "translai.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        workers=4 if not settings.debug else 1,
        log_level=settings.log_level.lower(),
        access_log=False,
    )
