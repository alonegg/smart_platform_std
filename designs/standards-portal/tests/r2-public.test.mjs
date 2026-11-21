import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import test from "node:test";
import { isPublicR2, hostname } from "../scripts/edition.mjs";
import publicWorker from "../server/r2-public.mjs";
import reviewWorker from "../server/worker.mjs";

const origin = `https://${hostname}`;
const blocked = ["/compare/", "/compare/index.html", "/admin", "/admin/api/readers", "/comment/", "/responses/", "/privacy/", "/api/comments", "/api/registration"];
const dist = new URL("../dist/", import.meta.url);

test("public r2 builds only the reading site without comparison assets or links", { skip: !isPublicR2 }, async () => {
  const files = await readdir(dist, { recursive: true });
  const internal = /INTERNAL REVISION PREVIEW|r2-comparison|修订编号：/;
  for (const file of files.filter((name) => /\.(html|js|xml)$/.test(name))) {
    const text = await readFile(new URL(file, dist), "utf8");
    assert.doesNotMatch(text, internal, file);
    if (!file.endsWith(".html")) continue;
    assert.match(text, /<meta name="robots" content="noindex">/, file);
    assert.ok(text.includes(`rel="canonical" href="${origin}/`), file);
    assert.doesNotMatch(text, /href="\/(compare|comment|responses|admin|privacy)(\/|")/, file);
  }
  for (const route of ["compare", "comment", "admin", "responses", "privacy"])
    assert.ok(!files.includes(route), route);
  await assert.rejects(readFile(new URL("../src/r2/comparison.json", import.meta.url)), { code: "ENOENT" });
});

test("public r2 serves anonymous reads and keeps internal paths and writes closed", { skip: !isPublicR2 }, async () => {
  const env = {
    ASSETS: { fetch: async (request) => {
      assert.ok(["GET", "HEAD"].includes(request.method));
      assert.ok(!blocked.includes(new URL(request.url).pathname));
      return new Response("public asset");
    } },
  };
  for (const path of ["/", "/read/5/", "/version.json", "/downloads/standard-review.md"]) {
    const response = await publicWorker.fetch(new Request(origin + path), env);
    assert.equal(response.status, 200, path);
    assert.equal(await response.text(), "public asset");
    assert.equal(response.headers.get("X-Robots-Tag"), "noindex");
  }
  for (const path of blocked) {
    for (const method of ["GET", "POST"]) {
      const response = await publicWorker.fetch(new Request(origin + path, { method }), env);
      assert.equal(response.status, 404, path);
    }
  }
  const head = await publicWorker.fetch(new Request(origin, { method: "HEAD" }), env);
  assert.equal(head.status, 200);
  assert.equal(await head.text(), "");
  const write = await publicWorker.fetch(new Request(origin, { method: "POST" }), env);
  assert.equal(write.status, 405);
  assert.equal(write.headers.get("Allow"), "GET, HEAD");
  assert.equal((await reviewWorker.fetch(new Request(origin), env)).status, 503);
});

test("public review shows the controlled date, decisions and email channel", { skip: !isPublicR2 }, async () => {
  const home = await readFile(new URL("index.html", dist), "utf8");
  const decisions = await readFile(new URL("decisions/index.html", dist), "utf8");
  const appendixC = await readFile(new URL("read/c/index.html", dist), "utf8");
  const appendixE = await readFile(new URL("read/e/index.html", dist), "utf8");
  const downloads = await readFile(new URL("downloads/index.html", dist), "utf8");
  const manifest = JSON.parse(await readFile(new URL("version.json", dist), "utf8"));
  assert.ok(home.includes(manifest.documentDate.replaceAll("-", "/")));
  assert.match(decisions, /<code>missing_reasons<\/code>/);
  assert.match(decisions, /href="\/read\/e\/#clause-E-3"/);
  assert.match(decisions, /href="\/read\/e\/#clause-E-4"/);
  assert.match(appendixE, /id="clause-E-4"/);
  assert.match(appendixC, /id="clause-C-4-2"/);
  assert.match(appendixC, /mailto:alone@swufe.edu.cn\?subject=/);
  assert.match(downloads, /mailto:alone@swufe.edu.cn/);
  for (const file of ["d2-review-draft.md", "wire-fields-draft.csv", "atomic-cases-draft.json"]) {
    assert.ok(manifest.downloads.some((item) => item.file === file), file);
    assert.ok(downloads.includes(`href="/downloads/${file}"`), file);
  }
});
