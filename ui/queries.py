"""Read-only queries for the review UI.

Keeps app.py thin and core.py tool-only. Every function takes an open
sqlite connection and returns plain dicts ready for the renderer.
"""

import json


def _rows(cur):
    return [dict(r) for r in cur]


# ---------------------------------------------------------------- dashboard

def counts(conn) -> dict:
    def one(sql):
        return conn.execute(sql).fetchone()[0]

    return {
        "learners": one("SELECT COUNT(*) FROM learners"),
        "evidence_events": one("SELECT COUNT(*) FROM raw_events"),
        "profile_entries": one("SELECT COUNT(*) FROM profile_entries"),
        "pending_flags": one("SELECT COUNT(*) FROM flags WHERE status='pending_review'"),
        "pending_gates": one(
            "SELECT COUNT(*) FROM approvals WHERE action='share_summary' AND status='pending'"),
        "shared": one("SELECT COUNT(*) FROM summaries WHERE status='shared'"),
        "audit_rows": one("SELECT COUNT(*) FROM audit_log"),
    }


def pending_flags(conn, limit=20):
    return _rows(conn.execute(
        f"""SELECT f.*, l.name FROM flags f JOIN learners l ON l.id = f.learner_id
            WHERE f.status='pending_review'
            ORDER BY f.created_at DESC, f.id DESC LIMIT {int(limit)}"""))


def gates(conn, limit=20):
    """Share-gate approvals with their summary attached (newest first)."""
    out = []
    for a in conn.execute(
            """SELECT * FROM approvals WHERE action='share_summary'
               ORDER BY id DESC LIMIT ?""", (int(limit),)):
        a = dict(a)
        payload = json.loads(a["payload"] or "{}")
        a["summary_id"] = payload.get("summary_id")
        s = conn.execute(
            "SELECT s.*, l.name FROM summaries s JOIN learners l ON l.id = s.learner_id "
            "WHERE s.id=?", (a["summary_id"],)).fetchone()
        a["summary"] = dict(s) if s else None
        out.append(a)
    return out


def recently_shared(conn, limit=10):
    return _rows(conn.execute(
        f"""SELECT s.*, l.name FROM summaries s JOIN learners l ON l.id = s.learner_id
            WHERE s.status='shared' ORDER BY s.id DESC LIMIT {int(limit)}"""))


# ---------------------------------------------------------------- learners

def roster(conn, limit=200):
    return _rows(conn.execute(
        f"""SELECT l.*,
              (SELECT COUNT(*) FROM flags f
                WHERE f.learner_id=l.id AND f.status='pending_review') AS pending_flags,
              (SELECT COUNT(*) FROM profile_entries p WHERE p.learner_id=l.id) AS entries,
              (SELECT COUNT(*) FROM raw_events r WHERE r.learner_id=l.id) AS events
            FROM learners l ORDER BY l.id LIMIT {int(limit)}"""))


def learner(conn, learner_id: str):
    row = conn.execute("SELECT * FROM learners WHERE id=?", (learner_id,)).fetchone()
    return dict(row) if row else None


def learner_summaries(conn, learner_id: str):
    summaries = _rows(conn.execute(
        """SELECT id, status, created_at, created_by, body FROM summaries
           WHERE learner_id=? ORDER BY id DESC""", (learner_id,)))
    # attach the share-gate decision for each summary, if one exists
    for s in summaries:
        a = conn.execute(
            """SELECT id, status, decided_by, decided_at FROM approvals
               WHERE action='share_summary'
                 AND json_extract(payload, '$.summary_id')=? ORDER BY id DESC LIMIT 1""",
            (s["id"],)).fetchone()
        s["approval"] = dict(a) if a else None
    return summaries


def learner_flags(conn, learner_id: str):
    return _rows(conn.execute(
        "SELECT * FROM flags WHERE learner_id=? ORDER BY id DESC", (learner_id,)))


