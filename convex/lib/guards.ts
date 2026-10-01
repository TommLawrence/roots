/**
 * Shared guards for Longview write functions.
 *
 * The prototype enforces two rules in longview_mcp/core.py, in code - not in
 * prompts. The production backend enforces the SAME rules here, in the same
 * place (inside the mutations, so nothing can bypass them):
 *
 *  1. The citation rule: a claim about a learner needs at least one evidence
 *     reference, and every reference must resolve to a real record. An
 *     unsourced label on a child is worse than no label at all.
 *  2. The human gate: decisions (approving a share, resolving a flag) are
 *     made by NAMED humans. The agent proposes; it never decides.
 *
 * Refusals are errors with a stable `code`, and every refusing mutation
 * writes its refusal to the audit log BEFORE throwing (same transaction),
 * mirroring core.py.
 */
import type { GenericMutationCtx, GenericQueryCtx } from "convex/server";
import type { DataModel } from "../_generated/dataModel";

export type Ctx = GenericQueryCtx<DataModel> | GenericMutationCtx<DataModel>;

/** Actors namespaced to the agent - never allowed to make decisions. */
const AGENT_ACTOR = /^agent(:|$)/i;

export class Refusal extends Error {
  constructor(
    public readonly code:
      | "UnsourcedClaim"
      | "HumanRequired"
      | "NotFound"
      | "AlreadyDecided"
      | "ApprovalRequired"
      | "BadArgument",
    message: string
  ) {
    super(message);
  }
}

/** Human-only guard: a non-empty name that is not the agent's. */
export function assertHuman(actor: string, what: string): string {
  const name = (actor ?? "").trim();
  if (!name) {
    throw new Refusal("HumanRequired", `refused: ${what} needs a named human - the deciding name cannot be empty`);
  }
  if (AGENT_ACTOR.test(name)) {
    throw new Refusal(
      "HumanRequired",
      `refused: ${what} is decided by humans only - the agent cannot do it itself. The named person approves in the review UI.`
    );
  }
  return name;
}

export function nowIso(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

export async function recordAudit(
  ctx: GenericMutationCtx<DataModel>,
  entry: { actor: string; tool: string; args: unknown; result: unknown }
): Promise<void> {
  await ctx.db.insert("auditLog", {
    ts: Date.now(),
    actor: entry.actor || "(none)",
    tool: entry.tool,
    args: entry.args,
    result: entry.result,
  });
}

/**
 * The citation rule, at the data layer. Resolves every sourceRef against the
 * evidenceEvents table (by_source_ref index) and refuses empty or dangling
 * references. Returns the resolved events so callers can cite them onward.
 */
export async function resolveEvidence(
  ctx: Ctx,
  refs: string[]
): Promise<Array<{ _id: string; sourceRef: string }>> {
  const wanted = (refs ?? []).map((r) => (r ?? "").trim()).filter(Boolean);
  if (wanted.length === 0) {
    throw new Refusal(
      "UnsourcedClaim",
      "refused: a claim about a learner needs at least one evidence reference (an unsourced label is worse than no label)"
    );
  }
  const resolved: Array<{ _id: string; sourceRef: string }> = [];
  const missing: string[] = [];
  for (const ref of wanted) {
    const doc = await ctx.db
      .query("evidenceEvents")
      .withIndex("by_source_ref", (q) => q.eq("sourceRef", ref))
      .first();
    if (doc) {
      resolved.push({ _id: doc._id, sourceRef: doc.sourceRef });
    } else {
      missing.push(ref);
    }
  }
  if (missing.length > 0) {
    throw new Refusal("UnsourcedClaim", `refused: evidence refs not found in records: ${missing.join(", ")}`);
  }
  return resolved;
}

export async function learnerExists(ctx: Ctx, learnerCode: string): Promise<boolean> {
  const doc = await ctx.db
    .query("learners")
    .withIndex("by_learner_code", (q) => q.eq("learnerCode", learnerCode))
    .unique();
  return doc !== null;
}
