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


# ------------------------------------------------------------------ hash chain

def test_audit_chain_verifies(db):
    from longview_mcp import auditchain
    core.ingest_result(db, "tester", "L101", "quiz", "math", "Y2T1", value=70.0,
                       detail="arithmetic quiz 3")
    v = auditchain.verify(db)
    assert v["ok"] and v["rows"] > 0 and v["first_bad_id"] is None


def test_audit_chain_detects_field_tampering(db):
    from longview_mcp import auditchain
    core.ingest_result(db, "tester", "L101", "quiz", "math", "Y2T1", value=70.0,
                       detail="arithmetic quiz 3")
    victim = db.execute("SELECT MIN(id) i FROM audit_log").fetchone()["i"]
    db.execute("UPDATE audit_log SET result='{\"hacked\": true}' WHERE id=?", (victim,))
    db.commit()
    v = auditchain.verify(db)
    assert not v["ok"] and v["first_bad_id"] == victim
    assert "edited" in v["reason"] or "hash" in v["reason"]


def test_audit_chain_detects_deletion(db):
    from longview_mcp import auditchain
    res = core.ingest_result(db, "tester", "L101", "quiz", "math", "Y2T1", value=70.0,
                             detail="arithmetic quiz 3")
    core.update_profile(db, "tester", "L101", "strength", "solid score",
                        [res["event_id"]])
    mid = db.execute("SELECT MIN(id) i FROM audit_log").fetchone()["i"]
    db.execute("DELETE FROM audit_log WHERE id=?", (mid,))
    db.commit()
    v = auditchain.verify(db)
    assert not v["ok"] and v["first_bad_id"] == mid + 1
    assert "link" in v["reason"]


def test_backfill_chains_legacy_rows(tmp_path):
    """A database written before the hash columns must migrate on connect()."""
    from longview_mcp import auditchain
    from longview_mcp.db import connect
    p = tmp_path / "legacy.db"
    conn = connect(str(p))
    conn.execute("INSERT INTO learners (id, name) VALUES ('L101', 'Baraka O.')")
    conn.execute("INSERT INTO audit_log (ts, actor, tool, args, result) "
                 "VALUES ('2026-01-01T00:00:00+00:00','legacy','ingest_result','{}','{}')")
    conn.execute("UPDATE audit_log SET prev_hash=NULL, entry_hash=NULL")
    conn.commit()
    conn.close()
    conn2 = connect(str(p))                      # migration must backfill the chain
    n_hashed = conn2.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE entry_hash IS NOT NULL").fetchone()["c"]
    assert n_hashed == 1
    assert auditchain.verify(conn2)["ok"]
    # new writes continue the same chain
    core.ingest_result(conn2, "tester", "L101", "quiz", "math", "Y2T1", value=71.0,
                       detail="arithmetic quiz 4")
    assert auditchain.verify(conn2)["ok"]
