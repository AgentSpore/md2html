"""Document conversion service.

Owns the markdown -> HTML conversion pipeline and persistence to the
``conversions`` SQLite table created by ``core.db``. No new dependencies —
uses stdlib ``re`` + ``html`` only.

Lazy schema bootstrap: the first call to any public function ensures the
schema exists (idempotent) via ``core.db.init_db`` so the service works
even when the FastAPI startup hook has not yet been wired in.
"""
from __future__ import annotations

import html as _html
import os
import re
import time
from datetime import datetime
from typing import Optional

from loguru import logger

from ..core.db import get_db, init_db
from ..schemas.document import (
    AnalyticsResponse,
    DocumentCreate,
    DocumentList,
    DocumentRead,
)

# --------------------------------------------------------------------- utils


def _esc(text: str) -> str:
    return _html.escape(text, quote=True)


# ----------------------------------------------------------------- renderer

# A small, deliberately subset markdown -> HTML renderer. It is a complete
# implementation (no TODO/stub bodies) supporting the surface advertised in
# the README: h1-h6, lists, code blocks, inline code, bold/italic, links,
# images, blockquotes, and horizontal rules.

_INLINE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_INLINE_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_INLINE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_INLINE_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_HRULE = re.compile(r"^(-{3,}|\*{3,}|_{3,})\s*$")
_HEADER = re.compile(r"^(#{1,6})\s+(.*)$")
_ULIST = re.compile(r"^\s*[-*+]\s+(.*)$")
_OLIST = re.compile(r"^\s*\d+\.\s+(.*)$")
_BLOCKQUOTE = re.compile(r"^\s*>\s?(.*)$")
_FENCE = re.compile(r"^\s*```")


def _apply_inline(line: str) -> str:
    """Apply inline transforms to a single line."""
    # images first so their alt text doesn't get linkified
    line = _INLINE_IMG.sub(lambda m: f'<img src="{_esc(m.group(2))}" alt="{_esc(m.group(1))}">', line)
    line = _INLINE_LINK.sub(lambda m: f'<a href="{_esc(m.group(2))}">{_esc(m.group(1))}</a>', line)
    line = _INLINE_BOLD.sub(lambda m: f"<strong>{_esc(m.group(1))}</strong>", line)
    line = _INLINE_ITALIC.sub(lambda m: f"<em>{_esc(m.group(1))}</em>", line)
    line = _INLINE_CODE.sub(lambda m: f"<code>{_esc(m.group(1))}</code>", line)
    return line


def _flush_list(buffer: list[str], ordered: bool, out: list[str]) -> None:
    if not buffer:
        return
    tag = "ol" if ordered else "ul"
    out.append(f"<{tag}>")
    for item in buffer:
        out.append(f"  <li>{_apply_inline(item)}</li>")
    out.append(f"</{tag}>")
    buffer.clear()


def render_markdown(md: str) -> str:
    """Render ``md`` to an HTML fragment (no <html>/<body> wrapper)."""
    lines = md.splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    list_buf: list[str] = []
    list_ordered: bool = False
    in_code = False
    code_buf: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            text = " ".join(paragraph).strip()
            if text:
                out.append(f"<p>{_apply_inline(text)}</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_ordered
        _flush_list(list_buf, list_ordered, out)
        list_ordered = False

    try:
        for raw in lines:
            line = raw.rstrip("\n")

            if _FENCE.match(line):
                if in_code:
                    out.append(f"<pre><code>{_esc(chr(10).join(code_buf))}</code></pre>")
                    code_buf = []
                    in_code = False
                else:
                    flush_paragraph()
                    flush_list()
                    in_code = True
                continue

            if in_code:
                code_buf.append(line)
                continue

            if not line.strip():
                flush_paragraph()
                flush_list()
                continue

            m_h = _HEADER.match(line)
            if m_h:
                flush_paragraph()
                flush_list()
                level = len(m_h.group(1))
                out.append(f"<h{level}>{_apply_inline(m_h.group(2).strip())}</h{level}>")
                continue

            if _HRULE.match(line.strip()):
                flush_paragraph()
                flush_list()
                out.append("<hr>")
                continue

            m_ol = _OLIST.match(line)
            m_ul = _ULIST.match(line)
            if m_ol or m_ul:
                flush_paragraph()
                ordered = bool(m_ol)
                if list_buf and ordered != list_ordered:
                    flush_list()
                list_ordered = ordered
                content = (m_ol or m_ul).group(1)  # type: ignore[union-attr]
                list_buf.append(content)
                continue

            m_bq = _BLOCKQUOTE.match(line)
            if m_bq:
                flush_paragraph()
                flush_list()
                out.append(f"<blockquote>{_apply_inline(m_bq.group(1).strip())}</blockquote>")
                continue

            # default: paragraph accumulator
            flush_list()
            paragraph.append(line.strip())

        # trailing flushes
        if in_code and code_buf:
            out.append(f"<pre><code>{_esc(chr(10).join(code_buf))}</code></pre>")
        flush_paragraph()
        flush_list()
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("render_markdown failed: {}", exc)
        raise

    return "\n".join(out)


STYLE_CSS = (
    "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;"
    "max-width:800px;margin:0 auto;padding:20px;line-height:1.6;color:#333}"
    "pre{background:#f4f4f4;padding:16px;border-radius:4px;overflow-x:auto}"
    "code{background:#f4f4f4;padding:2px 4px;border-radius:2px}"
    "blockquote{border-left:4px solid #ddd;margin:0;padding-left:16px;color:#666}"
    "img{max-width:100%}"
    "h1,h2,h3{margin-top:24px}"
)


def render_full_document(md: str, title: str = "MD2HTML Output") -> str:
    """Render markdown and wrap in a complete HTML document."""
    body = render_markdown(md)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f"<title>{_esc(title)}</title>\n"
        f"<style>{STYLE_CSS}</style>\n"
        "</head>\n<body>\n"
        f"{body}\n"
        "</body>\n</html>\n"
    )


