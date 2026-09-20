from types import SimpleNamespace

from image_gen_controller.image_backend import (
    GeminiImageBackend,
    build_paint_prompt,
    estimate_image_cost_usd,
    extract_inline_image,
)


def test_extract_inline_image_decodes_bytes():
    part = SimpleNamespace(
        inline_data=SimpleNamespace(mime_type="image/png", data=b"png-bytes")
    )
    response = SimpleNamespace(
        candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))]
    )

    data, mime = extract_inline_image(response)

    assert data == b"png-bytes"
    assert mime == "image/png"


def test_extract_inline_image_rejects_empty_candidates():
    try:
        extract_inline_image(SimpleNamespace(candidates=[]))
    except RuntimeError as exc:
        assert "no candidates" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_paint_prompt_keeps_product_constraints():
    text = build_paint_prompt("red ceramic mug on a white sweep")
    assert "red ceramic mug" in text
    assert "product still" in text.lower()
    assert "No logos" in text


def test_estimate_known_lite_price():
    assert estimate_image_cost_usd("gemini-3.1-flash-lite-image") == 0.034


def test_gemini_backend_uses_injected_client():
    part = SimpleNamespace(
        inline_data=SimpleNamespace(mime_type="image/png", data=b"img")
    )
    response = SimpleNamespace(
        candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))]
    )

    class FakeModels:
        def generate_content(self, **kwargs):
            assert kwargs["model"] == "gemini-lite"
            assert "IMAGE" in kwargs["config"].response_modalities
            return response

    class FakeClient:
        models = FakeModels()

    from image_gen_controller.config import Settings

    backend = GeminiImageBackend(Settings(gemini_api_key="x"), client=FakeClient())
    result = backend.generate("red mug", "gemini-lite")

    assert result.image_bytes == b"img"
    assert result.model == "gemini-lite"
