"""FastAPI application entrypoint for PrintSight."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
from app.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.exceptions import ValidationError as AppValidationError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("PrintSight starting up — creating tables if needed...")
    Base.metadata.create_all(bind=engine)
    yield
    logger.info("PrintSight shutting down...")


app = FastAPI(
    title=settings.app_name,
    description="SaaS dashboard that turns printer CSV logs into cost and toner yield insights",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ConflictError)
async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(ForbiddenError)
async def forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(AppValidationError)
async def validation_handler(request: Request, exc: AppValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# Health check
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


os.makedirs("uploads/printers", exist_ok=True)
app.mount("/uploads/printers", StaticFiles(directory="uploads/printers"), name="printer_images")

# Routers
from app.routers.auth import router as auth_router
from app.routers.printers import router as printers_router
from app.routers.print_jobs import router as uploads_router, jobs_router
from app.routers.cost_config import router as cost_config_router
from app.routers.analytics import router as analytics_router
from app.routers.toner_replacements import router as toner_router
from app.routers.reports import router as reports_router
from app.routers.admin import router as admin_router

prefix = settings.api_v1_prefix

app.include_router(auth_router, prefix=prefix)
app.include_router(printers_router, prefix=prefix)
app.include_router(uploads_router, prefix=prefix)
app.include_router(jobs_router, prefix=prefix)
app.include_router(cost_config_router, prefix=prefix)
app.include_router(analytics_router, prefix=prefix)
app.include_router(toner_router, prefix=prefix)
app.include_router(reports_router, prefix=prefix)
app.include_router(admin_router, prefix=prefix)
