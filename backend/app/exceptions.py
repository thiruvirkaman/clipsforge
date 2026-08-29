"""Custom application exceptions for ClipForge.

These are caught by global exception handlers in `app.main` and converted
into consistent JSON error responses.
"""


class AppException(Exception):
    """Base class for all application-level exceptions."""

    def __init__(self, message: str, code: str, status_code: int = 500) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppException):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str) -> None:
        super().__init__(f"{resource} not found", "NOT_FOUND", 404)


class ConflictError(AppException):
    """Raised when a request conflicts with the current state of a resource."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "CONFLICT", 409)


class ValidationError(AppException):
    """Raised when request data fails application-level validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "VALIDATION_ERROR", 422)


class UnauthorizedError(AppException):
    """Raised when authentication is missing or invalid."""

    def __init__(self, message: str = "Not authenticated") -> None:
        super().__init__(message, "UNAUTHORIZED", 401)


class ForbiddenError(AppException):
    """Raised when the authenticated user lacks permission for an action."""

    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message, "FORBIDDEN", 403)


class QuotaExceededError(AppException):
    """Raised when a user's current plan usage is already at/over their limit."""

    def __init__(self, message: str = "Plan usage limit reached") -> None:
        super().__init__(message, "QUOTA_EXCEEDED", 402)


class EnqueueError(AppException):
    """Raised when a background job could not be queued (e.g. broker unavailable)."""

    def __init__(self, message: str = "Could not queue background processing") -> None:
        super().__init__(message, "ENQUEUE_FAILED", 503)


class FeatureNotImplementedError(AppException):
    """Raised by stubbed/deferred features that must not silently claim success."""

    def __init__(self, message: str = "This feature is not available yet") -> None:
        super().__init__(message, "NOT_IMPLEMENTED", 501)
