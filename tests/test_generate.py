"""Generate only after Jev authorizes spend. One Gemini call, one model."""

from image_gen_controller.decisions import JevSignals
from image_gen_controller.generate import run_generate
from image_gen_controller.image_backend import ImageResult


class FakeGateway:
    def __init__(self, signals: JevSignals):
        self.signals = signals

    def evaluate(self, state: dict) -> JevSignals:
        return self.signals


class RecordingBackend:
    def __init__(self):
        self.calls = []

    def generate(self, prompt: str, model: str) -> ImageResult:
        self.calls.append({"prompt": prompt, "model": model})
        return ImageResult(
            image_bytes=b"fake-png",
            mime_type="image/png",
            model=model,
            est_cost_usd=0.034,
        )


def _allow_lite() -> JevSignals:
    return JevSignals(
        policy_violation=0.02,
        specificity_score=3.0,
        specificity_confidence=0.9,
        recommended_action="allow_lite",
        action_confidence=0.88,
    )


def _block() -> JevSignals:
    return JevSignals(
        policy_violation=0.9,
        specificity_score=3.0,
        specificity_confidence=0.9,
        recommended_action="allow_premium",
        action_confidence=0.9,
    )


def test_does_not_call_image_api_when_jev_blocks():
    backend = RecordingBackend()
    result = run_generate(
        "Nike shoe, Tom Cruise, add the swoosh",
        FakeGateway(_block()),
        backend,
        lite_model="gemini-lite",
        premium_model="gemini-pro",
    )

    assert result.preflight.decision.will_spend is False
    assert result.image is None
    assert backend.calls == []


def test_calls_lite_model_when_jev_allows_lite():
    backend = RecordingBackend()
    result = run_generate(
        "studio photo of a red ceramic mug on a white sweep, no text, no logos",
        FakeGateway(_allow_lite()),
        backend,
        lite_model="gemini-3.1-flash-lite-image",
        premium_model="gemini-3-pro-image-preview",
    )

    assert result.preflight.decision.action == "allow_lite"
    assert result.image is not None
    assert result.image.model == "gemini-3.1-flash-lite-image"
    assert len(backend.calls) == 1
    assert "red ceramic mug" in backend.calls[0]["prompt"]


def test_calls_premium_model_when_jev_allows_premium():
    backend = RecordingBackend()
    signals = JevSignals(
        policy_violation=0.02,
        specificity_score=3.0,
        specificity_confidence=0.95,
        recommended_action="allow_premium",
        action_confidence=0.92,
    )
    result = run_generate(
        "studio photo of a brushed steel water bottle, three-quarter view, white sweep",
        FakeGateway(signals),
        backend,
        lite_model="gemini-lite",
        premium_model="gemini-pro",
    )

    assert result.image.model == "gemini-pro"
    assert backend.calls[0]["model"] == "gemini-pro"


def test_returns_decision_when_image_model_raises():
    class BoomBackend:
        def generate(self, prompt: str, model: str):
            raise RuntimeError("RESOURCE_EXHAUSTED")

    result = run_generate(
        "studio photo of a red ceramic mug on a white sweep, no text, no logos",
        FakeGateway(_allow_lite()),
        BoomBackend(),
        lite_model="gemini-lite",
        premium_model="gemini-pro",
    )

    assert result.preflight.decision.will_spend is True
    assert result.image is None
    assert result.image_skip_reason == "image_generation_failed"


def test_skips_image_when_backend_is_missing():
    result = run_generate(
        "studio photo of a red ceramic mug on a white sweep, no text, no logos",
        FakeGateway(_allow_lite()),
        backend=None,
        lite_model="gemini-lite",
        premium_model="gemini-pro",
    )

    assert result.preflight.decision.will_spend is True
    assert result.image is None
    assert result.image_skip_reason == "image_backend_unavailable"