def _term_key(term: str):
    """Sort key for terms like Y1T1 / Y4T3 (falls back to the raw string)."""
    digits = "".join(ch if ch.isdigit() else " " for ch in str(term)).split()
    nums = [int(d) for d in digits]
    return (nums + [0, 0])[:2] if len(nums) >= 2 else (0, 0), str(term)


def learner_series(conn, learner_id: str) -> dict:
    """Per subject/skill: ordered [(term, mean, n)] for quiz + assignment scores."""
    series: dict[str, list] = {}
    for r in conn.execute(
            """SELECT subject, skill, term, AVG(value) AS mean, COUNT(*) AS n
               FROM raw_events
               WHERE learner_id=? AND value IS NOT NULL
                 AND kind IN ('quiz','assignment')
               GROUP BY subject, skill, term""", (learner_id,)):
        key = f"{r['subject']} / {r['skill']}"
        series.setdefault(key, []).append(
            (r["term"], round(r["mean"], 1), r["n"]))
    for key in series:
        series[key].sort(key=lambda t: _term_key(t[0]))
    return series


def attendance_series(conn, learner_id: str) -> list:
    rows = _rows(conn.execute(
        """SELECT term, AVG(value) AS mean, COUNT(*) AS n FROM raw_events
           WHERE learner_id=? AND kind='attendance' AND value IS NOT NULL
           GROUP BY term""", (learner_id,)))
    rows.sort(key=lambda r: _term_key(r["term"]))
    return [(r["term"], round(r["mean"], 2), r["n"]) for r in rows]


# ---------------------------------------------------------------- evidence

def evidence_by_ids(conn, ids) -> list:
    clean = []
    for e in (ids or []):
        try:
            clean.append(int(e))
        except (TypeError, ValueError):
            continue
    if not clean:
        return []
    q = ",".join("?" * len(clean))
    return _rows(conn.execute(
        f"SELECT * FROM raw_events WHERE id IN ({q}) ORDER BY id", clean))


def evidence_by_ref(conn, ref: str):
    row = conn.execute("SELECT * FROM raw_events WHERE source_ref=?", (ref,)).fetchone()
    return dict(row) if row else None


def evidence_by_id(conn, event_id: int):
    row = conn.execute("SELECT * FROM raw_events WHERE id=?", (int(event_id),)).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------- gate detail

def gate_detail(conn, approval_id: int):
    """Everything a teacher needs on one screen before deciding."""
    a = conn.execute("SELECT * FROM approvals WHERE id=? AND action='share_summary'",
                     (approval_id,)).fetchone()
    if not a:
        return None
    approval = dict(a)
    payload = json.loads(approval["payload"] or "{}")
    summary_id = payload.get("summary_id")
    s = conn.execute(
        "SELECT s.*, l.name, l.guardian FROM summaries s "
        "JOIN learners l ON l.id = s.learner_id WHERE s.id=?", (summary_id,)).fetchone()
    summary = dict(s) if s else None
    evidence_map = json.loads(summary["evidence_map"]) if summary else {}

    findings = []
    for f in evidence_map.get("findings", []):
        findings.append({**f, "evidence": evidence_by_ids(conn, f.get("evidence_ids", []))})

    entries = []
    for eid in evidence_map.get("profile_entry_ids", []):
        row = conn.execute("SELECT * FROM profile_entries WHERE id=?", (eid,)).fetchone()
        if not row:
            continue
        row = dict(row)
        row["evidence"] = evidence_by_ids(conn, json.loads(row["evidence_ids"]))
        entries.append(row)

    return {"approval": approval, "summary": summary, "payload": payload,
            "findings": findings, "profile_entries": entries}


# ---------------------------------------------------------------- audit

def audit_page(conn, limit=50, offset=0):
    limit, offset = max(1, min(int(limit), 200)), max(0, int(offset))
    total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    rows = _rows(conn.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)))
    return rows, total
