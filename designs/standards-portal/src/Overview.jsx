import React, { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  CircleHelp,
} from "lucide-react";
import data from "./generated.json";

import {
  AppLink,
  SectionHeading,
  ArchitectureGraphic,
  standards,
  subtitles,
  cleanTitle,
  roleGuides,
} from "./shared.jsx";
export function Home({ navigate }) {
  const [role, setRole] = useState(0);
  return (
    <div data-screen-label="标准总览" className="home page-enter">
      <div className="edition-strip">
        <span className="status-dot"></span>
        <span>征求意见稿</span>
        <span className="edition-divider"></span>
        <span>{data.version}</span>
        <span className="edition-date">2026 年 11 月 06 日</span>
        <AppLink to="/read/foreword/" navigate={navigate}>
          本次修订 <ArrowUpRight size={14} />
        </AppLink>
      </div>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">FUTURE SMART TEACHING PLATFORM</p>
          <h1>
            让教学资产连续，
            <br />
            让应用持续演进<span>。</span>
          </h1>
          <p className="hero-description">
            未来智慧教学平台架构与数据资产标准体系。
            <br className="desktop-break" />
            为学校、教师与建设方，建立共同的理解与协作依据。
          </p>
          <div className="hero-actions">
            <AppLink
              className="button primary"
              to="/read/introduction/"
              navigate={navigate}
            >
              <BookOpen size={17} />
              开始阅读
              <ArrowRight size={17} />
            </AppLink>
            <AppLink className="text-link" to="/profiles/" navigate={navigate}>
              查阅能力适用矩阵 <ArrowUpRight size={16} />
            </AppLink>
          </div>
          <div className="hero-note">
            <span className="tiny-line"></span>共同核心模型 ＋ 场景 Profile ＋
            标准适配
          </div>
        </div>
        <ArchitectureGraphic navigate={navigate} />
      </section>
      <div className="document-scope">
        <CircleHelp size={17} />
        <p>
          本文为校级标准征求意见稿。条文中的“应”表示拟议要求；正式审定、系统实现与验证验收，分别需要相应程序和证据。
        </p>
        <AppLink to="/read/1/#clause-1-4" navigate={navigate}>
          文件性质 <ArrowUpRight size={14} />
        </AppLink>
      </div>
      <section className="role-section">
        <SectionHeading
          eyebrow="READING PATHS"
          title="从你的角色，找到阅读起点"
          aside={<span className="small-muted">一份标准，多方协同</span>}
        />
        <div
          className="role-tabs"
          role="tablist"
          aria-label="按角色选择阅读路径"
        >
          {roleGuides.map((r, i) => (
            <button
              key={r.label}
              id={`role-${i}`}
              role="tab"
              aria-controls="role-panel"
              aria-selected={i === role}
              tabIndex={i === role ? 0 : -1}
              onKeyDown={(e) => {
                if (["ArrowLeft", "ArrowRight"].includes(e.key)) {
                  e.preventDefault();
                  const next = (role + (e.key === "ArrowRight" ? 1 : 3)) % 4;
                  setRole(next);
                  document.getElementById(`role-${next}`)?.focus();
                }
              }}
              className={i === role ? "active" : ""}
              onClick={() => setRole(i)}
            >
              {r.label}
              <ArrowUpRight size={15} />
            </button>
          ))}
        </div>
        <div
          className="role-panel"
          id="role-panel"
          role="tabpanel"
          aria-labelledby={`role-${role}`}
        >
          <div>
            <h3>{roleGuides[role].caption}</h3>
            <p>{roleGuides[role].text}</p>
          </div>
          <div className="reading-steps">
            {roleGuides[role].links.map(([key, title], i) => (
              <AppLink key={key} to={`/read/${key}/`} navigate={navigate}>
                <span>0{i + 1}</span>
                {title}
                <ChevronRight size={15} />
              </AppLink>
            ))}
          </div>
        </div>
      </section>
      <section className="standards-section">
        <SectionHeading
          eyebrow="THE STANDARDS"
          title="八组规范，构成共同的底座"
          aside={
            <AppLink className="text-link" to="/read/4/" navigate={navigate}>
              先读总则 <ArrowUpRight size={16} />
            </AppLink>
          }
        />
        <div className="standard-grid">
          {standards.map((s, i) => (
            <AppLink
              className="standard-card"
              key={s.key}
              to={`/read/${s.key}/`}
              navigate={navigate}
            >
              <div className="card-top">
                <span className="mono">S{i}</span>
                <span>第 {s.key} 章</span>
              </div>
              <h3>{cleanTitle(s.title)}</h3>
              <p>{subtitles[i]}</p>
              <ArrowUpRight className="card-arrow" size={18} />
            </AppLink>
          ))}
        </div>
        <p className="mapping-note">
          S0—S7 为前序版本编号，现分别对应第 5—12 章，便于跨版本对照。
        </p>
      </section>
      <section className="bottom-grid">
        <div className="roadmap-summary">
          <SectionHeading
            eyebrow="FROM DESIGN TO PRACTICE"
            title="从审议到运行，分阶段推进"
          />
          <p>
            每一阶段有明确成果和放行条件。以下为实施顺序，不表示阶段已完成。
          </p>
          <div className="mini-phases">
            {data.phases.map((phase, i) => (
              <AppLink
                key={phase.name}
                to="/read/d/#clause-D-1"
                navigate={navigate}
              >
                <span>0{i + 1}</span>
                <strong>{phase.name.slice(3)}</strong>
              </AppLink>
            ))}
          </div>
          <AppLink className="text-link" to="/roadmap/" navigate={navigate}>
            查看实施路线与放行条件 <ArrowRight size={16} />
          </AppLink>
        </div>
        <div className="revision-card">
          <span className="eyebrow">REVISION / {data.version}</span>
          <h2>
            让讨论有据，
            <br />
            让决定可追溯。
          </h2>
          <p>
            综合两轮公开专家意见，保留修订依据、意见落实位置与学校待决事项。
          </p>
          <div className="revision-numbers">
            <div>
              <strong>15</strong>
              <span>专家意见 #11—#25</span>
            </div>
            <div>
              <strong>{data.pending.length}</strong>
              <span>学校待决事项</span>
            </div>
          </div>
          <AppLink to="/decisions/" navigate={navigate}>
            查阅修订与待决事项
            <ArrowUpRight size={17} />
          </AppLink>
        </div>
      </section>
    </div>
  );
}

