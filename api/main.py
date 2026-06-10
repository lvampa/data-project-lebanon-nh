from dotenv import load_dotenv

load_dotenv()  # must run before postgres client initializes

from fastapi import FastAPI  # noqa: E402
from api.routers import incidents, stats, addresses, categories, llcs, search  # noqa: E402

app = FastAPI(title="Lebanon PD Log — Internal API")

app.include_router(incidents.router, prefix="/api/incidents", tags=["incidents"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(addresses.router, prefix="/api/addresses", tags=["addresses"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])
app.include_router(llcs.router, prefix="/api/llcs", tags=["llcs"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
