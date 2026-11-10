import consultation from "../src/consultation.json" with { type: "json" };
import { verifyAccess } from "./access.mjs";
import {
  bodyJson,
  json,
  message,
  nowIso,
  readToken,
  sameOrigin,
  sha256,
  validToken,
} from "./worker.mjs";

const roles = new Set(Object.keys(consultation.roles));
const categories = new Set(consultation.categories);
const dispositions = new Set(Object.keys(consultation.dispositions));
const BODY_LIMIT = 48 * 1024;

const text = (input, key, max, required = false, multiline = false) => {
  const raw = input[key] ?? "";
  if (typeof raw !== "string") throw new Error("意见字段格式不正确。");
  const pattern = multiline
    ? /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/
    : /[\x00-\x1f\x7f]/;
  if (pattern.test(raw)) throw new Error("意见字段含有不支持的控制字符。");
  const value = raw.replace(/\r\n?/g, "\n").trim().normalize("NFC");
  if (required && !value) throw new Error(`请填写${labels[key]}。`);
  if (value.length > max)
    throw new Error(`${labels[key]}超过 ${max} 字，请精简或拆分为多条意见。`);
  return value;
};
const labels = {
  clause: "条款位置",
  sectionKey: "章节",
  category: "评议类别",
  role: "参与身份",
  profile: "应用类型、Profile 或专业方向",
  problem: "具体问题与场景",
  proposal: "建议条文或方案",
  rationale: "依据与影响范围",
  submitter: "提议人",
  organization: "提议单位",
  email: "联系邮箱",
  response: "处理理由",
  publicSummary: "公开摘要",
};

export function validateComment(input) {
  if (!input || typeof input !== "object" || Array.isArray(input))
    throw new Error("请填写意见内容。");
  if (input.website) throw new Error("意见提交未通过校验。");
  const fields = {
    clause: text(input, "clause", 120, true),
    sectionKey: text(input, "sectionKey", 16),
    category: text(input, "category", 16, true),
    role: text(input, "role", 16, true),
    profile: text(input, "profile", 200),
    problem: text(input, "problem", 4000, true, true),
    proposal: text(input, "proposal", 4000, false, true),
    rationale: text(input, "rationale", 3000, false, true),
    submitter: text(input, "submitter", 60),
    organization: text(input, "organization", 160),
    email: text(input, "email", 254),
  };
  if (fields.sectionKey && !/^(?:[0-9]{1,2}|[a-e]|foreword|introduction)$/.test(fields.sectionKey))
    throw new Error("意见章节格式不正确。");
  if (!categories.has(fields.category)) throw new Error("请选择评议类别。");
  if (!roles.has(fields.role)) throw new Error("请选择参与身份。");
  if (fields.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(fields.email))
    throw new Error("请填写有效的联系邮箱。");
  if (input.allowPublic !== undefined && typeof input.allowPublic !== "boolean")
    throw new Error("意见公开选择格式不正确。");
  return { ...fields, allowPublic: input.allowPublic === true };
}

const ownView = (row) => ({
  ref: row.ref,
  clause: row.clause,
  category: row.category,
  createdAt: row.created_at,
  disposition: row.disposition,
  response: row.disposition === "pending" ? "" : row.response,
});
// Public view: never exposes names, organisations or e-mail. Full text only with consent.
const publicView = (row) => ({
  ref: row.ref,
  round: row.round,
  clause: row.clause,
  sectionKey: row.section_key,
  category: row.category,
  role: row.role,
  summary: row.public_summary || (row.allow_public ? row.problem : ""),
  proposal: row.allow_public ? row.proposal : "",
  disposition: row.disposition,
  response: row.response,
  respondedAt: row.responded_at,
});

async function nextRef(env) {
  const row = await env.READERS_DB.prepare(
    "SELECT MAX(CAST(substr(ref, instr(ref, '-') + 1) AS INTEGER)) AS last FROM review_comments WHERE round = ?",
  )
    .bind(consultation.round)
    .first();
  return `R${consultation.round}-${String((row?.last ?? 0) + 1).padStart(4, "0")}`;
}

