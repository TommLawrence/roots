"""Citation integrity - the one rule that is not negotiable."""

import pytest

from longview_mcp import core


def test_unsourced_claim_refused_empty(db):
    with pytest.raises(core.UnsourcedClaimError):
        core.update_profile(db, "test", "L100", "strength", "great at reading", [])


def test_unsourced_claim_refused_phantom_evidence(db):
    with pytest.raises(core.UnsourcedClaimError):
        core.update_profile(db, "test", "L100", "strength", "great at reading", [999999])


def test_refusal_is_audited(db):
    before = db.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"]
    with pytest.raises(core.UnsourcedClaimError):
        core.update_profile(db, "test", "L100", "strength", "great", [])
    row = db.execute("SELECT tool, result FROM audit_log ORDER BY id DESC").fetchone()
    assert db.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"] == before + 1
    assert row["tool"] == "update_profile" and "refused" in row["result"]


def test_cited_entry_stored_and_resolvable(db):
    event_id = db.execute(
        "SELECT id FROM raw_events WHERE source_ref='quiz:Y1T1:english:reading:q1'"
    ).fetchone()["id"]
    entry = core.update_profile(db, "test", "L100", "weakness",
                                "reading scores fell across three terms", [event_id])
    profile = core.get_learner_profile(db, "L100")
    stored = [e for e in profile["profile_entries"] if e["id"] == entry["profile_entry_id"]]
    assert len(stored) == 1
    assert stored[0]["evidence"][0]["source_ref"] == "quiz:Y1T1:english:reading:q1"


def test_unknown_learner_refused(db):
    with pytest.raises(core.NotFoundError):
        core.ingest_result(db, "test", "L999", "quiz", "math", "Y1T1", value=50,
                           detail="geometry quiz")


def test_profile_never_contains_ranking_fields(db):
    """The schema has no field for ranking/scoring a child against classmates."""
    cols = {r[1] for r in db.execute("PRAGMA table_info(profile_entries)")}
    banned = {"rank", "score", "percentile", "track", "band", "level"}
    assert not (cols & banned)
