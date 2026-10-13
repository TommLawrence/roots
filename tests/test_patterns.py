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


def test_infer_skill_kiswahili_vocabulary():
    """Plain Kiswahili remark-book phrases map to skills (exact word match)."""
    assert patterns.infer_skill("alikuwa anasoma vizuri", "kiswahili") == "reading"
    assert patterns.infer_skill("anaandika insha nzuri", "kiswahili") == "writing"
    assert patterns.infer_skill("nzuri kwa hesabu", "hisabati") == "arithmetic"
    assert patterns.infer_skill("anapenda maumbo na jiometri", "hisabati") == "geometry"


def test_infer_skill_recovers_typoed_kiswahili():
    """The E11 fix: "kuosma" is a typo of "kusoma" (reading). The fuzzy token
    pass (difflib cutoff 0.80) recovers it deterministically - no ML, no LLM."""
    assert patterns.infer_skill("anahitaji msaada wa kuosma", "kiswahili") == "reading"
    # the full original E11 note (also contains the exact word "sauti")
    assert patterns.infer_skill("anahitaji msaada wa kuosma kwa sauti", "kiswahili") == \
        "reading"


def test_infer_skill_stays_conservative_on_gibberish():
    """The guardrail behind the E11 fix: no recognisable signal -> unknown_skill,
    never a guess. A wrong auto-label on a child is worse than no label."""
    assert patterns.infer_skill("anahitaji msaada sasa hivi tafadhali", "kiswahili") == \
        "unknown_skill"
    assert patterns.infer_skill("", "kiswahili") == "unknown_skill"
