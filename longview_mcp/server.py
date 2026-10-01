"""FastMCP wrapper around longview_mcp.core.

Run standalone (stdio):
    python -m longview_mcp.server
or with HTTP transport:
    LONGVIEW_TRANSPORT=http python -m longview_mcp.server
"""

import os

from fastmcp import FastMCP

from . import core

mcp = FastMCP("longview", instructions=(
    "Longview: longitudinal learner profiling. Every claim must cite evidence ids. "
    "The agent builds sourced profiles and NEVER assigns tracks or labels. "
    "Anything leaving the classroom (share_summary) is hard-gated on a named "
    "human approving via request_approval + the review UI."
))


def _conn():
    return core.open_db()


def _actor() -> str:
    return os.environ.get("LONGVIEW_ACTOR", "agent")


@mcp.tool
def ingest_result(learner_id: str, kind: str, subject: str, term: str,
                  value: float | None = None, skill: str | None = None,
                  detail: str | None = None, week: int | None = None,
                  source_ref: str | None = None, event_date: str | None = None,
                  recorded_at: str | None = None) -> dict:
    """Append one raw record (quiz | assignment | attendance | note) to the learner's history."""
    conn = _conn()
    try:
        return core.ingest_result(conn, _actor(), learner_id, kind, subject, term, value,
                                  skill, detail, week, source_ref, event_date, recorded_at)
    finally:
        conn.close()


@mcp.tool
def update_profile(learner_id: str, kind: str, claim: str,
                   evidence_ids: list[int], term_span: str | None = None) -> dict:
    """Add a cited strength/weakness/note entry. Refuses if evidence_ids is empty or unknown."""
    conn = _conn()
    try:
        return core.update_profile(conn, _actor(), learner_id, kind, claim, evidence_ids, term_span)
    finally:
        conn.close()


@mcp.tool
def flag_pattern(learner_id: str, pattern_type: str, rationale: str,
                 evidence_ids: list[int]) -> dict:
    """Raise a pattern for teacher review (pending_review - never auto-sent anywhere)."""
    conn = _conn()
    try:
        return core.flag_pattern(conn, _actor(), learner_id, pattern_type, rationale, evidence_ids)
    finally:
        conn.close()


@mcp.tool
def get_learner_profile(learner_id: str) -> dict:
    """Full profile with citations: every entry carries its evidence records."""
    conn = _conn()
    try:
        return core.get_learner_profile(conn, learner_id)
    finally:
        conn.close()


@mcp.tool
def analyse_learner(learner_id: str) -> list[dict]:
    """Run deterministic longitudinal analysis: declines, sustained strengths, attendance risk."""
    conn = _conn()
    try:
        return core.patterns.analyse(conn, learner_id)
    finally:
        conn.close()


@mcp.tool
def draft_summary(learner_id: str, use_llm: bool = True) -> dict:
    """Draft a plain-language summary from cited facts only (open-weights model; template fallback)."""
    conn = _conn()
    try:
        return core.draft_summary(conn, _actor(), learner_id, use_llm)
    finally:
        conn.close()


@mcp.tool
def request_approval(action: str, payload: dict) -> dict:
    """Request the human gate for an irreversible action, e.g. action='share_summary'."""
    conn = _conn()
    try:
        return core.request_approval(conn, _actor(), action, payload)
    finally:
        conn.close()


@mcp.tool
def resolve_approval(approval_id: int, decision: str, decided_by: str,
                     note: str | None = None) -> dict:
    """A NAMED human approves/rejects a pending gate (done in the teacher review UI)."""
    conn = _conn()
    try:
        return core.resolve_approval(conn, _actor(), approval_id, decision, decided_by, note)
    finally:
        conn.close()


@mcp.tool
def share_summary(summary_id: int, channel: str = "sms_to_guardian") -> dict:
    """Send a summary to a guardian. BLOCKED unless a named human approved this exact summary."""
    conn = _conn()
    try:
        return core.share_summary(conn, _actor(), summary_id, channel)
    finally:
        conn.close()


if __name__ == "__main__":
    transport = os.environ.get("LONGVIEW_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="http", host="127.0.0.1", port=8100)
    else:
        mcp.run()
