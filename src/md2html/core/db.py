"""Async SQLite layer.

Uses aiosqlite (NOT sqlalchemy) — a plain file-path connection, per the
hard rule: aiosqlite.connect wants a path, never a `sqlite:///` URL.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import aiosqlite

from .config import get_settings

# --- schema ----------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    source_kind  TEXT    NOT NULL,                -- 'inline' | 'file' | 'url'
    title        TEXT    NOT NULL DEFAULT '',
    markdown     TEXT    NOT NULL,
    html         TEXT    NOT NULL,
    byte_size    INTEGER NOT NULL,
    elapsed_ms   REAL    NOT NULL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS ix_conversions_created_at
    ON conversions(created_at DESC);
"""


# --- dependency ------------------------------------------------------------

@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Yield an aiosqlite connection bound to the configured file path.

    The connection is opened with `isolation_level=None` so aiosqlite manages
    transactions explicitly via BEGIN/COMMIT, and rows are returned as
    mappings (`row_factory = aiosqlite.Row`).
    """
    settings = get_settings()
    db_path = settings.database_path
    # Ensure parent dir exists when the path points somewhere other than cwd.
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    try:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        yield conn
    finally:
        await conn.close()


# --- lifecycle -------------------------------------------------------------

async def init_db() -> None:
    """Create tables on startup. Idempotent."""
    async with get_db() as conn:
        await conn.executescript(SCHEMA)
        await conn.commit()