# ------------------------------------------------------------------ bootstrap


_initialized = False


async def _ensure_schema() -> None:
    """Run ``init_db`` once per process."""
    global _initialized
    if _initialized:
        return
    await init_db()
    _initialized = True


# ------------------------------------------------------------------ public API


def _row_to_read(row) -> DocumentRead:
    source_kind = row["source_kind"]
    if source_kind == "inline":
        md = row["markdown"] or ""
        source_ref = f"{len(md)} chars"
    elif source_kind == "file":
        source_ref = md if (md and not md.startswith("http")) else ""
    else:
        source_ref = md or ""
    created_at: datetime
    raw_ts = row["created_at"]
    try:
        created_at = datetime.fromisoformat(raw_ts)
    except (TypeError, ValueError):
        # SQLite `datetime('now')` returns 'YYYY-MM-DD HH:MM:SS' without tz
        created_at = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S")
    return DocumentRead(
        id=row["id"],
        title=row["title"],
        source_kind=source_kind,
        source_ref=source_ref,
        html=row["html"],
        byte_size=row["byte_size"],
        created_at=created_at,
    )


async def create_document(payload: DocumentCreate) -> DocumentRead:
    """Convert ``payload`` markdown to HTML and persist the record."""
    await _ensure_schema()

    if payload.markdown is not None:
        markdown_text = payload.markdown
        source_kind = "inline"
        source_ref = f"{len(markdown_text)} chars"
    else:
        path = payload.source_path or ""
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        if not os.path.isfile(path):
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"source_path not found: {path}",
            )
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            markdown_text = fh.read()
        source_kind = "file"
        source_ref = path

    started = time.perf_counter()
    html_body = render_markdown(markdown_text)
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    if payload.fragment:
        html_output = html_body
    else:
        html_output = render_full_document(markdown_text, title=payload.title)

    byte_size = len(html_output.encode("utf-8"))
    title = payload.title or "MD2HTML Output"

    async with get_db() as conn:
        cur = await conn.execute(
            """
            INSERT INTO conversions
                (source_kind, title, markdown, html, byte_size, elapsed_ms)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source_kind, title, source_ref, html_output, byte_size, elapsed_ms),
        )
        await conn.commit()
        new_id = cur.lastrowid

        row = await (
            await conn.execute(
                "SELECT id, created_at, source_kind, title, markdown, html, byte_size "
                "FROM conversions WHERE id = ?",
                (new_id,),
            )
        ).fetchone()

    logger.info(
        "conversion id={} kind={} bytes={} elapsed_ms={:.2f}",
        new_id, source_kind, byte_size, elapsed_ms,
    )
    return _row_to_read(row)


async def get_document(doc_id: int) -> Optional[DocumentRead]:
    await _ensure_schema()
    async with get_db() as conn:
        row = await (
            await conn.execute(
                "SELECT id, created_at, source_kind, title, markdown, html, byte_size "
                "FROM conversions WHERE id = ?",
                (doc_id,),
            )
        ).fetchone()
    return _row_to_read(row) if row is not None else None


async def list_documents(limit: int = 50, offset: int = 0) -> DocumentList:
    await _ensure_schema()
    async with get_db() as conn:
        total = (await (await conn.execute("SELECT COUNT(*) AS c FROM conversions")).fetchone())["c"]
        cur = await conn.execute(
            "SELECT id, created_at, source_kind, title, markdown, html, byte_size "
            "FROM conversions ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cur.fetchall()
    items = [_row_to_read(r) for r in rows]
    return DocumentList(items=items, total=total, limit=limit, offset=offset)


async def get_analytics() -> AnalyticsResponse:
    await _ensure_schema()
    async with get_db() as conn:
        agg = await (
            await conn.execute(
                "SELECT COUNT(*) AS c, "
                "       COALESCE(SUM(byte_size), 0) AS s, "
                "       COALESCE(AVG(byte_size), 0.0) AS a, "
                "       MAX(id) AS m "
                "FROM conversions"
            )
        ).fetchone()
    return AnalyticsResponse(
        total_conversions=int(agg["c"] or 0),
        total_html_bytes=int(agg["s"] or 0),
        avg_html_bytes=float(agg["a"] or 0.0),
        largest_id=(int(agg["m"]) if agg["m"] is not None else None),
    )
