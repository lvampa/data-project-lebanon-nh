from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.auth import require_admin
from api.deps import Paging, get_db, get_paging
from api.schemas import AddressRecord, AddressResult, AddressUpdate, Page
from api.services import addresses

router = APIRouter()


@router.get("", response_model=Page[AddressRecord])
def list_addresses(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[Paging, Depends(get_paging)],
) -> Page[AddressRecord]:
    return addresses.list_addresses(db, paging)


@router.patch(
    "/{raw_address:path}",
    response_model=AddressResult,
    dependencies=[Depends(require_admin)],
)
def update_address(
    raw_address: str,
    body: AddressUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> AddressResult:
    return addresses.update_address(db, raw_address, body)
