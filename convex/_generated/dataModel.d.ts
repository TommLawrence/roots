// LOCAL TYPECHECK STUB - replaced by `npx convex dev` codegen on first run.
// This file is gitignored (convex/_generated/) and mirrors what the real
// codegen emits: DataModel derived from ../schema.ts via Convex's own helper.
import type { DataModelFromSchemaDefinition } from "convex/server";
import type schemaDef from "../schema";

export type DataModel = DataModelFromSchemaDefinition<typeof schemaDef>;
