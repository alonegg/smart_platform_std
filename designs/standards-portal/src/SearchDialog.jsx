import React, { useEffect, useRef, useState } from "react";
import { ArrowUpRight, Search, X } from "lucide-react";
import data from "./generated.json";

export function SearchDialog({ onClose, navigate }) {
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState([]);
  const [loadError, setLoadError] = useState(false);
  useEffect(() => {
    import("./search-index.json")
      .then((module) => setIndex(module.default))
      .catch(() => setLoadError(true));
  }, []);
  const inputRef = useRef(null);
  const boxRef = useRef(null);
  const results = query.trim()
    ? index
        .filter((block) =>
          `${block.title} ${block.text}`
            .toLowerCase()
            .includes(query.trim().toLowerCase()),
        )
        .sort(
          (a, b) =>
            Number(b.title.toLowerCase().includes(query.toLowerCase())) -
            Number(a.title.toLowerCase().includes(query.toLowerCase())),
        )
        .slice(0, 40)
    : [];
  useEffect(() => {
    const old = document.activeElement;
    inputRef.current?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
      old?.focus();
    };
  }, []);
  const excerpt = (text) => {
    const at = text.toLowerCase().indexOf(query.trim().toLowerCase());
    return (
      (at > 35 ? "…" : "") +
      text
        .slice(Math.max(0, at - 35), Math.max(0, at - 35) + 130)
        .replaceAll("\n", " ")
    );
  };
  return (
    <div
      className="search-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={boxRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="search-title"
        className="search-dialog"
        onKeyDown={(e) => {
          if (e.key === "Escape") onClose();
          if (e.key === "Tab") {
            const items = [
              ...boxRef.current.querySelectorAll("button,input,a"),
            ];
            if (e.shiftKey && document.activeElement === items[0]) {
              e.preventDefault();
              items.at(-1).focus();
            } else if (!e.shiftKey && document.activeElement === items.at(-1)) {
              e.preventDefault();
              items[0].focus();
            }
          }
        }}
      >
        <h2 id="search-title" className="sr-only">
          搜索标准全文
        </h2>
        <div className="search-input">
          <Search size={21} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索章节、条款、术语或 Profile…"
            aria-label="搜索标准全文"
          />
          <button onClick={onClose} aria-label="关闭搜索">
            <X size={19} />
          </button>
        </div>
        <div className="search-results" aria-live="polite">
          {loadError ? (
            <div className="empty-state">
              <p>搜索索引加载失败，请刷新后重试。章节目录仍可直接阅读。</p>
            </div>
          ) : !index.length ? (
            <div className="empty-state">
              <p>正在加载全文索引…</p>
            </div>
          ) : !query.trim() ? (
            <div className="search-hint">
              <p>搜索 {data.version} 标准全文</p>
              <span>试试这些关键词</span>
              <div>
                {["权利", "人工责任", "P-AI", "应用接替", "unknown"].map(
                  (word) => (
                    <button key={word} onClick={() => setQuery(word)}>
                      {word}
                    </button>
                  ),
                )}
              </div>
            </div>
          ) : results.length ? (
            <>
              <p className="search-count">
                找到 {results.length}
                {results.length === 40 ? "+" : ""} 个相关段落
              </p>
              {results.map((r, i) => (
                <a
                  key={`${r.section.key}-${i}`}
                  href={`/read/${r.section.key}/${r.anchor ? `#${r.anchor}` : ""}`}
                  onClick={(e) => {
                    e.preventDefault();
                    navigate(e.currentTarget.getAttribute("href"));
                    onClose();
                  }}
                >
                  <span>{r.section.title}</span>
                  <h3>{r.title}</h3>
                  <p>{excerpt(r.text)}</p>
                  <ArrowUpRight size={16} />
                </a>
              ))}
            </>
          ) : (
            <div className="empty-state">
              <Search size={25} />
              <h3>没有找到“{query}”</h3>
              <p>试试更短的关键词，或使用条款号。</p>
            </div>
          )}
        </div>
        <div className="search-footer">
          <span>全文本地检索 · 无需登录</span>
          <span>
            <kbd>ESC</kbd> 关闭
          </span>
        </div>
      </div>
    </div>
  );
}
