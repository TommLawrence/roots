/**
 * Flags - patterns proposed by the agent, decided by a named human.
 *
 * Production mirror of core.flag_pattern + core.resolve_flag. Two-sided rule:
 *  - raising a flag needs evidence (citation rule, refusals audited),
 *  - resolving a flag is HUMAN-ONLY: `actor` must be a named person, and the
 *    name attached to the decision cannot be the agent rubber-stamping itself.
 * Flags never auto-send anything anywhere; they wait in pending_review.
 */
import { mutation, query } from "./_generated/server";
import { v } from "convex/values";
import {
  Refusal,
  assertHuman,
  learnerExists,
  nowIso,
  recordAudit,
  resolveEvidence,
} from "./lib/guards";

export const raise = mutation({
  args: {
    actor: v.string(),
    learnerCode: v.string(),
    patternType: v.string(),
    rationale: v.string(),
    evidenceRefs: v.array(v.string()),
  },
  handler: async (ctx, a) => {
    const args = { ...a };
    try {
      if (!a.rationale.trim()) {
        throw new Refusal("BadArgument", "refused: rationale cannot be empty");
      }
      if (!(await learnerExists(ctx, a.learnerCode))) {
        throw new Refusal("NotFound", `refused: unknown learner ${a.learnerCode}`);
      }
      const resolved = await resolveEvidence(ctx, a.evidenceRefs);
      const id = await ctx.db.insert("flags", {
        learnerCode: a.learnerCode,
        patternType: a.patternType,
        rationale: a.rationale,
        evidenceRefs: resolved.map((r) => r.sourceRef),
        status: "pending_review",
        createdAt: nowIso(),
        createdBy: a.actor,
      });
      const result = { flagId: id, status: "pending_review" as const };
      await recordAudit(ctx, { actor: a.actor, tool: "raiseFlag", args, result });
      return result;
    } catch (e) {
      if (e instanceof Refusal) {
        await recordAudit(ctx, { actor: a.actor, tool: "raiseFlag", args, result: { refused: e.message } });
      }
      throw e;
    }
  },
});

/** Teacher decision: raised (act on it) or dismissed. Human-only. */
export const decide = mutation({
  args: {
    actor: v.string(),
    flagId: v.id("flags"),
    decision: v.union(v.literal("raised"), v.literal("dismissed")),
    decidedBy: v.string(),
  },
  handler: async (ctx, a) => {
    const args = { ...a };
    try {
      // One lock on the operator, one on the name attached to the decision.
      assertHuman(a.actor, `resolving flag ${a.flagId}`);
      const decidedBy = assertHuman(a.decidedBy, `resolving flag ${a.flagId}`);

      const flag = await ctx.db.get(a.flagId);
      if (!flag) {
        throw new Refusal("NotFound", `refused: unknown flag ${a.flagId}`);
      }
      if (flag.status !== "pending_review") {
        throw new Refusal("AlreadyDecided", `refused: flag already ${flag.status}`);
      }
      await ctx.db.patch(a.flagId, {
        status: a.decision,
        decidedBy,
        decidedAt: nowIso(),
      });
      const result = { flagId: a.flagId, status: a.decision, decidedBy };
      await recordAudit(ctx, { actor: a.actor, tool: "decideFlag", args, result });
      return result;
    } catch (e) {
      if (e instanceof Refusal) {
        await recordAudit(ctx, { actor: a.actor, tool: "decideFlag", args, result: { refused: e.message } });
      }
      throw e;
    }
  },
});

export const listByStatus = query({
  args: { status: v.string(), limit: v.optional(v.number()) },
  handler: async (ctx, a) =>
    ctx.db
      .query("flags")
      .withIndex("by_status", (q) => q.eq("status", a.status))
      .take(a.limit ?? 50),
});

export const listByLearner = query({
  args: { learnerCode: v.string() },
  handler: async (ctx, a) =>
    ctx.db
      .query("flags")
      .withIndex("by_learner", (q) => q.eq("learnerCode", a.learnerCode))
      .collect(),
});
