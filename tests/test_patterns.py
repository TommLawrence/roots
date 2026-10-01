"""Deterministic pattern detection - findings must cite resolvable evidence."""

from longview_mcp import patterns


def test_decline_detected_with_citations(db):
    findings = [f for f in patterns.analyse(db, "L100") if f["pattern_type"] == "decline"]
    assert findings, "declining reader must be detected"
    reading = [f for f in findings if f["skill"] == "reading"][0]
    assert reading["total_drop"] >= 12
    assert reading["from_term"] == "Y1T1" and reading["to_term"] == "Y1T3"
    assert len(reading["evidence_ids"]) == 12          # 3 terms x 4 quizzes
    for eid in reading["evidence_ids"]:
        assert db.execute("SELECT 1 FROM raw_events WHERE id=?", (eid,)).fetchone()


def test_no_decline_false_positive_on_steady_learner(db):
    findings = [f for f in patterns.analyse(db, "L101") if f["pattern_type"] == "decline"]
    assert findings == []


def test_strength_detected(db):
    findings = [f for f in patterns.analyse(db, "L100")
                if f["pattern_type"] == "sustained_strength"]
    assert findings, "geometry strength must be detected"
    f = findings[0]
    assert f["skill"] == "geometry" and f["mean_over_span"] >= 80


def test_attendance_risk_window(db):
    findings = [f for f in patterns.analyse(db, "L100")
                if f["pattern_type"] == "attendance_risk"]
    assert findings, "5-week attendance crisis must be detected"
    f = findings[0]
    assert f["from_week"] == 2 and f["to_week"] == 6
    assert f["mean_attendance"] < 0.75


def test_infer_skill_mapping():
    assert patterns.infer_skill("geometry quiz 1", "math") == "geometry"
    assert patterns.infer_skill("reading comprehension", "english") == "reading"
    assert patterns.infer_skill("arithmetic quiz", "math") == "arithmetic"


def test_infer_skill_refuses_to_guess_kiswahili():
    """The E11 known failure: unrecognisable note -> unknown_skill, never a guess."""
    assert patterns.infer_skill("anahitaji msaada wa kuosma kwa sauti", "kiswahili") == \
        "unknown_skill"
