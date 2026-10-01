"""Shared fixtures: a small, handcrafted, fully deterministic records DB."""

import pytest

from longview_mcp.db import connect


@pytest.fixture()
def db(tmp_path):
    """Handcrafted cohort:
    L100 - declining reader (80 -> 74 -> 65 across 3 terms), strong at geometry,
           attendance crisis for 5 weeks in Y2T1.
    L101 - steady average (no patterns).
    """
    conn = connect(str(tmp_path / "test.db"))
    conn.execute("INSERT INTO learners (id, name, guardian, cohort_year) VALUES "
                 "('L100', 'Amina K.', 'Mama Amina', 2022)")
    conn.execute("INSERT INTO learners (id, name, guardian, cohort_year) VALUES "
                 "('L101', 'Baraka O.', 'Baba Baraka', 2022)")

    def quiz(lid, term, subject, skill, score, q):
        conn.execute(
            "INSERT INTO raw_events (learner_id, kind, subject, skill, term, value, detail, "
            "source_ref, event_date, recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (lid, "quiz", subject, skill, term, score, f"{skill} quiz {q}",
             f"quiz:{term}:{subject}:{skill}:q{q}", term, term))

    def attend(lid, term, week, value):
        conn.execute(
            "INSERT INTO raw_events (learner_id, kind, subject, skill, term, week, value, "
            "source_ref, event_date, recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (lid, "attendance", "general", "attendance", term, week, value,
             f"register:{term}:w{week:02d}", term, term))

    # L100: declining reading
    for q, s in enumerate((80, 79, 81, 80), 1):
        quiz("L100", "Y1T1", "english", "reading", s, q)
    for q, s in enumerate((74, 75, 73, 74), 1):
        quiz("L100", "Y1T2", "english", "reading", s, q)
    for q, s in enumerate((66, 65, 64, 65), 1):
        quiz("L100", "Y1T3", "english", "reading", s, q)
    # L100: sustained geometry strength
    for ti, term in enumerate(("Y1T1", "Y1T2", "Y1T3"), 1):
        for q, s in enumerate((85 + ti, 86 + ti, 84 + ti), 1):
            quiz("L100", term, "math", "geometry", s, q)
    # L100: attendance crisis, Y2T1 weeks 2-6
    for w in range(1, 11):
        attend("L100", "Y2T1", w, 0.3 if 2 <= w <= 6 else 0.95)
    # L100: Kiswahili note (skill mapper must refuse to guess)
    conn.execute(
        "INSERT INTO raw_events (learner_id, kind, subject, skill, term, detail, source_ref, "
        "event_date, recorded_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("L100", "note", "kiswahili", "conduct", "Y1T2",
         "anahitaji msaada wa kuosma kwa sauti", "notebook:L100:Y1T2:555", "Y1T2", "Y1T2"))

    # L101: steady average
    for term in ("Y1T1", "Y1T2", "Y1T3"):
        for q, s in enumerate((68, 69, 67, 70), 1):
            quiz("L101", term, "english", "reading", s, q)
            quiz("L101", term, "math", "geometry", s - 1, q)
        for w in range(1, 11):
            attend("L101", term, w, 0.95)

    conn.commit()
    yield conn
    conn.close()
