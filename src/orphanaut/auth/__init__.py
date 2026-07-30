"""AWS auth package."""

from orphanaut.auth.credentials import (
    AuthenticationError,
    create_session,
    list_sso_profiles,
    validate_credentials,
)

__all__ = [
    "AuthenticationError",
    "create_session",
    "list_sso_profiles",
    "validate_credentials",
]
