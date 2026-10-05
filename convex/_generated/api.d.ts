// LOCAL TYPECHECK STUB - replaced by `npx convex dev` codegen on first run.
// Function references for every public mutation/query and internal function
// defined in this project, matching the real generated api.d.ts shape.
import type { FunctionReference } from "convex/server";

export declare const api: {
  learners: {
    ensure: FunctionReference<"mutation", "public">;
    getByCode: FunctionReference<"query", "public">;
    list: FunctionReference<"query", "public">;
  };
  evidence: {
    add: FunctionReference<"mutation", "public">;
    getBySourceRef: FunctionReference<"query", "public">;
    listByLearner: FunctionReference<"query", "public">;
  };
  profile: {
    addEntry: FunctionReference<"mutation", "public">;
    listByLearner: FunctionReference<"query", "public">;
  };
  flags: {
    raise: FunctionReference<"mutation", "public">;
    decide: FunctionReference<"mutation", "public">;
    listByStatus: FunctionReference<"query", "public">;
    listByLearner: FunctionReference<"query", "public">;
  };
  summaries: {
    draft: FunctionReference<"mutation", "public">;
    share: FunctionReference<"mutation", "public">;
    listByLearner: FunctionReference<"query", "public">;
    get: FunctionReference<"query", "public">;
  };
  approvals: {
    request: FunctionReference<"mutation", "public">;
    decide: FunctionReference<"mutation", "public">;
    listByStatus: FunctionReference<"query", "public">;
  };
};

export declare const internal: {
  evidence: {
    importBatch: FunctionReference<"mutation", "internal">;
  };
  migrations: {
    backfill_skill: {
      backfillSkill: FunctionReference<"mutation", "internal">;
    };
    backfill_cohort_year: {
      backfillCohortYear: FunctionReference<"mutation", "internal">;
    };
  };
};
