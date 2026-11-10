import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import worker from "../server/worker.mjs";

const origin = "https://stds.example.test";
const pausedEnv = () => ({
  PUBLICATION_PAUSED: "true",
  ASSETS: { fetch: () => assert.fail("Paused requests must not reach assets") },
  READERS_DB: { prepare: () => assert.fail("Paused requests must not access reader data") },
});

test("publication pause covers deep links, downloads, search bundles and registration writes", async () => {
  const paths = ["/", "/read/9/", "/downloads/", "/downloads/standard.docx", "/assets/app.js", "/search-index.json", "/sitemap.xml", "/privacy/", "/admin/", "/admin/api/readers"];
  for (const path of paths) {
    const response = await worker.fetch(new Request(origin + path), pausedEnv());
    assert.equal(response.status, 503, path);
    assert.match(response.headers.get("Content-Type"), /text\/html/);
    assert.match(await response.text(), /当前审阅版本已冻结，网站内容正在更新/);
    assert.equal(response.headers.get("Retry-After"), "3600");
    assert.match(response.headers.get("Cache-Control"), /no-store/);
    assert.match(response.headers.get("X-Robots-Tag"), /noindex/);
  }
  for (const [path, method] of [["/api/registration/session", "GET"], ["/api/registration", "POST"], ["/api/registration", "PUT"], ["/api/registration", "DELETE"], ["/api/registration/read-confirmation", "POST"], ["/version.json", "GET"]]) {
    const response = await worker.fetch(new Request(origin + path, { method }), pausedEnv());
    assert.equal(response.status, 503, `${method} ${path}`);
    const body = await response.json();
    assert.equal(body.status, "publication_paused");
    assert.equal(body.reviewStatus, "frozen");
    assert.equal(response.headers.get("Set-Cookie"), null);
  }
});

test("pause responses support HEAD and stop indexing without loading site resources", async () => {
  const response = await worker.fetch(new Request(origin, { method: "HEAD" }), pausedEnv());
  assert.equal(response.status, 503);
  assert.equal(await response.text(), "");
  const robots = await worker.fetch(new Request(origin + "/robots.txt"), pausedEnv());
  assert.equal(robots.status, 200);
  assert.match(await robots.text(), /User-agent: \*\nDisallow: \//);
  const page = await (await worker.fetch(new Request(origin), pausedEnv())).text();
  assert.doesNotMatch(page, /<script|<link|<iframe|<form/);
  assert.match(page, /本文件仍为征求意见稿/);
});

test("deployment routes all assets through the pause gate and can explicitly resume", async () => {
  const config = await readFile(new URL("../wrangler.jsonc", import.meta.url), "utf8");
  assert.match(config, /"run_worker_first": true/);
  // The switch must be declared explicitly; resuming sets it to "false".
  assert.match(config, /"PUBLICATION_PAUSED": "(true|false)"/);
  let assetCalls = 0;
  const response = await worker.fetch(new Request(origin), {
    PUBLICATION_PAUSED: "false",
    ASSETS: { fetch: async () => { assetCalls += 1; return new Response("resumed asset"); } },
  });
  assert.equal(response.status, 200);
  assert.equal(await response.text(), "resumed asset");
  assert.equal(assetCalls, 1);
});
