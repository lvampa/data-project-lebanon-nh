import os
from typing import Annotated

from elasticsearch import Elasticsearch
from fastapi import APIRouter, Depends, Query
from postgres.models.address_normalization import AddressNormalization
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import SearchResponse, SearchResult

router = APIRouter()

ES_HOST = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")

ES_INDICES = [
    "properties",
    "incidents",
    "planning_meetings",
    "planning_documents",
    "city_staff",
    "officers",
    "llcs",
    "budget_line_items",
    "budget_capital_projects",
]

_es: Elasticsearch | None = None


def _get_es() -> Elasticsearch:
    global _es
    if _es is None:
        _es = Elasticsearch(ES_HOST)
    return _es


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
    limit: int = Query(default=5, ge=1, le=20),
) -> SearchResponse:
    es = _get_es()
    normalized = _normalize_query(q, db)
    search_query = normalized or q

    searches = []
    for index in ES_INDICES:
        searches.append({"index": index})
        searches.append(
            {
                "query": {
                    "multi_match": {
                        "query": search_query,
                        "fields": [
                            "normalized_address^3",
                            "location^2",
                            "owner^2",
                            "name^2",
                            "file_name^2",
                            "project_name^2",
                            "*",
                        ],
                        "fuzziness": "AUTO",
                    }
                },
                "size": limit,
            }
        )

    resp = es.msearch(searches=searches)

    results: dict[str, list[SearchResult]] = {idx: [] for idx in ES_INDICES}
    for index, response in zip(ES_INDICES, resp["responses"], strict=True):
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
