import React, { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  Download,
  GitBranch,
  Layers3,
  Menu,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import data from "./generated.json";

import { AppLink, cleanTitle, sourceRepo } from "./shared.jsx";
import { Home, Architecture } from "./Overview.jsx";
import { Reader } from "./Reader.jsx";
import { Profiles, Roadmap, Decisions, Downloads } from "./Topics.jsx";
import { SearchDialog } from "./SearchDialog.jsx";
export { routes } from "./shared.jsx";

export default function App({ initialPath = "/" }) {
  const [path, setPath] = useState(initialPath);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const basePath = path.split("#")[0];
  const key = basePath.match(/^\/read\/([^/]+)\/?$/)?.[1];
  const section = data.sections.find((s) => s.key === key);
  const navItems = [
    ["/", "阅读指南", BookOpen],
    ["/architecture/", "三层架构", Layers3],
    ["/profiles/", "能力适用矩阵", SlidersHorizontal],
    ["/roadmap/", "实施路线", ArrowRight],
    ["/decisions/", "修订与待决", GitBranch],
    ["/downloads/", "资料下载", Download],
  ];
  const label =
    section?.title ??
    navItems.find(([to]) => to === basePath)?.[1] ??
    "页面未找到";
  const navigate = (target) => {
    const next = target.split("#")[0];
    history.pushState(null, "", target);
    setPath(target);
    setMobileMenu(false);
    if (next !== basePath) window.scrollTo({ top: 0 });
    setTimeout(() => {
      if (document.querySelector("[role=dialog]")) return;
      if (target.includes("#"))
        document
          .getElementById(decodeURIComponent(target.split("#")[1]))
          ?.scrollIntoView({ behavior: "smooth", block: "start" });
      else
        document.getElementById("main-content")?.focus({ preventScroll: true });
    }, 70);
  };
  useEffect(() => {
    const onPop = () => {
      setPath(location.pathname + location.hash);
      setMobileMenu(false);
    };
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen((open) => !open);
      }
      if (e.key === "Escape") {
        setMobileMenu(false);
        setSearchOpen(false);
      }
    };
    window.addEventListener("popstate", onPop);
    document.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("popstate", onPop);
      document.removeEventListener("keydown", onKey);
    };
  }, []);
  useEffect(() => {
    document.title = `${label} · 智慧教学标准阅读室`;
  }, [label]);
  useEffect(() => {
    if (location.hash)
      setTimeout(
        () =>
          document
            .getElementById(decodeURIComponent(location.hash.slice(1)))
            ?.scrollIntoView(),
        100,
      );
  }, []);
  return (
    <>
      <a className="skip-link" href="#main-content">
        跳到正文
      </a>
      <header className="topbar">
        <AppLink className="brand" to="/" navigate={navigate}>
          <span className="brand-mark">
            <Layers3 size={23} strokeWidth={1.6} />
          </span>
          <span>
            <strong>智慧教学 · 标准阅读室</strong>
            <small>SMART TEACHING STANDARDS</small>
          </span>
        </AppLink>
        <span className="topbar-divider"></span>
        <span className="topbar-caption">架构与数据资产标准体系</span>
        <div className="topbar-actions">
          <button
            className="search-trigger"
            aria-label="搜索标准"
            onClick={() => setSearchOpen(true)}
          >
            <Search size={16} />
            <span>搜索标准</span>
            <kbd>⌘ K</kbd>
          </button>
          <a
            className="github-link"
            href={sourceRepo}
            target="_blank"
            rel="noreferrer"
          >
            GitHub
            <ArrowUpRight size={14} />
          </a>
          <button
            className="mobile-menu-button"
            onClick={() => setMobileMenu(!mobileMenu)}
            aria-expanded={mobileMenu}
            aria-label="切换阅读目录"
          >
            {mobileMenu ? <X size={23} /> : <Menu size={23} />}
          </button>
        </div>
      </header>
      <div className="app-layout">
        {mobileMenu && (
          <button
            className="sidebar-backdrop"
            aria-label="关闭阅读目录"
            onClick={() => setMobileMenu(false)}
          ></button>
        )}
        <aside
          className={`sidebar ${mobileMenu ? "open" : ""}`}
          aria-label="网站目录"
        >
          <div className="sidebar-edition">
            <span className="eyebrow">当前阅读版本</span>
            <strong>
              {data.version}
              <span>征求意见稿</span>
            </strong>
          </div>
          <nav className="main-nav" aria-label="导读与专题">
            {navItems.map(([to, title, Icon]) => (
              <AppLink
                key={to}
                className={basePath === to ? "active" : ""}
                to={to}
                navigate={navigate}
                aria-current={basePath === to ? "page" : undefined}
              >
                <Icon size={17} strokeWidth={1.7} />
                {title}
                {basePath === to && <span className="nav-dot"></span>}
              </AppLink>
            ))}
          </nav>
          <div className="sidebar-section">
            <p className="nav-label">
              标准正文 <span>01—12</span>
            </p>
            <nav aria-label="标准章节">
              {data.sections
                .filter((s) => !/^[a-e]$/.test(s.key))
                .map((s) => (
                  <AppLink
                    key={s.key}
                    className={`chapter-nav ${key === s.key ? "active" : ""}`}
                    aria-current={key === s.key ? "page" : undefined}
                    to={`/read/${s.key}/`}
                    navigate={navigate}
                  >
                    <span className="chapter-num">
                      {/^\d+$/.test(s.key) ? s.key.padStart(2, "0") : "·"}
                    </span>
                    <span>{cleanTitle(s.title)}</span>
                  </AppLink>
                ))}
            </nav>
          </div>
          <div className="sidebar-section appendices">
            <p className="nav-label">
              附录 <span>A—E</span>
            </p>
            <nav aria-label="标准附录">
              {data.sections
                .filter((s) => /^[a-e]$/.test(s.key))
                .map((s) => (
                  <AppLink
                    key={s.key}
                    className={`chapter-nav ${key === s.key ? "active" : ""}`}
                    to={`/read/${s.key}/`}
                    navigate={navigate}
                  >
                    <span className="chapter-num">{s.key.toUpperCase()}</span>
                    <span>{cleanTitle(s.title)}</span>
                  </AppLink>
                ))}
            </nav>
          </div>
          <div className="sidebar-bottom">
            <span className="status-dot"></span>基于已合并文稿{" "}
            <a href={`${sourceRepo}/pull/26`} target="_blank" rel="noreferrer">
              PR #26 ↗
            </a>
            <small>文稿日期 {data.date}</small>
          </div>
        </aside>
        <div className={`workspace ${section ? "reading-workspace" : ""}`}>
          <div className="breadcrumb">
            <span>标准阅读室</span>
            <ChevronRight size={13} />
            <span>{label}</span>
            <span className="breadcrumb-right">公开阅读 · 版本可追溯</span>
          </div>
          <main id="main-content" tabIndex={-1}>
            {basePath === "/" ? (
              <Home navigate={navigate} />
            ) : section ? (
              <Reader section={section} navigate={navigate} />
            ) : basePath === "/architecture/" ? (
              <Architecture navigate={navigate} />
            ) : basePath === "/profiles/" ? (
              <Profiles navigate={navigate} />
            ) : basePath === "/roadmap/" ? (
              <Roadmap navigate={navigate} />
            ) : basePath === "/decisions/" ? (
              <Decisions navigate={navigate} />
            ) : basePath === "/downloads/" ? (
              <Downloads navigate={navigate} />
            ) : (
              <div className="topic-page empty-state">
                <h1>页面未找到</h1>
                <p>这个阅读地址不存在，请从目录继续。</p>
                <AppLink className="button primary" to="/" navigate={navigate}>
                  返回阅读指南
                </AppLink>
              </div>
            )}
          </main>
          <footer className="footer">
            <span>未来智慧教学平台 · 架构与数据资产标准体系</span>
            <span>
              征求意见稿 / {data.version}
              <a
                href={`${sourceRepo}/blob/main/NOTICE`}
                target="_blank"
                rel="noreferrer"
              >
                来源与许可 <ArrowUpRight size={12} />
              </a>
            </span>
          </footer>
        </div>
      </div>
      {searchOpen && (
        <SearchDialog
          navigate={navigate}
          onClose={() => setSearchOpen(false)}
        />
      )}
    </>
  );
}
