"""Teacher review UI - the human gate, visible.

Pages
  /                dashboard: pending flags, share gates, recently shared
  /learners        roster of the cohort
  /learner/{code}  cited profile, trends, flags, summaries for one learner
  /gate/{id}       the share gate: summary + the records behind every claim
  /evidence?id=N   one raw record (what a citation points at)
  /audit           every tool call, refusal and decision, newest first

Rules that hold here (enforced in core.py, not in this UI):
  - approving / rejecting / raising / dismissing needs a NAMED human,
  - the agent cannot do any of those itself,
  - sharing only works behind an approved gate.

Run:  longview-ui --port 8080      (or: python -m ui.app)
"""

import argparse
import urllib.parse

import uvicorn
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from longview_mcp import core
from ui import queries
from ui.render import (render_404, render_audit, render_dashboard, render_evidence,
                       render_gate, render_learner, render_roster)

app = FastAPI(title="Longview - Teacher Review", docs_url=None, redoc_url=None)

UI_ACTOR = "teacher_ui"


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, 303)


def _back(url: str, error: str | None = None, ok: str | None = None) -> RedirectResponse:
    """Redirect with a flash message (query params, picked up by the page)."""
    params = {}
    if error:
        params["error"] = f"{type(error).__name__}: {error}"
    if ok:
        params["ok"] = ok
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    return _redirect(url)


@app.get("/", response_class=HTMLResponse)
def index(error: str | None = None, ok: str | None = None):
    conn = core.open_db()
    try:
        return render_dashboard(queries.counts(conn), queries.pending_flags(conn),
                                queries.gates(conn), queries.recently_shared(conn),
                                error=error, ok=ok)
    finally:
        conn.close()


@app.get("/learners", response_class=HTMLResponse)
def learners_page():
    conn = core.open_db()
    try:
        return render_roster(queries.roster(conn))
    finally:
        conn.close()


@app.get("/learner/{learner_id}", response_class=HTMLResponse)
def learner_page(learner_id: str, error: str | None = None, ok: str | None = None):
    conn = core.open_db()
    try:
        row = queries.learner(conn, learner_id)
        if not row:
            return HTMLResponse(render_404(f"No learner {learner_id!r} in the cohort."),
                                status_code=404)
        try:
            profile = core.get_learner_profile(conn, learner_id)
        except core.NotFoundError:
            return HTMLResponse(render_404(f"No learner {learner_id!r} in the cohort."),
                                status_code=404)
        return render_learner(row, queries.learner_series(conn, learner_id),
                              queries.attendance_series(conn, learner_id),
                              profile["profile_entries"],
                              queries.learner_flags(conn, learner_id),
                              queries.learner_summaries(conn, learner_id),
                              error=error, ok=ok)
    finally:
        conn.close()


@app.get("/gate/{approval_id}", response_class=HTMLResponse)
def gate_page(approval_id: int, error: str | None = None, ok: str | None = None):
    conn = core.open_db()
    try:
        detail = queries.gate_detail(conn, approval_id)
        if not detail:
            return HTMLResponse(render_404(f"No share gate #{approval_id}."), status_code=404)
        return render_gate(detail, error=error, ok=ok)
    finally:
        conn.close()


@app.get("/evidence", response_class=HTMLResponse)
def evidence_page(id: int | None = None, ref: str | None = None):
    conn = core.open_db()
    try:
        row = queries.evidence_by_id(conn, id) if id is not None else \
            (queries.evidence_by_ref(conn, ref) if ref else None)
        if not row:
            return HTMLResponse(render_404("No such record. Citations must resolve to a "
                                           "raw record - that is the whole point."),
                                status_code=404)
        return render_evidence(row, back_to=f"/learner/{row['learner_id']}")
    finally:
        conn.close()


@app.get("/audit", response_class=HTMLResponse)
def audit_page(limit: int = 50, offset: int = 0):
    limit = max(10, min(limit, 200))
    conn = core.open_db()
    try:
        rows, total = queries.audit_page(conn, limit=limit, offset=offset)
        return render_audit(rows, total, limit, offset)
    finally:
        conn.close()


# ---------------------------------------------------------------- decisions

@app.post("/resolve")
def resolve(approval_id: int = Form(...), decision: str = Form(...),
            decided_by: str = Form(...), note: str = Form("")):
    conn = core.open_db()
    try:
        try:
            core.resolve_approval(conn, UI_ACTOR, approval_id, decision,
                                  decided_by, note or None)
        except Exception as exc:  # surface the refusal - never crash the gate
            return _back(f"/gate/{approval_id}", error=exc)
    finally:
        conn.close()
    label = "approved" if decision == "approved" else "rejected"
    return _back(f"/gate/{approval_id}",
                 ok=f"Gate #{approval_id} {label} by {decided_by.strip()}.")


@app.post("/share")
def share(summary_id: int = Form(...)):
    conn = core.open_db()
    try:
        learner_id = conn.execute("SELECT learner_id FROM summaries WHERE id=?",
                                  (summary_id,)).fetchone()
        try:
            core.share_summary(conn, UI_ACTOR, summary_id)
        except Exception as exc:
            target = f"/learner/{learner_id['learner_id']}" if learner_id else "/"
            return _back(target, error=exc)
    finally:
        conn.close()
    target = f"/learner/{learner_id['learner_id']}" if learner_id else "/"
    return _back(target, ok=f"Summary #{summary_id} sent to the guardian.")


@app.post("/flag/resolve")
def flag_resolve(flag_id: int = Form(...), decision: str = Form(...),
                 decided_by: str = Form(...)):
    conn = core.open_db()
    try:
        row = conn.execute("SELECT learner_id FROM flags WHERE id=?", (flag_id,)).fetchone()
        if not row:
            return HTMLResponse(render_404(f"No flag #{flag_id}."), status_code=404)
        learner_id = row["learner_id"]
        try:
            core.resolve_flag(conn, UI_ACTOR, flag_id, decision, decided_by)
        except Exception as exc:
            return _back(f"/learner/{learner_id}", error=exc)
    finally:
        conn.close()
    return _back(f"/learner/{learner_id}",
                 ok=f"Flag #{flag_id} {decision} by {decided_by.strip()}.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
