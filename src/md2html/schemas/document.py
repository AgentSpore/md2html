"""Pydantic schemas for markdown -> HTML document conversions."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class DocumentCreate(BaseModel):
    """Request body to convert a markdown document to HTML.

    Either `markdown` (inline) or `source_path` (server-side file) must be
    supplied. `title` controls the generated HTML <title>.
    """

    markdown: Optional[str] = Field(
        default=None,
        description="Inline markdown source. Mutually exclusive with source_path.",
    )
    source_path: Optional[str] = Field(
        default=None,
        description="Path to a markdown file on the server. Mutually exclusive with markdown.",
    )
    title: str = Field(
        default="MD2HTML Output",
        max_length=200,
        description="Title written into the generated HTML <title> tag.",
    )
    fragment: bool = Field(
        default=False,
        description=(
            "If true, return only the converted body HTML without the wrapping "
            "HTML document shell."
        ),
    )


class DocumentRead(BaseModel):
    """A single conversion record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Server-side numeric id of the conversion record.")
    title: str
    source_kind: str = Field(..., description="Either 'inline' or 'file'.")
    source_ref: str = Field(..., description="Either the inline text length, or the file path.")
    html: str = Field(..., description="The rendered HTML output.")
    byte_size: int = Field(..., ge=0, description="Size of the HTML output in bytes.")
    created_at: datetime


class DocumentList(BaseModel):
    """Paginated list of recent conversions."""

    items: list[DocumentRead]
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)


class AnalyticsResponse(BaseModel):
    """Lightweight analytics summary for the converter."""

    total_conversions: int = Field(..., ge=0)
    total_html_bytes: int = Field(..., ge=0)
    avg_html_bytes: float = Field(..., ge=0)
    largest_id: Optional[int] = None
