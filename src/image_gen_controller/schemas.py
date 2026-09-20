"""HTTP request and response bodies."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Action = Literal["block", "ask_clarify", "allow_lite", "allow_premium"]


class PreflightRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    remaining_usd: float | None = Field(default=None, ge=0.0, le=10.0)


class SignalPayload(BaseModel):
    policy_violation: float
    specificity_score: float
    specificity_confidence: float
    recommended_action: str
    action_confidence: float
    available: bool


class PreflightResponse(BaseModel):
    action: Action
    will_spend: bool
    reason: str
    message: str
    policy_id: str
    question_version: str
    jev_model: str
    prompt_preview: str
    signals: SignalPayload


class ImagePayload(BaseModel):
    generated: bool
    model: str | None = None
    mime_type: str | None = None
    base64_data: str | None = None
    est_cost_usd: float | None = None
    skip_reason: str | None = None


class GenerateResponse(PreflightResponse):
    image: ImagePayload


class ErrorResponse(BaseModel):
    code: str
    message: str
