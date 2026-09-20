"""Call Jev once. On any failure, return unavailable signals - never spend."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from image_gen_controller.config import Settings, get_settings
from image_gen_controller.decisions import JevSignals
from image_gen_controller.questions import QUESTION_VERSION, build_sdk_questions

logger = logging.getLogger(__name__)

UNAVAILABLE = JevSignals(
    policy_violation=0.0,
    specificity_score=0.0,
    specificity_confidence=0.0,
    recommended_action="ask_clarify",
    action_confidence=0.0,
    available=False,
)


class JevGateway(Protocol):
    def evaluate(self, state: dict) -> JevSignals:
        """Return typed signals, or unavailable signals if Jev cannot be used."""


def extract_signals(payload: Any) -> JevSignals:
    """Read a System One response (SDK object or dict) into JevSignals."""
    answers = _answers(payload)

    policy = _require(answers, "policy_violation")
    specificity = _require(answers, "specificity")
    action = _require(answers, "next_action")

    return JevSignals(
        policy_violation=float(_field(policy, "noul")),
        specificity_score=float(_field(specificity, "score")),
        specificity_confidence=float(_field(specificity, "confidence", default=0.0)),
        recommended_action=str(_field(action, "choice")),
        action_confidence=float(_field(action, "confidence", default=0.0)),
        available=True,
    )


class TypeSafeJevGateway:
    """Thin wrapper around TypeSafeClient. Never raises to the caller."""

    def __init__(self, settings: Settings | None = None, client_factory=None):
        self._settings = settings or get_settings()
        self._client_factory = client_factory

    def evaluate(self, state: dict) -> JevSignals:
        if not self._settings.typesafe_api_key:
            logger.warning("TypeSafe API key is missing; skipping Jev call")
            return UNAVAILABLE

        try:
            factory = self._client_factory or _default_client_factory
            with factory(self._settings) as client:
                response = client.system_one(
                    state=state,
                    questions=build_sdk_questions(),
                    model=self._settings.jev_model,
                )
            signals = extract_signals(response)
            logger.info(
                "Jev preflight complete model=%s questions=%s action=%s "
                "action_confidence=%.2f policy_noul=%.2f specificity=%.2f",
                self._settings.jev_model,
                QUESTION_VERSION,
                signals.recommended_action,
                signals.action_confidence,
                signals.policy_violation,
                signals.specificity_score,
            )
            return signals
        except Exception:
            logger.exception("Jev call failed; refusing to spend")
            return UNAVAILABLE


def _default_client_factory(settings: Settings):
    import os

    from typesafe_sdk import TypeSafeClient

    os.environ.setdefault("TYPESAFE_API_KEY", settings.typesafe_api_key)
    return TypeSafeClient(
        api_key=settings.typesafe_api_key,
        model=settings.jev_model,
        timeout=settings.jev_timeout_seconds,
    )


def _answers(payload: Any) -> dict:
    if payload is None:
        raise ValueError("empty Jev payload")
    if isinstance(payload, dict):
        return payload.get("answers") or payload
    answers = getattr(payload, "answers", None)
    if answers is not None:
        return dict(answers)
    # Older / alternate SDK accessors
    merged = {}
    for group in ("nouls", "scores", "choices"):
        part = getattr(payload, group, None)
        if part:
            merged.update(dict(part))
    if not merged:
        raise ValueError("Jev payload has no answers")
    return merged


def _require(answers: dict, key: str) -> Any:
    if key not in answers:
        raise ValueError(f"Jev answer missing: {key}")
    return answers[key]


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        if name in obj:
            return obj[name]
        if default is not None:
            return default
        raise ValueError(f"Jev answer missing field: {name}")
    if hasattr(obj, name):
        return getattr(obj, name)
    if default is not None:
        return default
    raise ValueError(f"Jev answer missing field: {name}")
