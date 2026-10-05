// LOCAL TYPECHECK STUB - replaced by `npx convex dev` codegen on first run.
// Binds the convex/server builders to this project's DataModel, exactly like
// the generated server.d.ts does.
import type {
  ActionBuilder,
  GenericActionCtx,
  GenericMutationCtx,
  GenericQueryCtx,
  MutationBuilder,
  PublicHttpAction,
  QueryBuilder,
} from "convex/server";
import type { DataModel } from "./dataModel";

export declare const query: QueryBuilder<DataModel, "public">;
export declare const mutation: MutationBuilder<DataModel, "public">;
export declare const internalQuery: QueryBuilder<DataModel, "internal">;
export declare const internalMutation: MutationBuilder<DataModel, "internal">;
export declare const action: ActionBuilder<DataModel, "public">;
export declare const internalAction: ActionBuilder<DataModel, "internal">;

export declare const httpAction: (
  func: (ctx: GenericActionCtx<DataModel>, request: Request) => Promise<Response>
) => PublicHttpAction;

export type { GenericActionCtx, GenericMutationCtx, GenericQueryCtx, PublicHttpAction } from "convex/server";

export type QueryCtx = GenericQueryCtx<DataModel>;
export type MutationCtx = GenericMutationCtx<DataModel>;
export type ActionCtx = GenericActionCtx<DataModel>;
