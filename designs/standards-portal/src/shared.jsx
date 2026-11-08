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
  "/privacy/",
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
export const reviewHref = (section) => {
  const title = section
    ? `[标准评议] ${section.title}`
    : `[标准评议] ${data.title}`;
  const body = `## 条款位置
${section ? section.title : "请填写条款号、字段或 Profile"}

## 应用类型与能力 Profile / 专家方向

## 具体问题与场景

## 建议条文或方案

## 技术或业务依据与影响范围

## 提议方与联系渠道（自愿）
`;
  return `${sourceRepo}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
};
export const roleGuides = [
  {
    label: "应用厂商",
    caption: "从能力范围，核对接入与实现要求",
    text: "结合产品承担的业务声明 Profile，检查数据语义、接口、授权和验证条件，按具体条款提出可实现性、互操作与责任边界方面的意见。",
    links: [
      ["a", "能力 Profile"],
      ["5", "公共模型"],
      ["8", "交换接口"],
      ["c", "提出评议"],
    ],
  },
  {
    label: "标准专家",
    caption: "从技术一致性，审阅条文与验证条件",
    text: "围绕适用范围、术语、外部标准采用、技术一致性和可验证性进行审阅，说明问题、建议文字及依据；尚需明确的事项可结合附录 E 评议。",
    links: [
      ["4", "总则与适用范围"],
      ["b", "标准采用登记"],
      ["12", "验证条件"],
      ["c", "评议指引"],
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
