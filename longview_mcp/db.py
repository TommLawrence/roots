"""SQLite schema + connection helper. Single source of truth for the DDL.

Zones:
  raw       : learners, raw_events              (immutable, messy on purpose)
  derived   : profile_entries, flags, summaries (every row cites raw_events.id)
  governance: approvals, audit_log
"""

import os
import sqlite3

DDL = """
CREATE TABLE IF NOT EXISTS learners (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  guardian    TEXT,
  cohort_year INTEGER
);

CREATE TABLE IF NOT EXISTS raw_events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  learner_id  TEXT NOT NULL REFERENCES learners(id),
  kind        TEXT NOT NULL CHECK (kind IN ('quiz','assignment','attendance','note')),
  subject     TEXT NOT NULL,
  skill       TEXT NOT NULL,
  term        TEXT NOT NULL,
  week        INTEGER,
  value       REAL,
  detail      TEXT,
  source_ref  TEXT NOT NULL,
  event_date  TEXT,
  recorded_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_raw_learner ON raw_events(learner_id, kind, skill, term);

CREATE TABLE IF NOT EXISTS profile_entries (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  learner_id   TEXT NOT NULL REFERENCES learners(id),
  kind         TEXT NOT NULL CHECK (kind IN ('strength','weakness','note')),
  claim        TEXT NOT NULL,
  evidence_ids TEXT NOT NULL,          -- JSON array of raw_events.id (>=1, enforced in code)
  term_span    TEXT,
  created_at   TEXT NOT NULL,
  created_by   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flags (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  learner_id   TEXT NOT NULL REFERENCES learners(id),
  pattern_type TEXT NOT NULL,
  rationale    TEXT NOT NULL,
  evidence_ids TEXT NOT NULL,          -- JSON array
  status       TEXT NOT NULL DEFAULT 'pending_review'
               CHECK (status IN ('pending_review','raised','dismissed')),
  created_at   TEXT NOT NULL,
  created_by   TEXT NOT NULL,
  decided_by   TEXT,
  decided_at   TEXT
);

CREATE TABLE IF NOT EXISTS summaries (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  learner_id   TEXT NOT NULL REFERENCES learners(id),
  body         TEXT NOT NULL,
  evidence_map TEXT NOT NULL,          -- JSON: claims -> evidence ids used
  status       TEXT NOT NULL DEFAULT 'draft'
               CHECK (status IN ('draft','approved','shared')),
  created_at   TEXT NOT NULL,
  created_by   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  action       TEXT NOT NULL,
  payload      TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'pending'
               CHECK (status IN ('pending','approved','rejected')),
  requested_at TEXT NOT NULL,
  decided_by   TEXT,                   -- named human, required for approval
  decided_at   TEXT,
  note         TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      TEXT NOT NULL,
  actor   TEXT NOT NULL,
  tool    TEXT NOT NULL,
  args    TEXT NOT NULL,
  result  TEXT NOT NULL
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    directory = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(DDL)
    return conn


def default_db_path() -> str:
    return os.environ.get("LONGVIEW_DB", os.path.join("data", "longview.db"))
