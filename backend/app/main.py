"""FastAPI application entry point."""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import api_router
from app.config import settings
from app.core.rate_limit import limiter
from app.database import init_db
from app.utils.logger import logger


async def _coc_cleanup_loop():
    """Run COC archive cleanup at startup and every 24 hours thereafter."""
    from app.database import SessionLocal
    from app.services.lot_service import LotService

    while True:
        try:
            db = SessionLocal()
            try:
                LotService().cleanup_expired_coc_archives(db)
            finally:
                db.close()
        except Exception:
            logger.opt(exception=True).error("COC archive cleanup failed")
        await asyncio.sleep(24 * 60 * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    init_db()
    from app.services.result_import_worker import (
        start_result_import_worker,
        stop_result_import_worker,
    )

    await start_result_import_worker()
    cleanup_task = asyncio.create_task(_coc_cleanup_loop())
    yield
    # Shutdown
    cleanup_task.cancel()
    await stop_result_import_worker()


app = FastAPI(
    title=settings.app_name,
    description="LabTrack API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "https://labtrack.bodytools.work",  # Production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Mount uploads directory for static file serving (logos, etc.)
uploads_path = settings.upload_path
if not os.path.exists(uploads_path):
    os.makedirs(uploads_path, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_path), name="uploads")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Prevent stack traces from leaking to clients in production."""
    if settings.debug:
        raise exc
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.environment,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8009,
        reload=settings.debug,
    )
