"""Teacher review UI - the human gate, visible.

The agent cannot share anything; only a named human typing their name here
unlocks it. Every decision lands in the audit log with a timestamp.
"""

import argparse

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from longview_mcp import core

app = FastAPI(title="Longview - Teacher Review", docs_url=None, redoc_url=None)


def _conn():
    return core.open_db()


def _flag_rows(conn):
    rows = []
    for r in conn.execute(
            """SELECT f.*, l.name FROM flags f JOIN learners l ON l.id = f.learner_id
               WHERE f.status='pending_review' ORDER BY f.created_at DESC LIMIT 20"""):
        rows.append(dict(r))
    return rows


def _gate_rows(conn):
    rows = []
    for a in conn.execute(
            """SELECT * FROM approvals WHERE action='share_summary'
               AND status IN ('pending','approved') ORDER BY id DESC LIMIT 20"""):
        a = dict(a)
        payload = __import__("json").loads(a["payload"])
        s = conn.execute("SELECT s.*, l.name FROM summaries s JOIN learners l ON "
                         "l.id = s.learner_id WHERE s.id=?",
                         (payload.get("summary_id"),)).fetchone()
        a["summary"] = dict(s) if s else None
        rows.append(a)
    return rows


def _shared_rows(conn):
    return [dict(r) for r in conn.execute(
        """SELECT s.*, l.name FROM summaries s JOIN learners l ON l.id = s.learner_id
           WHERE s.status='shared' ORDER BY s.id DESC LIMIT 10""")]


@app.get("/", response_class=HTMLResponse)
def index():
    conn = _conn()
    try:
        from ui.render import render_index
        return render_index(_flag_rows(conn), _gate_rows(conn), _shared_rows(conn))
    finally:
        conn.close()


@app.post("/resolve")
def resolve(approval_id: int = Form(...), decision: str = Form(...),
            decided_by: str = Form(...), note: str = Form("")):
    conn = _conn()
    try:
        try:
            core.resolve_approval(conn, "teacher_ui", approval_id, decision,
                                  decided_by, note or None)
        except Exception as exc:  # surface the refusal, don't crash the UI
            return RedirectResponse(f"/?error={type(exc).__name__}: {exc}", 303)
    finally:
        conn.close()
    return RedirectResponse("/", 303)


@app.post("/share")
def share(summary_id: int = Form(...)):
    conn = _conn()
    try:
        try:
            core.share_summary(conn, "teacher_ui", summary_id)
        except Exception as exc:
            return RedirectResponse(f"/?error={type(exc).__name__}: {exc}", 303)
    finally:
        conn.close()
    return RedirectResponse("/", 303)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
