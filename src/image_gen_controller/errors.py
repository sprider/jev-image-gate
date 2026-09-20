"""Typed failures so the API can respond without leaking internals."""


class ControllerError(Exception):
    """Base error for this service."""

    def __init__(self, message: str, *, code: str = "controller_error"):
        super().__init__(message)
        self.message = message
        self.code = code


class InvalidPromptError(ControllerError):
    def __init__(self, message: str = "Prompt is empty."):
        super().__init__(message, code="invalid_prompt")


class DecisionServiceError(ControllerError):
    """Jev could not be reached or returned an unusable payload."""

    def __init__(self, message: str = "Decision service is unavailable."):
        super().__init__(message, code="decision_service_unavailable")
