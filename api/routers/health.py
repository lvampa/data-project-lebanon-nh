from typing import Annotated

import logfire
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.deps import get_db

router = APIRouter()


@router.get("/healthz")
def healthz(db: Annotated[Session, Depends(get_db)]) -> JSONResponse:
    checks = {"postgres": _postgres_status(db)}
    failing = [name for name, status in checks.items() if status != "ok"]
    if failing:
        logfire.warning("healthz failing: {failing}", failing=failing)
    return JSONResponse(checks, status_code=503 if failing else 200)


def _postgres_status(db: Session) -> str:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return "error"
    return "ok"
