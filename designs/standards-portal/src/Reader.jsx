import React, { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ExternalLink,
  GitBranch,
} from "lucide-react";
import data from "./generated.json";

import { AppLink, sourceRepo } from "./shared.jsx";
export function Reader({ section, navigate }) {
  const articleRef = useRef(null);
  const [active, setActive] = useState("");
  const [copied, setCopied] = useState(false);
  const position = data.sections.indexOf(section);
  useEffect(() => {
    setActive("");
    const observer = new IntersectionObserver(
      (entries) => {
        const current = entries.find((entry) => entry.isIntersecting);
        if (current) setActive(current.target.id);
      },
      { rootMargin: "-90px 0px -65% 0px" },
    );
    articleRef.current
      ?.querySelectorAll("h2[id],h3[id]")
      .forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [section.key]);
  return (
    <div className="reader-layout page-enter" data-screen-label={section.title}>
      <article className="reader-article">
        <div className="reader-kicker">
          <span>
            标准全文 / {section.key.match(/^[a-e]$/) ? "附录" : "正文"}
          </span>
          <span>{data.version}</span>
        </div>
        <h1>{section.title}</h1>
        <div className="reader-tools">
          <span
            className={`tag ${["c", "d", "e", "foreword", "introduction"].includes(section.key) ? "neutral" : ""}`}
          >
            {["c", "d", "e"].includes(section.key)
              ? "资料性附录"
              : ["a", "b"].includes(section.key)
                ? "规范性附录"
                : ["foreword", "introduction"].includes(section.key)
                  ? "编制与阅读说明"
                  : "拟议条文"}
          </span>
          <a href={data.sourceUrl} target="_blank" rel="noreferrer">
            GitHub 原文 <ExternalLink size={13} />
          </a>
          <button
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(location.href);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              } catch {
                setCopied(false);
              }
            }}
            aria-label="复制当前章节链接"
          >
            {copied ? <Check size={14} /> : <GitBranch size={14} />}
            {copied ? "已复制" : "复制链接"}
          </button>
          <button onClick={() => window.print()}>打印</button>
        </div>
        <div className="reader-status">
          征求意见稿 · 本页按原文呈现，条文采纳不等于实现或验收已完成。
        </div>
        <>
          {section.key === "foreword" && (
            <details className="document-metadata">
              <summary>文件标识与编制信息（原文）</summary>
              <div
                dangerouslySetInnerHTML={{ __html: data.frontMatterHtml }}
              ></div>
            </details>
          )}
        </>
        <div
          ref={articleRef}
          className="prose"
          onClick={(event) => {
            const anchor = event.target.closest("a");
            if (anchor?.getAttribute("href")?.startsWith("#")) {
              event.preventDefault();
              navigate(`/read/${section.key}/${anchor.getAttribute("href")}`);
            }
          }}
          dangerouslySetInnerHTML={{ __html: section.html }}
        ></div>
        <div className="chapter-pagination">
          {position > 0 ? (
            <AppLink
              to={`/read/${data.sections[position - 1].key}/`}
              navigate={navigate}
            >
              <span>
                <ArrowLeft size={15} />
                上一节
              </span>
              <strong>{data.sections[position - 1].title}</strong>
            </AppLink>
          ) : (
            <div></div>
          )}
          {position < data.sections.length - 1 && (
            <AppLink
              to={`/read/${data.sections[position + 1].key}/`}
              navigate={navigate}
            >
              <span>
                下一节
                <ArrowRight size={15} />
              </span>
              <strong>{data.sections[position + 1].title}</strong>
            </AppLink>
          )}
        </div>
      </article>
      <aside className="page-toc" aria-label="本页目录">
        <p>本页内容</p>
        {section.headings
          .filter((h) => h.depth === 3)
          .map((h) => (
            <AppLink
              className={h.id === active ? "active" : ""}
              key={h.id}
              to={`/read/${section.key}/#${h.id}`}
              navigate={navigate}
            >
              {h.title}
            </AppLink>
          ))}
        <div className="toc-source">
          来源 PR #26
          <br />
          <a
            href={`${sourceRepo}/commit/${data.sourceCommit}`}
            target="_blank"
            rel="noreferrer"
          >
            {data.sourceCommit.slice(0, 7)} <ExternalLink size={11} />
          </a>
          <span>版本用于追溯，正式基线仍需学校审定。</span>
        </div>
      </aside>
    </div>
  );
}
