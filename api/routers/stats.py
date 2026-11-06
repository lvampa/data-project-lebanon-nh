from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import HourStat, TypeStat, WeekdayStat
from api.services import stats

router = APIRouter()


@router.get("/by-type", response_model=list[TypeStat])
def by_type(db: Annotated[Session, Depends(get_db)]) -> list[TypeStat]:
    return stats.by_type(db)


@router.get("/by-hour", response_model=list[HourStat])
def by_hour(db: Annotated[Session, Depends(get_db)]) -> list[HourStat]:
    return stats.by_hour(db)


@router.get("/by-weekday", response_model=list[WeekdayStat])
def by_weekday(db: Annotated[Session, Depends(get_db)]) -> list[WeekdayStat]:
    return stats.by_weekday(db)
