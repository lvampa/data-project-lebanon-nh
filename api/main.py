from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # must run before postgres client initializes

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from api.routers import incidents, stats, addresses, categories  # noqa: E402

app = FastAPI(title="Lebanon PD Log — Internal")

app.include_router(incidents.router, prefix="/api/incidents", tags=["incidents"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(addresses.router, prefix="/api/addresses", tags=["addresses"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])

_static = Path(__file__).parent / "static"
# All API routes must use /api/ prefix — static mount at / catches everything else
app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")
