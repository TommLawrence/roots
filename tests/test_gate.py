"""The human gate - nothing leaves the classroom without a named human."""

import pytest

from longview_mcp import core


def test_share_refused_without_approval(db):
    res = core.draft_summary(db, "test", "L100", use_llm=False)
    with pytest.raises(core.ApprovalRequiredError):
        core.share_summary(db, "test", res["summary_id"])


def test_approval_requires_named_human(db):
    req = core.request_approval(db, "test", "share_summary", {"summary_id": 1})
    with pytest.raises(ValueError):
        core.resolve_approval(db, "test", req["approval_id"], "approved", "   ")


def test_wrong_decision_word_refused(db):
    req = core.request_approval(db, "test", "share_summary", {"summary_id": 1})
    with pytest.raises(ValueError):
        core.resolve_approval(db, "test", req["approval_id"], "sure, go ahead", "Ms. W")


def test_rejected_approval_blocks_share(db):
    res = core.draft_summary(db, "test", "L100", use_llm=False)
    req = core.request_approval(db, "test", "share_summary", {"summary_id": res["summary_id"]})
    core.resolve_approval(db, "test", req["approval_id"], "rejected", "Ms. Wanjiru",
                          note="family prefers in-person chat")
    with pytest.raises(core.ApprovalRequiredError):
        core.share_summary(db, "test", res["summary_id"])


def test_approved_gate_unlocks_share_exactly_once(db):
    res = core.draft_summary(db, "test", "L100", use_llm=False)
    req = core.request_approval(db, "test", "share_summary", {"summary_id": res["summary_id"]})
    core.resolve_approval(db, "test", req["approval_id"], "approved", "Mr. Otieno")
    shared = core.share_summary(db, "test", res["summary_id"])
    assert shared["approved_by"] == "Mr. Otieno"
    row = db.execute("SELECT status FROM summaries WHERE id=?",
                     (res["summary_id"],)).fetchone()
    assert row["status"] == "shared"


def test_flags_start_pending_and_never_auto_share(db):
    event_ids = [r["id"] for r in db.execute(
        "SELECT id FROM raw_events WHERE learner_id='L100' AND skill='reading' LIMIT 4")]
    flag = core.flag_pattern(db, "test", "L100", "decline", "reading is slipping",
                             event_ids)
    row = db.execute("SELECT status FROM flags WHERE id=?", (flag["flag_id"],)).fetchone()
    assert row["status"] == "pending_review"
