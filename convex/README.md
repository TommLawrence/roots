# Longview production backend (Convex)

The prototype runs on SQLite so a stranger can clone and run it in one command.
Production runs on Convex. This folder keeps both in lockstep - the schema here
mirrors `longview_mcp/db.py` table for table, and the citation rule carries over:
a profile entry with zero evidence refs is invalid and the write functions refuse it.

## Layout

| File | Purpose |
|---|---|
| `schema.ts` | Tables + indexes (mirror of the prototype DDL) |
| `migrations/runner.ts` | Checkpoint-based idempotent data-migration runner |
| `migrations/backfill_skill.ts` | 0001 - backfill `skill` on imported events |
| `migrations/backfill_cohort_year.ts` | 0002 - backfill `cohortYear` on learners |
| `migrations/index.ts` | Ordered registry; runs everything pending |

## How migrations work in Convex

Convex has no SQL-style schema migrations: **the schema file itself is the migration** -
`npx convex dev` (local) and `npx convex deploy` (production) push `schema.ts` and
codegen `_generated/`. What still needs migrating is DATA, which is what `migrations/`
is for: each migration checks the `migrations` checkpoint table, does its work, and
records itself - safe to re-run, ordered by `index.ts`.

## First-time setup

```bash
cd convex
npm install
npx convex dev        # creates the project, pushes schema, writes _generated/
```

## Loading the synthetic dataset

From the repo root, export the prototype database to JSONL (camelCase, matching schema):

```bash
python scripts/export_for_convex.py --db data/longview.db --out data/export
```

Then import (run from the `convex/` directory):

```bash
npx convex import --table learners        ../data/export/learners.jsonl
npx convex import --table evidenceEvents  ../data/export/evidence_events.jsonl
npx convex import --table profileEntries  ../data/export/profile_entries.jsonl
npx convex import --table flags           ../data/export/flags.jsonl
npx convex import --table summaries       ../data/export/summaries.jsonl
npx convex import --table approvals       ../data/export/approvals.jsonl
npx convex import --table auditLog        ../data/export/audit_log.jsonl
```

## Running data migrations

```bash
npx convex run migrations/index:runAll
# or individually:
npx convex run migrations/backfill_skill:backfillSkill
```

(Re-running is safe: each migration skips itself via the checkpoint table.)

## Production

```bash
npx convex deploy     # pushes schema + functions to the production deployment
npx convex run migrations/index:runAll --prod
```

## Design note: evidenceRefs vs Convex ids

Evidence is referenced by `sourceRef` (the portable natural key, e.g.
`quiz:Y3T2:english:reading:q3`) instead of a Convex `_id`, so JSONL imports never
need id remapping and citations stay meaningful across deployments. Resolution uses
the `by_source_ref` index. A future `evidenceRefsById` variant can be added once
writes go through Convex mutations natively.
