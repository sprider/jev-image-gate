"""Product-still policy. This is domain rules, not Jev output."""

POLICY_ID = "product_stills_v1"

POLICY_RULES = (
    "Generate a single commercial product still only.",
    "No celebrity or recognizable real person.",
    "No third-party brand marks, logos, or wordmarks (including Nike, Apple, Coca-Cola).",
    "No readable text, labels, or slogans on the product or in the scene.",
    "No medical, financial, or legal claims implied by the image.",
    "Clean studio or simple environment; one primary product.",
)

POLICY_TEXT = " ".join(POLICY_RULES)

DEFAULT_BUDGET_USD = 0.05
DEFAULT_ATTEMPT = 1
DEFAULT_MAX_ATTEMPTS = 1


def build_state(prompt: str, *, remaining_usd: float = DEFAULT_BUDGET_USD) -> dict:
    """Compact factual state for one System One call."""
    return {
        "prompt": prompt,
        "policy": {
            "id": POLICY_ID,
            "rules": list(POLICY_RULES),
        },
        "budget": {
            "remaining_usd": remaining_usd,
            "attempt": DEFAULT_ATTEMPT,
            "max_attempts": DEFAULT_MAX_ATTEMPTS,
        },
        "workflow": "image_generation_preflight",
    }
