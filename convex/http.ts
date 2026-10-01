/**
 * HTTP bridge - how the Python agent reaches Convex in production.
 *
 * The prototype agent talks to SQLite directly through our MCP server. In
 * production the SAME MCP tools (update_profile, flag_pattern, draft_summary,
 * share_summary ...) call these routes on the deployment's convex.site host
 * instead. Same tool surface, same rules - the enforcement moved with the
 * data into the mutations, so the HTTP layer adds nothing but JSON.
 *
 * Wire format (POST, JSON body = the mutation args):
 *   curl -X POST https://<deployment>.convex.site/api/v1/profileEntry \
 *        -H 'content-type: application/json' \
 *        -d '{"actor":"agent","learnerCode":"L002","kind":"strength",
 *             "claim":"Reading improved across Y3","evidenceRefs":["quiz:Y3T1:english:reading:q1"]}'
 *   -> 200 {"ok":true,...result} | 422 {"ok":false,"error":"refused: ..."}
 *
 * Note there are NO scheduled functions anywhere in this backend - batch
 * work is triggered manually (npx convex run ...) or by these routes. Ever.
 */
import { httpRouter } from "convex/server";
import type { FunctionReference } from "convex/server";
import { httpAction } from "./_generated/server";
import { api } from "./_generated/api";

function route(fn: FunctionReference<"mutation", "public">) {
  return httpAction(async (ctx, req) => {
    if (req.method !== "POST") {
      return json({ ok: false, error: "POST only" }, 405);
    }
    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return json({ ok: false, error: "invalid JSON body" }, 400);
    }
    try {
      const result = await ctx.runMutation(fn, body as Record<string, unknown>);
      return json({ ok: true, ...(result as object) }, 200);
    } catch (e) {
      // Refusals (UnsourcedClaim, HumanRequired, ApprovalRequired, ...) and
      // validation errors all come back as 422 with the refusal text - the
      // caller sees the same message the audit log recorded.
      return json({ ok: false, error: String(e) }, 422);
    }
  });
}

function json(payload: unknown, status: number): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const http = httpRouter();

http.route({ path: "/api/v1/learner", method: "POST", handler: route(api.learners.ensure) });
http.route({ path: "/api/v1/evidence", method: "POST", handler: route(api.evidence.add) });
http.route({ path: "/api/v1/profileEntry", method: "POST", handler: route(api.profile.addEntry) });
http.route({ path: "/api/v1/flag", method: "POST", handler: route(api.flags.raise) });
http.route({ path: "/api/v1/flag/decide", method: "POST", handler: route(api.flags.decide) });
http.route({ path: "/api/v1/summary", method: "POST", handler: route(api.summaries.draft) });
http.route({ path: "/api/v1/summary/share", method: "POST", handler: route(api.summaries.share) });
http.route({ path: "/api/v1/approval", method: "POST", handler: route(api.approvals.request) });
http.route({ path: "/api/v1/approval/decide", method: "POST", handler: route(api.approvals.decide) });

export default http;
