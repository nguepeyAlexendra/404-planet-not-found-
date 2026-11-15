from fastapi import APIRouter

from app.api.v1 import analytics, catalog, content, system, tiles, translator

api = APIRouter(prefix="/api/v1")
for r in (system.router, catalog.router, tiles.router, translator.router, analytics.router, content.router):
    api.include_router(r)
