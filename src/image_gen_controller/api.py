"""HTTP API. Jev is never exposed as a chatbot - only typed decisions."""

from __future__ import annotations

import base64
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from image_gen_controller.config import Settings, get_settings
from image_gen_controller.errors import ControllerError, InvalidPromptError
from image_gen_controller.generate import run_generate
from image_gen_controller.image_backend import GeminiImageBackend
from image_gen_controller.jev_gateway import JevGateway, TypeSafeJevGateway
from image_gen_controller.logging_config import configure_logging, get_logger
from image_gen_controller.preflight import PreflightResult, run_preflight
from image_gen_controller.schemas import (
    ErrorResponse,
    GenerateResponse,
    ImagePayload,
    PreflightRequest,
    PreflightResponse,
    SignalPayload,
)

logger = get_logger(__name__)

MESSAGES = {
    "jev_action": "Jev recommended this action and the guardrails agreed.",
    "policy_violation": "Blocked: the prompt conflicts with the product-still policy. No image API call.",
    "prompt_too_vague": "Need a clearer product, setting, and constraints before spending.",
    "low_confidence": "Jev was not confident enough to authorize spend.",
    "low_confidence_degraded": "Premium spend was refused because confidence was too low. Lite is allowed.",
    "decision_service_unavailable": "Decision service is unavailable. Refusing to spend.",
    "invalid_jev_action": "Decision service returned an unknown action. Refusing to spend.",
}

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(
    settings: Settings | None = None,
    gateway: JevGateway | None = None,
    image_backend=None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    gateway = gateway or TypeSafeJevGateway(settings)

    app = FastAPI(
        title="Jev Image Gate",
        description=(
            "Jev decides whether an image-generation workflow should spend "
            "and which Gemini tier to use. Code calls the image API only "
            "after that decision."
        ),
        version="0.1.0",
    )
    app.state.settings = settings
    app.state.gateway = gateway
    if image_backend is None and settings.gemini_api_key:
        image_backend = GeminiImageBackend(settings)
    app.state.image_backend = image_backend

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled error path=%s",
                request.url.path,
                extra={"request_id": request_id},
            )
            return JSONResponse(
                status_code=500,
                content={
                    "code": "internal_error",
                    "message": "Unexpected server error.",
                },
                headers={"x-request-id": request_id},
            )
        response.headers["x-request-id"] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        logger.warning(
            "Invalid request path=%s errors=%s",
            request.url.path,
            exc.errors(),
            extra={"request_id": getattr(request.state, "request_id", "-")},
        )
        return JSONResponse(
            status_code=400,
            content={
                "code": "invalid_request",
                "message": "Request body is invalid. Send JSON with a non-empty prompt.",
            },
        )

    @app.exception_handler(ControllerError)
    async def controller_error_handler(request: Request, exc: ControllerError):
        status = 400 if isinstance(exc, InvalidPromptError) else 503
        logger.warning(
            "Controller error code=%s message=%s",
            exc.code,
            exc.message,
            extra={"request_id": getattr(request.state, "request_id", "-")},
        )
        return JSONResponse(
            status_code=status,
            content=ErrorResponse(code=exc.code, message=exc.message).model_dump(),
        )

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "service": "jev-image-gate"}

    @app.post("/v1/preflight", response_model=PreflightResponse)
    def preflight(body: PreflightRequest, request: Request):
        remaining = (
            body.remaining_usd
            if body.remaining_usd is not None
            else request.app.state.settings.remaining_budget_usd
        )
        result = run_preflight(
            body.prompt,
            request.app.state.gateway,
            remaining_usd=remaining,
            jev_model=request.app.state.settings.jev_model,
        )
        return _preflight_body(result)

    @app.post("/v1/generate", response_model=GenerateResponse)
    def generate(body: PreflightRequest, request: Request):
        settings = request.app.state.settings
        remaining = (
            body.remaining_usd
            if body.remaining_usd is not None
            else settings.remaining_budget_usd
        )
        result = run_generate(
            body.prompt,
            request.app.state.gateway,
            request.app.state.image_backend,
            remaining_usd=remaining,
            jev_model=settings.jev_model,
            lite_model=settings.gemini_image_model_lite,
            premium_model=settings.gemini_image_model_premium,
        )
        preflight = _preflight_body(result.preflight)
        if result.image is None:
            image = ImagePayload(
                generated=False,
                skip_reason=result.image_skip_reason,
            )
        else:
            image = ImagePayload(
                generated=True,
                model=result.image.model,
                mime_type=result.image.mime_type,
                base64_data=base64.b64encode(result.image.image_bytes).decode("ascii"),
                est_cost_usd=result.image.est_cost_usd,
            )
        return GenerateResponse(**preflight.model_dump(), image=image)

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

        @app.get("/", response_class=HTMLResponse)
        def playground():
            return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    return app


def _preflight_body(result: PreflightResult) -> PreflightResponse:
    return PreflightResponse(
        action=result.decision.action,
        will_spend=result.decision.will_spend,
        reason=result.decision.reason,
        message=MESSAGES.get(result.decision.reason, result.decision.reason),
        policy_id=result.policy_id,
        question_version=result.question_version,
        jev_model=result.jev_model,
        prompt_preview=result.prompt_preview,
        signals=SignalPayload(
            policy_violation=result.signals.policy_violation,
            specificity_score=result.signals.specificity_score,
            specificity_confidence=result.signals.specificity_confidence,
            recommended_action=result.signals.recommended_action,
            action_confidence=result.signals.action_confidence,
            available=result.signals.available,
        ),
    )
