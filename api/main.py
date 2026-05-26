from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from api.routers import incidents, stats, addresses

app = FastAPI(title="Lebanon PD Log — Internal")

app.include_router(incidents.router, prefix="/api/incidents", tags=["incidents"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(addresses.router, prefix="/api/addresses", tags=["addresses"])

_static = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")
