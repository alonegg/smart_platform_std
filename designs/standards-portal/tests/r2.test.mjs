import test, { before } from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { marked } from "marked";
import { checkEditionConfig, validateR2Config, isR2, expected } from "../scripts/edition.mjs";
import { project, root, sourcePath, sourceCommit } from "../scripts/content.mjs";
import worker from "../server/worker.mjs";
import { verifyAccess } from "../server/access.mjs";

const data = JSON.parse(await readFile(path.join(project, "src/generated.json")));
const artifact = (name) => readFile(path.join(project, "dist", name), "utf8");

test("r2 build requires Access enabled in the actual r2 configuration", async () => {
  await checkEditionConfig();
  const config = { vars: { REQUIRE_ACCESS: "true", PORTAL_EDITION: "r2" }, assets: { run_worker_first: true } };
  assert.doesNotThrow(() => validateR2Config(config));
  for (const value of [false, "false", undefined, "", true])
    assert.throws(() => validateR2Config({ ...config, vars: { ...config.vars, REQUIRE_ACCESS: value } }), /REQUIRE_ACCESS/);
  assert.throws(() => validateR2Config({}), /REQUIRE_ACCESS/);
  assert.throws(() => validateR2Config({ ...config, assets: {} }), /run_worker_first/);
});

test("edition pins exact clause units and tables without relaxing appendix A", async () => {
  const source = await readFile(path.join(root, sourcePath), "utf8");
  assert.equal(marked.lexer(source).filter((token) => token.type === "table").length, expected.tables);
  assert.equal(data.sourceCommit, sourceCommit);
  const review = await readFile(path.join(root, "标准/评审稿/智慧教学-数据模型标准.md"), "utf8");
  const appendix = (text) => text.split("## 附录 A")[1].split("## 附录 B")[0];
  assert.equal(appendix(source), appendix(review));
  assert.equal(expected.units, isR2 ? 805 : 786);
});

