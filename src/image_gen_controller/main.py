"""CLI entrypoint."""

from __future__ import annotations

import logging

import uvicorn

from image_gen_controller.api import create_app
from image_gen_controller.config import get_settings
from image_gen_controller.logging_config import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not settings.typesafe_api_key:
        logger.warning(
            "TYPESAFE_API_KEY is not set. Preflight will refuse to spend "
            "(graceful fallback)."
        )
    if not settings.gemini_api_key:
        logger.warning(
            "GEMINI_API_KEY is not set. /v1/generate will return the Jev "
            "decision but will not call an image model."
        )
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_config=None)


if __name__ == "__main__":
    main()
