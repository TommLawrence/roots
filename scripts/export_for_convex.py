"""Export the prototype SQLite database to JSONL for Convex import.

Field names are camelCase to match convex/schema.ts exactly. Evidence
references are exported as sourceRef strings (portable natural key) - see
convex/README.md for why.

Usage:
    python scripts/export_for_convex.py --db data/longview.db --out data/export
"""

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

BATCH = "prototype_import_001"


def rows(conn, sql):
    for row in conn.execute(sql):
        yield dict(row)


def write_jsonl(path, records):
    count = 0
    with open(path, "w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
            count += 1
    return count


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/longview.db")
    ap.add_argument("--out", default="data/export")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    # Map raw_event id -> source_ref so citations survive the move to Convex
    ref_of = {r["id"]: r["source_ref"] for r in rows(conn, "SELECT id, source_ref FROM raw_events")}

    counts = {}
    counts["learners.jsonl"] = write_jsonl(
        os.path.join(args.out, "learners.jsonl"),
        ({"learnerCode": r["id"], "name": r["name"], "guardian": r["guardian"],
          "cohortYear": r["cohort_year"]} for r in rows(conn, "SELECT * FROM learners")))

    counts["evidence_events.jsonl"] = write_jsonl(
        os.path.join(args.out, "evidence_events.jsonl"),
        ({"learnerCode": r["learner_id"], "kind": r["kind"], "subject": r["subject"],
          "skill": r["skill"], "term": r["term"], "week": r["week"], "value": r["value"],
          "detail": r["detail"], "sourceRef": r["source_ref"], "eventDate": r["event_date"],
          "recordedAt": r["recorded_at"], "importedBatch": BATCH}
         for r in rows(conn, "SELECT * FROM raw_events")))

    def with_refs(row):
        ids = json.loads(row["evidence_ids"])
        return {**row, "evidenceRefs": [ref_of[i] for i in ids if i in ref_of]}

    counts["profile_entries.jsonl"] = write_jsonl(
        os.path.join(args.out, "profile_entries.jsonl"),
        ({"learnerCode": r["learner_id"], "kind": r["kind"], "claim": r["claim"],
          "evidenceRefs": [ref_of[i] for i in json.loads(r["evidence_ids"]) if i in ref_of],
          "termSpan": r["term_span"], "createdAt": r["created_at"], "createdBy": r["created_by"]}
         for r in rows(conn, "SELECT * FROM profile_entries")))

    counts["flags.jsonl"] = write_jsonl(
        os.path.join(args.out, "flags.jsonl"),
        ({"learnerCode": r["learner_id"], "patternType": r["pattern_type"],
          "rationale": r["rationale"],
          "evidenceRefs": [ref_of[i] for i in json.loads(r["evidence_ids"]) if i in ref_of],
          "status": r["status"], "createdAt": r["created_at"], "createdBy": r["created_by"],
          "decidedBy": r["decided_by"], "decidedAt": r["decided_at"]}
         for r in rows(conn, "SELECT * FROM flags")))

    counts["summaries.jsonl"] = write_jsonl(
        os.path.join(args.out, "summaries.jsonl"),
        ({"learnerCode": r["learner_id"], "body": r["body"], "evidenceMap": r["evidence_map"],
          "status": r["status"], "createdAt": r["created_at"], "createdBy": r["created_by"]}
         for r in rows(conn, "SELECT * FROM summaries")))

    counts["approvals.jsonl"] = write_jsonl(
        os.path.join(args.out, "approvals.jsonl"),
        ({"action": r["action"], "payload": r["payload"], "status": r["status"],
          "requestedAt": r["requested_at"], "decidedBy": r["decided_by"],
          "decidedAt": r["decided_at"], "note": r["note"]}
         for r in rows(conn, "SELECT * FROM approvals")))

    counts["audit_log.jsonl"] = write_jsonl(
        os.path.join(args.out, "audit_log.jsonl"),
        ({"ts": r["ts"], "actor": r["actor"], "tool": r["tool"], "args": r["args"],
          "result": r["result"]}
         for r in rows(conn, "SELECT * FROM audit_log")))

    conn.close()
    print(json.dumps({"out": args.out, "counts": counts}, indent=2))


if __name__ == "__main__":
    main()
