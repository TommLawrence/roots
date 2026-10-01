/**
 * Ordered registry - the single place that lists migrations IN ORDER.
 * Run everything pending:  npx convex run migrations/index:runAll
 */
import { internalMutation } from "../_generated/server";
import { internal } from "../_generated/api";

export const runAll = internalMutation({
  handler: async (ctx) => {
    const order = [
      internal.migrations.backfill_skill.backfillSkill,
      internal.migrations.backfill_cohort_year.backfillCohortYear,
    ];
    for (const fn of order) {
      await ctx.runMutation(fn, {});
    }
  },
});
