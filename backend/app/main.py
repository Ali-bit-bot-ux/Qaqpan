import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .config import parse_cors_origins
from .db import init_db
from .api.transfers import router as transfers_router, recover_pending_timeouts, stop_timeout_tasks
from .api.trusted import router as trusted_router
from .api.analyst import router as analyst_router
from .api.benchmark import router as benchmark_router
from .api.trap import router as trap_router, recover_trap_sessions, stop_trap_tasks

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("qaqpan.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Qaqpan Anti-Fraud Guardian Service...")
    init_db()
    logger.info("Database initialized successfully.")
    try:
        recover_pending_timeouts()
        recover_trap_sessions()
        yield
    finally:
        await stop_timeout_tasks()
        await stop_trap_tasks()
        logger.info("Shutting down Qaqpan Anti-Fraud Guardian Service...")


app = FastAPI(
    title="ҚАҚПАН (Qaqpan) Anti-Fraud API",
    description="Adaptive multi-tier transaction security system for CenterCredit Bank hackathon",
    version="1.0.0",
    lifespan=lifespan
)

_cors_origins = parse_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # Browsers reject wildcard origins combined with credentials.
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transfers_router, prefix="/api/v1")
app.include_router(trusted_router, prefix="/api/v1")
app.include_router(analyst_router, prefix="/api/v1")
app.include_router(benchmark_router, prefix="/api/v1")
app.include_router(trap_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def root():
    return {
        "service": "Қақпан (Qaqpan) Anti-Fraud Guardian",
        "status": "healthy",
        "docs_url": "/docs",
        "api_v1_prefix": "/api/v1"
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
