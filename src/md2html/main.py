"""MD2HTML — Markdown to HTML converter.

FastAPI application entrypoint. Domain logic lives in services/ (G4).
Routers are mounted under /api.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.document import router as document_router

__version__ = "0.1.0"

app = FastAPI(
    title="MD2HTML",
    version=__version__,
    description="Zero-dependency Markdown to HTML converter (HTTP + CLI).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(document_router, prefix="/api/v1/documents")


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": __version__}
