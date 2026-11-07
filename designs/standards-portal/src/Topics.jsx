import React, { useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Download,
  FileText,
  GitBranch,
  ListFilter,
  Search,
  ShieldCheck,
} from "lucide-react";
import data from "./generated.json";

import { AppLink, sourceRepo } from "./shared.jsx";
export function Profiles({ navigate }) {
  const [selected, setSelected] = useState("P-RES");
  const profile = data.profiles.find((p) => p.code === selected);
  return (
    <div
      className="topic-page wide-topic page-enter"
      data-screen-label="能力适用矩阵"
    >
      <p className="eyebrow">CAPABILITY PROFILES</p>
      <h1>按实际业务能力，确定适用要求。</h1>
      <p className="page-lead">
        所有接入应用均应满足 P-COM。一个应用可声明多个
        Profile，各条款组取最严格者；以下按单个 Profile
        查阅原表，不代替适用声明与审核。
      </p>
      <div className="profile-selector" aria-label="选择能力 Profile">
        {data.profiles.map((p) => (
          <button
            key={p.code}
            className={selected === p.code ? "active" : ""}
            aria-pressed={selected === p.code}
            onClick={() => setSelected(p.code)}
          >
            <span>{p.code}</span>
            {p.name}
          </button>
        ))}
      </div>
      <div className="profile-detail">
        <div>
          <span className="eyebrow">{profile.code}</span>
          <h2>{profile.name}</h2>
          <p>{profile.scope}</p>
        </div>
        <div>
          <span className="small-muted">权限边界</span>
          <p>{profile.boundary}</p>
        </div>
      </div>
      <div className="matrix-legend">
        <span>
          <b className="matrix-M">M</b>强制
        </span>
        <span>
          <b className="matrix-C">C</b>条件适用
        </span>
        <span>
          <b className="matrix-O">O</b>可选
        </span>
        <span>
          <b className="matrix-none">—</b>不适用
        </span>
      </div>
      {data.matrixTables.map((table, i) => (
        <div className="matrix-panel" key={i}>
          <h2>
            表 A.{i + 1}
            <span>
              第 {5 + i * 2}、{6 + i * 2} 章
            </span>
          </h2>
          <div className="table-scroll">
            <table>
              <caption className="sr-only">
                {profile.code} 与共同要求的适用程度
              </caption>
              <thead>
                <tr>
                  <th scope="col">Profile</th>
                  {table.columns.map((col) => (
                    <th scope="col" key={col}>
                      <AppLink to="/read/a/#clause-A-3" navigate={navigate}>
                        {col}
                      </AppLink>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.rows
                  .filter(
                    (row) =>
                      row[0].startsWith("P-COM ") ||
                      row[0].startsWith(`${selected} `),
                  )
                  .map((row) => (
                    <tr key={row[0]}>
                      <th scope="row">{row[0]}</th>
                      {row.slice(1).map((cell, j) => (
                        <td key={j}>
                          <b
                            className={`matrix-${cell === "—" ? "none" : cell}`}
                          >
                            {cell}
                          </b>
                        </td>
                      ))}
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
      <div className="callout">
        <strong>C 项须核对触发条件，O 项一经声明即按 M 验证。</strong>
        <p>
          “—”表示该 Profile
          不承担相应业务，相关写入权限及访问范围应保持关闭。条款组定义、触发条件与验证用例选择见附录
          A。
        </p>
        <AppLink
          className="text-link"
          to="/read/a/#clause-A-3"
          navigate={navigate}
        >
          阅读附录 A 完整规则 <ArrowRight size={15} />
        </AppLink>
      </div>
    </div>
  );
}

export function Roadmap({ navigate }) {
  return (
    <div className="topic-page page-enter" data-screen-label="实施路线">
      <p className="eyebrow">IMPLEMENTATION & RELEASE GATES</p>
      <h1>逐阶段形成成果，逐能力验证放行。</h1>
      <p className="page-lead">
        依据附录 D
        整理。阶段顺序描述拟议实施路径，进度与放行状态须由学校另行记录。
      </p>
      <div className="phase-list">
        {data.phases.map((phase, i) => (
          <section key={phase.name}>
            <div className="phase-number">D{i + 1}</div>
            <div>
              <p className="eyebrow">阶段 0{i + 1}</p>
              <h2>{phase.name.slice(3)}</h2>
              <h3>主要成果</h3>
              <p>{phase.output}</p>
              <div className="gate">
                <ShieldCheck size={18} />
                <div>
                  <h3>放行条件</h3>
                  <p>{phase.gate}</p>
                </div>
              </div>
              <span className="small-muted">前置意见 {phase.issues}</span>
            </div>
          </section>
        ))}
      </div>
      <div className="callout">
        <strong>专项放行单独判断</strong>
        <p>
          资源对外开放须完成权利清理与审批；一期认知能力可先建设记录承载、解释与交换，并明确真实方法尚未放行。
        </p>
        <AppLink className="text-link" to="/read/d/" navigate={navigate}>
          阅读附录 D 原文 <ArrowRight size={15} />
        </AppLink>
      </div>
    </div>
  );
}

export function Decisions({ navigate }) {
  const [query, setQuery] = useState("");
  const [stage, setStage] = useState("all");
  const rows = data.pending.filter(
    (row) =>
      (stage === "all" || row.stage.includes(stage)) &&
      `${row.code} ${row.title} ${row.owner} ${row.treatment}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  return (
    <div
      className="topic-page wide-topic page-enter"
      data-screen-label="修订与待决"
    >
      <p className="eyebrow">DECISIONS & TRACEABILITY</p>
      <h1>区分条文落实与学校决定。</h1>
      <p className="page-lead">
        两轮 15
        项专家意见形成此次修订。部分条文明确了程序，具体取值、岗位与评估结论仍需决定；附录
        E 共列出 30 项待决事项。
      </p>
      <div className="revision-links">
        <AppLink to="/read/foreword/" navigate={navigate}>
          <FileText size={21} />
          <strong>与 v0.1 的主要差异</strong>
          <span>12 项主要技术修订</span>
          <ArrowUpRight size={18} />
        </AppLink>
        <AppLink to="/read/c/" navigate={navigate}>
          <GitBranch size={21} />
          <strong>专家意见—条款对照</strong>
          <span>#11—#25 逐项追溯</span>
          <ArrowUpRight size={18} />
        </AppLink>
      </div>
      <div className="decision-tools">
        <label className="filter-input">
          <Search size={17} />
          <input
            aria-label="搜索待决事项"
            placeholder="搜索事项、编号或决定主体…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <label className="stage-filter">
          <ListFilter size={16} />
          <select
            aria-label="筛选决定阶段"
            value={stage}
            onChange={(e) => setStage(e.target.value)}
          >
            <option value="all">全部阶段</option>
            {[1, 2, 3, 4, 5, 6].map((n) => (
              <option key={n} value={`D${n}`}>
                D{n} 阶段
              </option>
            ))}
            <option value="每学期">每学期复核</option>
            <option value="对外开放">对外开放前</option>
            <option value="版本标签">首个版本标签前</option>
          </select>
        </label>
      </div>
      <p className="result-count" aria-live="polite">
        显示 {rows.length} / {data.pending.length} 项 · 原文的“宜决定于阶段”
      </p>
      <div className="decision-list">
        {rows.map((row) => (
          <section key={row.code}>
            <div className="decision-number">{row.code}</div>
            <div>
              <h2>{row.title}</h2>
              <p>{row.treatment}</p>
              <div className="decision-meta">
                <span>决定主体：{row.owner}</span>
                <span>{row.stage}</span>
                <span>关联 {row.clause}</span>
              </div>
            </div>
          </section>
        ))}
        {!rows.length && (
          <div className="empty-state">
            <Search size={24} />
            <h2>没有找到匹配事项</h2>
            <p>换个关键词，或清除阶段筛选。</p>
            <button
              className="button"
              onClick={() => {
                setQuery("");
                setStage("all");
              }}
            >
              清除筛选
            </button>
          </div>
        )}
      </div>
      <AppLink className="text-link" to="/read/e/" navigate={navigate}>
        阅读附录 E 完整原文 <ArrowRight size={15} />
      </AppLink>
    </div>
  );
}

export function Downloads({ navigate }) {
  return (
    <div className="topic-page page-enter" data-screen-label="资料下载">
      <p className="eyebrow">DOCUMENTS & SOURCES</p>
      <h1>带着版本引用，带着依据讨论。</h1>
      <p className="page-lead">
        在线正文与当前版本的 Markdown 使用同一源文件；Word 便于批注。v0.1
        背景资料保留原版本标识，尚未冻结为新版规范性附件。
      </p>
      <div className="download-list">
        {data.downloads.map((file) => (
          <a href={`/downloads/${file.file}`} download key={file.file}>
            <span className={`file-type ${file.current ? "current" : ""}`}>
              {file.type}
            </span>
            <div>
              <h2>{file.title}</h2>
              <p>{file.description}</p>
              <small>
                {(file.bytes / 1024).toFixed(1)} KB · SHA-256{" "}
                {file.sha256.slice(0, 12)}…
              </small>
            </div>
            <Download size={21} />
          </a>
        ))}
      </div>
      <div className="source-card">
        <GitBranch size={22} />
        <div>
          <h2>公开源码与修订记录</h2>
          <p>
            内容基线 PR #26 · {data.sourceCommit.slice(0, 7)} · 文稿日期{" "}
            {data.date}
          </p>
          <a
            className="text-link"
            href={sourceRepo}
            target="_blank"
            rel="noreferrer"
          >
            在 GitHub 查看仓库 <ArrowUpRight size={15} />
          </a>
          <a
            className="text-link source-manifest"
            href="/version.json"
            target="_blank"
            rel="noreferrer"
          >
            版本与文件校验值 <ArrowUpRight size={15} />
          </a>
        </div>
      </div>
      <div className="callout">
        <strong>引用与使用</strong>
        <p>
          引用时写明标准名称、版本和适用能力 Profile。许可与第三方材料边界见仓库
          LICENSE、LICENSE-DOCS 与
          NOTICE；本网站按授权呈现仓库内文稿，不分发外部标准正文。
        </p>
        <AppLink
          className="text-link"
          to="/read/4/#clause-4-1-6"
          navigate={navigate}
        >
          查阅文件体系与授权边界 <ArrowRight size={15} />
        </AppLink>
      </div>
    </div>
  );
}
