/**
 * Summaries - plain-language drafts for guardians, and THE share gate.
 *
 * Production mirror of core.draft_summary + core.share_summary. The hard
 * rule carries over unchanged: `share` is the ONLY path out of the classroom,
 * and it refuses unless there is an APPROVED approval row for exactly this
 * summary with a NAMED human on it. No approval, no share - whatever the
 * caller claims. That approval row can only be created by approvals.decide,
 * which is human-only (the agent cannot approve its own output).
 */
import { mutation, query } from "./_generated/server";
import { v } from "convex/values";
import {
  Refusal,
  learnerExists,
  nowIso,
  recordAudit,
  type Ctx,
} from "./lib/guards";

export const draft = mutation({
  args: {
    actor: v.string(),
    learnerCode: v.string(),
    body: v.string(),
    evidenceMap: v.any(), // findings -> evidenceRefs used; profileEntryIds
    source: v.optional(v.string()),
  },
  handler: async (ctx, a) => {
    const args = { ...a };
    try {
      if (!a.body.trim()) {
        throw new Refusal("BadArgument", "refused: summary body cannot be empty");
      }
      if (!(await learnerExists(ctx, a.learnerCode))) {
        throw new Refusal("NotFound", `refused: unknown learner ${a.learnerCode}`);
      }
      const id = await ctx.db.insert("summaries", {
        learnerCode: a.learnerCode,
        body: a.body,
        evidenceMap: a.evidenceMap,
        status: "draft",
        createdAt: nowIso(),
        createdBy: a.actor,
      });
      const result = { summaryId: id, source: a.source ?? "unknown" };
      await recordAudit(ctx, { actor: a.actor, tool: "draftSummary", args, result });
      return result;
    } catch (e) {
      if (e instanceof Refusal) {
        await recordAudit(ctx, { actor: a.actor, tool: "draftSummary", args, result: { refused: e.message } });
      }
      throw e;
    }
  },
});

/** Find the approved gate for a summary, if a named human approved it. */
async function approvedGate(ctx: Ctx, summaryId: string) {
  const approved = await ctx.db
    .query("approvals")
    .withIndex("by_status", (q) => q.eq("status", "approved"))
    .collect();
  return (
    approved
      .filter(
        (a) =>
          a.action === "share_summary" &&
          // prototype payloads use snake_case + numeric ids; new writes use
          // summaryId + Convex ids. Only an exact Convex-id match unlocks a
          // share - imported prototype gates are history, not permissions.
          ((a.payload as { summaryId?: string })?.summaryId ??
            (a.payload as { summary_id?: string })?.summary_id) === summaryId
      )
      // newest decision wins
      .sort((a, b) => (a.decidedAt ?? "").localeCompare(b.decidedAt ?? ""))
      .pop() ?? null
  );
}

export const share = mutation({
  args: {
    actor: v.string(),
    summaryId: v.id("summaries"),
    channel: v.optional(v.string()),
  },
  handler: async (ctx, a) => {
    const args = { ...a };
    try {
      const summary = await ctx.db.get(a.summaryId);
      if (!summary) {
        throw new Refusal("NotFound", `refused: unknown summary ${a.summaryId}`);
      }
      const gate = await approvedGate(ctx, a.summaryId);
      if (!gate || !gate.decidedBy) {
        throw new Refusal(
          "ApprovalRequired",
          `refused: sharing summary ${a.summaryId} needs an approved gate with a named human (request approval, then the teacher decides in the review UI)`
        );
      }
      await ctx.db.patch(a.summaryId, { status: "shared" });
      const result = {
        summaryId: a.summaryId,
        status: "shared" as const,
        channel: a.channel ?? "sms_to_guardian",
        approvedBy: gate.decidedBy,
      };
      await recordAudit(ctx, { actor: a.actor, tool: "shareSummary", args, result });
      return result;
    } catch (e) {
      if (e instanceof Refusal) {
        await recordAudit(ctx, { actor: a.actor, tool: "shareSummary", args, result: { refused: e.message } });
      }
      throw e;
    }
  },
});

export const listByLearner = query({
  args: { learnerCode: v.string() },
  handler: async (ctx, a) =>
    ctx.db
      .query("summaries")
      .withIndex("by_learner", (q) => q.eq("learnerCode", a.learnerCode))
      .collect(),
});

export const get = query({
  args: { summaryId: v.id("summaries") },
  handler: async (ctx, a) => ctx.db.get(a.summaryId),
});
