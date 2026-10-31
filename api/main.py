from dotenv import load_dotenv

load_dotenv()  # must run before postgres client initializes

import os  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

import logfire  # noqa: E402
from elasticsearch import Elasticsearch  # noqa: E402
from fastapi import FastAPI  # noqa: E402

from api.routers import (  # noqa: E402
    addresses,
    categories,
    incidents,
    llcs,
    search,
    stats,
)

ES_HOST = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logfire.configure()
    app.state.es = Elasticsearch(ES_HOST, request_timeout=10)
    yield
    app.state.es.close()


app = FastAPI(title="Lebanon PD Log — Internal API", lifespan=lifespan)

app.include_router(incidents.router, prefix="/api/incidents", tags=["incidents"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(addresses.router, prefix="/api/addresses", tags=["addresses"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])
app.include_router(llcs.router, prefix="/api/llcs", tags=["llcs"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
