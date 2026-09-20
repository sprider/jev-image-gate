"""Preflight, then optionally one image call. Code owns the spend gate."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from image_gen_controller.decisions import SPEND_ACTIONS
from image_gen_controller.image_backend import ImageBackend, ImageResult
from image_gen_controller.jev_gateway import JevGateway
from image_gen_controller.preflight import PreflightResult, run_preflight

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GenerateResult:
    preflight: PreflightResult
    image: ImageResult | None
    image_skip_reason: str | None = None


def select_model(action: str, *, lite_model: str, premium_model: str) -> str:
    if action == "allow_premium":
        return premium_model
    return lite_model


def run_generate(
    prompt: str,
    gateway: JevGateway,
    backend: ImageBackend | None,
    *,
    remaining_usd: float = 0.05,
    jev_model: str = "jev-1.13.0",
    lite_model: str = "gemini-3.1-flash-lite-image",
    premium_model: str = "gemini-3-pro-image-preview",
) -> GenerateResult:
    preflight = run_preflight(
        prompt,
        gateway,
        remaining_usd=remaining_usd,
        jev_model=jev_model,
    )
    decision = preflight.decision

    if decision.action not in SPEND_ACTIONS or not decision.will_spend:
        logger.info(
            "Skipping image API action=%s reason=%s",
            decision.action,
            decision.reason,
        )
        return GenerateResult(preflight=preflight, image=None, image_skip_reason="not_authorized")

    if backend is None:
        logger.warning("Spend authorized but no image backend is configured")
        return GenerateResult(
            preflight=preflight,
            image=None,
            image_skip_reason="image_backend_unavailable",
        )

    model = select_model(
        decision.action,
        lite_model=lite_model,
        premium_model=premium_model,
    )
    try:
        image = backend.generate(preflight.state["prompt"], model)
    except Exception:
        logger.exception("Image model failed model=%s; returning decision only", model)
        return GenerateResult(
            preflight=preflight,
            image=None,
            image_skip_reason="image_generation_failed",
        )

    return GenerateResult(preflight=preflight, image=image, image_skip_reason=None)
