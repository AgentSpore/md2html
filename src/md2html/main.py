"""MD2HTML — Markdown to HTML converter.

Thin FastAPI application entrypoint. Domain logic and routers (markdown
conversion endpoint, history, etc.) are added in later scaffold groups
(G2..G5).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": __version__}
