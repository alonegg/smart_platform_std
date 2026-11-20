import { readFile } from "node:fs/promises";

export const edition = process.env.PORTAL_EDITION ?? "review";
if (!["review", "r2"].includes(edition)) throw new Error(`Unknown PORTAL_EDITION: ${edition}`);
export const isR2 = edition === "r2";
export const expectations = {
  review: { sections: 19, units: 786, tables: 56, profiles: 9, groups: 32, triggers: 17, pending: 30, phases: 6, matrices: 4, matrixRows: 9, cells: 288, pages: 29 },
  r2: { sections: 19, units: 805, tables: 57, profiles: 9, groups: 32, triggers: 17, pending: 30, phases: 6, matrices: 4, matrixRows: 9, cells: 288, pages: 30 },
};
export const expected = expectations[edition];
export const sourcePath = isR2
  ? "维护/第2轮修订稿/智慧教学-数据模型标准-修订稿.md"
  : "标准/评审稿/智慧教学-数据模型标准.md";
export const sourceCommit = isR2
  ? "0ebb33034179adde310f4616fba06365f959337e"
  : "904d37a9797a4ad2ab238b5e00946e8a9dcbfdd7";

export function validateR2Config(config) {
  if (config.vars?.REQUIRE_ACCESS !== "true" || config.vars?.PORTAL_EDITION !== "r2" || config.assets?.run_worker_first !== true)
    throw new Error('r2 requires REQUIRE_ACCESS="true", PORTAL_EDITION="r2" and run_worker_first=true in wrangler.r2.jsonc');
}

export async function checkEditionConfig() {
  if (!isR2) return;
  const jsonc = await readFile(new URL("../wrangler.r2.jsonc", import.meta.url), "utf8");
  validateR2Config(JSON.parse(jsonc.replace(/^\s*\/\/.*$/gm, "").replace(/,\s*([}\]])/g, "$1")));
}
