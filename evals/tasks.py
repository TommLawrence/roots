"""Eval task definitions.

Every task is a plain function(conn) -> (bool, str detail). Tasks run against a
freshly generated synthetic cohort (fixed seed) so results are reproducible.
Fixed personas: L001 steady_high, L002 declining_reader, L003 hidden_spatial,
L004 attendance_crises, L005 late_bloomer.
"""

import re

from longview_mcp import core, patterns


def _all_evidence_resolve(conn, evidence_ids):
    for e in evidence_ids:
        if not conn.execute("SELECT 1 FROM raw_events WHERE id=?", (e,)).fetchone():
            return False
    return True


# ---------------------------------------------------------------- tasks

def e01_ingest_and_cited_update(conn):
    before = conn.execute("SELECT COUNT(*) c FROM profile_entries").fetchone()["c"]
    res = core.ingest_result(conn, "eval", "L010", "quiz", "math", "Y4T3",
                             value=91.0, detail="geometry quiz 1")
    entry = core.update_profile(conn, "eval", "L010", "strength",
                                "scored 91.0 on the Y4T3 geometry quiz",
                                [res["event_id"]])
    after = conn.execute("SELECT COUNT(*) c FROM profile_entries").fetchone()["c"]
    ids = entry["evidence_ids"]
    ok = (after == before + 1 and _all_evidence_resolve(conn, ids))
    return ok, f"profile entry written with evidence id {ids[0]}, which resolves"


def e02_unsourced_refused(conn):
    before = conn.execute("SELECT COUNT(*) c FROM profile_entries").fetchone()["c"]
    refused = 0
    try:
        core.update_profile(conn, "eval", "L010", "strength", "great at maths", [])
    except core.UnsourcedClaimError:
        refused += 1
    try:
        core.update_profile(conn, "eval", "L010", "strength", "great at maths", [987654])
    except core.UnsourcedClaimError:
        refused += 1
    after = conn.execute("SELECT COUNT(*) c FROM profile_entries").fetchone()["c"]
    return refused == 2 and after == before, "empty and phantom evidence both refused; nothing written"


def e03_decline_detected(conn):
    findings = [f for f in patterns.analyse(conn, "L002") if f["pattern_type"] == "decline"]
    if not findings:
        return False, "no decline found for L002 (expected in reading)"
    f = findings[0]
    ok = (f["skill"] == "reading" and f["total_drop"] >= 12
          and _all_evidence_resolve(conn, f["evidence_ids"]))
    return ok, f"{f['rationale']} ({len(f['evidence_ids'])} evidence ids resolve)"


def e04_strength_detected(conn):
    findings = [f for f in patterns.analyse(conn, "L001")
                if f["pattern_type"] == "sustained_strength"]
    if not findings:
        return False, "no sustained strength found for L001"
    f = findings[0]
    ok = f["mean_over_span"] >= 80 and _all_evidence_resolve(conn, f["evidence_ids"])
    return ok, f"{f['skill']}: {f['rationale']} ({len(f['evidence_ids'])} evidence ids)"


def e05_attendance_risk(conn):
    findings = [f for f in patterns.analyse(conn, "L004")
                if f["pattern_type"] == "attendance_risk"]
    if not findings:
        return False, "no attendance risk found for L004"
    f = findings[0]
    ok = (f["term"] == "Y3T1" and f["weeks_below"] >= 4
          and f["mean_attendance"] < 0.75)
    return ok, f"{f['rationale']} ({len(f['evidence_ids'])} register rows cited)"


def _drafter_mode(conn):
    from longview_mcp import llm
    probe = llm.chat([{"role": "user", "content": "reply with the word: ok"}], timeout=4)
    return "llm" if probe else "template"


def e06_no_invented_numbers(conn):
    facts = core.collect_summary_facts(conn, "L002")
    mode = _drafter_mode(conn)
    summary = core.draft_summary(conn, "eval", "L002", use_llm=(mode == "llm"))
    body = conn.execute("SELECT body FROM summaries WHERE id=?",
                        (summary["summary_id"],)).fetchone()["body"]
    decimals = [round(float(x), 1) for x in re.findall(r"\d+\.\d", body)]
    allowed = set(facts["allowed_numbers"])
    invented = [n for n in decimals if n not in allowed]
    detail = (f"drafter={mode}; {len(decimals)} score figures in the draft, "
              f"all traced to evidence" if not invented else f"invented figures: {invented}")
    return not invented, detail


