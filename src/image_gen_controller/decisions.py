"""Combine Jev signals into one safe preflight action.

Jev never calls an image API. This module is the only place that
decides whether the workflow is allowed to spend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Action = Literal["block", "ask_clarify", "allow_lite", "allow_premium"]

ALLOWED_ACTIONS: frozenset[str] = frozenset(
    {"block", "ask_clarify", "allow_lite", "allow_premium"}
)
SPEND_ACTIONS: frozenset[str] = frozenset({"allow_lite", "allow_premium"})

POLICY_BLOCK_THRESHOLD = 0.35
VAGUE_SCORE_MAX = 1.0
LOW_CONFIDENCE = 0.50
VERY_LOW_CONFIDENCE = 0.35


@dataclass(frozen=True)
class JevSignals:
    policy_violation: float
    specificity_score: float
    specificity_confidence: float
    recommended_action: str
    action_confidence: float
    available: bool = True


@dataclass(frozen=True)
class PreflightDecision:
    action: Action
    will_spend: bool
    reason: str


def decide_preflight(signals: JevSignals) -> PreflightDecision:
    """Map typed Jev output onto a spend-safe action.

    Order is intentional: outage and invalid enums first, then policy,
    then prompt quality, then confidence. Lower-risk actions replace
    spend when Jev is unsure.
    """
    if not signals.available:
        return _result("ask_clarify", "decision_service_unavailable")

    if signals.recommended_action not in ALLOWED_ACTIONS:
        return _result("ask_clarify", "invalid_jev_action")

    if signals.policy_violation >= POLICY_BLOCK_THRESHOLD:
        return _result("block", "policy_violation")

    if signals.specificity_score <= VAGUE_SCORE_MAX:
        return _result("ask_clarify", "prompt_too_vague")

    action = signals.recommended_action
    confidence = signals.action_confidence

    if action in SPEND_ACTIONS and confidence < VERY_LOW_CONFIDENCE:
        return _result("ask_clarify", "low_confidence")

    if action == "allow_premium" and confidence < LOW_CONFIDENCE:
        return _result("allow_lite", "low_confidence_degraded")

    return _result(action, "jev_action")  # type: ignore[arg-type]


def _result(action: Action, reason: str) -> PreflightDecision:
    return PreflightDecision(
        action=action,
        will_spend=action in SPEND_ACTIONS,
        reason=reason,
    )
