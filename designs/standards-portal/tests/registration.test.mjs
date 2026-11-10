import test, { before } from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { readFile } from "node:fs/promises";
import worker, {
  handleRequest,
  validateRegistration,
} from "../server/worker.mjs";
import { verifyAccess } from "../server/access.mjs";
import policy from "../src/registration-policy.json" with { type: "json" };

const origin = "https://stds.example.test";
const validInput = {
  name: "合成验收读者",
  organization: "自动测试样例",
  role: "expert",
  field: "数据模型",
  email: "reader@example.invalid",
  allowContact: false,
  consent: true,
  consentVersion: policy.version,
};
const migration =
  (await readFile(
    new URL("../migrations/0001_readers.sql", import.meta.url),
    "utf8",
  )) +
  (await readFile(
    new URL("../migrations/0002_comments.sql", import.meta.url),
    "utf8",
  ));
class LocalD1 {
  constructor() {
    this.db = new DatabaseSync(":memory:");
    this.db.exec(migration);
  }
  prepare(sql) {
    const statement = this.db.prepare(sql);
    const bound = (args) => ({
      first: async () => statement.get(...args) ?? null,
      all: async () => ({ results: statement.all(...args) }),
      run: async () => ({ success: true, meta: statement.run(...args) }),
    });
    return { bind: (...args) => bound(args), ...bound([]) };
  }
  count() {
    return this.db
      .prepare("SELECT COUNT(*) AS n FROM reader_registrations")
      .get().n;
  }
}
const envFor = () => ({
  READERS_DB: new LocalD1(),
  DOCUMENT_SHA: "test-document-sha",
  ADMIN_EMAIL: "organizer@example.invalid",
  ACCESS_TEAM_DOMAIN: "registration-test.cloudflareaccess.com",
  ACCESS_AUD: "test-audience",
  ASSETS: { fetch: async () => new Response("protected asset") },
});
const request = (path, method = "GET", body, cookie = "", extra = {}) =>
  new Request(origin + path, {
    method,
    headers: {
      ...(method !== "GET"
        ? { Origin: origin, "Content-Type": "application/json" }
        : {}),
      ...(cookie ? { Cookie: cookie } : {}),
      ...extra,
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
const sessionCookie = async (env) => {
  const response = await worker.fetch(
    request("/api/registration/session"),
    env,
  );
  assert.equal(response.status, 200);
  return response.headers.get("Set-Cookie").split(";")[0];
};
let pair;
let jwks;
before(async () => {
  pair = await crypto.subtle.generateKey(
    {
      name: "RSASSA-PKCS1-v1_5",
      modulusLength: 2048,
      publicExponent: new Uint8Array([1, 0, 1]),
      hash: "SHA-256",
    },
    true,
    ["sign", "verify"],
  );
  jwks = {
    keys: [
      {
        ...(await crypto.subtle.exportKey("jwk", pair.publicKey)),
        kid: "registration-test-key",
        alg: "RS256",
      },
    ],
  };
});
const b64 = (input) =>
  Buffer.from(
    typeof input === "string" ? input : JSON.stringify(input),
  ).toString("base64url");
async function signedToken(changes = {}) {
  const header = b64({ alg: "RS256", kid: "registration-test-key" });
  const payload = b64({
    iss: "https://registration-test.cloudflareaccess.com",
    aud: ["test-audience"],
    exp: Math.floor(Date.now() / 1000) + 300,
    email: "organizer@example.invalid",
    ...changes,
  });
  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    pair.privateKey,
    new TextEncoder().encode(`${header}.${payload}`),
  );
  return `${header}.${payload}.${Buffer.from(signature).toString("base64url")}`;
}

test("validation requires explicit purpose consent and bounds every field", () => {
  assert.equal(validateRegistration(validInput).name, validInput.name);
  for (const change of [
    { consent: false },
    { consentVersion: "stale" },
    { role: "administrator" },
    { name: "" },
    { organization: "a".repeat(161) },
    { email: "not-an-email" },
    { allowContact: true, email: "" },
    { name: "line\nfeed" },
    { website: "spam" },
  ])
    assert.throws(() => validateRegistration({ ...validInput, ...change }));
});

test("anonymous session does not write a person and uses a secure HttpOnly opaque cookie", async () => {
  const env = envFor();
  const response = await worker.fetch(
    request("/api/registration/session"),
    env,
  );
  assert.deepEqual(await response.json(), {
    registration: null,
    consentVersion: policy.version,
  });
  assert.match(
    response.headers.get("Set-Cookie"),
    /__Host-stds_reader=[a-f0-9]{64}; Path=\/; HttpOnly; SameSite=Lax; Max-Age=15552000; Secure/,
  );
  assert.equal(env.READERS_DB.count(), 0);
});

test("CSRF, body type, size and missing consent fail without a database write", async () => {
  const env = envFor();
  const cookie = await sessionCookie(env);
  const cases = [
    request("/api/registration", "POST", validInput, cookie, {
      Origin: "https://other.example",
    }),
    request("/api/registration", "POST", validInput, cookie, {
      "Content-Type": "text/plain",
    }),
    request(
      "/api/registration",
      "POST",
      { ...validInput, consent: false },
      cookie,
    ),
    request("/api/registration", "POST", { name: "a".repeat(5000) }, cookie),
  ];
  for (const input of cases)
    assert.ok((await worker.fetch(input, env)).status >= 400);
  assert.equal(env.READERS_DB.count(), 0);
});

test("registration commits, retries idempotently, stays private, updates and withdraws only its owner row", async () => {
  const env = envFor();
  const cookie = await sessionCookie(env);
  const created = await worker.fetch(
    request("/api/registration", "POST", validInput, cookie),
    env,
  );
  assert.equal(created.status, 201);
  const first = (await created.json()).registration;
  const retry = await worker.fetch(
    request("/api/registration", "POST", validInput, cookie),
    env,
  );
  assert.equal(retry.status, 200);
  assert.equal((await retry.json()).registration.id, first.id);
  assert.equal(env.READERS_DB.count(), 1);
  assert.equal(
    (
      await (
        await worker.fetch(request("/api/registration/session"), env)
      ).json()
    ).registration,
    null,
  );
  const other = await sessionCookie(env);
  await worker.fetch(
    request(
      "/api/registration",
      "POST",
      { ...validInput, name: "另一条合成记录" },
      other,
    ),
    env,
  );
  const confirmed = await worker.fetch(
    request(
      "/api/registration/read-confirmation",
      "POST",
      { confirmed: true },
      cookie,
    ),
    env,
  );
  assert.ok((await confirmed.json()).registration.readConfirmedAt);
  const edited = await worker.fetch(
    request(
      "/api/registration",
      "PUT",
      { ...validInput, name: "修改后的合成读者" },
      cookie,
    ),
    env,
  );
  assert.equal(edited.status, 200);
  const row = (await edited.json()).registration;
  assert.equal(row.name, "修改后的合成读者");
  assert.equal(row.readConfirmedAt, null);
  const deleted = await worker.fetch(
    request("/api/registration", "DELETE", undefined, cookie),
    env,
  );
  assert.equal(deleted.status, 200);
  assert.match(deleted.headers.get("Set-Cookie"), /Max-Age=0/);
  assert.equal(env.READERS_DB.count(), 1);
  assert.equal(
    (
      await (
        await worker.fetch(
          request("/api/registration/session", "GET", undefined, cookie),
          env,
        )
      ).json()
    ).registration,
    null,
  );
});

test("database failures never return a success receipt or personal details", async () => {
  const env = envFor();
  const cookie = await sessionCookie(env);
  env.READERS_DB = {
    prepare() {
      throw new Error("private database detail");
    },
  };
  const response = await worker.fetch(
    request("/api/registration", "POST", validInput, cookie),
    env,
  );
  assert.equal(response.status, 503);
  const text = await response.text();
  assert.ok(!text.includes("private database detail"));
  assert.ok(!text.includes(validInput.name));
  assert.ok(!text.includes('"registration"'));
});

test("expired rows can re-register and the scheduled purge leaves active readers alone", async () => {
  const env = envFor();
  const cookie = await sessionCookie(env);
  await worker.fetch(
    request("/api/registration", "POST", validInput, cookie),
    env,
  );
  env.READERS_DB.db.exec(
    "UPDATE reader_registrations SET expires_at = '2000-01-01T00:00:00.000Z'",
  );
  const again = await worker.fetch(
    request("/api/registration", "POST", validInput, cookie),
    env,
  );
  assert.equal(again.status, 201);
  assert.equal(env.READERS_DB.count(), 1);
  const other = await sessionCookie(env);
  await worker.fetch(
    request("/api/registration", "POST", validInput, other),
    env,
  );
  env.READERS_DB.db
    .prepare(
      "UPDATE reader_registrations SET expires_at = '2000-01-01T00:00:00.000Z' WHERE id = ?",
    )
    .run((await again.json()).registration.id);
  await worker.scheduled({}, env);
  assert.equal(env.READERS_DB.count(), 1);
});

test("Access checks a real signature, issuer, audience, expiry and exact administrator email", async () => {
  const env = envFor();
  const keys = async () => Response.json(jwks);
  const auth = async (token) =>
    verifyAccess(
      request("/admin/api/readers", "GET", undefined, "", {
        "Cf-Access-Jwt-Assertion": token,
      }),
      env,
      keys,
    );
  assert.deepEqual(await auth(await signedToken()), { email: env.ADMIN_EMAIL });
  for (const changes of [
    { iss: "https://attacker.example" },
    { aud: ["different"] },
    { exp: 0 },
    { nbf: Math.floor(Date.now() / 1000) + 300 },
    { email: "other@example.invalid" },
  ])
    assert.equal(await auth(await signedToken(changes)), null);
  const good = await signedToken();
  assert.equal(await auth(good.slice(0, -8) + "AAAAAAAA"), null);
  assert.equal(
    await verifyAccess(
      request("/admin/", "GET", undefined, "", {
        "Cf-Access-Authenticated-User-Email": env.ADMIN_EMAIL,
      }),
      env,
      keys,
    ),
    null,
  );
});

test("admin list/export require authentication, omit session hashes and neutralize CSV formulas", async (t) => {
  const env = envFor();
  const cookie = await sessionCookie(env);
  await worker.fetch(
    request(
      "/api/registration",
      "POST",
      { ...validInput, name: "=1+2" },
      cookie,
    ),
    env,
  );
  assert.equal(
    (await worker.fetch(request("/admin/api/readers"), env)).status,
    401,
  );
  t.mock.method(globalThis, "fetch", async () => Response.json(jwks));
  const token = await signedToken();
  const auth = { "Cf-Access-Jwt-Assertion": token };
  const list = await worker.fetch(
    request("/admin/api/readers", "GET", undefined, "", auth),
    env,
  );
  assert.equal(list.status, 200);
  assert.match(list.headers.get("Cache-Control"), /no-store/);
  const text = await list.text();
  assert.ok(!text.includes("session_hash"));
  assert.equal(JSON.parse(text).total, 1);
  const csv = await worker.fetch(
    request("/admin/api/readers.csv", "GET", undefined, "", auth),
    env,
  );
  assert.equal(csv.status, 200);
  assert.ok((await csv.text()).includes('"\'=1+2"'));
});

test("rate limit returns 429 before inserting a registration", async () => {
  const env = envFor();
  const cookie = await sessionCookie(env);
  env.REGISTRATION_LIMITER = { limit: async () => ({ success: false }) };
  const response = await worker.fetch(
    request("/api/registration", "POST", validInput, cookie),
    env,
  );
  assert.equal(response.status, 429);
  assert.equal(env.READERS_DB.count(), 0);
});

const validComment = {
  clause: "5.1.3",
  sectionKey: "5",
  category: "技术语义",
  role: "vendor",
  profile: "P-SUB",
  problem: "合成样例：无版本对象无法使用 ObjectRef。\n第二行说明。",
  proposal: "建议区分 ObjectRef 与 VersionRef。",
  rationale: "",
  submitter: "合成提议人",
  organization: "自动测试厂商",
  email: "vendor@example.invalid",
  allowPublic: false,
};
const commentCount = (env) =>
  env.READERS_DB.db.prepare("SELECT COUNT(*) AS n FROM review_comments").get()
    .n;

test("comments need no registration, get sequential refs and stay private until resolved", async (t) => {
  const env = envFor();
  const cookie = await sessionCookie(env);
  const first = await worker.fetch(
    request("/api/comments", "POST", validComment, cookie),
    env,
  );
  assert.equal(first.status, 201);
  assert.equal((await first.json()).comment.ref, "R1-0001");
  const second = await worker.fetch(
    request("/api/comments", "POST", { ...validComment, allowPublic: true }, ""),
    env,
  );
  assert.equal((await second.json()).comment.ref, "R1-0002");
  const mine = await (
    await worker.fetch(request("/api/comments/mine", "GET", undefined, cookie), env)
  ).json();
  assert.deepEqual(
    mine.comments.map((c) => c.ref),
    ["R1-0001"],
  );
  const stats = await (
    await worker.fetch(request("/api/comments/stats"), env)
  ).json();
  assert.equal(stats.total, 2);
  assert.equal(stats.byDisposition.pending, 2);
  let pub = await (await worker.fetch(request("/api/comments/public"), env)).json();
  assert.equal(pub.comments.length, 0);

  assert.equal(
    (await worker.fetch(request("/admin/api/comments"), env)).status,
    401,
  );
  t.mock.method(globalThis, "fetch", async () => Response.json(jwks));
  const auth = { "Cf-Access-Jwt-Assertion": await signedToken() };
  const list = await (
    await worker.fetch(request("/admin/api/comments", "GET", undefined, "", auth), env)
  ).json();
  assert.equal(list.total, 2);
  const [newest, oldest] = list.comments;
  const missingReason = await worker.fetch(
    request(`/admin/api/comments/${oldest.id}`, "PUT", { disposition: "accepted" }, "", auth),
    env,
  );
  assert.equal(missingReason.status, 400);
  for (const [row, summary] of [
    [oldest, "编制组摘要：引用类型需区分"],
    [newest, ""],
  ]) {
    const res = await worker.fetch(
      request(
        `/admin/api/comments/${row.id}`,
        "PUT",
        { disposition: "partial", response: "已在 5.1 增加 VersionRef。", publicSummary: summary },
        "",
        auth,
      ),
      env,
    );
    assert.equal(res.status, 200);
  }
  const publicText = await (
    await worker.fetch(request("/api/comments/public"), env)
  ).text();
  pub = JSON.parse(publicText);
  assert.equal(pub.comments.length, 2);
  for (const secret of ["合成提议人", "自动测试厂商", "vendor@example.invalid", "session"])
    assert.ok(!publicText.includes(secret), secret);
  const privateOne = pub.comments.find((c) => c.ref === "R1-0001");
  assert.equal(privateOne.summary, "编制组摘要：引用类型需区分");
  assert.equal(privateOne.proposal, "");
  const publicOne = pub.comments.find((c) => c.ref === "R1-0002");
  assert.ok(publicOne.summary.includes("合成样例"));
  const csv = await worker.fetch(
    request("/admin/api/comments.csv", "GET", undefined, "", auth),
    env,
  );
  assert.ok((await csv.text()).includes("R1-0002"));
  const del = await worker.fetch(
    request(`/admin/api/comments/${newest.id}`, "DELETE", undefined, "", auth),
    env,
  );
  assert.equal(del.status, 200);
  const third = await worker.fetch(
    request("/api/comments", "POST", validComment, ""),
    env,
  );
  assert.equal((await third.json()).comment.ref, "R1-0002");
});

test("comment validation, origin check, size cap and rate limit fail without writes", async () => {
  const env = envFor();
  for (const change of [
    { clause: "" },
    { problem: "" },
    { category: "随便" },
    { role: "admin" },
    { sectionKey: "../x" },
    { email: "bad" },
    { clause: "a\nb" },
    { problem: "x".repeat(4001) },
    { website: "spam" },
    { allowPublic: "yes" },
  ]) {
    const res = await worker.fetch(
      request("/api/comments", "POST", { ...validComment, ...change }),
      env,
    );
    assert.equal(res.status, 400, JSON.stringify(change));
  }
  const crossSite = await worker.fetch(
    new Request(origin + "/api/comments", {
      method: "POST",
      headers: { Origin: "https://evil.example", "Content-Type": "application/json" },
      body: JSON.stringify(validComment),
    }),
    env,
  );
  assert.equal(crossSite.status, 403);
  const huge = await worker.fetch(
    request("/api/comments", "POST", { ...validComment, rationale: "长".repeat(17000) }),
    env,
  );
  assert.equal(huge.status, 400);
  env.REGISTRATION_LIMITER = { limit: async () => ({ success: false }) };
  const limited = await worker.fetch(
    request("/api/comments", "POST", validComment),
    env,
  );
  assert.equal(limited.status, 429);
  assert.equal(commentCount(env), 0);
});
