/**
 * Evidence events - the raw, append-only records.
 *
 * Production mirror of core.ingest_result. The agent may APPEND records it
 * was given (a quiz score from the mark book), but raw records are never
 * edited or deleted afterwards - that is what makes them usable as citations.
 */
import { mutation, internalMutation, query } from "./_generated/server";
import { v } from "convex/values";
import { Refusal, learnerExists, nowIso, recordAudit } from "./lib/guards";

export const KINDS = ["quiz", "assignment", "attendance", "note"] as const;

const eventArgs = {
  actor: v.string(),
  learnerCode: v.string(),
  kind: v.string(),
  subject: v.string(),
  skill: v.string(),
  term: v.string(),
  week: v.optional(v.number()),
  value: v.optional(v.number()),
  detail: v.optional(v.string()),
  sourceRef: v.string(),
  eventDate: v.optional(v.string()),
  recordedAt: v.optional(v.string()),
  importedBatch: v.optional(v.string()),
};

export const add = mutation({
  args: eventArgs,
  handler: async (ctx, a) => {
    const args = { ...a };
    try {
      if (!KINDS.includes(a.kind as (typeof KINDS)[number])) {
        throw new Refusal("BadArgument", `refused: kind must be one of ${KINDS.join("|")}, got ${a.kind}`);
      }
      if (!(await learnerExists(ctx, a.learnerCode))) {
        throw new Refusal("NotFound", `refused: unknown learner ${a.learnerCode}`);
      }
      if (!a.sourceRef.trim()) {
        throw new Refusal("BadArgument", "refused: sourceRef is the citation key - it cannot be empty");
      }
      const id = await ctx.db.insert("evidenceEvents", {
        learnerCode: a.learnerCode,
        kind: a.kind,
        subject: a.subject,
        skill: a.skill || "uncategorised",
        term: a.term,
        week: a.week,
        value: a.value,
        detail: a.detail,
        sourceRef: a.sourceRef,
        eventDate: a.eventDate || a.term,
        recordedAt: a.recordedAt || nowIso(),
        importedBatch: a.importedBatch,
      });
      const result = { sourceRef: a.sourceRef, id };
      await recordAudit(ctx, {
        actor: a.actor,
        tool: "addEvidenceEvent",
        args,
        result,
      });
      return result;
    } catch (e) {
      if (e instanceof Refusal) {
        await recordAudit(ctx, { actor: a.actor, tool: "addEvidenceEvent", args, result: { refused: e.message } });
      }
      throw e;
    }
  },
});

/**
 * Bulk insert for the import pipeline (scripts/export_for_convex.py output).
 * Internal: one audit row per batch, not per row. Idempotence is the caller's
 * job (re-running `npx convex import` on a fresh table is the normal path).
 */
export const importBatch = internalMutation({
  args: {
    actor: v.string(),
    importedBatch: v.string(),
    rows: v.array(v.any()),
  },
  handler: async (ctx, a) => {
    let inserted = 0;
    for (const row of a.rows) {
      if (!KINDS.includes(row.kind)) continue;
      if (!row.sourceRef) continue;
      await ctx.db.insert("evidenceEvents", {
        learnerCode: row.learnerCode,
        kind: row.kind,
        subject: row.subject,
        skill: row.skill || "uncategorised",
        term: row.term,
        week: row.week,
        value: row.value,
        detail: row.detail,
        sourceRef: row.sourceRef,
        eventDate: row.eventDate || row.term,
        recordedAt: row.recordedAt || nowIso(),
        importedBatch: a.importedBatch,
      });
      inserted += 1;
    }
    await recordAudit(ctx, {
      actor: a.actor,
      tool: "importEvidenceBatch",
      args: { batch: a.importedBatch, rows: a.rows.length },
      result: { inserted },
    });
    return { inserted };
  },
});

export const getBySourceRef = query({
  args: { sourceRef: v.string() },
  handler: async (ctx, a) =>
    ctx.db
      .query("evidenceEvents")
      .withIndex("by_source_ref", (q) => q.eq("sourceRef", a.sourceRef))
      .first(),
});

export const listByLearner = query({
  args: { learnerCode: v.string(), limit: v.optional(v.number()) },
  handler: async (ctx, a) =>
    ctx.db
      .query("evidenceEvents")
      .withIndex("by_learner", (q) => q.eq("learnerCode", a.learnerCode))
      .take(a.limit ?? 500),
});
