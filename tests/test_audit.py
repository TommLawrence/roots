"""Audit log completeness - every tool call leaves a trace."""

import json

from longview_mcp import core


def test_every_write_is_audited(db):
    before = db.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"]
    res = core.ingest_result(db, "tester", "L101", "quiz", "math", "Y1T3", value=72.0,
                             detail="geometry quiz 9")
    core.update_profile(db, "tester", "L101", "strength", "solid geometry score",
                        [res["event_id"]])
    core.flag_pattern(db, "tester", "L101", "sustained_strength", "steady maths",
                      [res["event_id"]])
    rows = db.execute("SELECT * FROM audit_log WHERE id > ?", (before,)).fetchall()
    assert len(rows) == 3
    for r in rows:
        assert r["ts"] and r["actor"] == "tester"
        assert r["tool"] in ("ingest_result", "update_profile", "flag_pattern")
        assert json.loads(r["args"]) and json.loads(r["result"])


def test_draft_and_gate_actions_audited(db):
    before = db.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"]
    res = core.draft_summary(db, "tester", "L101", use_llm=False)
    req = core.request_approval(db, "tester", "share_summary",
                                {"summary_id": res["summary_id"]})
    core.resolve_approval(db, "tester", req["approval_id"], "approved", "Ms. Wanjiru")
    tools = [r["tool"] for r in db.execute(
        "SELECT tool FROM audit_log WHERE id > ?", (before,))]
    assert tools == ["draft_summary", "request_approval", "resolve_approval"]


def test_audit_survives_share(db):
    res = core.draft_summary(db, "tester", "L101", use_llm=False)
    req = core.request_approval(db, "tester", "share_summary",
                                {"summary_id": res["summary_id"]})
    core.resolve_approval(db, "tester", req["approval_id"], "approved", "Ms. Wanjiru")
    core.share_summary(db, "tester", res["summary_id"])
    row = db.execute(
        "SELECT result FROM audit_log WHERE tool='share_summary' "
        "ORDER BY id DESC LIMIT 1").fetchone()
    assert "approved_by" in json.loads(row["result"])
