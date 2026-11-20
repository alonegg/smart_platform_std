import React, { useState } from "react";
import App from "../App.jsx";
import { routes as reviewRoutes } from "../shared.jsx";
import comparison from "./comparison.json";
import "./preview.css";

export const routes = [...reviewRoutes, "/compare/"];

function Compare() {
  const [changesOnly, setChangesOnly] = useState(true);
  const rows = comparison.filter((row) => !changesOnly || row.kind !== "未改动");
  return (
    <main id="main-content" className="topic-page r2-compare">
      <p className="eyebrow">INTERNAL REVISION PREVIEW</p>
      <h1>条款对照</h1>
      <p className="page-lead">维护用内部预览。左侧为当前正文，右侧为第2轮修订稿；不表示标准已获批准或验证。</p>
      <label className="r2-filter"><input type="checkbox" checked={changesOnly} onChange={(event) => setChangesOnly(event.target.checked)} />只看改动</label>
      <p role="status">显示 {rows.length} 个条款单元</p>
      <div className="r2-comparison-list">
        {rows.map((row) => <section key={row.clause} className={`r2-comparison ${row.kind !== "未改动" ? "changed" : ""}`}>
          <h2>{row.clause} <small>{row.kind}</small></h2>
          <p className="r2-references">修订编号：{row.revisions.join("、") || "—"} · Issue：{row.issues.length ? row.issues.map((n) => <a key={n} href={`https://github.com/alonegg/smart_platform_std/issues/${n}`} target="_blank" rel="noreferrer">#{n} </a>) : "—（修订清单未关联 Issue）"}</p>
          <div className="r2-columns">
            <div><h3>当前正文</h3><pre>{row.before || "（无此条款）"}</pre></div>
            <div><h3>第2轮修订稿</h3><pre>{row.after || "（无此条款）"}</pre></div>
          </div>
        </section>)}
      </div>
    </main>
  );
}

export default function PreviewApp({ initialPath = "/" }) {
  const compare = /^\/compare\/?$/.test(initialPath.split("?")[0]);
  return <>
    <div className="r2-edition-bar" role="note" aria-label="预览状态">
      <strong>第2轮修订稿预览，非现行征求意见稿</strong>
      <nav aria-label="内部预览"><a href="/">阅读修订稿</a><a href="/compare/">条款对照</a><a href="/downloads/">下载修订稿</a></nav>
    </div>
    {compare ? <Compare /> : <App initialPath={initialPath} />}
  </>;
}
