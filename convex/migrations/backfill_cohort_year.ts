/**
 * 0002 - Backfill cohortYear on learners imported before the field existed.
 */
import { internalMutation, MutationCtx } from "../_generated/server";
import { runOnce } from "./runner";

export const NAME = "0002_backfill_cohort_year";

const DEFAULT_COHORT_YEAR = 2022;

async function migrate(ctx: MutationCtx): Promise<void> {
  const learners = await ctx.db.query("learners").collect();
  let patched = 0;
  for (const l of learners) {
    if (l.cohortYear === undefined) {
      await ctx.db.patch(l._id, { cohortYear: DEFAULT_COHORT_YEAR });
      patched += 1;
    }
  }
  console.log(`${NAME}: patched ${patched} learners`);
}

export const backfillCohortYear = internalMutation({
  handler: async (ctx) => {
    await runOnce(ctx, NAME, migrate);
  },
});
