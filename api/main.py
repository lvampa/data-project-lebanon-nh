from contextlib import asynccontextmanager

import logfire
from elasticsearch import Elasticsearch
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.routers import (
    addresses,
    categories,
    health,
    incidents,
    llcs,
    search,
    stats,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.es = Elasticsearch(settings.elasticsearch_host, request_timeout=10)
    yield
    app.state.es.close()


app = FastAPI(title="Lebanon PD Log — Internal API", lifespan=lifespan)
# Not in the lifespan: Starlette builds the middleware stack before the
# lifespan runs, so instrumenting there never wraps a request.
logfire.configure()
logfire.instrument_fastapi(app)

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins)

app.include_router(health.router, tags=["health"])
app.include_router(incidents.router, prefix="/api/incidents", tags=["incidents"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(addresses.router, prefix="/api/addresses", tags=["addresses"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])
app.include_router(llcs.router, prefix="/api/llcs", tags=["llcs"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
