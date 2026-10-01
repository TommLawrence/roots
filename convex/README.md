# Longview production backend (Convex)

The prototype runs on SQLite so a stranger can clone and run it in one command.
Production runs on Convex. This folder keeps both in lockstep - the schema here
mirrors `longview_mcp/db.py` table for table, and the citation rule carries over:
a profile entry with zero evidence refs is invalid and the write functions refuse it.

## Layout

| File | Purpose |
|---|---|
| `schema.ts` | Tables + indexes (mirror of the prototype DDL) |
| `lib/guards.ts` | **The two rules, at the data layer**: citation rule (`resolveEvidence`) + human-only gate (`assertHuman`), refusals audited before throwing |
| `evidence.ts` | Raw records: `add` (append-only), `importBatch`, read queries |
| `profile.ts` | Cited profile entries: `addEntry` refuses unsourced claims |
| `flags.ts` | Agent `raise`s (evidence required), named human `decide`s |
| `summaries.ts` | `draft` + `share` - the ONLY path out, hard-gated on an approved gate |
| `approvals.ts` | The gate queue: `request` (agent), `decide` (human-only) |
| `learners.ts` | Roster reads + idempotent `ensure` for imports |
| `http.ts` | HTTPS bridge (`/api/v1/*`) so the Python agent can write without a JS client |
| `migrations/runner.ts` | Checkpoint-based idempotent data-migration runner |
| `migrations/backfill_skill.ts` | 0001 - backfill `skill` on imported events |
| `migrations/backfill_cohort_year.ts` | 0002 - backfill `cohortYear` on learners |
| `migrations/index.ts` | Ordered registry; runs everything pending |

## The two enforced rules (same as the prototype, same layer)

| Rule | Where | Behaviour |
|---|---|---|
| Citation rule | `lib/guards.ts` `resolveEvidence`, used by `profile.addEntry` + `flags.raise` | `evidenceRefs` must be non-empty and every ref must resolve to an `evidenceEvents` row via the `by_source_ref` index - otherwise `UnsourcedClaim` refusal, written to `auditLog` in the same transaction, then thrown |
| Human gate | `assertHuman` on `approvals.decide` + `flags.decide`; `summaries.share` requires an approved gate with a named `decidedBy` | The agent can request and propose, never decide; `agent` / `agent:*` actors and empty names are refused (`HumanRequired`), and the attempt is audit-logged |
| No scores/labels/tracks | by construction | There IS no write function for scores or tracks; the only agent-writable tables are `profileEntries`, `flags`, `summaries`, and raw `evidenceEvents` append |

Every public mutation writes one `auditLog` row on success AND on refusal -
`npx convex run auditLog:...` or the dashboard shows the full trail.

## How migrations work in Convex

Convex has no SQL-style schema migrations: **the schema file itself is the migration** -
`npx convex dev` (local) and `npx convex deploy` (production) push `schema.ts` and
codegen `_generated/`. What still needs migrating is DATA, which is what `migrations/`
is for: each migration checks the `migrations` checkpoint table, does its work, and
records itself - safe to re-run, ordered by `index.ts`.

Note: `_generated/` in this repo currently holds hand-written typecheck stubs
(gitignored). The first `npx convex dev` replaces them with real codegen - nothing
in the function files changes.

## First-time setup

```bash
cd convex
npm install
npx convex dev        # creates the project, pushes schema, writes _generated/
npx tsc --noEmit      # typecheck (works offline after npm install, via the stubs)
```

## Calling the write functions

From JS/TS (dashboard, future production UI):

```ts
import { api } from "./_generated/api";
await ctx.runMutation(api.profile.addEntry, {
  actor: "Ms. Wanjiru", learnerCode: "L002", kind: "strength",
  claim: "Reading improved across Y3",
  evidenceRefs: ["quiz:Y3T1:english:reading:q1", "quiz:Y3T2:english:reading:q1"],
});
```

From Python / the agent (production path - the MCP tools post here):

```bash
curl -X POST https://<deployment>.convex.site/api/v1/profileEntry \
  -H 'content-type: application/json' \
  -d '{"actor":"agent","learnerCode":"L002","kind":"strength","claim":"...",
       "evidenceRefs":["quiz:Y3T1:english:reading:q1"]}'
# 200 {"ok":true,"profileEntryId":"..."}  |  422 {"ok":false,"error":"refused: ..."}
```

Routes: `/api/v1/learner`, `/api/v1/evidence`, `/api/v1/profileEntry`,
`/api/v1/flag`, `/api/v1/flag/decide`, `/api/v1/summary`,
`/api/v1/summary/share`, `/api/v1/approval`, `/api/v1/approval/decide`.

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
npx convex deploy     # pushes schema + functions + http routes to production
npx convex run migrations/index:runAll --prod
```

## Design note: evidenceRefs vs Convex ids

Evidence is referenced by `sourceRef` (the portable natural key, e.g.
`quiz:Y3T2:english:reading:q3`) instead of a Convex `_id`, so JSONL imports never
need id remapping and citations stay meaningful across deployments. Resolution uses
the `by_source_ref` index - the same index the citation guard runs against, so an
imported dataset is immediately citable.

## No scheduled functions, on purpose

There is no `crons.ts` and no scheduled function anywhere in this backend. Batch
work (imports, migrations) is triggered manually or by the HTTP routes. The agent
pipeline is event-driven: ingest -> analyse -> propose -> HUMAN GATE -> share.
