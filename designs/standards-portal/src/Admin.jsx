import React, { useEffect, useState } from "react";
import {
  ArrowLeft,
  Download,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import { registrationApi } from "./registration.jsx";
import consultation from "./consultation.json";
const roles = { expert: "标准专家", vendor: "应用厂商", other: "其他参与者" };
const time = (value) =>
  value ? new Date(value).toLocaleString("zh-CN") : "未确认";
export function AdminPage() {
  const [tab, setTab] = useState("comments");
  return (
    <>
      <nav className="admin-tabs" aria-label="管理分类">
        <button
          className={tab === "comments" ? "active" : ""}
          aria-pressed={tab === "comments"}
          onClick={() => setTab("comments")}
        >
          评议意见
        </button>
        <button
          className={tab === "readers" ? "active" : ""}
          aria-pressed={tab === "readers"}
          onClick={() => setTab("readers")}
        >
          阅读者登记
        </button>
      </nav>
      {tab === "comments" ? <AdminComments /> : <AdminReaders />}
    </>
  );
}

function AdminComments() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [filters, setFilters] = useState({ q: "", disposition: "", role: "", category: "" });
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null);
  const query = () =>
    new URLSearchParams(
      Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
    ).toString();
  const load = async () => {
    setBusy(true);
    setError("");
    try {
      setData(await registrationApi(`/admin/api/comments?${query()}&offset=${offset}`));
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    load();
  }, [filters, offset]);
  const save = async (row) => {
    try {
      await registrationApi(`/admin/api/comments/${row.id}`, {
        method: "PUT",
        body: JSON.stringify({
          disposition: editing.disposition,
          response: editing.response,
          publicSummary: editing.publicSummary,
        }),
      });
      setEditing(null);
      await load();
    } catch (failure) {
      setError(failure.message);
    }
  };
  const remove = async (row) => {
    if (!window.confirm(`确认删除意见 ${row.ref}？删除后不可恢复。`)) return;
    try {
      await registrationApi(`/admin/api/comments/${row.id}`, { method: "DELETE" });
      await load();
    } catch (failure) {
      setError(failure.message);
    }
  };
  const setFilter = (key) => (event) => {
    setOffset(0);
    setFilters((f) => ({ ...f, [key]: event.target.value }));
  };
  return (
    <main className="admin-page">
      <a className="text-link" href="/">
        <ArrowLeft size={16} />
        返回标准
      </a>
      <div className="admin-heading">
        <div>
          <p className="eyebrow">COMMENT RESOLUTION</p>
          <h1>评议意见处理</h1>
          <p>
            填写处理结论与理由后，意见出现在公开的“意见处理情况”页。提议人、单位和邮箱从不公开；未同意公开原文的意见，请填写公开摘要。
          </p>
        </div>
        <ShieldCheck size={32} />
      </div>
      <form
        className="decision-tools"
        onSubmit={(event) => {
          event.preventDefault();
          setOffset(0);
          setFilters((f) => ({ ...f, q }));
        }}
      >
        <label className="filter-input">
          <Search size={17} />
          <input
            aria-label="搜索意见"
            placeholder="编号、条款、内容、提议人或单位"
            value={q}
            onChange={(event) => setQ(event.target.value)}
          />
        </label>
        <select aria-label="处理结论" value={filters.disposition} onChange={setFilter("disposition")}>
          <option value="">全部结论</option>
          {Object.entries(consultation.dispositions).map(([k, t]) => (
            <option key={k} value={k}>{t}</option>
          ))}
        </select>
        <select aria-label="参与身份" value={filters.role} onChange={setFilter("role")}>
          <option value="">全部身份</option>
          {Object.entries(consultation.roles).map(([k, t]) => (
            <option key={k} value={k}>{t}</option>
          ))}
        </select>
        <select aria-label="评议类别" value={filters.category} onChange={setFilter("category")}>
          <option value="">全部类别</option>
          {consultation.categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <button className="button" type="submit">搜索</button>
        <button type="button" className="button" onClick={load} disabled={busy}>
          <RefreshCw size={16} />
          刷新
        </button>
        <a className="button" href={`/admin/api/comments.csv?${query()}`}>
          <Download size={16} />
          导出意见汇总表
        </a>
      </form>
      {error && <p className="registration-error" role="alert">{error}</p>}
      {busy && <p role="status" className="admin-loading">正在读取意见…</p>}
      {data && (
        <>
          <p className="result-count">当前筛选共 {data.total} 条意见</p>
          <div className="admin-comments">
            {data.comments.map((row) => (
              <article key={row.id} className="admin-comment">
                <header>
                  <code>{row.ref}</code>
                  <strong>{row.clause}</strong>
                  <span>{row.category}</span>
                  <span>{consultation.roles[row.role]}</span>
                  <span className={`disposition ${row.disposition}`}>
                    {consultation.dispositions[row.disposition]}
                  </span>
                  <small>{time(row.createdAt)}</small>
                </header>
                <dl>
                  {row.profile && (<><dt>Profile / 方向</dt><dd>{row.profile}</dd></>)}
                  <dt>问题与场景</dt><dd>{row.problem}</dd>
                  {row.proposal && (<><dt>建议条文</dt><dd>{row.proposal}</dd></>)}
                  {row.rationale && (<><dt>依据与影响</dt><dd>{row.rationale}</dd></>)}
                  <dt>提议方</dt>
                  <dd>
                    {[row.submitter, row.organization, row.email].filter(Boolean).join(" · ") || "未填写"}
                    {" · "}
                    {row.allowPublic ? "同意公开原文" : "不公开原文"}
                  </dd>
                  {row.response && editing?.id !== row.id && (
                    <><dt>处理理由</dt><dd>{row.response}</dd></>
                  )}
                  {row.publicSummary && editing?.id !== row.id && (
                    <><dt>公开摘要</dt><dd>{row.publicSummary}</dd></>
                  )}
                </dl>
                {editing?.id === row.id ? (
                  <div className="admin-resolve">
                    <select
                      aria-label="处理结论"
                      value={editing.disposition}
                      onChange={(e) => setEditing({ ...editing, disposition: e.target.value })}
                    >
                      {Object.entries(consultation.dispositions).map(([k, t]) => (
                        <option key={k} value={k}>{t}</option>
                      ))}
                    </select>
                    <textarea
                      aria-label="处理理由"
                      placeholder="处理理由（公开）"
                      rows={3}
                      value={editing.response}
                      onChange={(e) => setEditing({ ...editing, response: e.target.value })}
                    />
                    <textarea
                      aria-label="公开摘要"
                      placeholder={row.allowPublic ? "可选：公开摘要（留空则公开原文）" : "公开摘要（提议方未同意公开原文）"}
                      rows={2}
                      value={editing.publicSummary}
                      onChange={(e) => setEditing({ ...editing, publicSummary: e.target.value })}
                    />
                    <div>
                      <button className="button primary" type="button" onClick={() => save(row)}>保存</button>
                      <button className="text-link" type="button" onClick={() => setEditing(null)}>取消</button>
                    </div>
                  </div>
                ) : (
                  <div className="admin-comment-actions">
                    <button
                      className="text-link"
                      type="button"
                      onClick={() =>
                        setEditing({
                          id: row.id,
                          disposition: row.disposition,
                          response: row.response,
                          publicSummary: row.publicSummary,
                        })
                      }
                    >
                      填写处理结论
                    </button>
                    <button className="text-link danger" type="button" onClick={() => remove(row)}>
                      删除
                    </button>
                  </div>
                )}
              </article>
            ))}
            {!data.comments.length && <p className="empty-state">暂无匹配的意见。</p>}
          </div>
          <div className="admin-pagination">
            <button className="button" disabled={!offset || busy} onClick={() => setOffset(Math.max(0, offset - 50))}>上一页</button>
            <span>
              {data.comments.length ? offset + 1 : 0}—{offset + data.comments.length} / {data.total}
            </span>
            <button className="button" disabled={offset + 50 >= data.total || busy} onClick={() => setOffset(offset + 50)}>下一页</button>
          </div>
        </>
      )}
    </main>
  );
}

