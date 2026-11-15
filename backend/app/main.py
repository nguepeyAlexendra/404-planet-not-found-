import logging
import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)
log = logging.getLogger("nisar.http")

app = FastAPI(title="NISAR Vision API", version="1.0.0",
              description="API de la plateforme NISAR Vision : catalogue, tuiles, traducteur radar, récits, apprentissage, analyses.",
              docs_url="/api/docs" if settings.env != "prod" else None, openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type", "X-Client-Id", "Idempotency-Key"])
install_error_handlers(app)
_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    request.state.request_id = rid
    ip = request.client.host if request.client else "?"
    if settings.rate_limit_per_minute and not request.url.path.startswith("/api/v1/health"):
        q, now = _hits[ip], time.monotonic()
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= settings.rate_limit_per_minute:
            return JSONResponse({"error": {"code": "rate_limited", "message": "Trop de requêtes, réessayez dans une minute.",
                                           "details": None, "request_id": rid}}, status_code=429, headers={"Retry-After": "60"})
        q.append(now)
    t0 = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    log.info("request", extra={"request_id": rid, "path": request.url.path, "status": response.status_code,
                               "duration_ms": round((time.perf_counter() - t0) * 1000, 1)})
    return response


app.include_router(api)
