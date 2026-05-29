"""API error types for AgentChart."""

from __future__ import annotations


class AgentChartApiError(RuntimeError):
    """Base class for upstream API failures."""


class AuthenticationFailure(AgentChartApiError):
    """Raised when the upstream service rejects the provided credentials."""


class RateLimitFailure(AgentChartApiError):
    """Raised when the upstream service rejects the request due to rate limits."""


class RequestFailure(AgentChartApiError):
    """Raised for generic request or transport failures."""
