"""Records inbox: read school file exports through the official filesystem MCP server.

The agent never opens inbox files with its own code. In the MCP path it talks to
the borrowed official `filesystem` server (`npx -y @modelcontextprotocol/server-filesystem
records_inbox/`) over stdio, using list_directory + read_text_file. If Node is not
available on the host, we fall back to a direct read-only listing and SAY SO in the
returned transport label — the pipeline still works offline, honestly labelled.

Every file is ingested at most once: processed exports are renamed to *.done.
"""

import asyncio
import csv
import io
import os
from pathlib import Path

INBOX = Path(__file__).resolve().parent.parent / "records_inbox"

EXPORT_COLUMNS = {"learner_id", "kind", "subject", "skill", "term", "value"}


# ------------------------------------------------------------------ MCP path

def _fs_transport():
    from fastmcp.client.transports import StdioTransport

    return StdioTransport("npx", ["-y", "@modelcontextprotocol/server-filesystem",
                                 str(INBOX)])


async def _list_via_fs_mcp_async() -> list[str]:
    from fastmcp import Client

    async with Client(_fs_transport()) as client:
        result = await client.call_tool("list_directory", {"path": str(INBOX)})
        text = "".join(getattr(c, "text", "") for c in result.content)
    # listing lines look like: "[FILE] sample_term_export.csv" / "[DIR] sub"
    return [ln.split("]", 1)[-1].strip() for ln in text.splitlines() if ln.strip()]


async def _read_via_fs_mcp_async(name: str) -> str:
    from fastmcp import Client

    async with Client(_fs_transport()) as client:
        result = await client.call_tool("read_text_file", {"path": str(INBOX / name)})
        return "".join(getattr(c, "text", "") for c in result.content)


def _list_via_filesystem_mcp() -> tuple[list[str], str]:
    """List the inbox through the official filesystem MCP server (stdio/npx)."""
    entries = asyncio.run(asyncio.wait_for(_list_via_fs_mcp_async(), timeout=60))
    return entries, "official filesystem MCP server (stdio/npx)"


def _read_via_filesystem_mcp(name: str) -> str:
    return asyncio.run(asyncio.wait_for(_read_via_fs_mcp_async(name), timeout=60))


# ------------------------------------------------------------------ fallback

def _list_fallback() -> tuple[list[str], str]:
    entries = sorted(p.name + ("/" if p.is_dir() else "") for p in INBOX.iterdir())
    return entries, "direct read-only listing (filesystem MCP server unavailable)"


def _read_fallback(name: str) -> str:
    return (INBOX / name).read_text(encoding="utf-8")


# ------------------------------------------------------------------ public API

def list_inbox() -> tuple[list[str], str]:
    """Entries of the inbox plus which transport served them."""
    try:
        return _list_via_filesystem_mcp()
    except Exception:
        return _list_fallback()


def parse_export(text: str, source_name: str) -> list[dict]:
    """Parse one term-export CSV into trigger dicts (validated, order kept)."""
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        return []
    missing = EXPORT_COLUMNS - set(rows[0].keys())
    if missing:
        raise ValueError(f"{source_name}: missing columns {sorted(missing)}")
    triggers = []
    for i, r in enumerate(rows):
        if not (r.get("learner_id") or "").strip():
            continue
        triggers.append({
            "learner_id": r["learner_id"].strip(),
            "kind": (r.get("kind") or "quiz").strip(),
            "subject": (r.get("subject") or "unknown").strip(),
            "skill": (r.get("skill") or None) or None,
            "term": (r.get("term") or "").strip(),
            "value": float(r["value"]) if (r.get("value") or "").strip() else None,
            "detail": (r.get("detail") or "").strip() or f"imported from {source_name}",
            "source_ref": (r.get("source_ref") or source_name).strip(),
        })
    return triggers


def next_pending_export() -> tuple[str, list[dict], str] | tuple[None, None, str]:
    """Find the first pending *.csv export; return (name, triggers, transport)."""
    entries, transport = list_inbox()
    for entry in entries:
        name = entry.rstrip("/")
        if not name.endswith(".csv") or name.endswith(".done.csv"):
            continue
        if (INBOX / (name + ".done")).exists():
            continue
        try:
            text = _read_via_filesystem_mcp(name)
        except Exception:
            text = _read_fallback(name)
        return name, parse_export(text, name), transport
    return None, None, transport


def mark_done(name: str) -> None:
    (INBOX / name).rename(INBOX / (name + ".done"))
