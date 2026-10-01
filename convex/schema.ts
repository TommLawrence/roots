import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

/**
 * Longview production schema - mirrors the prototype's SQLite tables
 * (see longview_mcp/db.py). The citation rule carries over unchanged:
 * a profileEntry without >= 1 evidenceRef is invalid and the write
 * functions refuse it.
 *
 * Evidence is referenced by sourceRef (the portable natural key from the
 * records system) instead of a Convex id, so bulk imports from JSONL do not
 * need id remapping. Resolution goes through the by_source_ref index.
 */
export default defineSchema({
  learners: defineTable({
    learnerCode: v.string(),          // "L002" - portable key
    name: v.string(),
    guardian: v.optional(v.string()),
    cohortYear: v.optional(v.number()),
  }).index("by_learner_code", ["learnerCode"]),

  evidenceEvents: defineTable({
    learnerCode: v.string(),
    kind: v.string(),                 // quiz | assignment | attendance | note
    subject: v.string(),
    skill: v.string(),
    term: v.string(),                 // "Y3T2"
    week: v.optional(v.number()),
    value: v.optional(v.number()),
    detail: v.optional(v.string()),
    sourceRef: v.string(),            // citation target - required, non-empty
    eventDate: v.optional(v.string()),
    recordedAt: v.optional(v.string()),
    importedBatch: v.optional(v.string()),
  })
    .index("by_learner", ["learnerCode"])
    .index("by_learner_term", ["learnerCode", "term"])
    .index("by_source_ref", ["sourceRef"]),

  profileEntries: defineTable({
    learnerCode: v.string(),
    kind: v.string(),                 // strength | weakness | note
    claim: v.string(),
    evidenceRefs: v.array(v.string()), // >= 1, enforced in write functions
    termSpan: v.optional(v.string()),
    createdAt: v.string(),
    createdBy: v.string(),
  }).index("by_learner", ["learnerCode"]),

  flags: defineTable({
    learnerCode: v.string(),
    patternType: v.string(),
    rationale: v.string(),
    evidenceRefs: v.array(v.string()),
    status: v.string(),               // pending_review | raised | dismissed
    createdAt: v.string(),
    createdBy: v.string(),
    decidedBy: v.optional(v.string()),
    decidedAt: v.optional(v.string()),
  }).index("by_status", ["status"]),

  summaries: defineTable({
    learnerCode: v.string(),
    body: v.string(),
    evidenceMap: v.any(),             // claims -> evidence refs used
    status: v.string(),               // draft | approved | shared
    createdAt: v.string(),
    createdBy: v.string(),
  }).index("by_learner", ["learnerCode"]),

  approvals: defineTable({
    action: v.string(),
    payload: v.any(),
    status: v.string(),               // pending | approved | rejected
    requestedAt: v.string(),
    decidedBy: v.optional(v.string()),// named human - required for approval
    decidedAt: v.optional(v.string()),
    note: v.optional(v.string()),
  }).index("by_status", ["status"]),

  auditLog: defineTable({
    ts: v.number(),                   // epoch millis - sortable
    actor: v.string(),
    tool: v.string(),
    args: v.any(),
    result: v.any(),
  }).index("by_ts", ["ts"]),

  // Checkpoint table for the migration runner (migrations/runner.ts)
  migrations: defineTable({
    name: v.string(),
    ts: v.number(),
  }).index("by_name", ["name"]),
});
