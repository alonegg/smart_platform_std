import React, { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  CalendarClock,
  Check,
  CircleAlert,
  MessageSquareText,
  Send,
} from "lucide-react";
import data from "./generated.json";
import consultation from "./consultation.json";
import { AppLink, cleanTitle, githubIssueHref } from "./shared.jsx";
import { registrationApi } from "./registration.jsx";

const zhDate = (value) =>
  value ? value.replaceAll("-", "/") : "";
export const deadlineText = `${zhDate(consultation.deadline)}${consultation.deadlineNote ? `（${consultation.deadlineNote}）` : ""}`;

export function useCommentStats() {
  const [stats, setStats] = useState(null);
  useEffect(() => {
    let active = true;
    fetch("/api/comments/stats", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((value) => active && setStats(value))
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);
  return stats;
}

export function ConsultationStrip({ navigate }) {
  const stats = useCommentStats();
  return (
    <div className="consultation-strip" role="note" aria-label="征求意见安排">
      <CalendarClock size={15} />
      <span>
        <strong>征求意见稿 · {consultation.roundLabel}</strong>
        <span className="strip-sep">·</span>意见截止 {deadlineText}
        {stats?.total ? (
          <>
            <span className="strip-sep">·</span>已收到意见 {stats.total} 条
          </>
        ) : null}
      </span>
      <AppLink to="/comment/" navigate={navigate}>
        提交意见 <ArrowRight size={13} />
      </AppLink>
      <AppLink to="/responses/" navigate={navigate}>
        处理情况
      </AppLink>
    </div>
  );
}

const sectionOptions = data.sections.map((s) => ({
  key: s.key,
  title: s.title,
}));
const emptyForm = {
  clause: "",
  sectionKey: "",
  category: "",
  role: "",
  profile: "",
  problem: "",
  proposal: "",
  rationale: "",
  submitter: "",
  organization: "",
  email: "",
  allowPublic: false,
  website: "",
};

export function CommentPage({ navigate, registration }) {
  const [form, setForm] = useState(emptyForm);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const [submitted, setSubmitted] = useState(null);
  const [mine, setMine] = useState([]);
  const loadMine = () =>
    registrationApi("/api/comments/mine")
      .then((r) => setMine(r.comments))
      .catch(() => {});
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const clause = params.get("clause")?.slice(0, 120) ?? "";
    const section = params.get("section") ?? "";
    const known = sectionOptions.find((s) => s.key === section);
    setForm((current) => ({
      ...current,
      clause: clause || (known ? known.title : current.clause),
      sectionKey: known ? known.key : current.sectionKey,
    }));
    // Prefill identity from the reader's own registration when available.
    registrationApi("/api/registration/session")
      .then((r) => {
        const reg = r.registration;
        if (!reg) return;
        setForm((current) => ({
          ...current,
          submitter: current.submitter || reg.name,
          organization: current.organization || reg.organization,
          email: current.email || reg.email,
          role:
            current.role ||
            (["vendor", "expert", "other"].includes(reg.role) ? reg.role : ""),
        }));
      })
      .catch(() => {})
      .finally(loadMine);
  }, []);
  const update = (key) => (event) =>
    setForm((current) => ({
      ...current,
      [key]:
        event.target.type === "checkbox"
          ? event.target.checked
          : event.target.value,
    }));
  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setFailure("");
    try {
      const result = await registrationApi("/api/comments", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setSubmitted(result.comment);
      setForm((current) => ({
        ...emptyForm,
        role: current.role,
        profile: current.profile,
        submitter: current.submitter,
        organization: current.organization,
        email: current.email,
        allowPublic: current.allowPublic,
      }));
      loadMine();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      setFailure(error.message);
    } finally {
      setBusy(false);
    }
  };
  const sectionLink = form.sectionKey
    ? `/read/${form.sectionKey}/${/^(?:\d+|[A-E])(?:\.\d+)+$/.test(form.clause) ? `#clause-${form.clause.replaceAll(".", "-")}` : ""}`
    : "";
  return (
    <div className="topic-page page-enter comment-page" data-screen-label="提交意见">
      <p className="eyebrow">SUBMIT A REVIEW COMMENT</p>
      <h1>按条款提交意见</h1>
      <p className="page-lead">
        {consultation.roundLabel}，截止 {deadlineText}。意见直接提交给编制组（
        {consultation.draftingUnit}），不需要 GitHub 账号；默认不公开。每条意见宜只讨论一个问题，多个问题请分条提交。
      </p>
      {submitted && (
        <div className="comment-success" role="status">
          <Check size={18} />
          <div>
            <strong>已收到意见，编号 {submitted.ref}</strong>
            <p>
              请保留编号以便查询。处理结论将在
              <AppLink to="/responses/" navigate={navigate}>
                意见处理情况
              </AppLink>
              中发布；你也可以在本页下方查看本浏览器提交过的意见。
            </p>
          </div>
        </div>
      )}
      <form className="comment-form" onSubmit={submit}>
        <fieldset>
          <legend>1　意见定位</legend>
          <div className="registration-fields">
            <label>
              条款位置<span>必填</span>
              <input
                name="clause"
                required
                maxLength={120}
                placeholder="如 5.1.3、表 A.1、字段 version_id、E07"
                value={form.clause}
                onChange={update("clause")}
              />
            </label>
            <label>
              所在章节<span>选填</span>
              <select
                name="sectionKey"
                value={form.sectionKey}
                onChange={update("sectionKey")}
              >
                <option value="">不指定</option>
                {sectionOptions.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              评议类别<span>必填</span>
              <select
                name="category"
                required
                value={form.category}
                onChange={update("category")}
              >
                <option value="">请选择</option>
                {consultation.categories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <label>
              参与身份<span>必填</span>
              <select
                name="role"
                required
                value={form.role}
                onChange={update("role")}
              >
                <option value="">请选择</option>
                {Object.entries(consultation.roles).map(([value, title]) => (
                  <option key={value} value={value}>
                    {title}
                  </option>
                ))}
              </select>
            </label>
            <label className="full">
              应用类型与能力 Profile，或专业方向<span>选填</span>
              <input
                name="profile"
                maxLength={200}
                placeholder="厂商可填产品承担的业务及拟声明的 Profile，如 P-SUB、P-GRD；专家可填专业方向"
                value={form.profile}
                onChange={update("profile")}
              />
            </label>
          </div>
          {sectionLink && (
            <AppLink className="text-link" to={sectionLink} navigate={navigate}>
              对照原文 <ArrowUpRight size={14} />
            </AppLink>
          )}
        </fieldset>
        <fieldset>
          <legend>2　意见内容</legend>
          <label className="comment-area">
            具体问题与场景<span>必填</span>
            <textarea
              name="problem"
              required
              rows={6}
              maxLength={4000}
              placeholder="说明歧义、缺漏、冲突或难以实现的情形，并给出具体业务或技术场景。请使用合成或脱敏样例。"
              value={form.problem}
              onChange={update("problem")}
            />
          </label>
          <label className="comment-area">
            建议条文或方案<span>建议填写</span>
            <textarea
              name="proposal"
              rows={5}
              maxLength={4000}
              placeholder="给出建议文字、字段定义、处理规则或测试条件。"
              value={form.proposal}
              onChange={update("proposal")}
            />
          </label>
          <label className="comment-area">
            技术或业务依据与影响范围<span>选填</span>
            <textarea
              name="rationale"
              rows={4}
              maxLength={3000}
              placeholder="引用的标准、产品实践、关联条款及对实现的影响。"
              value={form.rationale}
              onChange={update("rationale")}
            />
          </label>
        </fieldset>
        <fieldset>
          <legend>3　提议方（均为选填）</legend>
          <div className="registration-fields">
            <label>
              提议人
              <input
                name="submitter"
                autoComplete="name"
                maxLength={60}
                value={form.submitter}
                onChange={update("submitter")}
              />
            </label>
            <label>
              提议单位
              <input
                name="organization"
                autoComplete="organization"
                maxLength={160}
                value={form.organization}
                onChange={update("organization")}
              />
            </label>
            <label className="full">
              联系邮箱（编制组需要澄清时使用）
              <input
                name="email"
                type="email"
                autoComplete="email"
                maxLength={254}
                value={form.email}
                onChange={update("email")}
              />
            </label>
          </div>
          <label className="registration-check optional">
            <input
              type="checkbox"
              checked={form.allowPublic}
              onChange={update("allowPublic")}
            />
            同意在“意见处理情况”中公开本意见的问题与建议原文（不公开提议人、单位和邮箱）。不勾选时，仅公开编制组撰写的摘要与处理结论。
          </label>
          <input
            className="visually-hidden"
            tabIndex={-1}
            autoComplete="off"
            aria-hidden="true"
            name="website"
            value={form.website}
            onChange={update("website")}
          />
        </fieldset>
        {failure && (
          <div className="registration-error" role="alert">
            {failure}
          </div>
        )}
        <div className="registration-actions">
          <button className="button primary" type="submit" disabled={busy}>
            <Send size={16} />
            {busy ? "正在提交…" : "提交意见"}
          </button>
          <span className="small-muted">
            提交即表示同意编制组为处理意见保存上述信息，详见
            <AppLink to="/privacy/" navigate={navigate}>
              信息处理说明
            </AppLink>
            。
          </span>
        </div>
      </form>
      {mine.length > 0 && (
        <section className="my-comments">
          <h2>本浏览器提交的意见</h2>
          <ul>
            {mine.map((c) => (
              <li key={c.ref}>
                <code>{c.ref}</code>
                <span>{c.clause}</span>
                <span className={`disposition ${c.disposition}`}>
                  {consultation.dispositions[c.disposition]}
                </span>
                {c.response && <p>{c.response}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}
      <div className="callout">
        <strong>其他提交方式</strong>
        <p>
          也可下载评议意见表（Word，多行汇总格式）填写后发送至
          <a href={`mailto:${consultation.contactEmail}`}>
            {consultation.contactEmail}
          </a>
          （联系人：{consultation.contactName}）；或在
          <a href={githubIssueHref()} target="_blank" rel="noreferrer">
            GitHub 上公开提交
          </a>
          。
        </p>
        <AppLink className="text-link" to="/downloads/" navigate={navigate}>
          下载评议意见表 <ArrowRight size={15} />
        </AppLink>
      </div>
    </div>
  );
}

export function ResponsesPage({ navigate }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");
  const stats = useCommentStats();
  useEffect(() => {
    fetch("/api/comments/public", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((value) => setRows(value.comments))
      .catch(() => setError("暂时无法读取处理情况，请稍后刷新。"));
  }, []);
  const shown = useMemo(
    () => (rows ?? []).filter((r) => !filter || r.disposition === filter),
    [rows, filter],
  );
  const sectionTitle = (key) =>
    data.sections.find((s) => s.key === key)?.title;
  return (
    <div className="topic-page wide-topic page-enter" data-screen-label="意见处理情况">
      <p className="eyebrow">COMMENT RESOLUTION</p>
      <h1>意见处理情况</h1>
      <p className="page-lead">
        按轮次公开意见的处理结论与理由。提议人、单位和邮箱不公开；未同意公开原文的意见，仅列出编制组撰写的摘要。本页不属于标准正文，不进入下载文稿。
      </p>
      <div className="response-stats">
        <div>
          <span>{consultation.roundLabel}</span>
          <strong>{stats?.total ?? "—"}</strong>
          <small>已收到意见（条）</small>
        </div>
        {Object.entries(consultation.dispositions).map(([key, title]) => (
          <div key={key}>
            <span>{title}</span>
            <strong>{stats ? (stats.byDisposition?.[key] ?? 0) : "—"}</strong>
          </div>
        ))}
      </div>
      <div className="response-filter">
        <label>
          按处理结论筛选
          <select
            aria-label="按处理结论筛选"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="">全部已处理意见</option>
            {Object.entries(consultation.dispositions)
              .filter(([key]) => key !== "pending")
              .map(([key, title]) => (
                <option key={key} value={key}>
                  {title}
                </option>
              ))}
          </select>
        </label>
      </div>
      {error && (
        <p className="registration-error" role="alert">
          {error}
        </p>
      )}
      {rows === null && !error && (
        <p className="small-muted" role="status">
          正在读取处理情况…
        </p>
      )}
      {rows && !shown.length && (
        <div className="empty-state">
          <CircleAlert size={18} />
          <p>
            尚无已发布的处理结论。编制组将在意见截止（{deadlineText}
            ）后集中研究并发布本轮处理情况。
          </p>
        </div>
      )}
      {shown.length > 0 && (
        <div className="table-scroll">
          <table className="response-table">
            <thead>
              <tr>
                <th>编号</th>
                <th>条款</th>
                <th>类别 / 身份</th>
                <th>意见摘要</th>
                <th>结论</th>
                <th>处理理由</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.ref}>
                  <td>
                    <code>{r.ref}</code>
                  </td>
                  <td>
                    {r.sectionKey ? (
                      <AppLink
                        to={`/read/${r.sectionKey}/${/^(?:\d+|[A-E])(?:\.\d+)+$/.test(r.clause) ? `#clause-${r.clause.replaceAll(".", "-")}` : ""}`}
                        navigate={navigate}
                        title={sectionTitle(r.sectionKey)}
                      >
                        {r.clause}
                      </AppLink>
                    ) : (
                      r.clause
                    )}
                  </td>
                  <td>
                    {r.category}
                    <small>{consultation.roles[r.role]}</small>
                  </td>
                  <td className="response-text">
                    {r.summary || "（未公开原文）"}
                    {r.proposal && (
                      <details>
                        <summary>建议原文</summary>
                        {r.proposal}
                      </details>
                    )}
                  </td>
                  <td>
                    <span className={`disposition ${r.disposition}`}>
                      {consultation.dispositions[r.disposition]}
                    </span>
                  </td>
                  <td className="response-text">{r.response}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="callout">
        <strong>对处理结论有不同意见？</strong>
        <p>
          可引用意见编号再次提交，或联系 {consultation.contactName}（
          <a href={`mailto:${consultation.contactEmail}`}>
            {consultation.contactEmail}
          </a>
          ）。
        </p>
        <AppLink className="text-link" to="/comment/" navigate={navigate}>
          提交意见 <MessageSquareText size={15} />
        </AppLink>
      </div>
    </div>
  );
}

const rank = { M: 3, C: 2, O: 1, "—": 0 };
export function QuickStart({ navigate }) {
  const [selected, setSelected] = useState(["P-SUB"]);
  const cells = useMemo(() => {
    const map = new Map();
    for (const table of data.matrixTables)
      for (const row of table.rows)
        table.columns.forEach((group, i) =>
          map.set(`${row[0].split(" ")[0]}/${group}`, row[i + 1]),
        );
    return map;
  }, []);
  const groups = data.groups.map(([code, title]) => code);
  const groupTitle = Object.fromEntries(data.groups);
  const trigger = Object.fromEntries(
    data.triggers.flatMap((t) =>
      t.group.split("、").map((g) => [g.trim(), t.condition]),
    ),
  );
  const chosen = ["P-COM", ...selected.filter((p) => p !== "P-COM")];
  const result = groups.map((group) => {
    let best = "—";
    let from = [];
    for (const p of chosen) {
      const value = cells.get(`${p}/${group}`) ?? "—";
      if (rank[value] > rank[best]) {
        best = value;
        from = [p];
      } else if (value === best && value !== "—") from.push(p);
    }
    return { group, level: best, from };
  });
  const bucket = (level) => result.filter((r) => r.level === level);
  const toggle = (code) =>
    setSelected((current) =>
      current.includes(code)
        ? current.filter((c) => c !== code)
        : [...current, code],
    );
  const chapterOf = (group) => group.split("-")[0];
  const Group = ({ r }) => (
    <li>
      <AppLink to={`/read/${chapterOf(r.group)}/`} navigate={navigate}>
        <code>{r.group}</code>
        <span>{groupTitle[r.group]}</span>
      </AppLink>
      <small>来自 {r.from.join("、")}</small>
      {r.level === "C" && trigger[r.group] && (
        <p className="trigger">触发条件：{trigger[r.group]}</p>
      )}
    </li>
  );
  return (
    <div className="topic-page wide-topic page-enter" data-screen-label="厂商速读">
      <p className="eyebrow">VENDOR QUICK START</p>
      <h1>厂商速读：我的产品要满足哪些条款？</h1>
      <p className="page-lead">
        选择产品实际承担的能力 Profile（可多选），页面按附录 A 合并适用程度：取各
        Profile 中最严格的一项，P-COM 始终计入。结果仅用于快速定位阅读范围，正式适用声明仍按附录
        A.1 逐项核定并经审核。
      </p>
      <div className="profile-selector" aria-label="选择能力 Profile（可多选）">
        {data.profiles
          .filter((p) => p.code !== "P-COM")
          .map((p) => (
            <button
              key={p.code}
              className={selected.includes(p.code) ? "active" : ""}
              aria-pressed={selected.includes(p.code)}
              onClick={() => toggle(p.code)}
              title={p.scope}
            >
              <span>{p.code}</span>
              {p.name}
            </button>
          ))}
      </div>
      <p className="small-muted">
        已选：{chosen.join(" ＋ ")}。凡产生或保存学生提交须声明 P-SUB；给出评分提议或发布反馈须声明
        P-GRD；输出认知判断或学习建议须声明 P-DIA（A.1.5）。
      </p>
      <div className="quickstart-grid">
        <section>
          <h2>
            强制 M <small>{bucket("M").length} 组 · 放行前须验证</small>
          </h2>
          <ul>{bucket("M").map((r) => <Group key={r.group} r={r} />)}</ul>
        </section>
        <section>
          <h2>
            条件 C <small>{bucket("C").length} 组 · 触发即按 M</small>
          </h2>
          <ul>{bucket("C").map((r) => <Group key={r.group} r={r} />)}</ul>
        </section>
        <section>
          <h2>
            可选 O <small>{bucket("O").length} 组 · 声明实现即按 M</small>
          </h2>
          <ul>{bucket("O").map((r) => <Group key={r.group} r={r} />)}</ul>
          <h2 className="muted-heading">
            不适用 — <small>{bucket("—").length} 组 · 相关权限保持关闭</small>
          </h2>
          <p className="small-muted">
            {bucket("—").map((r) => r.group).join("、") || "无"}
          </p>
        </section>
      </div>
      <div className="callout">
        <strong>建议阅读顺序</strong>
        <p>
          第 4 章总则（文件体系、Profile 与符合性表述）→ 第 5 章公共数据模型 → 上表 M 组所在章节 → 第 12
          章与附录 A.6 验证用例。发现无法实现或无法无损映射的要求，请直接按条款提交意见。
        </p>
        <AppLink className="text-link" to="/comment/" navigate={navigate}>
          提交意见 <ArrowRight size={15} />
        </AppLink>
        <AppLink className="text-link" to="/profiles/" navigate={navigate}>
          查看完整适用矩阵 <ArrowUpRight size={15} />
        </AppLink>
      </div>
    </div>
  );
}
