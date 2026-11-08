import React, { useEffect, useState } from "react";
import {
  ArrowLeft,
  Download,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import { registrationApi } from "./registration.jsx";
const roles = { expert: "标准专家", vendor: "应用厂商", other: "其他参与者" };
const time = (value) =>
  value ? new Date(value).toLocaleString("zh-CN") : "未确认";
export function AdminPage() {
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
