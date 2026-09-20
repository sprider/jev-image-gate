from fastapi.testclient import TestClient

from image_gen_controller.api import create_app
from image_gen_controller.decisions import JevSignals


class FakeGateway:
    def __init__(self, signals: JevSignals):
        self.signals = signals

    def evaluate(self, state: dict) -> JevSignals:
        return self.signals


def _client(signals: JevSignals) -> TestClient:
    app = create_app(gateway=FakeGateway(signals))
    return TestClient(app, raise_server_exceptions=False)


def test_preflight_endpoint_returns_typed_decision():
    client = _client(
        JevSignals(
            policy_violation=0.03,
            specificity_score=3.0,
            specificity_confidence=0.9,
            recommended_action="allow_lite",
            action_confidence=0.86,
        )
    )

    response = client.post(
        "/v1/preflight",
        json={
            "prompt": (
                "studio photo of a red ceramic mug on a white sweep, "
                "no text, no logos"
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "allow_lite"
    assert body["will_spend"] is True
    assert body["reason"] == "jev_action"
    assert "signals" in body


def test_preflight_rejects_empty_prompt():
    client = _client(
        JevSignals(
            policy_violation=0.0,
            specificity_score=3.0,
            specificity_confidence=1.0,
            recommended_action="allow_lite",
            action_confidence=1.0,
        )
    )

    response = client.post("/v1/preflight", json={"prompt": "  "})

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_prompt"


def test_preflight_blocks_policy_violation():
    client = _client(
        JevSignals(
            policy_violation=0.91,
            specificity_score=3.0,
            specificity_confidence=0.9,
            recommended_action="allow_premium",
            action_confidence=0.9,
        )
    )

    response = client.post(
        "/v1/preflight",
        json={"prompt": "Nike Air Force 1, Tom Cruise holding it, add the swoosh"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "block"
    assert body["will_spend"] is False
    assert body["reason"] == "policy_violation"


def test_generate_skips_image_when_blocked():
    client = _client(
        JevSignals(
            policy_violation=0.91,
            specificity_score=3.0,
            specificity_confidence=0.9,
            recommended_action="allow_premium",
            action_confidence=0.9,
        )
    )

    response = client.post(
        "/v1/generate",
        json={"prompt": "Nike Air Force 1, Tom Cruise holding it, add the swoosh"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["will_spend"] is False
    assert body["image"]["generated"] is False
    assert body["image"]["skip_reason"] == "not_authorized"


def test_generate_returns_image_when_authorized():
    from image_gen_controller.image_backend import ImageResult

    class FakeBackend:
        def generate(self, prompt: str, model: str) -> ImageResult:
            return ImageResult(
                image_bytes=b"png-bytes",
                mime_type="image/png",
                model=model,
                est_cost_usd=0.034,
            )

    app = create_app(
        gateway=FakeGateway(
            JevSignals(
                policy_violation=0.02,
                specificity_score=3.0,
                specificity_confidence=0.9,
                recommended_action="allow_lite",
                action_confidence=0.88,
            )
        ),
        image_backend=FakeBackend(),
    )
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/v1/generate",
        json={
            "prompt": "studio photo of a red ceramic mug on a white sweep, no text, no logos"
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["image"]["generated"] is True
    assert body["image"]["model"] == "gemini-3.1-flash-lite-image"
    assert body["image"]["base64_data"]


def test_healthz():
    client = _client(
        JevSignals(
            policy_violation=0.0,
            specificity_score=0.0,
            specificity_confidence=0.0,
            recommended_action="ask_clarify",
            action_confidence=0.0,
            available=False,
        )
    )
    assert client.get("/healthz").status_code == 200
