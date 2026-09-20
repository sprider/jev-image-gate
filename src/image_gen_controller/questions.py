"""Atomic Jev questions for image-generation preflight.

Criteria follow TypeSafe shapes: Noul {true,false}, Score ordered
situations starting at level 0, Choice option → description.
"""

from __future__ import annotations

from image_gen_controller.policy import POLICY_ID

QUESTION_VERSION = "preflight-v1"

# Kept as plain dicts so tests and the HTTP audit log can show them
# without importing the TypeSafe SDK.
QUESTION_SPECS = {
    "policy_violation": {
        "type": "noul",
        "instructions": (
            "Does this prompt ask for an image that violates the product-still "
            f"policy in `policy.rules` (policy id {POLICY_ID})?"
        ),
        "criteria": {
            "true": (
                "The prompt requests a celebrity or recognizable real person, "
                "a third-party brand mark or logo, readable text or slogans, "
                "or a medical/financial/legal claim."
            ),
            "false": (
                "The prompt is a generic product still with no real person, "
                "no third-party marks, no readable text, and no regulated claim."
            ),
        },
    },
    "specificity": {
        "type": "score",
        "instructions": (
            "How specific is `prompt` for generating one product still?"
        ),
        "criteria": [
            "Unusable: empty, nonsense, or not an image request.",
            "Vague: mood-only (for example 'make it look cool') with no product.",
            "Adequate: names a product and a simple setting.",
            "Specific: product, material or color, setting, and constraints.",
        ],
    },
    "next_action": {
        "type": "choice",
        "instructions": (
            "Select the safest next step for this image-generation request."
        ),
        "criteria": {
            "block": "The prompt violates policy and must not be sent to an image model.",
            "ask_clarify": (
                "The prompt is too vague or uncertain; ask the caller for a "
                "clearer product-still description. Do not spend."
            ),
            "allow_lite": (
                "On-policy and specific enough for a cheap image model."
            ),
            "allow_premium": (
                "On-policy, highly specific, and remaining budget justifies "
                "a premium image model. Use only when the cheaper model is "
                "unlikely to succeed."
            ),
        },
    },
}


def build_sdk_questions():
    """Build TypeSafe SDK question objects. Imported only when Jev is called."""
    from typesafe_sdk import Choice, Noul, Score

    specs = QUESTION_SPECS
    noul_criteria = specs["policy_violation"]["criteria"]
    try:
        from typesafe_sdk import NoulCriteria

        noul_criteria = NoulCriteria(**noul_criteria)
    except (ImportError, TypeError):
        pass

    return {
        "policy_violation": Noul(
            instructions=specs["policy_violation"]["instructions"],
            criteria=noul_criteria,
        ),
        "specificity": Score(
            instructions=specs["specificity"]["instructions"],
            criteria=specs["specificity"]["criteria"],
        ),
        "next_action": Choice(
            instructions=specs["next_action"]["instructions"],
            criteria=specs["next_action"]["criteria"],
        ),
    }
