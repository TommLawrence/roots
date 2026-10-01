/**
 * Migration runner - hand-rolled checkpoint pattern (the documented Convex
 * approach: schema changes deploy with `npx convex dev` / `npx convex deploy`,
 * DATA migrations run through this runner and record themselves in the
 * `migrations` table so they are idempotent).
 */
import { MutationCtx } from "../_generated/server";
import { internal } from "../_generated/api";

export const MIGRATIONS_TABLE = "migrations" as const;

export async function hasRun(ctx: MutationCtx, name: string): Promise<boolean> {
  const row = await ctx.db
    .query(MIGRATIONS_TABLE)
    .withIndex("by_name", (q) => q.eq("name", name))
    .unique();
  return row !== null;
}

/**
 * Wrap a migration body: skip if the checkpoint row exists, otherwise run and
 * record. Runs inside the caller's mutation so the migration + checkpoint are
 * applied atomically.
 */
export async function runOnce(
  ctx: MutationCtx,
  name: string,
  fn: (ctx: MutationCtx) => Promise<void>
): Promise<"ran" | "skipped"> {
  if (await hasRun(ctx, name)) {
    return "skipped";
  }
  await fn(ctx);
  await ctx.db.insert(MIGRATIONS_TABLE, { name, ts: Date.now() });
  return "ran";
}
