/**
 * 0001 - Backfill `skill` for evidence events imported with unknown_skill.
 *
 * Mirrors longview_mcp/patterns.py::infer_skill. Keep the two in sync; a
 * comment in each points at the other.
 */
import { internalMutation, MutationCtx } from "../_generated/server";
import { runOnce } from "./runner";

export const NAME = "0001_backfill_skill_from_subject";

function inferSkill(detail: string, subject: string): string {
  const text = `${detail ?? ""} ${subject ?? ""}`.toLowerCase();
  const checks: Array<[string[], string]> = [
    [["geometry", "shape", "spatial", "pattern", "block"], "geometry"],
    [["add", "subtract", "multiply", "divide", "number", "arithmetic", "sum"], "arithmetic"],
    [["read", "comprehend", "comprehension", "story", "paragraph"], "reading"],
    [["write", "essay", "composition", "handwrit", "spelling"], "writing"],
    [["reason", "logic", "puzzle", "experiment", "science"], "reasoning"],
  ];
  for (const [keywords, skill] of checks) {
    if (keywords.some((k) => text.includes(k))) return skill;
  }
  return "unknown_skill";
}

async function migrate(ctx: MutationCtx): Promise<void> {
  const events = await ctx.db.query("evidenceEvents").collect();
  let patched = 0;
  for (const e of events) {
    if (e.skill === "unknown_skill") {
      const inferred = inferSkill(e.detail ?? "", e.subject);
      if (inferred !== "unknown_skill") {
        await ctx.db.patch(e._id, { skill: inferred });
        patched += 1;
      }
    }
  }
  console.log(`${NAME}: patched ${patched} events`);
}

export const backfillSkill = internalMutation({
  handler: async (ctx) => {
    await runOnce(ctx, NAME, migrate);
  },
});
