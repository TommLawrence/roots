/**
 * Learners - roster reads and an idempotent upsert for the import pipeline.
 */
import { mutation, query } from "./_generated/server";
import { v } from "convex/values";
import { nowIso, recordAudit } from "./lib/guards";

export const ensure = mutation({
  args: {
    actor: v.string(),
    learnerCode: v.string(),
    name: v.string(),
    guardian: v.optional(v.string()),
    cohortYear: v.optional(v.number()),
  },
  handler: async (ctx, a) => {
    const existing = await ctx.db
      .query("learners")
      .withIndex("by_learner_code", (q) => q.eq("learnerCode", a.learnerCode))
      .unique();
    if (existing) {
      // idempotent: fill in missing fields only, never overwrite a name
      await ctx.db.patch(existing._id, {
        guardian: existing.guardian ?? a.guardian,
        cohortYear: existing.cohortYear ?? a.cohortYear,
      });
      return { learnerId: existing._id, created: false };
    }
    const id = await ctx.db.insert("learners", {
      learnerCode: a.learnerCode,
      name: a.name,
      guardian: a.guardian,
      cohortYear: a.cohortYear,
    });
    await recordAudit(ctx, {
      actor: a.actor,
      tool: "ensureLearner",
      args: a,
      result: { learnerId: id, created: true, at: nowIso() },
    });
    return { learnerId: id, created: true };
  },
});

export const getByCode = query({
  args: { learnerCode: v.string() },
  handler: async (ctx, a) =>
    ctx.db
      .query("learners")
      .withIndex("by_learner_code", (q) => q.eq("learnerCode", a.learnerCode))
      .unique(),
});

export const list = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, a) => ctx.db.query("learners").take(a.limit ?? 500),
});
