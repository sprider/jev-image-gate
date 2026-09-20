"""Preflight policy: Jev signals in, a safe action out. Code owns spend."""

from image_gen_controller.decisions import JevSignals, decide_preflight


def _signals(**overrides) -> JevSignals:
    base = dict(
        policy_violation=0.05,
        specificity_score=3.0,
        specificity_confidence=0.9,
        recommended_action="allow_lite",
        action_confidence=0.85,
        available=True,
    )
    base.update(overrides)
    return JevSignals(**base)


def test_uses_jev_action_when_signals_are_clear():
    decision = decide_preflight(_signals(recommended_action="allow_lite"))

    assert decision.action == "allow_lite"
    assert decision.will_spend is True
    assert decision.reason == "jev_action"


def test_blocks_when_policy_violation_is_material():
    decision = decide_preflight(
        _signals(recommended_action="allow_premium", policy_violation=0.62)
    )

    assert decision.action == "block"
    assert decision.will_spend is False
    assert decision.reason == "policy_violation"


def test_asks_to_clarify_when_prompt_is_too_vague_to_paint():
    decision = decide_preflight(
        _signals(recommended_action="allow_lite", specificity_score=0.8)
    )

    assert decision.action == "ask_clarify"
    assert decision.will_spend is False
    assert decision.reason == "prompt_too_vague"


def test_never_allows_premium_when_action_confidence_is_low():
    decision = decide_preflight(
        _signals(recommended_action="allow_premium", action_confidence=0.42)
    )

    assert decision.action == "allow_lite"
    assert decision.will_spend is True
    assert decision.reason == "low_confidence_degraded"


def test_does_not_spend_when_action_confidence_is_very_low():
    decision = decide_preflight(
        _signals(recommended_action="allow_lite", action_confidence=0.2)
    )

    assert decision.action == "ask_clarify"
    assert decision.will_spend is False
    assert decision.reason == "low_confidence"


def test_does_not_spend_when_jev_is_unavailable():
    decision = decide_preflight(_signals(available=False, recommended_action="allow_premium"))

    assert decision.action == "ask_clarify"
    assert decision.will_spend is False
    assert decision.reason == "decision_service_unavailable"


def test_rejects_unknown_jev_action():
    decision = decide_preflight(_signals(recommended_action="generate_anyway"))

    assert decision.action == "ask_clarify"
    assert decision.will_spend is False
    assert decision.reason == "invalid_jev_action"


def test_policy_block_wins_over_vague_prompt():
    decision = decide_preflight(
        _signals(
            recommended_action="allow_lite",
            policy_violation=0.8,
            specificity_score=0.4,
        )
    )

    assert decision.action == "block"
    assert decision.reason == "policy_violation"
