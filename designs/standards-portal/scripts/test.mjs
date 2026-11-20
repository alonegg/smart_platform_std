import { readdir, readFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { checkEditionConfig, isR2 } from "./edition.mjs";

await checkEditionConfig();
const data = JSON.parse(await readFile(new URL("../src/generated.json", import.meta.url)));
if ((data.edition === "r2") !== isR2) throw new Error("Build the selected PORTAL_EDITION before testing");
const tests = (await readdir(new URL("../tests/", import.meta.url))).filter((file) => file.endsWith(".test.mjs") && (!isR2 || !["registration.test.mjs", "publication.test.mjs"].includes(file)));
const result = spawnSync(process.execPath, ["--test", ...tests.map((file) => `tests/${file}`)], { stdio: "inherit" });
process.exit(result.status ?? 1);
