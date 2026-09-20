"""Preflight service: build state, ask Jev, apply decision policy."""

from image_gen_controller.decisions import JevSignals
from image_gen_controller.errors import InvalidPromptError
from image_gen_controller.preflight import run_preflight
import pytest


class FakeGateway:
    def __init__(self, signals: JevSignals):
        self.signals = signals
        self.last_state = None

    def evaluate(self, state: dict) -> JevSignals:
        self.last_state = state
        return self.signals


def test_rejects_blank_prompt_without_calling_jev():
    gateway = FakeGateway(
        JevSignals(
            policy_violation=0.0,
            specificity_score=3.0,
            specificity_confidence=1.0,
            recommended_action="allow_lite",
            action_confidence=1.0,
        )
    )

    with pytest.raises(InvalidPromptError):
        run_preflight("   ", gateway)

    assert gateway.last_state is None


def test_returns_decision_and_forwards_compact_state_to_jev():
    gateway = FakeGateway(
        JevSignals(
            policy_violation=0.04,
            specificity_score=3.0,
            specificity_confidence=0.91,
            recommended_action="allow_lite",
            action_confidence=0.88,
        )
    )

    result = run_preflight(
        "studio photo of a red ceramic mug on a white sweep, no text, no logos",
        gateway,
    )

    assert result.decision.action == "allow_lite"
    assert result.decision.will_spend is True
    assert result.prompt_preview.startswith("studio photo")
    assert gateway.last_state["prompt"].startswith("studio photo")
    assert "policy" in gateway.last_state
    assert gateway.last_state["budget"]["remaining_usd"] > 0


def test_unavailable_jev_does_not_spend():
    gateway = FakeGateway(
        JevSignals(
            policy_violation=0.0,
            specificity_score=3.0,
            specificity_confidence=1.0,
            recommended_action="allow_premium",
            action_confidence=1.0,
            available=False,
        )
    )

    result = run_preflight("studio photo of a red ceramic mug, white sweep", gateway)

    assert result.decision.will_spend is False
    assert result.decision.reason == "decision_service_unavailable"
