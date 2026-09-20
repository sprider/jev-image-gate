from image_gen_controller.jev_gateway import (
    TypeSafeJevGateway,
    extract_signals,
)


def test_extract_signals_from_answers_dict():
    signals = extract_signals(
        {
            "answers": {
                "policy_violation": {"noul": 0.12},
                "specificity": {"score": 2.4, "confidence": 0.7},
                "next_action": {"choice": "allow_lite", "confidence": 0.81},
            }
        }
    )

    assert signals.available is True
    assert signals.policy_violation == 0.12
    assert signals.specificity_score == 2.4
    assert signals.recommended_action == "allow_lite"
    assert signals.action_confidence == 0.81


def test_gateway_returns_unavailable_when_api_key_missing(monkeypatch):
    from image_gen_controller.config import Settings

    gateway = TypeSafeJevGateway(Settings(typesafe_api_key=""))
    signals = gateway.evaluate({"prompt": "red mug"})

    assert signals.available is False
    assert signals.recommended_action == "ask_clarify"


def test_gateway_returns_unavailable_when_client_raises():
    from image_gen_controller.config import Settings

    class Boom:
        def __enter__(self):
            raise RuntimeError("network down")

        def __exit__(self, *args):
            return False

    gateway = TypeSafeJevGateway(
        Settings(typesafe_api_key="test-key"),
        client_factory=lambda settings: Boom(),
    )
    signals = gateway.evaluate({"prompt": "red mug"})

    assert signals.available is False
