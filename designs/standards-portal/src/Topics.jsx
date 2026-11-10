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

import { AppLink, reviewHref } from "./shared.jsx";
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
        Profile，先核定 C 项触发条件及 O 项声明，再合并适用要求。
        验证按实际操作、角色和子用例分工；以下按单个 Profile
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
      data-screen-label="待决事项"
    >
      <p className="eyebrow">OPEN QUESTIONS FOR REVIEW</p>
      <h1>聚焦尚需明确的条件与职责。</h1>
      <p className="page-lead">
        下列 30
        项事项涉及具体取值、适用范围、岗位与评估结论，尚需学校决定。欢迎应用厂商与标准专家结合条文提出建议及技术、业务依据。
      </p>
      <div className="revision-links">
        <AppLink to="/read/c/" navigate={navigate}>
          <FileText size={21} />
          <strong>评议指引与意见格式</strong>
          <span>按条款组织具体建议</span>
          <ArrowUpRight size={18} />
        </AppLink>
        <AppLink to="/read/4/" navigate={navigate}>
          <GitBranch size={21} />
          <strong>适用范围与责任</strong>
          <span>先核对当前要求和决定主体</span>
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
      <h1>阅读、批注，并提出具体建议。</h1>
      <p className="page-lead">
        下载完整征求意见稿或评议意见汇总表。PDF 便于阅读打印，Word 便于批注，Markdown
        便于引用条款；在线全文与下载稿使用同一正文。
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
              <small>{(file.bytes / 1024).toFixed(1)} KB</small>
            </div>
            <Download size={21} />
          </a>
        ))}
      </div>
      <div className="source-card">
        <FileText size={22} />
        <div>
          <h2>按条款组织评议</h2>
          <p>
            请说明条款位置、实际场景、具体问题、建议文字及依据，便于标准组织方研究处理。
          </p>
          <AppLink className="text-link" to="/read/c/" navigate={navigate}>
            查看评议指引 <ArrowUpRight size={15} />
          </AppLink>
          <AppLink
            className="text-link source-manifest"
            to={reviewHref()}
            navigate={navigate}
          >
            在线提交意见 <ArrowUpRight size={15} />
          </AppLink>
        </div>
      </div>
      <div className="callout">
        <strong>引用与使用</strong>
        <p>
          评议时注明标准名称、文稿日期、条款位置和适用能力
          Profile。许可与第三方材料边界见仓库 LICENSE、LICENSE-DOCS 与
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
