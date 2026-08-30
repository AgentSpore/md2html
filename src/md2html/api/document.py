"""HTTP router for markdown -> HTML document conversions.

The router is kept thin: it parses the request, hands the markdown off to
``services.document_service`` (added in G4) and returns the response. The
service is imported lazily inside each handler so a missing/in-progress
service does not crash the whole process at import time.
"""
from __future__ import annotations

import importlib
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from ..schemas.document import (
    AnalyticsResponse,
    DocumentCreate,
    DocumentList,
    DocumentRead,
)

router = APIRouter(tags=["documents"])


def _service() -> Any:
    """Return the ``document_service`` module, importing it lazily."""
    try:
        return importlib.import_module("md2html.services.document_service")
    except Exception as exc:  # pragma: no cover - import guard
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"document_service unavailable: {exc}",
        ) from exc


@router.post(
    "",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Convert markdown to HTML",
)
async def create_document(payload: DocumentCreate) -> DocumentRead:
    """Convert a markdown payload (or server-side file) to HTML and persist it."""
    if not payload.markdown and not payload.source_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'markdown' or 'source_path' must be provided.",
        )
    if payload.markdown and payload.source_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide only one of 'markdown' or 'source_path', not both.",
        )
    return await _service().create_document(payload)


@router.get(
    "",
    response_model=DocumentList,
    summary="List recent conversions",
)
async def list_documents(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> DocumentList:
    """Return a paginated list of recent conversion records, newest first."""
    return await _service().list_documents(limit=limit, offset=offset)


@router.get(
    "/analytics",
    response_model=AnalyticsResponse,
    summary="Conversion analytics",
)
async def get_analytics() -> AnalyticsResponse:
    """Return aggregate statistics over all stored conversions."""
    return await _service().get_analytics()


@router.get(
    "/{doc_id}",
    response_model=DocumentRead,
    summary="Get a single conversion by id",
)
async def get_document(doc_id: int) -> DocumentRead:
    """Fetch a single conversion record by its numeric id."""
    doc = await _service().get_document(doc_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"document {doc_id} not found",
        )
    return doc
