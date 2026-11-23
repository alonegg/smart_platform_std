import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";
import documentInfo from "../server/document-info.json" with { type: "json" };
import worker from "../server/worker.mjs";

const dist = new URL("../dist/", import.meta.url);

test("the main build contains two independently sourced editions", { skip: !documentInfo.primarySite }, async () => {
  const main = await readFile(new URL("index.html", dist), "utf8");
  const revision = await readFile(new URL("v2/index.html", dist), "utf8");
  assert.match(main, /href="\/v2\/"[^>]*>第 2 轮修订稿</);
  assert.match(revision, /href="\/"[^>]*>第 1 轮征求意见稿</);
  assert.match(revision, /rel="canonical" href="https:\/\/stds\.chunlin\.ch\/v2\/"/);
  assert.match(revision, /href="\/v2\/read\/introduction\/"/);
  assert.match(revision, /src="\/v2\/assets\//);
  const originalManifest = JSON.parse(await readFile(new URL("version.json", dist), "utf8"));
  const revisionManifest = JSON.parse(await readFile(new URL("v2/version.json", dist), "utf8"));
  assert.notEqual(originalManifest.sourceCommit, revisionManifest.sourceCommit);
  assert.equal(originalManifest.siteCommit, revisionManifest.siteCommit);
  assert.equal(revisionManifest.version, "第2轮修订稿");
  assert.equal(originalManifest.sourceSha256, documentInfo.sourceSha);
  for (const [base, manifest] of [["", originalManifest], ["v2/", revisionManifest]]) {
    for (const item of manifest.downloads) {
      const bytes = await readFile(new URL(`${base}downloads/${item.file}`, dist));
      assert.equal(createHash("sha256").update(bytes).digest("hex"), item.sha256, item.file);
    }
  }
  assert.match(await readFile(new URL("v2/downloads/index.html", dist), "utf8"),
    /href="\/v2\/downloads\/standard-review\.pdf"/);
});

test("the second edition shares the publication gate and does not expose write endpoints", { skip: !documentInfo.primarySite }, async () => {
  const env = {
    ASSETS: { fetch: (request) => new Response(new URL(request.url).pathname) },
    READERS_DB: { prepare: () => assert.fail("Wrong edition reached the database") },
  };
  const get = (path, method = "GET", overrides = {}) =>
    worker.fetch(new Request(`https://stds.chunlin.ch${path}`, { method }), { ...env, ...overrides });
  const revision = await get("/v2/downloads/standard-review.pdf");
  assert.equal(revision.status, 200);
  assert.equal(await revision.text(), "/v2/downloads/standard-review.pdf");
  assert.equal(revision.headers.get("X-Robots-Tag"), "noindex");
  for (const path of ["admin/", "comment/", "compare/", "api/registration", "api/comments"]) {
    assert.equal((await get(`/v2/${path}`)).status, 404, path);
    assert.equal((await get(`/v2/${path}`, "POST")).status, 404, path);
  }
  assert.equal((await get("/v2/", "POST")).status, 405);
  assert.equal((await get("/v2/", "GET", { PUBLICATION_PAUSED: "true" })).status, 503);
  assert.equal((await get("/api/registration/config")).status, 200);
  assert.equal((await get("/comment/")).status, 200);
});
