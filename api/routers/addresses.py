from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from api.auth import require_admin
from api.config import Settings, get_settings
from api.deps import (
    NormalizationFilter,
    Paging,
    get_db,
    get_normalization_filter,
    get_paging,
)
from api.schemas import AddressRecord, AddressResult, AddressUpdate, Page
from api.services import addresses

router = APIRouter()


@router.get("", response_model=Page[AddressRecord])
def list_addresses(
    db: Annotated[Session, Depends(get_db)],
    paging: Annotated[Paging, Depends(get_paging)],
    filters: Annotated[NormalizationFilter, Depends(get_normalization_filter)],
) -> Page[AddressRecord]:
    return addresses.list_addresses(db, paging, filters)


@router.patch(
    "/{raw_address:path}",
    response_model=AddressResult,
    dependencies=[Depends(require_admin)],
)
def update_address(
    raw_address: str,
    body: AddressUpdate,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AddressResult:
    return addresses.update_address(
        db, raw_address, body, nominatim_contact=settings.nominatim_contact
    )


@router.delete(
    "/{raw_address:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_address(
    raw_address: str, db: Annotated[Session, Depends(get_db)]
) -> Response:
    if not addresses.delete_address(db, raw_address):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No normalization for that value"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
