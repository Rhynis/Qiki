"""Custom exception classes for the application."""


class GasBotException(Exception):
    """Base exception for all application errors."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, detail: str, error_code: str | None = None) -> None:
        self.detail = detail
        if error_code:
            self.error_code = error_code
        super().__init__(detail)


class NotFoundException(GasBotException):
    """Resource not found."""

    status_code = 404
    error_code = "not_found"


class ValidationException(GasBotException):
    """Input validation failed."""

    status_code = 400
    error_code = "validation_error"


class UnauthorizedException(GasBotException):
    """Authentication required or failed."""

    status_code = 401
    error_code = "unauthorized"


class ForbiddenException(GasBotException):
    """Authenticated user is not authorized."""

    status_code = 403
    error_code = "forbidden"


class ConflictException(GasBotException):
    """Resource conflict."""

    status_code = 409
    error_code = "conflict"


class RateLimitException(GasBotException):
    """Rate limit exceeded."""

    status_code = 429
    error_code = "rate_limited"


class LLMException(GasBotException):
    """LLM provider error."""

    status_code = 503
    error_code = "llm_error"


class RAGException(GasBotException):
    """RAG pipeline error."""

    status_code = 500
    error_code = "rag_error"


class InsufficientStockException(ConflictException):
    """Not enough stock to fulfill request."""

    error_code = "insufficient_stock"


class IdempotencyException(ConflictException):
    """Idempotency key conflict."""

    error_code = "idempotency_conflict"


class NotImplementedException(GasBotException):
    """A feature is configured but not implemented on the server yet."""

    status_code = 501
    error_code = "not_implemented"
