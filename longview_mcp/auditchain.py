"""Tamper-evident audit chain for the audit_log table.

Every audit row carries prev_hash + entry_hash. entry_hash is the SHA-256 of
the row's canonical payload (including the previous row's hash), so the log is
a linked chain: editing any historical field breaks that row's hash, and
deleting or reordering rows breaks the link between neighbours.

Pure stdlib (hashlib). The agent cannot rewrite history without detection -
which is the whole point of an audit log.
"""

import hashlib
import sqlite3

GENESIS = "0" * 64
_SEP = "\x1f"  # unit separator: cannot appear in JSON-encoded fields


def entry_digest(prev_hash: str, ts: str, actor: str, tool: str, args: str,
                 result: str) -> str:
    payload = _SEP.join((prev_hash, ts, actor, tool, args, result))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def row_digest(row: sqlite3.Row) -> str:
    return entry_digest(row["prev_hash"] or GENESIS, row["ts"], row["actor"],
                        row["tool"], row["args"], row["result"])


def backfill(conn: sqlite3.Connection) -> int:
    """Chain any rows written before hash columns existed (one-time migration)."""
    pending = conn.execute(
        "SELECT id, ts, actor, tool, args, result FROM audit_log "
        "WHERE entry_hash IS NULL ORDER BY id").fetchall()
    if not pending:
        return 0
    prev = conn.execute(
        "SELECT entry_hash FROM audit_log WHERE entry_hash IS NOT NULL "
        "ORDER BY id DESC LIMIT 1").fetchone()
    prev = prev["entry_hash"] if prev else GENESIS
    for r in pending:
        h = entry_digest(prev, r["ts"], r["actor"], r["tool"], r["args"], r["result"])
        conn.execute("UPDATE audit_log SET prev_hash=?, entry_hash=? WHERE id=?",
                     (prev, h, r["id"]))
        prev = h
    conn.commit()
    return len(pending)


def verify(conn: sqlite3.Connection) -> dict:
    """Re-walk the whole chain. Reports the first broken entry, if any."""
    prev = GENESIS
    n = 0
    for r in conn.execute("SELECT * FROM audit_log ORDER BY id"):
        n += 1
        if (r["prev_hash"] or GENESIS) != prev:
            return {"ok": False, "rows": n, "first_bad_id": r["id"],
                    "reason": "link broken: this entry does not follow the previous one "
                              "(row deleted, reordered, or hashes rewritten)"}
        if (r["entry_hash"] or "") != row_digest(r):
            return {"ok": False, "rows": n, "first_bad_id": r["id"],
                    "reason": "entry contents do not match their recorded hash "
                              "(a field was edited after write)"}
        prev = r["entry_hash"]
    return {"ok": True, "rows": n, "first_bad_id": None, "reason": None}