export async function commentApi(request, env, url) {
  const value = readToken(request);
  const hash = validToken(value) ? await sha256(value) : "";
  if (url.pathname === "/api/comments/mine") {
    if (request.method !== "GET")
      return json({ error: "请求方式不支持。" }, 405, { Allow: "GET" });
    if (!hash) return json({ comments: [] });
    const rows = await env.READERS_DB.prepare(
      "SELECT * FROM review_comments WHERE session_hash = ? ORDER BY created_at DESC, round DESC, ref DESC LIMIT 200",
    )
      .bind(hash)
      .all();
    return json({ comments: rows.results.map(ownView) });
  }
  if (url.pathname !== "/api/comments")
    return json({ error: "接口不存在。" }, 404);
  if (request.method !== "POST")
    return json({ error: "请求方式不支持。" }, 405, { Allow: "POST" });
  if (!sameOrigin(request)) return json({ error: "来源校验失败。" }, 403);
  if (env.REGISTRATION_LIMITER) {
    const networkKey = await sha256(
      "stds-comments:" + (request.headers.get("CF-Connecting-IP") ?? "local"),
    );
    const result = await env.REGISTRATION_LIMITER.limit({ key: networkKey });
    if (!result.success)
      return json({ error: "提交较频繁，请一分钟后重试。" }, 429, {
        "Retry-After": "60",
      });
  }
  const fields = validateComment(await bodyJson(request, BODY_LIMIT));
  const now = nowIso();
  for (let attempt = 0; attempt < 5; attempt++) {
    const ref = await nextRef(env);
    const id = crypto.randomUUID();
    const result = await env.READERS_DB.prepare(
      "INSERT OR IGNORE INTO review_comments (id, ref, round, clause, section_key, category, role, profile, problem, proposal, rationale, submitter, organization, email, allow_public, document_sha, session_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    )
      .bind(
        id,
        ref,
        consultation.round,
        fields.clause,
        fields.sectionKey,
        fields.category,
        fields.role,
        fields.profile,
        fields.problem,
        fields.proposal,
        fields.rationale,
        fields.submitter,
        fields.organization,
        fields.email,
        fields.allowPublic ? 1 : 0,
        env.DOCUMENT_SHA,
        hash,
        now,
      )
      .run();
    if (!result.meta || result.meta.changes !== 0) {
      const saved = await env.READERS_DB.prepare(
        "SELECT * FROM review_comments WHERE id = ?",
      )
        .bind(id)
        .first();
      if (!saved) throw new Error("Comment readback failed");
      return json({ comment: ownView(saved) }, 201);
    }
  }
  return json({ error: "意见编号分配冲突，请稍后重试。" }, 409);
}

export async function publicCommentApi(request, env, url) {
  if (request.method !== "GET")
    return json({ error: "请求方式不支持。" }, 405, { Allow: "GET" });
  const cache = { "Cache-Control": "public, max-age=60" };
  if (url.pathname === "/api/comments/stats") {
    const rows = await env.READERS_DB.prepare(
      "SELECT disposition, COUNT(*) AS total FROM review_comments WHERE round = ? GROUP BY disposition",
    )
      .bind(consultation.round)
      .all();
    const byDisposition = Object.fromEntries(
      rows.results.map((r) => [r.disposition, r.total]),
    );
    const total = rows.results.reduce((sum, r) => sum + r.total, 0);
    return json({ round: consultation.round, total, byDisposition }, 200, cache);
  }
  const rows = await env.READERS_DB.prepare(
    "SELECT * FROM review_comments WHERE disposition != 'pending' ORDER BY round, ref LIMIT 2000",
  ).all();
  return json({ comments: rows.results.map(publicView) }, 200, cache);
}

const csvCell = (value) => {
  const raw = String(value ?? "");
  return `"${(/^[=+\-@\t\r]/.test(raw) ? "'" + raw : raw).replaceAll('"', '""')}"`;
};

export async function adminCommentApi(request, env, url) {
  const admin = await verifyAccess(request, env);
  if (!admin) return json({ error: "需要使用获授权邮箱登录管理端。" }, 401);
  const id = url.pathname.match(
    /^\/admin\/api\/comments\/([a-f0-9-]{36})$/,
  )?.[1];
  if (id) {
    if (!sameOrigin(request)) return json({ error: "来源校验失败。" }, 403);
    if (request.method === "DELETE") {
      await env.READERS_DB.prepare("DELETE FROM review_comments WHERE id = ?")
        .bind(id)
        .run();
      return json({ deleted: true });
    }
    if (request.method !== "PUT")
      return json({ error: "请求方式不支持。" }, 405, { Allow: "PUT, DELETE" });
    const input = await bodyJson(request, BODY_LIMIT);
    if (!dispositions.has(input.disposition))
      return message("请选择处理结论。");
    const response = text(input, "response", 3000, false, true);
    const summary = text(input, "publicSummary", 1000, false, true);
    if (input.disposition !== "pending" && !response)
      return message("请填写处理理由。");
    await env.READERS_DB.prepare(
      "UPDATE review_comments SET disposition = ?, response = ?, public_summary = ?, responded_at = ? WHERE id = ?",
    )
      .bind(
        input.disposition,
        response,
        summary,
        input.disposition === "pending" ? null : nowIso(),
        id,
      )
      .run();
    const saved = await env.READERS_DB.prepare(
      "SELECT * FROM review_comments WHERE id = ?",
    )
      .bind(id)
      .first();
    if (!saved) return json({ error: "记录不存在。" }, 404);
    return json({ comment: adminView(saved) });
  }
  if (request.method !== "GET")
    return json({ error: "请求方式不支持。" }, 405, { Allow: "GET" });
  if (!["/admin/api/comments", "/admin/api/comments.csv"].includes(url.pathname))
    return json({ error: "接口不存在。" }, 404);
  const q = (url.searchParams.get("q") ?? "").trim();
  if (q.length > 80) return message("搜索内容过长。");
  const search = `%${q.replace(/[\\%_]/g, "\\$&")}%`;
  const conditions = [
    "(clause LIKE ? ESCAPE '\\' OR problem LIKE ? ESCAPE '\\' OR organization LIKE ? ESCAPE '\\' OR submitter LIKE ? ESCAPE '\\' OR ref LIKE ? ESCAPE '\\')",
  ];
  const args = [search, search, search, search, search];
  for (const [param, column, allowed] of [
    ["disposition", "disposition", dispositions],
    ["role", "role", roles],
    ["category", "category", categories],
  ]) {
    const value = url.searchParams.get(param);
    if (!value) continue;
    if (!allowed.has(value)) return message("筛选条件不正确。");
    conditions.push(`${column} = ?`);
    args.push(value);
  }
  const section = url.searchParams.get("section");
  if (section) {
    if (!/^(?:[0-9]{1,2}|[a-e]|foreword|introduction)$/.test(section))
      return message("筛选条件不正确。");
    conditions.push("section_key = ?");
    args.push(section);
  }
  const where = conditions.join(" AND ");
  if (url.pathname.endsWith(".csv")) {
    const rows = await env.READERS_DB.prepare(
      `SELECT * FROM review_comments WHERE ${where} ORDER BY round, ref LIMIT 5000`,
    )
      .bind(...args)
      .all();
    const lines = [
      [
        "意见编号",
        "轮次",
        "条款位置",
        "评议类别",
        "参与身份",
        "应用类型/Profile/方向",
        "具体问题与场景",
        "建议条文或方案",
        "依据与影响范围",
        "提议人",
        "提议单位",
        "联系邮箱",
        "同意公开全文",
        "提交时间",
        "处理结论",
        "处理理由",
        "公开摘要",
      ],
      ...rows.results.map((r) => [
        r.ref,
        r.round,
        r.clause,
        r.category,
        consultation.roles[r.role],
        r.profile,
        r.problem,
        r.proposal,
        r.rationale,
        r.submitter,
        r.organization,
        r.email,
        r.allow_public ? "是" : "否",
        r.created_at,
        consultation.dispositions[r.disposition],
        r.response,
        r.public_summary,
      ]),
    ];
    return new Response(
      "﻿" + lines.map((line) => line.map(csvCell).join(",")).join("\r\n"),
      {
        headers: {
          "Content-Type": "text/csv; charset=utf-8",
          "Cache-Control": "private, no-store",
          "X-Content-Type-Options": "nosniff",
          "Content-Disposition": 'attachment; filename="review-comments.csv"',
        },
      },
    );
  }
  const offset = Number(url.searchParams.get("offset") ?? 0);
  if (!Number.isSafeInteger(offset) || offset < 0 || offset > 1000000)
    return message("分页参数不正确。");
  const count = await env.READERS_DB.prepare(
    `SELECT COUNT(*) AS total FROM review_comments WHERE ${where}`,
  )
    .bind(...args)
    .first();
  const rows = await env.READERS_DB.prepare(
    `SELECT * FROM review_comments WHERE ${where} ORDER BY created_at DESC, round DESC, ref DESC LIMIT 50 OFFSET ?`,
  )
    .bind(...args, offset)
    .all();
  return json({
    email: admin.email,
    total: count.total,
    offset,
    limit: 50,
    comments: rows.results.map(adminView),
  });
}

const adminView = (r) => ({
  id: r.id,
  ref: r.ref,
  round: r.round,
  clause: r.clause,
  sectionKey: r.section_key,
  category: r.category,
  role: r.role,
  profile: r.profile,
  problem: r.problem,
  proposal: r.proposal,
  rationale: r.rationale,
  submitter: r.submitter,
  organization: r.organization,
  email: r.email,
  allowPublic: r.allow_public === 1,
  createdAt: r.created_at,
  disposition: r.disposition,
  response: r.response,
  publicSummary: r.public_summary,
  respondedAt: r.responded_at,
});
