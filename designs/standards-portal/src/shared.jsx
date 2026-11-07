import React from "react";
import { ArrowDown, ArrowUpRight, Layers3 } from "lucide-react";
import data from "./generated.json";

export const routes = [
  "/",
  "/architecture/",
  "/profiles/",
  "/roadmap/",
  "/decisions/",
  "/downloads/",
  ...data.sections.map((s) => `/read/${s.key}/`),
];
export const standards = data.sections.filter(
  (s) => /^\d+$/.test(s.key) && Number(s.key) >= 5,
);
export const subtitles = [
  "统一身份、版本、引用与字段约束",
  "组织课程结构，保留资源与复用关系",
  "连接教学事件、学生作品与评价记录",
  "让交换、接口和跨应用对账有据可循",
  "按业务能力接入，明确 AI 与人工责任",
  "以证据、方法和获准用途管理诊断",
  "贯穿数据全生命周期的保护与治理",
  "用互操作、接替与运行证据完成验证",
];
export const cleanTitle = (title) =>
  title.replace(/^\d+\s+/, "").replace(/^附录 [A-E]（[^）]+）/, "");
export const sourceRepo = "https://github.com/alonegg/smart_platform_std";
export const roleGuides = [
  {
    label: "学校管理者",
    caption: "从治理与放行条件理解全局",
    text: "先明确学校掌握什么、谁来决定，再确定试行范围、责任岗位与阶段性放行条件。",
    links: [
      ["4", "总则与责任"],
      ["d", "实施阶段"],
      ["e", "待决事项"],
    ],
  },
  {
    label: "业务部门与教师",
    caption: "从课程、作品和评价理解标准",
    text: "沿着课程资源、学习证据和评分责任阅读，理解教学资产如何组织、复用与持续积累。",
    links: [
      ["6", "课程资源"],
      ["7", "学习证据"],
      ["10", "学习诊断"],
    ],
  },
  {
    label: "建设与接入方",
    caption: "从能力声明走向实现与验证",
    text: "先按实际业务声明 Profile，再核对公共模型、数据契约和对应测试；一个应用可声明多种能力。",
    links: [
      ["a", "能力 Profile"],
      ["5", "公共模型"],
      ["8", "交换接口"],
      ["12", "验证与验收"],
    ],
  },
  {
    label: "评审与验收方",
    caption: "从受控版本追溯到验证证据",
    text: "围绕适用范围、外部规范版本与可复验的测试记录审阅，分别判断条文采纳、实现和真实验证。",
    links: [
      ["b", "标准采用登记"],
      ["12", "验收与运行"],
      ["c", "意见落实对照"],
    ],
  },
];

export function AppLink({ to, navigate, children, className = "", ...props }) {
  return (
    <a
      href={to}
      className={className}
      {...props}
      onClick={(event) => {
        if (
          !event.metaKey &&
          !event.ctrlKey &&
          !event.shiftKey &&
          event.button === 0
        ) {
          event.preventDefault();
          navigate(to);
        }
      }}
    >
      {children}
    </a>
  );
}
export function SectionHeading({ eyebrow, title, aside }) {
  return (
    <div className="section-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
      </div>
      {aside}
    </div>
  );
}
export function ArchitectureGraphic({ navigate, compact = false }) {
  return (
    <div className={`architecture-graphic ${compact ? "compact" : ""}`}>
      <div className="figure-label">
        <span>ARCHITECTURE / 01</span>
        <span>三层协同 · 资产连续</span>
      </div>
      <div className="diagram-apps">
        <span>教学应用</span>
        <span>学习工具</span>
        <span>AI 服务</span>
        <span>未来应用</span>
      </div>
      <div className="flow-line">
        <span>按需读取</span>
        <ArrowDown size={16} />
        <span>回传内容与证据</span>
      </div>
      <div className="asset-layer">
        <div className="asset-title">
          <Layers3 size={20} />
          <strong>学校教学数据资产</strong>
          <span>核心层</span>
        </div>
        <div className="asset-types">
          <span>课程资源</span>
          <span>过程与证据</span>
          <span>认知状态</span>
        </div>
        <p>共同模型 / 版本 / 权限 / 可追溯关系</p>
      </div>
      <div className="infra-connect" aria-hidden="true">
        <i></i>
        <i></i>
        <i></i>
      </div>
      <div className="infra-layer">
        <span>基础设施与校级公共能力</span>
        <small>身份 · 主数据 · 计算 · 存储 · 采集</small>
      </div>
      {!compact && (
        <div className="figure-footer">
          <span>应用可以更换，资产保持连续。</span>
          <AppLink to="/architecture/" navigate={navigate}>
            理解架构 <ArrowUpRight size={15} />
          </AppLink>
        </div>
      )}
    </div>
  );
}