export function Architecture({ navigate }) {
  return (
    <div className="topic-page page-enter" data-screen-label="三层架构">
      <p className="eyebrow">A SHARED ARCHITECTURE</p>
      <h1>三层分工，一份连续的教学资产。</h1>
      <p className="page-lead">
        三层按职责划分。学校掌握可解释、可追踪、可交换的教学对象，应用在共同模型与治理规则下读写数据。
      </p>
      <ArchitectureGraphic navigate={navigate} compact />
      <div className="layer-explainer">
        {[
          [
            "03",
            "应用层",
            "开展教学，回传新增内容与证据",
            "教学应用使用学校教学数据资产；应用功能和界面可以不同，其读写数据的契约、权限与验证遵循共同要求。",
            "9",
          ],
          [
            "02",
            "数据资产层",
            "管理三类核心资产及其关系",
            "课程资源、教学过程资源与学习证据、学生认知状态，由共同模型、版本、权限与可追溯关系连接。",
            "5",
          ],
          [
            "01",
            "基础设施层",
            "提供运行条件，复用校级公共能力",
            "身份、网络、计算、存储、采集与运行条件，复用学校统一身份、主数据及数据交换能力。",
            "introduction",
          ],
        ].map(([num, title, sub, text, key]) => (
          <div key={num}>
            <span className="layer-number">{num}</span>
            <div>
              <h2>
                {title}
                <small>{sub}</small>
              </h2>
              <p>{text}</p>
              <AppLink
                className="text-link"
                to={`/read/${key}/`}
                navigate={navigate}
              >
                阅读相关条文 <ArrowRight size={15} />
              </AppLink>
            </div>
          </div>
        ))}
      </div>
      <div className="callout">
        <strong>正式评价与认知推断分别治理</strong>
        <p>
          AI
          提议、教师确认、教务归档承担不同责任；认知记录与诊断方法的准入、用途和复核分别管理。架构介绍依据新版引言
          0.2、0.3 编制。
        </p>
      </div>
    </div>
  );
}
