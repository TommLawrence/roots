/**
 * Approvals - the human gate queue.
 *
 * Production mirror of core.request_approval + core.resolve_approval.
 * `request` is open to the agent (asking permission is fine).
 * `decide` is HUMAN-ONLY: the operator must be a named person, the name
 * attached to the decision must be a real person, and both refusal paths
 * are audited. For share_summary gates the target summary must exist, so
 * gates can never dangle.
 */
import { mutation, query } from "./_generated/server";
import { v } from "convex/values";
import { Refusal, assertHuman, nowIso, recordAudit } from "./lib/guards";

export const request = mutation({
  args: {
    actor: v.string(),
    action: v.string(),
    payload: v.any(),
  },
  handler: async (ctx, a) => {
    const id = await ctx.db.insert("approvals", {
      action: a.action,
      payload: a.payload,
      status: "pending",
      requestedAt: nowIso(),
    });
    const result = { approvalId: id, status: "pending" as const };
    await recordAudit(ctx, { actor: a.actor, tool: "requestApproval", args: a, result });
    return result;
  },
});

export const decide = mutation({
  args: {
    actor: v.string(),
    approvalId: v.id("approvals"),
    decision: v.union(v.literal("approved"), v.literal("rejected")),
    decidedBy: v.string(),
    note: v.optional(v.string()),
  },
  handler: async (ctx, a) => {
    const args = { ...a };
    try {
      // Two locks, same as the prototype: the operator is human, and the
      // name on the decision is a real person - not the agent itself.
      assertHuman(a.actor, `resolving approval ${a.approvalId}`);
      const decidedBy = assertHuman(a.decidedBy, `resolving approval ${a.approvalId}`);

      const row = await ctx.db.get(a.approvalId);
      if (!row) {
        throw new Refusal("NotFound", `refused: unknown approval ${a.approvalId}`);
      }
      if (row.status !== "pending") {
        throw new Refusal("AlreadyDecided", `refused: approval already ${row.status}`);
      }
      if (row.action === "share_summary") {
        const summaryId = (row.payload as { summaryId?: string })?.summaryId;
        if (!summaryId || !(await ctx.db.get(summaryId as any))) {
          throw new Refusal("NotFound", "refused: gate points at a summary that does not exist");
        }
      }
      await ctx.db.patch(a.approvalId, {
        status: a.decision,
        decidedBy,
        decidedAt: nowIso(),
        note: a.note,
      });
      const result = { approvalId: a.approvalId, status: a.decision, decidedBy };
      await recordAudit(ctx, { actor: a.actor, tool: "decideApproval", args, result });
      return result;
    } catch (e) {
      if (e instanceof Refusal) {
        await recordAudit(ctx, { actor: a.actor, tool: "decideApproval", args, result: { refused: e.message } });
      }
      throw e;
    }
  },
});

export const listByStatus = query({
  args: { status: v.string(), limit: v.optional(v.number()) },
  handler: async (ctx, a) =>
    ctx.db
      .query("approvals")
      .withIndex("by_status", (q) => q.eq("status", a.status))
      .take(a.limit ?? 50),
});
