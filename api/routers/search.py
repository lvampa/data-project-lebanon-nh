from typing import Annotated

import logfire
from elasticsearch import Elasticsearch
from fastapi import APIRouter, Depends, Query
from postgres.models.address_normalization import AddressNormalization
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db, get_es
from api.schemas import SearchResponse, SearchResult

router = APIRouter()

# Text fields that scripts/sync/sync_es.py indexes for each entity.
SEARCH_FIELDS = {
    "properties": [
        "normalized_address^3",
        "location^2",
        "owner^2",
        "parcel_id",
        "land_use",
    ],
    "incidents": [
        "normalized_address^3",
        "location^2",
        "case_number",
        "incident_type",
        "officer",
        "disposition",
        "raw_text",
    ],
    "planning_meetings": ["normalized_address^3", "location^2", "title", "category"],
    "planning_documents": ["normalized_address^3", "file_name^2", "raw_text"],
    "city_staff": ["name^2", "title", "department", "division"],
    "officers": ["name^2", "rank", "division"],
    "llcs": ["name^2", "raw_owner_name"],
    "budget_line_items": ["description", "department", "fund_name"],
    "budget_capital_projects": ["project_name^2", "fund_name"],
}
ES_INDICES = list(SEARCH_FIELDS)

# raw_text is large and owner_address is a resident mailing address. Neither is shown.
HIDDEN_FIELDS = ["raw_text", "owner_address"]


def _normalize_query(q: str, db: Session) -> str | None:
    row = db.execute(
        select(AddressNormalization).where(
            AddressNormalization.raw_address == q.upper()
        )
    ).scalar_one_or_none()
    return row.normalized_address if row else None


@router.get("", response_model=SearchResponse)
def search(
    q: Annotated[str, Query(min_length=1)],
    db: Annotated[Session, Depends(get_db)],
    es: Annotated[Elasticsearch, Depends(get_es)],
    limit: int = Query(default=5, ge=1, le=20),
) -> SearchResponse:
    normalized = _normalize_query(q, db)
    search_query = normalized or q

    searches = []
    for index, fields in SEARCH_FIELDS.items():
        searches.append({"index": index})
        searches.append(
            {
                "query": {
                    "multi_match": {
                        "query": search_query,
                        "fields": fields,
                        "fuzziness": "AUTO",
                    }
                },
                "_source": {"excludes": HIDDEN_FIELDS},
                "size": limit,
            }
        )

    resp = es.msearch(searches=searches)

    results: dict[str, list[SearchResult]] = {idx: [] for idx in ES_INDICES}
    for index, response in zip(ES_INDICES, resp["responses"], strict=True):
        if "error" in response:
            logfire.warning(
                "search skipped {index}", index=index, error=response["error"]
            )
            continue
        for hit in response["hits"]["hits"]:
            results[index].append(
                SearchResult(
                    id=int(hit["_id"]),
                    entity_type=index,
                    score=hit["_score"] if hit["_score"] is not None else 0.0,
                    data=hit["_source"],
                )
            )

    return SearchResponse(query=q, normalized_query=normalized, results=results)
