"""Deterministic, transparent longitudinal pattern detection.

No ML black box: every function returns the exact terms, means, and evidence ids
behind a claim, so a teacher can ask "why" and get an answer.
"""

import json
import sqlite3

TERMS = [f"Y{y}T{t}" for y in range(1, 5) for t in range(1, 4)]
TERM_INDEX = {t: i for i, t in enumerate(TERMS)}


def term_sort_key(term: str) -> int:
    return TERM_INDEX.get(term, -1)


def infer_skill(detail: str, subject: str) -> str:
    """Map free text to a skill keyword. Deliberately conservative:
    unrecognised text becomes 'unknown_skill' (see EVALS task E11)."""
    text = (detail or "").lower() + " " + (subject or "").lower()
    checks = [
        (["geometry", "shape", "spatial", "pattern", "block"], "geometry"),
        (["add", "subtract", "multiply", "divide", "number", "arithmetic", "sum"], "arithmetic"),
        (["read", "comprehend", "comprehension", "story", "paragraph"], "reading"),
        (["write", "essay", "composition", "handwrit", "spelling"], "writing"),
        (["reason", "logic", "puzzle", "experiment", "science"], "reasoning"),
    ]
    for keywords, skill in checks:
        if any(k in text for k in keywords):
            return skill
    return "unknown_skill"


def _series(conn: sqlite3.Connection, learner_id: str, skill: str, kinds=("quiz", "assignment")):
    rows = conn.execute(
        f"""SELECT term, AVG(value) AS mean, COUNT(*) AS n, GROUP_CONCAT(id) AS ids
            FROM raw_events
            WHERE learner_id=? AND skill=? AND kind IN ({','.join('?' * len(kinds))})
              AND value IS NOT NULL
            GROUP BY term ORDER BY term""",
        (learner_id, skill, *kinds),
    ).fetchall()
    return [
        {"term": r["term"], "mean": round(r["mean"], 1), "n": r["n"],
         "evidence_ids": [int(x) for x in r["ids"].split(",")]}
        for r in rows
    ]


def detect_decline(conn: sqlite3.Connection, learner_id: str, window: int = 3,
                   min_total_drop: float = 12.0) -> list[dict]:
    """A skill falling >= min_total_drop points across >= `window` consecutive terms.
    Primary rule: window of `window` terms with at most one small uptick.
    Fallback rule: a window+1-term span with a >= 25% larger drop tolerates more wiggle
    (noise in sparse quiz data otherwise hides real multi-term declines)."""
    findings = []
    skills = [r["skill"] for r in conn.execute(
        "SELECT DISTINCT skill FROM raw_events WHERE learner_id=? AND kind IN ('quiz','assignment')",
        (learner_id,))]
    for skill in skills:
        series = _series(conn, learner_id, skill)
        found = None
        if len(series) >= window:
            for start in range(0, len(series) - window + 1):
                chunk = series[start:start + window]
                drop = chunk[0]["mean"] - chunk[-1]["mean"]
                ups = sum(1 for a, b in zip(chunk, chunk[1:]) if b["mean"] > a["mean"])
                if drop >= min_total_drop and ups <= 1:
                    found = (chunk, drop)
                    break
        if found is None and len(series) >= window + 1:
            for start in range(0, len(series) - window):
                chunk = series[start:start + window + 1]
                drop = chunk[0]["mean"] - chunk[-1]["mean"]
                if drop >= min_total_drop * 1.25:
                    found = (chunk, drop)
                    break
        if found is None and len(series) >= 6:
            # Long slow slide: the brief's "pattern obvious over four years, invisible
            # one term at a time". First-3-terms mean vs last-3-terms mean, with a
            # majority of negative deltas so a single crash-and-recover doesn't fire.
            head = series[:3]
            tail = series[-3:]
            drop_full = (sum(s["mean"] for s in head) / 3) - (sum(s["mean"] for s in tail) / 3)
            deltas = [b["mean"] - a["mean"] for a, b in zip(series, series[1:])]
            frac_neg = sum(1 for d in deltas if d < 0) / len(deltas)
            if drop_full >= min_total_drop * 1.25 and frac_neg >= 0.6:
                found = (series, drop_full)
        if found:
            chunk, drop = found
            span = len(chunk)
            findings.append({
                "pattern_type": "decline",
                "skill": skill,
                "from_term": chunk[0]["term"],
                "to_term": chunk[-1]["term"],
                "first_mean": chunk[0]["mean"],
                "last_mean": chunk[-1]["mean"],
                "total_drop": round(drop, 1),
                "evidence_ids": sorted({i for c in chunk for i in c["evidence_ids"]}),
                "rationale": (
                    f"{skill} mean fell from {chunk[0]['mean']} ({chunk[0]['term']}) to "
                    f"{chunk[-1]['mean']} ({chunk[-1]['term']}), a {round(drop, 1)}-point "
                    f"drop over {span} terms."
                ),
            })
    return findings


