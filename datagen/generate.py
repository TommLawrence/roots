"""Synthetic, realistically messy cohort generator.

Messiness on purpose (the challenge brief asks for it):
  - ~6% of quiz rows simply do not exist (never recorded, not zero)
  - results logged 0-21 days late, 5% logged 30-60 days late
  - teacher notes with typos, some blank, ~10% duplicated
  - attendance with whole missing weeks, clustered crises for one persona
  - Kiswahili notes that the skill mapper cannot parse (drives EVALS E11)

All data is synthetic. No real learner anywhere.
"""

import argparse
import json
import random
import sqlite3
import sys
from datetime import date, timedelta

sys.path.insert(0, __file__.rsplit("/", 2)[0])

from longview_mcp.db import connect
from datagen.personas import ALL_SKILLS, FIXED, KISWAHILI_NOTE_POOL, NOTE_POOL, PERSONAS

TERM_STARTS = {}
for y in range(1, 5):
    for t, month in enumerate((1, 5, 9), start=1):
        TERM_STARTS[f"Y{y}T{t}"] = date(2021 + y, month, 10)

FIRST_NAMES = ["Amina", "Baraka", "Chausiku", "David", "Esther", "Fikiri", "Grace",
               "Halima", "Juma", "Kesi", "Laila", "Makena", "Neema", "Otieno",
               "Pili", "Rehema", "Salim", "Wanjiru", "Zawadi", "Kipchumba"]
LAST_INITIALS = "ABCDEFGHJKLMNPQRSTUVWXYZ"


def term_list():
    return [f"Y{y}T{t}" for y in range(1, 5) for t in range(1, 4)]


def typo(text: str, rng: random.Random) -> str:
    if len(text) < 5 or rng.random() > 0.35:
        return text
    i = rng.randrange(1, len(text) - 2)
    chars = list(text)
    chars[i], chars[i + 1] = chars[i + 1], chars[i]
    return "".join(chars)


def event_date(term: str, week: int | None) -> str:
    start = TERM_STARTS[term]
    return (start + timedelta(days=7 * (week or 1) + rng_off(0, 4))).isoformat()


def rng_off(lo: int, hi: int) -> int:
    return random.randrange(lo, hi + 1)


def recorded_at(event_day: str) -> str:
    late = rng_off(0, 21)
    if random.random() < 0.05:
        late = rng_off(30, 60)
    return (date.fromisoformat(event_day) + timedelta(days=late)).isoformat()


def insert_event(conn: sqlite3.Connection, learner_id: str, kind: str, subject: str,
                 skill: str, term: str, value, detail, week, source_ref) -> None:
    day = event_date(term, week)
    conn.execute(
        """INSERT INTO raw_events (learner_id, kind, subject, skill, term, week, value,
           detail, source_ref, event_date, recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (learner_id, kind, subject, skill, term, week, value, detail,
         source_ref, day, recorded_at(day)))


def generate(conn: sqlite3.Connection, n_learners: int, seed: int) -> dict:
    random.seed(seed)
    terms = term_list()
    stats = {"learners": 0, "quizzes": 0, "assignments": 0, "notes": 0,
             "attendance": 0, "missing_quizzes": 0, "late_records": 0}

    for i in range(1, n_learners + 1):
        lid = f"L{i:03d}"
        persona_name = FIXED[i - 1] if i <= len(FIXED) else random.choice(list(PERSONAS))
        persona = PERSONAS[persona_name]
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_INITIALS)}."
        guardian = f"{random.choice(('Mama', 'Baba'))} {name.split()[0]}"
        conn.execute("INSERT INTO learners (id, name, guardian, cohort_year) VALUES (?,?,?,?)",
                     (lid, name, guardian, 2022))
        stats["learners"] += 1

        for ti, term in enumerate(terms):
            # quizzes + assignments
            for skill, subject in ALL_SKILLS.items():
                target = persona(skill, ti)
                for q in range(random.randint(4, 7)):
                    if random.random() < 0.06:          # never recorded at all
                        stats["missing_quizzes"] += 1
                        continue
                    score = round(max(35, min(100, random.gauss(target, 7))), 1)
                    ref = f"quiz:{term}:{subject}:{skill}:q{q + 1}"
                    insert_event(conn, lid, "quiz", subject, skill, term, score,
                                 f"{skill} quiz {q + 1}", None, ref)
                    stats["quizzes"] += 1
                for a in range(random.randint(1, 3)):
                    score = round(max(35, min(100, random.gauss(target, 9))), 1)
                    ref = f"assignment:{term}:{subject}:{skill}:a{a + 1}"
                    insert_event(conn, lid, "assignment", subject, skill, term, score,
                                 f"{skill} assignment {a + 1}", None, ref)
                    stats["assignments"] += 1

            # attendance: 10-13 weeks, mostly 0.9-1.0
            crisis = persona_name == "attendance_crises" and term in ("Y3T1", "Y3T2")
            for w in range(1, random.randint(10, 13) + 1):
                if random.random() < 0.04:               # whole week missing from the register
                    continue
                value = round(random.uniform(0.9, 1.0), 2)
                if crisis and 4 <= w <= 11:
                    value = round(random.uniform(0.1, 0.6), 2)
                insert_event(conn, lid, "attendance", "general", "attendance", term,
                             value, None, w, f"register:{term}:w{w:02d}")
                stats["attendance"] += 1

            # teacher notes (some Kiswahili, some typoed, some blank, some duplicated)
            pool = KISWAHILI_NOTE_POOL if (i % 4 == 0 and random.random() < 0.5) else NOTE_POOL
            for _ in range(random.randint(1, 2)):
                text = random.choice(pool)
                text = typo(text, random)
                if random.random() < 0.15:
                    text = ""                             # blank entry in the notebook
                insert_event(conn, lid, "note", "general", "conduct", term, None,
                             text, None, f"notebook:{lid}:{term}:{rng_off(100, 999)}")
                stats["notes"] += 1
                if random.random() < 0.10:                # accidental duplicate
                    insert_event(conn, lid, "note", "general", "conduct", term, None,
                                 text, None, f"notebook:{lid}:{term}:{rng_off(100, 999)}")
                    stats["notes"] += 1

    conn.commit()
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--learners", type=int, default=80)
    ap.add_argument("--db", default=None)
    args = ap.parse_args()

    from longview_mcp.db import default_db_path
    db_path = args.db or default_db_path()
    conn = connect(db_path)
    stats = generate(conn, args.learners, args.seed)
    counts = {t: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
              for t in ("learners", "raw_events", "profile_entries", "flags",
                        "summaries", "approvals", "audit_log")}
    print(json.dumps({"db": db_path, "generated": stats, "table_counts": counts}, indent=2))
    conn.close()


if __name__ == "__main__":
    main()
