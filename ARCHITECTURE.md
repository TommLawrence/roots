# ARCHITECTURE

One page. What the agent is, which MCP servers we built vs borrowed, and why.

## Shape

Longview is a **planner-executor agent with a hard human gate**, orchestrated by LangGraph.
On every new trigger (a quiz result, an assignment, a teacher note), it:

1. **Plans** — builds the tool sequence for this trigger (ingest → analyse → propose → draft).
2. **Ingests** — writes the raw event via `ingest_result` (audit-logged).
3. **Analyses** — runs deterministic longitudinal pattern detection (declining ≥3 terms,
   sustained strength ≥3 terms, attendance risk) over the learner's full history.
4. **Proposes** profile updates — each proposal carries evidence ids; the write tool
   refuses unsourced claims at the schema level.
5. **Stops at the gate** — anything that leaves the classroom (sharing a summary with a
   guardian) requires `request_approval` → a named human approving in the review UI.
6. **Drafts** — plain-language summary from cited facts only; numbers in the draft must
   exist in the evidence set (checked by eval E06).
7. **Recovers** — tool calls retry with backoff; repeated failure escalates and logs
   instead of silently dropping the trigger.

## MCP servers

**Built (ours) — `longview_mcp`:**

| Tool | Writes? | Purpose |
|---|---|---|
| `ingest_result` | yes | Append a raw record (quiz / assignment / attendance / note) with source ref |
| `update_profile` | yes | Add a cited strength/weakness entry — **refuses without evidence ids** |
| `flag_pattern` | yes | Raise a pattern for teacher review (status `pending_review`, never auto-sent) |
| `draft_summary` | yes | Plain-language summary from cited facts (open-weights model; template fallback) |
| `request_approval` / `resolve_approval` | yes | The human gate — named person, timestamp, decision |
| `share_summary` | yes | **Blocked without an approved gate** — the only path out of the classroom |
| `get_learner_profile` | no | Read back a profile with full citations |
| `search_history` | no | Term/skill slice of raw history (thin; bulk reads go to the borrowed server) |

Tool logic is pure stdlib Python (`core.py`); `server.py` is a thin FastMCP wrapper.
A stranger can reuse the tool boundaries without importing our agent.

**Borrowed — official `sqlite` MCP server** (`borrowed/`):
generic read-only SQL over the records database. Why borrow: query plumbing is a solved,
audited problem; writing our own would add attack surface and maintenance for zero
classroom value. One line, as required — that line is here.

## Model

Open-weights: **Qwen 2.5 3B Instruct (Q4_K_M)** served locally via Ollama — chosen so the
full task runs on an 8 GB RAM laptop, and because longitudinal learner records (minors)
should not leave the device by default. Provider is pluggable for frontier side-by-side.

## Storage

Prototype: one SQLite database, three zones — `raw_events` (immutable, messy), `profile_entries`
/ `flags` / `summaries` (derived, all cite `raw_events.id`), `approvals` + `audit_log`
(governance). Production path: same schema, mirrored to the `convex/` backend (migrations
in `convex/migrations/`).

## Defensibility

- Every claim → evidence ids → raw events with source refs. No orphans (tests enforce).
- Every tool call → `audit_log` row: actor, tool, args, result, timestamp.
- Every irreversible action → approval row with a named human and a decision timestamp.
- Nothing is ranked, scored, or compared against classmates — the schema has no ranking field.

## Known compromises

- Pattern detection is statistical and transparent (thresholds in `patterns.py`), not an
  ML black box — a teacher can ask "why" and get the exact terms and scores.
- The agent proposes; it never decides. "Track assignment" is not a tool that exists.
