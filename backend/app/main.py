"""FastAPI application entrypoint for ClipForge."""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.exceptions import AppException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Convert any AppException (and its subclasses) into a JSON error response."""
    logger.warning("AppException handled: %s (%s)", exc.message, exc.code)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


from app.routers import auth, clips, clips_export, projects, publish, usage  # noqa: E402

app.include_router(auth.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(clips.router, prefix="/api/v1")
app.include_router(clips_export.router, prefix="/api/v1")
app.include_router(publish.router, prefix="/api/v1")
app.include_router(usage.router, prefix="/api/v1")

# No static/public media mount: clip video and thumbnail files are only
# reachable via the authenticated, ownership-checked
# `/api/v1/clips/{id}/download` and `/api/v1/clips/{id}/thumbnail` routes
# (see app.routers.clips_export). The frontend fetches them through the API
# client (which attaches the bearer token) and renders them as blob URLs.


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness/readiness check."""
    return {"status": "healthy"}
