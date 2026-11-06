import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)


def require_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if credentials is None or not _is_admin_token(
        credentials.credentials, settings.admin_api_token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _is_admin_token(token: str, expected: str | None) -> bool:
    # An unset token must reject every request, never match an empty one.
    if not expected:
        return False
    return secrets.compare_digest(token.encode(), expected.encode())