function AdminReaders() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const load = async () => {
    setBusy(true);
    setError("");
    try {
      setData(
        await registrationApi(
          `/admin/api/readers?q=${encodeURIComponent(filter)}&offset=${offset}`,
        ),
      );
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    load();
  }, [filter, offset]);
  const remove = async (row) => {
    if (!window.confirm("确认删除这条登记及其已阅状态？此操作不会发送通知。"))
      return;
    try {
      await registrationApi(`/admin/api/readers/${row.id}`, {
        method: "DELETE",
      });
      await load();
    } catch (failure) {
      setError(failure.message);
    }
  };
  return (
    <main className="admin-page">
      <a className="text-link" href="/">
        <ArrowLeft size={16} />
        返回标准
      </a>
      <div className="admin-heading">
        <div>
          <p className="eyebrow">PRIVATE REVIEW ADMINISTRATION</p>
          <h1>阅读者登记管理</h1>
          <p>
            登记记录与本人确认已阅分别统计。姓名和单位由参与者自行填写，未作身份认证。
          </p>
        </div>
        <ShieldCheck size={32} />
      </div>
      {data && (
        <p className="admin-identity">
          当前管理邮箱：{data.email} · 仅授权组织方可见
        </p>
      )}
      <form
        className="decision-tools"
        onSubmit={(event) => {
          event.preventDefault();
          setOffset(0);
          setFilter(q);
        }}
      >
        <label className="filter-input">
          <Search size={17} />
          <input
            aria-label="搜索登记"
            placeholder="姓名、单位或邮箱"
            value={q}
            onChange={(event) => setQ(event.target.value)}
          />
        </label>
        <button className="button" type="submit">
          搜索
        </button>
        <button type="button" className="button" onClick={load} disabled={busy}>
          <RefreshCw size={16} />
          刷新
        </button>
        <a
          className="button"
          href={`/admin/api/readers.csv?q=${encodeURIComponent(filter)}`}
        >
          <Download size={16} />
          导出筛选结果
        </a>
      </form>
      {error && (
        <p className="registration-error" role="alert">
          {error}
        </p>
      )}
      {busy && (
        <p role="status" className="admin-loading">
          正在读取登记…
        </p>
      )}
      {data && (
        <>
          <p className="result-count">
            当前筛选共 {data.total} 条登记记录 · 导出最多 5000 条
          </p>
          <div className="table-scroll admin-table">
            <table>
              <thead>
                <tr>
                  {[
                    "姓名",
                    "单位或身份",
                    "参与角色",
                    "方向",
                    "邮箱 / 联系意愿",
                    "登记时间",
                    "本人确认已阅",
                    "操作",
                  ].map((title) => (
                    <th key={title}>{title}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.readers.map((row) => (
                  <tr key={row.id}>
                    <td>{row.name}</td>
                    <td>{row.organization}</td>
                    <td>{roles[row.role]}</td>
                    <td>{row.field || "—"}</td>
                    <td>
                      {row.email || "—"}
                      <small>
                        {row.allowContact ? "允许后续联系" : "未允许后续联系"}
                      </small>
                    </td>
                    <td>{time(row.createdAt)}</td>
                    <td>{time(row.readConfirmedAt)}</td>
                    <td>
                      <button
                        className="text-link danger"
                        type="button"
                        onClick={() => remove(row)}
                      >
                        删除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!data.readers.length && (
              <p className="empty-state">暂无匹配的登记记录。</p>
            )}
          </div>
          <div className="admin-pagination">
            <button
              className="button"
              disabled={!offset || busy}
              onClick={() => setOffset(Math.max(0, offset - 50))}
            >
              上一页
            </button>
            <span>
              {data.readers.length ? offset + 1 : 0}—
              {offset + data.readers.length} / {data.total}
            </span>
            <button
              className="button"
              disabled={offset + 50 >= data.total || busy}
              onClick={() => setOffset(offset + 50)}
            >
              下一页
            </button>
          </div>
        </>
      )}
      <p className="admin-footnote">
        名单仅用于本标准评议组织。公开署名或其他用途需另外征求意愿；已撤回或到期记录不会出现在名单中。
      </p>
    </main>
  );
}
