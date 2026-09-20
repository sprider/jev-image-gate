"""Run one preflight: validate prompt, ask Jev, apply spend policy."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from image_gen_controller.decisions import JevSignals, PreflightDecision, decide_preflight
from image_gen_controller.errors import InvalidPromptError
from image_gen_controller.jev_gateway import JevGateway
from image_gen_controller.policy import DEFAULT_BUDGET_USD, POLICY_ID, build_state
from image_gen_controller.questions import QUESTION_VERSION

logger = logging.getLogger(__name__)

PROMPT_MAX_CHARS = 2000


@dataclass(frozen=True)
class PreflightResult:
    prompt_preview: str
    decision: PreflightDecision
    signals: JevSignals
    state: dict
    policy_id: str
    question_version: str
    jev_model: str


def run_preflight(
    prompt: str,
    gateway: JevGateway,
    *,
    remaining_usd: float = DEFAULT_BUDGET_USD,
    jev_model: str = "jev-1.13.0",
) -> PreflightResult:
    cleaned = _require_prompt(prompt)
    state = build_state(cleaned, remaining_usd=remaining_usd)

    logger.info(
        "Preflight start policy=%s questions=%s prompt_chars=%s",
        POLICY_ID,
        QUESTION_VERSION,
        len(cleaned),
    )

    signals = gateway.evaluate(state)
    decision = decide_preflight(signals)

    logger.info(
        "Preflight result action=%s will_spend=%s reason=%s jev_available=%s",
        decision.action,
        decision.will_spend,
        decision.reason,
        signals.available,
    )

    return PreflightResult(
        prompt_preview=_preview(cleaned),
        decision=decision,
        signals=signals,
        state=state,
        policy_id=POLICY_ID,
        question_version=QUESTION_VERSION,
        jev_model=jev_model,
    )


def _require_prompt(prompt: str) -> str:
    if prompt is None:
        raise InvalidPromptError()
    cleaned = " ".join(str(prompt).split())
    if not cleaned:
        raise InvalidPromptError()
    if len(cleaned) > PROMPT_MAX_CHARS:
        raise InvalidPromptError(
            f"Prompt exceeds {PROMPT_MAX_CHARS} characters."
        )
    return cleaned


def _preview(prompt: str, limit: int = 120) -> str:
    if len(prompt) <= limit:
        return prompt
    return prompt[: limit - 1] + "…"
