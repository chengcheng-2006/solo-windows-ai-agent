from __future__ import annotations


class AgentTeamError(RuntimeError):
    """Base error with a stable, non-sensitive machine code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class AuthorizationDenied(AgentTeamError):
    pass


class InvalidStateTransition(AgentTeamError):
    pass


class RegistryViolation(AgentTeamError):
    pass


class TokenValidationError(AgentTeamError):
    pass


class ReviewRejected(AgentTeamError):
    pass
