import { execFileSync } from "node:child_process";
import { mkdir, mkdtemp, rename, rm } from "node:fs/promises";
import { resolve } from "node:path";

const project = new URL("../", import.meta.url);
const temporaryRoot = new URL("../../../temp/", import.meta.url);
await mkdir(temporaryRoot, { recursive: true });
const staging = await mkdtemp(new URL("primary-standards-", temporaryRoot));
const dist = new URL("dist/", project);

function build(edition) {
  execFileSync(process.execPath, ["scripts/build.mjs"], {
    cwd: project,
    env: { ...process.env, PORTAL_PRIMARY: "true", PORTAL_EDITION: edition },
    stdio: "inherit",
  });
}

try {
  build("r2-public");
  const secondEdition = resolve(staging, "v2");
  await rm(new URL("_headers", dist), { force: true });
  await rename(dist, secondEdition);
  build("review");
  await rename(secondEdition, new URL("v2/", dist));
} finally {
  await rm(staging, { recursive: true, force: true });
}
