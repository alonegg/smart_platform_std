import policy from "../src/registration-policy.json" with { type: "json" };
import documentInfo from "./document-info.json" with { type: "json" };
import { verifyAccess } from "./access.mjs";
import {
  commentApi,
  adminCommentApi,
  publicCommentApi,
} from "./comments.mjs";
import { publicationPausedResponse } from "./publication.mjs";

const cookieName = (request) =>
  new URL(request.url).protocol === "https:"
    ? "__Host-stds_reader"
    : "stds_reader_dev";
const roles = new Set(["expert", "vendor", "other"]);
export const sha256 = async (value) =>
  [
    ...new Uint8Array(
      await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)),
    ),
  ]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
export const token = () =>
  [...crypto.getRandomValues(new Uint8Array(32))]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
const headers = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "private, no-store",
  Vary: "Cookie",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "same-origin",
};
export const json = (value, status = 200, extra = {}) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { ...headers, ...extra },
  });
export const cookie = (value, request, maxAge = policy.retentionDays * 86400) =>
  `${cookieName(request)}=${value}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}${new URL(request.url).protocol === "https:" ? "; Secure" : ""}`;
export const readToken = (request) =>
  request.headers
    .get("Cookie")
    ?.split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${cookieName(request)}=`))
    ?.slice(cookieName(request).length + 1);
export const validToken = (value) =>
  typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
export const nowIso = () => new Date().toISOString();
const expiresIso = () =>
  new Date(Date.now() + policy.retentionDays * 86400000).toISOString();
export const message = (error) => json({ error }, 400);

export function validateRegistration(input) {
  if (!input || typeof input !== "object" || Array.isArray(input))
    throw new Error("请填写登记信息。");
  const clean = (key, max, required = false) => {
    const raw = input[key] ?? "";
    if (typeof raw !== "string" || /[\x00-\x1f\x7f]/.test(raw))
      throw new Error("登记字段格式不正确。");
    const value = raw.trim().normalize("NFC");
    if (value.length > max || (required && value.length < 1))
      throw new Error("请检查姓名、单位和字段长度。");
    return value;
  };
  const fields = {
    name: clean("name", 60, true),
    organization: clean("organization", 160, true),
    role: clean("role", 16, true),
    field: clean("field", 120),
    email: clean("email", 254),
  };
  if (!roles.has(fields.role)) throw new Error("请选择参与身份。");
  if (fields.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(fields.email))
    throw new Error("请填写有效邮箱。");
  if (
    input.allowContact !== undefined &&
    typeof input.allowContact !== "boolean"
  )
    throw new Error("联系选择格式不正确。");
  if (input.allowContact && !fields.email)
    throw new Error("允许后续联系时请填写邮箱。");
  if (
    input.consent !== true ||
    input.consentVersion !== policy.version
  )
    throw new Error("请阅读并确认登记说明。");
  if (input.website) throw new Error("登记请求未通过校验。");
  return { ...fields, allowContact: input.allowContact === true };
}

export async function bodyJson(request, limit = 4096) {
  if (
    !request.headers
      .get("Content-Type")
      ?.toLowerCase()
      .startsWith("application/json")
  )
    throw new Error("请使用 JSON 提交。");
  if (Number(request.headers.get("Content-Length") ?? 0) > limit)
    throw new Error("提交内容过长，请精简后重试。");
  const reader = request.body?.getReader();
  if (!reader) throw new Error("提交内容为空，请填写后重试。");
  let total = 0;
  const chunks = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > limit) {
      await reader.cancel();
      throw new Error("提交内容过长，请精简后重试。");
    }
    chunks.push(value);
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.length;
  }
  try {
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    throw new Error("提交内容格式不正确，请刷新后重试。");
  }
}

const publicRow = (row, env) =>
  row
    ? {
        id: row.id,
        name: row.name,
        organization: row.organization,
        role: row.role,
        field: row.field,
        email: row.email,
        allowContact: row.allow_contact === 1,
        createdAt: row.created_at,
        expiresAt: row.expires_at,
        consentVersion: row.consent_version,
        requiresConsent: row.consent_version !== policy.version,
        readConfirmedAt:
          row.read_document_sha === env.DOCUMENT_SHA
            ? row.read_confirmed_at
            : null,
      }
    : null;
async function readerRow(request, env) {
  const value = readToken(request);
  if (!validToken(value)) return null;
  return env.READERS_DB.prepare(
    "SELECT * FROM reader_registrations WHERE session_hash = ? AND expires_at > ?",
  )
    .bind(await sha256(value), nowIso())
    .first();
}
export const sameOrigin = (request) =>
  request.headers.get("Origin") === new URL(request.url).origin;
const methodAllowed = (request, allowed) => allowed.includes(request.method);
const protectedResponse = (response) => {
  const result = new Response(response.body, response);
  result.headers.set("Cache-Control", "private, no-store");
  result.headers.set("Vary", "Cookie");
  result.headers.set("X-Robots-Tag", "noindex, nofollow");
  return result;
};

async function adminApi(request, env, url) {
  const admin = await verifyAccess(request, env);
  if (!admin) return json({ error: "需要使用获授权邮箱登录管理端。" }, 401);
  if (request.method === "DELETE") {
    if (!sameOrigin(request)) return json({ error: "来源校验失败。" }, 403);
    const id = url.pathname.match(
      /^\/admin\/api\/readers\/([a-f0-9-]{36})$/,
    )?.[1];
    if (!id) return json({ error: "记录不存在。" }, 404);
    await env.READERS_DB.prepare(
      "DELETE FROM reader_registrations WHERE id = ?",
    )
      .bind(id)
      .run();
    return json({ deleted: true });
  }
  if (request.method !== "GET")
    return json({ error: "请求方式不支持。" }, 405, { Allow: "GET, DELETE" });
  if (!["/admin/api/readers", "/admin/api/readers.csv"].includes(url.pathname))
    return json({ error: "接口不存在。" }, 404);
  const q = (url.searchParams.get("q") ?? "").trim();
  if (q.length > 80) return message("搜索内容过长。");
  const search = q.replace(/[\\%_]/g, "\\$&");
  const condition =
    "expires_at > ? AND (name LIKE ? ESCAPE '\\' OR organization LIKE ? ESCAPE '\\' OR email LIKE ? ESCAPE '\\')";
  const args = [nowIso(), `%${search}%`, `%${search}%`, `%${search}%`];
  const count = await env.READERS_DB.prepare(
    `SELECT COUNT(*) AS total FROM reader_registrations WHERE ${condition}`,
  )
    .bind(...args)
    .first();
  if (url.pathname.endsWith(".csv")) {
    if (count.total > 5000)
      return message("超过 5000 条，请缩小筛选范围后导出。");
    const records = await env.READERS_DB.prepare(
      `SELECT name, organization, role, field, email, allow_contact, created_at, read_confirmed_at, read_document_sha FROM reader_registrations WHERE ${condition} ORDER BY created_at DESC, id DESC LIMIT 5000`,
    )
      .bind(...args)
      .all();
    const cell = (value) => {
      const text = String(value ?? "");
      return `"${(/^[=+\-@\t\r]/.test(text) ? "'" + text : text).replaceAll('"', '""')}"`;
    };
    const lines = [
      [
        "姓名",
        "单位或身份",
        "参与角色",
        "专业方向",
        "邮箱",
        "允许联系",
        "登记时间",
        "本人确认已阅时间",
      ],
      ...records.results.map((r) => [
        r.name,
        r.organization,
        r.role,
        r.field,
        r.email,
        r.allow_contact ? "是" : "否",
        r.created_at,
        r.read_document_sha === env.DOCUMENT_SHA ? r.read_confirmed_at : "",
      ]),
    ];
    return new Response(
      "\ufeff" + lines.map((line) => line.map(cell).join(",")).join("\r\n"),
      {
        headers: {
          ...headers,
          "Content-Type": "text/csv; charset=utf-8",
          "Content-Disposition":
            'attachment; filename="reader-registrations.csv"',
        },
      },
    );
  }
  const offset = Number(url.searchParams.get("offset") ?? 0);
  if (!Number.isSafeInteger(offset) || offset < 0 || offset > 1000000)
    return message("分页参数不正确。");
  const rows = await env.READERS_DB.prepare(
    `SELECT id, name, organization, role, field, email, allow_contact, consent_version, created_at, expires_at, read_confirmed_at, read_document_sha FROM reader_registrations WHERE ${condition} ORDER BY created_at DESC, id DESC LIMIT 50 OFFSET ?`,
  )
    .bind(...args, offset)
    .all();
  return json({
    email: admin.email,
    total: count.total,
    offset,
    limit: 50,
    readers: rows.results.map((r) => ({
      ...publicRow(r, env),
      consentVersion: r.consent_version,
    })),
  });
}

export async function handleRequest(request, env) {
  const url = new URL(request.url);
  if (
    url.protocol !== "https:" &&
    !["localhost", "127.0.0.1"].includes(url.hostname)
  )
    return Response.redirect(
      new URL(url.pathname + url.search, "https://" + url.host).href,
      308,
    );
  if (env.PUBLICATION_PAUSED === "true")
    return publicationPausedResponse(request);
  if (url.pathname.startsWith("/admin/api/comments"))
    return adminCommentApi(request, env, url);
  if (url.pathname.startsWith("/admin/api/"))
    return adminApi(request, env, url);
  if (url.pathname === "/admin" || url.pathname.startsWith("/admin/")) {
    if (!(await verifyAccess(request, env)))
      return new Response("请使用管理端登录链接，以获授权邮箱登录。", {
        status: 401,
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          "Cache-Control": "no-store",
        },
      });
    return protectedResponse(await env.ASSETS.fetch(request));
  }
  if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(request);
  if (url.pathname === "/api/registration/config")
    return request.method === "GET"
      ? json({ ...policy, available: Boolean(env.READERS_DB) })
      : json({ error: "请求方式不支持。" }, 405);
  if (!env.READERS_DB)
    return json({ error: "登记服务暂不可用，请稍后重试。" }, 503);
  if (url.pathname.startsWith("/api/comments/public") || url.pathname === "/api/comments/stats")
    return publicCommentApi(request, env, url);
  if (url.pathname.startsWith("/api/comments"))
    return commentApi(request, env, url);
  if (
    url.pathname === "/api/registration/session" &&
    request.method === "GET"
  ) {
    const value = readToken(request);
    const row = await readerRow(request, env);
    return json(
      { registration: publicRow(row, env), consentVersion: policy.version },
      200,
      validToken(value) ? {} : { "Set-Cookie": cookie(token(), request) },
    );
  }
  const validRoutes = [
    "/api/registration",
    "/api/registration/read-confirmation",
  ];
  if (!validRoutes.includes(url.pathname))
    return json({ error: "接口不存在。" }, 404);
  if (!sameOrigin(request)) return json({ error: "来源校验失败。" }, 403);
  if (
    !methodAllowed(
      request,
      url.pathname.endsWith("read-confirmation")
        ? ["POST"]
        : ["POST", "PUT", "DELETE"],
    )
  )
    return json({ error: "请求方式不支持。" }, 405);
  const value = readToken(request);
  if (!validToken(value))
    return json({ error: "请刷新页面以初始化登记会话。" }, 409);
  const hash = await sha256(value);
  if (request.method === "DELETE") {
    await env.READERS_DB.prepare(
      "DELETE FROM reader_registrations WHERE session_hash = ?",
    )
      .bind(hash)
      .run();
    return json({ deleted: true }, 200, {
      "Set-Cookie": cookie("", request, 0),
    });
  }
  if (url.pathname.endsWith("read-confirmation")) {
    const row = await readerRow(request, env);
    if (!row) return json({ error: "请先登记。" }, 401);
    const input = await bodyJson(request);
    if (input.confirmed !== true)
      return message("请确认是由本人提交已阅状态。");
    await env.READERS_DB.prepare(
      "UPDATE reader_registrations SET read_confirmed_at = ?, read_document_sha = ?, updated_at = ? WHERE id = ?",
    )
      .bind(nowIso(), env.DOCUMENT_SHA, nowIso(), row.id)
      .run();
    return json({
      registration: publicRow(await readerRow(request, env), env),
    });
  }
  if (env.REGISTRATION_LIMITER) {
    const networkKey = await sha256(
      "stds-readers:" + (request.headers.get("CF-Connecting-IP") ?? "local"),
    );
    const result = await env.REGISTRATION_LIMITER.limit({ key: networkKey });
    if (!result.success)
      return json({ error: "提交较频繁，请一分钟后重试。" }, 429, {
        "Retry-After": "60",
      });
  }
  const fields = validateRegistration(await bodyJson(request));
  const row = await readerRow(request, env);
  if (request.method === "POST" && row) {
    const previous = publicRow(row, env);
    if (Object.keys(fields).some((key) => fields[key] !== previous[key]))
      return json({ error: "已有登记，请使用修改登记入口。" }, 409);
    return json({ registration: previous });
  }
  if (request.method === "PUT" && !row)
    return json({ error: "登记已失效，请重新登记。" }, 409);
  const now = nowIso();
  if (request.method === "PUT") {
    const identityChanged =
      fields.name !== row.name ||
      fields.organization !== row.organization ||
      fields.role !== row.role;
    await env.READERS_DB.prepare(
      "UPDATE reader_registrations SET name=?, organization=?, role=?, field=?, email=?, allow_contact=?, consent_version=?, consented_at=?, international_consent_at=?, updated_at=?, expires_at=?, read_confirmed_at=?, read_document_sha=? WHERE id=?",
    )
      .bind(
        fields.name,
        fields.organization,
        fields.role,
        fields.field,
        fields.email,
        fields.allowContact ? 1 : 0,
        policy.version,
        now,
        now,
        now,
        expiresIso(),
        identityChanged ? null : row.read_confirmed_at,
        identityChanged ? null : row.read_document_sha,
        row.id,
      )
      .run();
  } else {
    await env.READERS_DB.prepare(
      "DELETE FROM reader_registrations WHERE session_hash = ? AND expires_at <= ?",
    )
      .bind(hash, nowIso())
      .run();
    const entry =
      typeof request.headers.get("X-Reading-Entry") === "string"
        ? request.headers.get("X-Reading-Entry")
        : "/";
    const entryPath =
      /^\/(?:read\/[a-z0-9]+\/|profiles\/|architecture\/|roadmap\/|decisions\/|downloads\/)?$/.test(
        entry ?? "",
      )
        ? entry
        : "/";
    await env.READERS_DB.prepare(
      "INSERT OR IGNORE INTO reader_registrations (id, session_hash, name, organization, role, field, email, allow_contact, consent_version, consented_at, international_consent_at, entry_path, document_sha, created_at, updated_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    )
      .bind(
        crypto.randomUUID(),
        hash,
        fields.name,
        fields.organization,
        fields.role,
        fields.field,
        fields.email,
        fields.allowContact ? 1 : 0,
        policy.version,
        now,
        now,
        entryPath,
        env.DOCUMENT_SHA,
        now,
        now,
        expiresIso(),
      )
      .run();
  }
  const saved = await readerRow(request, env);
  if (!saved) throw new Error("Registration readback failed");
  if (
    Object.keys(fields).some(
      (key) => fields[key] !== publicRow(saved, env)[key],
    )
  )
    return json({ error: "并发登记内容不一致，请刷新后核对本人记录。" }, 409);
  return json(
    { registration: publicRow(saved, env) },
    request.method === "POST" ? 201 : 200,
    { "Set-Cookie": cookie(value, request) },
  );
}

export default {
  async fetch(request, env) {
    try {
      return await handleRequest(request, {
        ...env,
        DOCUMENT_SHA: documentInfo.sourceSha,
      });
    } catch (error) {
      if (error instanceof Error && /请|登记字段|登记内容|提交内容|意见/.test(error.message))
        return message(error.message);
      return json(
        { error: "服务暂时不可用，信息尚未确认保存。请稍后重试。" },
        503,
      );
    }
  },
  async scheduled(event, env) {
    await env.READERS_DB.prepare(
      "DELETE FROM reader_registrations WHERE expires_at <= ?",
    )
      .bind(nowIso())
      .run();
  },
};
