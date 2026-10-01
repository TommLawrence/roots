/**
 * Profile entries - the derived, cited claims.
 *
 * Production mirror of core.update_profile. THE rule of this project lives
 * here at the data layer: a profile entry with zero evidence refs is invalid,
 * and every ref must resolve to a real evidenceEvents row by sourceRef.
 * Refusals are audited inside the same transaction, then thrown - an
 * attempted unsourced label on a child is exactly what the audit log exists
 * to catch.
 *
 * Note what is NOT here: no scores, no tracks, no rankings. The agent can
 * write a cited strength/weakness/note - nothing else.
 */
import { mutation, query } from "./_generated/server";
import { v } from "convex/values";
import { Refusal, learnerExists, nowIso, recordAudit, resolveEvidence } from "./lib/guards";

const KINDS = ["strength", "weakness", "note"] as const;

export const addEntry = mutation({
  args: {
    actor: v.string(),
    learnerCode: v.string(),
    kind: v.string(),
    claim: v.string(),
    evidenceRefs: v.array(v.string()),
    termSpan: v.optional(v.string()),
  },
  handler: async (ctx, a) => {
    const args = { ...a };
    try {
      if (!KINDS.includes(a.kind as (typeof KINDS)[number])) {
        throw new Refusal("BadArgument", `refused: kind must be one of ${KINDS.join("|")}, got ${a.kind}`);
      }
      if (!a.claim.trim()) {
        throw new Refusal("BadArgument", "refused: claim cannot be empty");
      }
      if (!(await learnerExists(ctx, a.learnerCode))) {
        throw new Refusal("NotFound", `refused: unknown learner ${a.learnerCode}`);
      }
      const resolved = await resolveEvidence(ctx, a.evidenceRefs);
      const id = await ctx.db.insert("profileEntries", {
        learnerCode: a.learnerCode,
        kind: a.kind,
        claim: a.claim,
        evidenceRefs: resolved.map((r) => r.sourceRef),
        termSpan: a.termSpan,
        createdAt: nowIso(),
        createdBy: a.actor,
      });
      const result = { profileEntryId: id, evidenceRefs: resolved.map((r) => r.sourceRef) };
      await recordAudit(ctx, { actor: a.actor, tool: "addProfileEntry", args, result });
      return result;
    } catch (e) {
      if (e instanceof Refusal) {
        await recordAudit(ctx, { actor: a.actor, tool: "addProfileEntry", args, result: { refused: e.message } });
      }
      throw e;
    }
  },
});

/** Profile entries with their evidence resolved inline (read model). */
export const listByLearner = query({
  args: { learnerCode: v.string() },
  handler: async (ctx, a) => {
    const entries = await ctx.db
      .query("profileEntries")
      .withIndex("by_learner", (q) => q.eq("learnerCode", a.learnerCode))
      .collect();
    return Promise.all(
      entries.map(async (entry) => ({
        ...entry,
        evidence: await Promise.all(
          entry.evidenceRefs.map((ref) =>
            ctx.db
              .query("evidenceEvents")
              .withIndex("by_source_ref", (q) => q.eq("sourceRef", ref))
              .first()
          )
        ),
      }))
    );
  },
});