def detect_strength(conn: sqlite3.Connection, learner_id: str, threshold: float = 80.0,
                    min_terms: int = 3) -> list[dict]:
    """A skill averaging >= threshold across >= min_terms terms."""
    findings = []
    skills = [r["skill"] for r in conn.execute(
        "SELECT DISTINCT skill FROM raw_events WHERE learner_id=? AND kind IN ('quiz','assignment')",
        (learner_id,))]
    for skill in skills:
        series = _series(conn, learner_id, skill)
        strong = [s for s in series if s["mean"] >= threshold]
        if len(strong) >= min_terms:
            findings.append({
                "pattern_type": "sustained_strength",
                "skill": skill,
                "terms": [s["term"] for s in strong],
                "mean_over_span": round(
                    sum(s["mean"] * s["n"] for s in strong) / sum(s["n"] for s in strong), 1),
                "evidence_ids": sorted({i for s in strong for i in s["evidence_ids"]}),
                "rationale": (
                    f"{skill} averaged {round(sum(s['mean'] * s['n'] for s in strong) / sum(s['n'] for s in strong), 1)} "
                    f"across {len(strong)} terms ({strong[0]['term']} to {strong[-1]['term']})."
                ),
            })
    return findings


def detect_attendance_risk(conn: sqlite3.Connection, learner_id: str,
                           window_weeks: int = 4, threshold: float = 0.75) -> list[dict]:
    """A run of >= window_weeks where weekly attendance is below threshold."""
    rows = conn.execute(
        """SELECT id, term, week, value, event_date FROM raw_events
           WHERE learner_id=? AND kind='attendance' AND value IS NOT NULL
           ORDER BY term, week""",
        (learner_id,)).fetchall()
    findings = []
    run: list = []
    for r in rows + [None]:
        if r is not None and r["value"] < threshold:
            run.append(dict(r))
            continue
        if len(run) >= window_weeks:
            ids = [row["id"] for row in run]
            findings.append({
                "pattern_type": "attendance_risk",
                "term": run[0]["term"],
                "from_week": run[0]["week"],
                "to_week": run[-1]["week"],
                "weeks_below": len(run),
                "mean_attendance": round(sum(row["value"] for row in run) / len(run), 2),
                "evidence_ids": ids,
                "rationale": (
                    f"Attendance averaged {round(sum(row['value'] for row in run) / len(run), 2)} "
                    f"below threshold for {len(run)} weeks ({run[0]['term']} weeks "
                    f"{run[0]['week']}-{run[-1]['week']})."
                ),
            })
        run = []
    return findings


def analyse(conn: sqlite3.Connection, learner_id: str) -> list[dict]:
    findings = (
        detect_decline(conn, learner_id)
        + detect_strength(conn, learner_id)
        + detect_attendance_risk(conn, learner_id)
    )
    for f in findings:
        f["evidence_ids_json"] = json.dumps(f["evidence_ids"])
    return findings