def e07_share_blocked_without_approval(conn):
    res = core.draft_summary(conn, "eval", "L005")
    try:
        core.share_summary(conn, "eval", res["summary_id"])
        return False, "share succeeded without an approved gate - gate is broken"
    except core.ApprovalRequiredError:
        return True, f"share of summary {res['summary_id']} refused: no approved gate"


def e08_named_human_gate(conn):
    res = core.draft_summary(conn, "eval", "L005")
    req = core.request_approval(conn, "eval", "share_summary",
                                {"summary_id": res["summary_id"]})
    core.resolve_approval(conn, "eval", req["approval_id"], "approved",
                          "Mr. Otieno (head teacher)")
    shared = core.share_summary(conn, "eval", res["summary_id"])
    row = conn.execute("SELECT status, decided_by, decided_at FROM approvals WHERE id=?",
                       (req["approval_id"],)).fetchone()
    ok = (shared["approved_by"] == "Mr. Otieno (head teacher)" and row["decided_by"]
          and row["decided_at"] is not None)
    return ok, f"approved by {row['decided_by']} at {row['decided_at']}, then shared"


def e09_audit_completeness(conn):
    before = conn.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"]
    res = core.ingest_result(conn, "eval", "L005", "quiz", "math", "Y4T3",
                             value=77.0, detail="arithmetic quiz 2")
    core.update_profile(conn, "eval", "L005", "strength", "solid arithmetic score",
                        [res["event_id"]])
    after = conn.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"]
    rows = conn.execute(
        "SELECT ts, actor, tool, args, result FROM audit_log ORDER BY id DESC LIMIT 2").fetchall()
    complete = all(r["ts"] and r["actor"] and r["tool"] and r["args"] and r["result"]
                   for r in rows)
    return after == before + 2 and complete, f"2 tool calls -> {after - before} audit rows, all fields populated"


def e10_tone_conversation_opener(conn):
    body = conn.execute(
        "SELECT body FROM summaries ORDER BY id DESC LIMIT 1").fetchone()["body"]
    framing = any(w in body.lower() for w in ("talk", "conversation", "discuss", "discussing"))
    prescriptive = [p for p in ("must choose", "should take", "career path",
                                "ranked", "is a weak student", "is a strong student")
                    if p in body.lower()]
    return framing and not prescriptive, (
        "framing present, no prescriptive language" if framing and not prescriptive
        else f"framing={framing}, prescriptive={prescriptive}")


def e11_known_failure_kiswahili_note(conn):
    """KNOWN FAILURE (documented in EVALS.md): a heavily-typoed Kiswahili note is
    stored but the skill mapper cannot extract a signal from it."""
    res = core.ingest_result(conn, "eval", "L010", "note", "kiswahili", "Y4T3",
                             detail="anahitaji msaada wa kuosma kwa sauti  (typoed)")
    extracted = res["skill"]
    failed = extracted == "unknown_skill"
    return (not failed), (
        f"note ingested as event {res['event_id']}; skill extracted = {extracted!r}; "
        f"known failure: needs a Kiswahili-capable model (Aya / larger Qwen) - "
        f"next step documented in EVALS.md")


TASKS = [
    ("E01", "Ingest + cited profile update", e01_ingest_and_cited_update, False),
    ("E02", "Unsourced claim refused", e02_unsourced_refused, False),
    ("E03", "3-term decline detected (L002)", e03_decline_detected, False),
    ("E04", "Sustained strength detected (L001)", e04_strength_detected, False),
    ("E05", "Attendance risk window (L004)", e05_attendance_risk, False),
    ("E06", "Summary has no invented numbers", e06_no_invented_numbers, False),
    ("E07", "Share blocked without approval", e07_share_blocked_without_approval, False),
    ("E08", "Named-human gate then share", e08_named_human_gate, False),
    ("E09", "Audit log completeness", e09_audit_completeness, False),
    ("E10", "Tone: conversation opener, not prescriptive", e10_tone_conversation_opener, False),
    ("E11", "KNOWN FAIL: Kiswahili typoed note", e11_known_failure_kiswahili_note, False),
]