test("only r2 has comparison, noindex and a disabled opinion page", async () => {
  const index = await artifact("index.html");
  const comment = await artifact("comment/index.html");
  const sitemap = await artifact("sitemap.xml");
  if (!isR2) {
    await assert.rejects(artifact("compare/index.html"), { code: "ENOENT" });
    assert.doesNotMatch(index, /\/compare\/|第2轮修订稿预览|name="robots" content="noindex"/);
    assert.doesNotMatch(sitemap, /\/compare\//);
    assert.match(await artifact("robots.txt"), /Allow: \//);
    assert.match(comment, /<form/);
    return;
  }
  assert.match(index, /第2轮修订稿预览，非现行征求意见稿/);
  assert.match(comment, /意见提交已禁用/);
  assert.match(comment, /disabled/);
  assert.doesNotMatch(comment, /<form/);
  const files = await readdir(path.join(project, "dist"), { recursive: true });
  for (const file of files.filter((file) => file.endsWith(".html")))
    assert.match(await artifact(file), /<meta name="robots" content="noindex">/, file);
  assert.equal(await artifact("robots.txt"), "User-agent: *\nDisallow: /\n");
  assert.ok(data.downloads.some((item) => item.type === "PDF"));
  assert.match(await artifact("downloads/standard-review.pdf"), /^%PDF-/);
  assert.match(await artifact("_headers"), /X-Robots-Tag: noindex/);
  assert.match(sitemap, /https:\/\/r2.stds.chunlin.ch\/compare\//);
  const compare = await artifact("compare/index.html");
  assert.match(compare, /只看改动/);
  assert.equal([...compare.matchAll(/class="r2-comparison changed"/g)].length, 27);
  assert.match(compare, /R01/);
  assert.match(compare, /issues\/72/);
  assert.match(compare, /当前正文/);
  assert.match(compare, /第2轮修订稿/);
  const rows = JSON.parse(await readFile(path.join(project, "src/r2/comparison.json")));
  assert.equal(rows.length, expected.units);
  assert.equal(rows.filter((row) => row.kind === "新增").length, 19);
  assert.equal(rows.filter((row) => row.kind === "修改").length, 8);
  const noIssue = rows.find((row) => row.revisions.includes("R16"));
  assert.deepEqual(noIssue.issues, []);
  assert.ok(rows.filter((row) => row.kind !== "未改动").every((row) => row.revisions.length));
  const search = await readFile(path.join(project, "src/search-index.json"), "utf8");
  assert.doesNotMatch(search, /INTERNAL REVISION PREVIEW|r2-comparison|修订编号|\/compare\//);
  assert.ok(data.downloads.filter((item) => item.file.startsWith("standard-review")).every((item) => item.from.startsWith("维护/第2轮修订稿/")));
  const markdown = await artifact("downloads/standard-review.md");
  assert.equal(markdown, await readFile(path.join(root, sourcePath), "utf8"));
  assert.doesNotMatch(markdown, /r2-comparison|INTERNAL REVISION PREVIEW/);
});

let pair, jwks;
const team = "r2-preview-test.cloudflareaccess.com";
const audience = "r2-preview-audience";
before(async () => {
  pair = await crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]);
  jwks = { keys: [{ ...await crypto.subtle.exportKey("jwk", pair.publicKey), kid: "r2-test", alg: "RS256" }] };
});
const b64 = (value) => Buffer.from(JSON.stringify(value)).toString("base64url");
async function jwt(change = {}) {
  const header = b64({ alg: "RS256", kid: "r2-test" });
  const payload = b64({ iss: `https://${team}`, aud: [audience], exp: Math.floor(Date.now() / 1000) + 300, email: "reviewer@example.invalid", ...change });
  const signature = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", pair.privateKey, new TextEncoder().encode(`${header}.${payload}`));
  return `${header}.${payload}.${Buffer.from(signature).toString("base64url")}`;
}
const env = () => ({
  PORTAL_EDITION: "r2", REQUIRE_ACCESS: "true", ACCESS_TEAM_DOMAIN: team, ACCESS_AUD: audience, ADMIN_EMAIL: "admin@example.invalid",
  READERS_DB: { prepare: () => assert.fail("Preview must not access D1") },
  ASSETS: { fetch: async () => new Response("preview asset") },
});
const request = (url, token, method = "GET") => new Request(`https://r2.example.test${url}`, { method, headers: token ? { "Cf-Access-Jwt-Assertion": token } : {} });

test("Access guards all routes, static files, APIs, errors and missing configuration", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json(jwks));
  const paths = ["/", "/compare/", "/compare/index.html", "/read/5/", "/assets/app.js", "/downloads/standard-review.docx", "/robots.txt", "/version.json", "/api/comments", "/admin/"];
  for (const url of paths) {
    const response = await worker.fetch(request(url), { ...env(), ASSETS: { fetch: () => assert.fail("Unauthenticated request reached assets") } });
    assert.equal(response.status, 401, url);
    assert.equal(response.headers.get("X-Robots-Tag"), "noindex");
  }
  for (const change of [{ aud: ["production-audience"] }, { iss: "https://wrong.example" }, { exp: 0 }, { email: "" }, { nbf: Math.floor(Date.now() / 1000) + 300 }])
    assert.equal((await worker.fetch(request("/compare/", await jwt(change)), env())).status, 401);
  assert.equal((await worker.fetch(request("/compare/", "invalid"), env())).status, 401);
  const missing = await worker.fetch(request("/compare/", await jwt()), { ...env(), REQUIRE_ACCESS: "false" });
  assert.equal(missing.status, 503);
  assert.equal(missing.headers.get("X-Robots-Tag"), "noindex");
  const token = await jwt();
  for (const url of paths.filter((url) => !url.startsWith("/api/") && !url.startsWith("/admin/"))) {
    const response = await worker.fetch(request(url, token), env());
    assert.equal(response.status, 200, url);
    assert.equal(response.headers.get("X-Robots-Tag"), "noindex");
    assert.match(response.headers.get("Cache-Control"), /private, no-store/);
  }
  assert.equal((await worker.fetch(request("/admin/", token), env())).status, 401);
  assert.equal(await verifyAccess(request("/", token), env(), async () => Response.json(jwks)), null, "Site access does not grant administrator access");
  const failed = await worker.fetch(request("/", token), { ...env(), ASSETS: { fetch() { throw new Error("asset failure"); } } });
  assert.equal(failed.status, 503);
  assert.equal(failed.headers.get("X-Robots-Tag"), "noindex");
  for (const [url, method] of [["/api/comments", "POST"], ["/api/comments/mine", "GET"], ["/api/registration", "POST"], ["/admin/api/comments/1", "PUT"]]) {
    const response = await worker.fetch(request(url, token, method), env());
    assert.equal(response.status, 403);
    assert.equal(response.headers.get("X-Robots-Tag"), "noindex");
  }
  await worker.scheduled({}, env());
});
