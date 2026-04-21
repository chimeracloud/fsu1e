import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import APIKeyMiddleware
from app.routers import api, admin
from app.state import state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger(__name__).info("FSU1E starting up")
    yield
    logging.getLogger(__name__).info("FSU1E shutting down")


app = FastAPI(
    title="FSU1E — Racing API Historic Ingest",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(APIKeyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://chimerasportstrading.com",
        "https://www.chimerasportstrading.com",
    ],
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type", "Authorization"],
)
app.include_router(api.router)
app.include_router(admin.router)


@app.get("/")
async def root():
    return {
        "service": "fsu1e",
        "name": "Racing API Historic Ingest",
        "status": state.status,
    }
