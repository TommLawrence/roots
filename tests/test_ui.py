"""The review UI: pages render, the gate works end-to-end, refusals surface."""

import pytest
from fastapi.testclient import TestClient

from longview_mcp import core


@pytest.fixture()
def client(db, tmp_path, monkeypatch):
    """TestClient pointed at the same handcrafted DB the fixture built."""
    monkeypatch.setenv("LONGVIEW_DB", str(tmp_path / "test.db"))
    from ui.app import app
    return TestClient(app)


def test_dashboard_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Flags awaiting review" in r.text
    assert "Sharing gate" in r.text


def test_roster_lists_cohort(client):
    r = client.get("/learners")
    assert r.status_code == 200
    assert "L100" in r.text and "Amina K." in r.text


def test_learner_page_shows_trends_and_404(client, db):
    r = client.get("/learner/L100")
    assert r.status_code == 200
    assert "Amina K." in r.text
    assert "<svg" in r.text                       # score trend sparklines
    assert "attendance" in r.text                 # attendance series rendered
    assert client.get("/learner/NOPE").status_code == 404


def test_learner_page_shows_cited_profile(client, db):
    ids = [r["id"] for r in db.execute(
        "SELECT id FROM raw_events WHERE learner_id='L100' AND skill='reading' LIMIT 2")]
    core.update_profile(db, "agent", "L100", "weakness",
                        "Reading scores have dropped across terms", ids)
    r = client.get("/learner/L100")
    assert "Reading scores have dropped across terms" in r.text
    assert f"/evidence?id={ids[0]}" in r.text     # citation chip links to the record


def test_evidence_drilldown_by_id_and_ref(client, db):
    row = db.execute(
        "SELECT id, source_ref FROM raw_events WHERE learner_id='L100' "
        "AND skill='reading' LIMIT 1").fetchone()
    ok = client.get(f"/evidence?id={row['id']}")
    assert ok.status_code == 200 and row["source_ref"] in ok.text
    ok2 = client.get(f"/evidence", params={"ref": row["source_ref"]})
    assert ok2.status_code == 200
    assert client.get("/evidence?id=99999").status_code == 404
    assert client.get("/evidence").status_code == 404


def test_gate_page_shows_summary_and_citations(client, db):
    res = core.draft_summary(db, "test", "L100", use_llm=False)
    req = core.request_approval(db, "test", "share_summary",
                                {"summary_id": res["summary_id"]})
    r = client.get(f"/gate/{req['approval_id']}")
    assert r.status_code == 200
    assert "Approve sharing" in r.text
    assert "quiz:Y1T1:english:reading:q1" in r.text   # the records behind the claims


def test_gate_page_404(client):
    assert client.get("/gate/4242").status_code == 404


def test_full_flow_through_the_ui(client, db):
    """draft -> gate page -> approve with a name -> share -> visible as shared."""
    res = core.draft_summary(db, "test", "L100", use_llm=False)
    sid = res["summary_id"]
    req = core.request_approval(db, "test", "share_summary", {"summary_id": sid})

    # approve without a name is refused and surfaced, not swallowed
    r = client.post("/resolve", data={"approval_id": req["approval_id"],
                                      "decision": "approved", "decided_by": "   "},
                    follow_redirects=False)
    assert "error=" in r.headers["location"]

    # a named human approves
    r = client.post("/resolve", data={"approval_id": req["approval_id"],
                                      "decision": "approved",
                                      "decided_by": "Ms. Wanjiru",
                                      "note": "guardian asked for it"},
                    follow_redirects=False)
    assert "ok=" in r.headers["location"]

    # share still refused before the gate? no - gate is approved now; share works
    r = client.post("/share", data={"summary_id": sid}, follow_redirects=False)
    assert "ok=" in r.headers["location"]
    row = db.execute("SELECT status FROM summaries WHERE id=?", (sid,)).fetchone()
    assert row["status"] == "shared"

    # the dashboard reflects it
    dash = client.get("/").text
    assert "Ms. Wanjiru" in dash


def test_share_without_gate_is_refused_in_ui(client, db):
    res = core.draft_summary(db, "test", "L100", use_llm=False)
    r = client.post("/share", data={"summary_id": res["summary_id"]},
                    follow_redirects=False)
    assert "ApprovalRequiredError" in r.headers["location"]


def test_flag_decision_flow_through_the_ui(client, db):
    ids = [r["id"] for r in db.execute(
        "SELECT id FROM raw_events WHERE learner_id='L100' AND skill='reading' LIMIT 4")]
    flag = core.flag_pattern(db, "agent", "L100", "decline", "reading is slipping", ids)

    r = client.post("/flag/resolve", data={"flag_id": flag["flag_id"],
                                           "decision": "raised",
                                           "decided_by": "Mr. Otieno"},
                    follow_redirects=False)
    assert "ok=" in r.headers["location"]
    row = db.execute("SELECT status, decided_by FROM flags WHERE id=?",
                     (flag["flag_id"],)).fetchone()
    assert (row["status"], row["decided_by"]) == ("raised", "Mr. Otieno")

    # the dashboard no longer lists it as pending, the learner page shows it decided
    assert "reading is slipping" not in client.get("/").text
    page = client.get("/learner/L100").text
    assert "raised by Mr. Otieno" in page


def test_audit_page_lists_decisions(client, db):
    res = core.draft_summary(db, "test", "L100", use_llm=False)
    req = core.request_approval(db, "test", "share_summary",
                                {"summary_id": res["summary_id"]})
    core.resolve_approval(db, "teacher_ui", req["approval_id"], "approved", "Ms. Wanjiru")
    r = client.get("/audit")
    assert r.status_code == 200
    assert "resolve_approval" in r.text and "Ms. Wanjiru" in r.text
    assert client.get("/audit", params={"limit": 10, "offset": 10}).status_code == 200
