"""Core tool logic for the Longview MCP server.

Pure stdlib. No MCP runtime, no LLM required (summary drafting falls back to a
deterministic template). The human gate and the citation rule are enforced HERE,
in code - not in prompts.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

from .db import connect, default_db_path
from . import patterns


class UnsourcedClaimError(ValueError):
    """A profile claim was attempted with no resolvable evidence."""


class ApprovalRequiredError(PermissionError):
    """An irreversible action was attempted without an approved gate."""


class NotFoundError(LookupError):
    """Referenced learner / event / record does not exist."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def audit(conn: sqlite3.Connection, actor: str, tool: str, args: dict, result) -> int:
    cur = conn.execute(
        "INSERT INTO audit_log (ts, actor, tool, args, result) VALUES (?,?,?,?,?)",
        (_now(), actor, tool, json.dumps(args, default=str), json.dumps(result, default=str)),
    )
    conn.commit()
    return cur.lastrowid


# ---------------------------------------------------------------- ingest

VALID_KINDS = ("quiz", "assignment", "attendance", "note")


def ingest_result(conn: sqlite3.Connection, actor: str, learner_id: str, kind: str,
                  subject: str, term: str, value=None, skill: str | None = None,
                  detail: str | None = None, week: int | None = None,
                  source_ref: str | None = None, event_date: str | None = None,
                  recorded_at: str | None = None) -> dict:
    if kind not in VALID_KINDS:
        raise ValueError(f"kind must be one of {VALID_KINDS}, got {kind!r}")
    if not conn.execute("SELECT 1 FROM learners WHERE id=?", (learner_id,)).fetchone():
        raise NotFoundError(f"unknown learner {learner_id!r}")
    if skill is None:
        skill = patterns.infer_skill(detail or "", subject)
    if source_ref is None:
        source_ref = f"{kind}:{term}:{subject}" + (f":w{week:02d}" if week else "")
    cur = conn.execute(
        """INSERT INTO raw_events
           (learner_id, kind, subject, skill, term, week, value, detail,
            source_ref, event_date, recorded_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (learner_id, kind, subject, skill, term, week, value, detail,
         source_ref, event_date or term, recorded_at or _now()),
    )
    conn.commit()
    result = {"event_id": cur.lastrowid, "skill": skill, "source_ref": source_ref}
    audit(conn, actor, "ingest_result",
          {"learner_id": learner_id, "kind": kind, "subject": subject, "term": term,
           "value": value, "source_ref": source_ref}, result)
    return result


# ---------------------------------------------------------------- profile

def _validate_evidence(conn: sqlite3.Connection, evidence_ids: list[int]) -> list[int]:
    ids = [int(e) for e in (evidence_ids or [])]
    if not ids:
        raise UnsourcedClaimError(
            "refused: a claim about a learner needs at least one evidence id "
            "(an unsourced label is worse than no label)")
    missing = [e for e in ids if not conn.execute(
        "SELECT 1 FROM raw_events WHERE id=?", (e,)).fetchone()]
    if missing:
        raise UnsourcedClaimError(f"refused: evidence ids not found in records: {missing}")
    return ids


def update_profile(conn: sqlite3.Connection, actor: str, learner_id: str, kind: str,
                   claim: str, evidence_ids: list[int], term_span: str | None = None) -> dict:
    if kind not in ("strength", "weakness", "note"):
        raise ValueError("kind must be strength | weakness | note")
    try:
        ids = _validate_evidence(conn, evidence_ids)
    except UnsourcedClaimError as e:
        # Refusals are audited too: an attempted unsourced label on a child
        # is exactly what the audit log exists to catch.
        audit(conn, actor, "update_profile",
              {"learner_id": learner_id, "kind": kind, "claim": claim,
               "evidence_ids": evidence_ids}, {"refused": str(e)})
        raise
    cur = conn.execute(
        """INSERT INTO profile_entries
           (learner_id, kind, claim, evidence_ids, term_span, created_at, created_by)
           VALUES (?,?,?,?,?,?,?)""",
        (learner_id, kind, claim, json.dumps(ids), term_span, _now(), actor),
    )
    conn.commit()
    result = {"profile_entry_id": cur.lastrowid, "evidence_ids": ids}
    audit(conn, actor, "update_profile",
          {"learner_id": learner_id, "kind": kind, "claim": claim}, result)
    return result


def flag_pattern(conn: sqlite3.Connection, actor: str, learner_id: str, pattern_type: str,
                 rationale: str, evidence_ids: list[int]) -> dict:
    ids = _validate_evidence(conn, evidence_ids)
    cur = conn.execute(
        """INSERT INTO flags
           (learner_id, pattern_type, rationale, evidence_ids, status, created_at, created_by)
           VALUES (?,?,?,?, 'pending_review', ?, ?)""",
        (learner_id, pattern_type, rationale, json.dumps(ids), _now(), actor),
    )
    conn.commit()
    result = {"flag_id": cur.lastrowid, "status": "pending_review", "evidence_ids": ids}
    audit(conn, actor, "flag_pattern",
          {"learner_id": learner_id, "pattern_type": pattern_type}, result)
    return result


def get_learner_profile(conn: sqlite3.Connection, learner_id: str) -> dict:
    learner = conn.execute("SELECT * FROM learners WHERE id=?", (learner_id,)).fetchone()
    if not learner:
        raise NotFoundError(f"unknown learner {learner_id!r}")
    entries = []
    for row in conn.execute(
            "SELECT * FROM profile_entries WHERE learner_id=? ORDER BY created_at", (learner_id,)):
        ids = json.loads(row["evidence_ids"])
        evidence = [dict(e) for e in conn.execute(
            "SELECT id, kind, subject, skill, term, value, source_ref FROM raw_events "
            f"WHERE id IN ({','.join('?' * len(ids))}) ORDER BY id", ids)]
        entries.append({
            "id": row["id"], "kind": row["kind"], "claim": row["claim"],
            "term_span": row["term_span"], "created_by": row["created_by"],
            "evidence": evidence,
        })
    flags = [dict(r) for r in conn.execute(
        "SELECT id, pattern_type, rationale, status, created_at FROM flags "
        "WHERE learner_id=? ORDER BY created_at", (learner_id,))]
    return {"learner": dict(learner), "profile_entries": entries, "flags": flags}


# ---------------------------------------------------------------- summaries

def collect_summary_facts(conn: sqlite3.Connection, learner_id: str) -> dict:
    profile = get_learner_profile(conn, learner_id)
    findings = patterns.analyse(conn, learner_id)
    numbers = set()
    for e in profile["profile_entries"]:
        for ev in e["evidence"]:
            if ev["value"] is not None:
                numbers.add(round(float(ev["value"]), 1))
    for f in findings:
        for key in ("first_mean", "last_mean", "total_drop", "mean_over_span",
                    "mean_attendance", "from_week", "to_week", "weeks_below"):
            if key in f:
                numbers.add(round(float(f[key]), 1))
    return {"profile": profile, "findings": findings, "allowed_numbers": sorted(numbers)}


def _template_summary(facts: dict) -> str:
    learner = facts["profile"]["learner"]
    lines = [
        f"Draft for {learner['name']}'s guardian - please use this to open a "
        f"conversation with {learner['name']}'s teacher. This is a summary of "
        f"recorded work, not a verdict on the child.",
    ]
    for f in facts["findings"]:
        if f["pattern_type"] == "sustained_strength":
            lines.append(f"- Kept doing well in {f['skill']}: {f['rationale']} Worth talking about together.")
        elif f["pattern_type"] == "decline":
            lines.append(f"- {f['skill']} has been slipping: {f['rationale']} The teacher would like to discuss what might help.")
        elif f["pattern_type"] == "attendance_risk":
            lines.append(f"- Missed some school: {f['rationale']} Worth checking in on.")
    if len(lines) == 1:
        lines.append("- No strong pattern has surfaced yet in the recorded work so far.")
    lines.append("Every point above comes from recorded quizzes, assignments, or the register - ask the teacher to see them.")
    return "\n".join(lines)


def draft_summary(conn: sqlite3.Connection, actor: str, learner_id: str,
                  use_llm: bool = True) -> dict:
    facts = collect_summary_facts(conn, learner_id)
    body = None
    source = "template"
    if use_llm:
        from . import llm  # lazy import keeps stdlib-only paths testable
        body = llm.summarize(facts)
        if body:
            source = f"llm:{os.environ.get('LONGVIEW_MODEL', 'local')}"
    if not body:
        body = _template_summary(facts)
    evidence_map = {
        "findings": [{"pattern_type": f["pattern_type"], "skill": f.get("skill"),
                      "evidence_ids": f["evidence_ids"]} for f in facts["findings"]],
        "profile_entry_ids": [e["id"] for e in facts["profile"]["profile_entries"]],
    }
    cur = conn.execute(
        """INSERT INTO summaries (learner_id, body, evidence_map, status, created_at, created_by)
           VALUES (?,?,?, 'draft', ?, ?)""",
        (learner_id, body, json.dumps(evidence_map), _now(), actor),
    )
    conn.commit()
    result = {"summary_id": cur.lastrowid, "source": source}
    audit(conn, actor, "draft_summary", {"learner_id": learner_id, "source": source}, result)
    return result


# ---------------------------------------------------------------- approvals / gate

def request_approval(conn: sqlite3.Connection, actor: str, action: str, payload: dict) -> dict:
    cur = conn.execute(
        "INSERT INTO approvals (action, payload, status, requested_at) VALUES (?,?,'pending',?)",
        (action, json.dumps(payload), _now()),
    )
    conn.commit()
    result = {"approval_id": cur.lastrowid, "status": "pending"}
    audit(conn, actor, "request_approval", {"action": action, "payload": payload}, result)
    return result


def resolve_approval(conn: sqlite3.Connection, actor: str, approval_id: int, decision: str,
                     decided_by: str, note: str | None = None) -> dict:
    if decision not in ("approved", "rejected"):
        raise ValueError("decision must be approved | rejected")
    if not decided_by or not decided_by.strip():
        raise ValueError("a named human must approve - decided_by cannot be empty")
    row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
    if not row:
        raise NotFoundError(f"unknown approval {approval_id}")
    if row["status"] != "pending":
        raise ValueError(f"approval {approval_id} already {row['status']}")
    conn.execute(
        "UPDATE approvals SET status=?, decided_by=?, decided_at=?, note=? WHERE id=?",
        (decision, decided_by.strip(), _now(), note, approval_id),
    )
    conn.commit()
    result = {"approval_id": approval_id, "status": decision, "decided_by": decided_by.strip()}
    audit(conn, actor, "resolve_approval", {"approval_id": approval_id, "decision": decision,
                                            "decided_by": decided_by}, result)
    return result


def share_summary(conn: sqlite3.Connection, actor: str, summary_id: int,
                  channel: str = "sms_to_guardian") -> dict:
    """The ONLY path out of the classroom. Hard-gated on an approved, named-human decision."""
    row = conn.execute("SELECT * FROM summaries WHERE id=?", (summary_id,)).fetchone()
    if not row:
        raise NotFoundError(f"unknown summary {summary_id}")
    approval = conn.execute(
        """SELECT * FROM approvals WHERE action='share_summary'
           AND status='approved'
           AND json_extract(payload, '$.summary_id')=? ORDER BY id DESC""",
        (summary_id,)).fetchone()
    if not approval:
        raise ApprovalRequiredError(
            f"refused: sharing summary {summary_id} needs an approved gate "
            f"(request_approval, then a named teacher approves in the review UI)")
    conn.execute("UPDATE summaries SET status='shared' WHERE id=?", (summary_id,))
    conn.commit()
    result = {"summary_id": summary_id, "status": "shared", "channel": channel,
              "approved_by": approval["decided_by"]}
    audit(conn, actor, "share_summary", {"summary_id": summary_id, "channel": channel}, result)
    return result


# ---------------------------------------------------------------- convenience

def open_db(db_path: str | None = None) -> sqlite3.Connection:
    return connect(db_path or default_db_path())
