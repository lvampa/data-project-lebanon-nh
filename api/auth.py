import os
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)


def require_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    if credentials is None or not _is_admin_token(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _is_admin_token(token: str) -> bool:
    expected = os.getenv("ADMIN_API_TOKEN", "")
    # An unset token must reject every request, never match an empty one.
    if not expected:
        return False
    return secrets.compare_digest(token.encode(), expected.encode())
