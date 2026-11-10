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
  MessageSquareText,
  Rocket,
  Search,
  SlidersHorizontal,
  UserRound,
  X,
} from "lucide-react";
import data from "./generated.json";

import { AppLink, cleanTitle, sourceRepo, reviewHref } from "./shared.jsx";
import { Home, Architecture } from "./Overview.jsx";
import { Reader } from "./Reader.jsx";
import { Profiles, Roadmap, Decisions, Downloads } from "./Topics.jsx";
import {
  RegistrationBanner,
  RegistrationDialog,
  PrivacyPage,
  useRegistration,
} from "./registration.jsx";
import {
  CommentPage,
  ConsultationStrip,
  QuickStart,
  ResponsesPage,
} from "./Consultation.jsx";
import { AdminPage } from "./Admin.jsx";
import { deadlineText } from "./Consultation.jsx";
import consultation from "./consultation.json";
import { SearchDialog } from "./SearchDialog.jsx";
export { routes } from "./shared.jsx";

export default function App({ initialPath = "/" }) {
  const [path, setPath] = useState(initialPath);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const basePath = path.split("#")[0].split("?")[0];
  const key = basePath.match(/^\/read\/([^/]+)\/?$/)?.[1];
  const isAdmin = basePath === "/admin/" || basePath === "/admin";
  const registration = useRegistration(isAdmin || basePath === "/privacy/");
  const section = data.sections.find((s) => s.key === key);
  const navItems = [
    ["/", "阅读指南", BookOpen],
    ["/quickstart/", "厂商速读", Rocket],
    ["/architecture/", "三层架构", Layers3],
    ["/profiles/", "能力适用矩阵", SlidersHorizontal],
    ["/roadmap/", "实施路线", ArrowRight],
    ["/decisions/", "待决事项", GitBranch],
    ["/downloads/", "资料下载", Download],
    ["/comment/", "提交意见", MessageSquareText],
    ["/responses/", "意见处理情况", GitBranch],
  ];
  const label =
    section?.title ??
    navItems.find(([to]) => to === basePath)?.[1] ??
    (basePath === "/privacy/"
      ? "登记与意见信息处理说明"
      : isAdmin
        ? "阅读者登记管理"
        : "页面未找到");
  const navigate = (target) => {
    const next = target.split("#")[0].split("?")[0];
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
      setPath(location.pathname + location.search + location.hash);
      setMobileMenu(false);
    };
    const onKey = (e) => {
      if (
        document.querySelector("[data-registration-dialog]") &&
        (e.metaKey || e.ctrlKey) &&
        e.key.toLowerCase() === "k"
      ) {
        e.preventDefault();
        return;
      }
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
    document.title = `${label} · ${data.title}`;
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
  if (isAdmin) return <AdminPage />;
  return (
    <>
      <div inert={registration.open ? true : undefined}>
        <a className="skip-link" href="#main-content">
          跳到正文
        </a>
        <header className="topbar">
          <AppLink className="brand" to="/" navigate={navigate}>
            <span className="brand-mark">
              <Layers3 size={23} strokeWidth={1.6} />
            </span>
            <span>
              <strong>{data.title}</strong>
              <small>SMART TEACHING DATA MODEL STANDARD</small>
            </span>
          </AppLink>
          <span className="topbar-divider"></span>
          <span className="topbar-caption">征求意见稿 · 厂商与专家评议</span>
          <div className="topbar-actions">
            <button
              className="reader-registration-trigger"
              onClick={() => {
                registration.refresh();
                registration.setOpen(true);
              }}
              aria-label="阅读登记"
            >
              <UserRound size={16} />
              <span>{registration.record ? "已登记" : "阅读登记"}</span>
            </button>
            <button
              className="search-trigger"
              aria-label="搜索标准"
              onClick={() => setSearchOpen(true)}
            >
              <Search size={16} />
              <span>搜索标准</span>
              <kbd>⌘ K</kbd>
            </button>
            <AppLink
              className="github-link"
              to={reviewHref(section)}
              navigate={navigate}
            >
              提出意见
              <MessageSquareText size={14} />
            </AppLink>
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
              <span className="eyebrow">评审材料</span>
              <strong>
                {data.title}
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
              <span className="status-dot"></span>意见截止 {deadlineText}{" "}
              <AppLink to="/comment/" navigate={navigate}>
                提交意见 →
              </AppLink>
              <small>起草单位：{consultation.draftingUnit}</small>
            </div>
          </aside>
          <div className={`workspace ${section ? "reading-workspace" : ""}`}>
            <div className="breadcrumb">
              <span>{data.title}</span>
              <ChevronRight size={13} />
              <span>{label}</span>
              <span className="breadcrumb-right">审阅 · 评议 · 提出意见</span>
            </div>
            <RegistrationBanner state={registration} />
            <ConsultationStrip navigate={navigate} />
            <main id="main-content" tabIndex={-1}>
              {basePath === "/privacy/" ? (
                <PrivacyPage />
              ) : basePath === "/comment/" ? (
                <CommentPage navigate={navigate} registration={registration} />
              ) : basePath === "/responses/" ? (
                <ResponsesPage navigate={navigate} />
              ) : basePath === "/quickstart/" ? (
                <QuickStart navigate={navigate} />
              ) : basePath === "/" ? (
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
                  <AppLink
                    className="button primary"
                    to="/"
                    navigate={navigate}
                  >
                    返回阅读指南
                  </AppLink>
                </div>
              )}
            </main>
            <footer className="footer">
              <span>{data.title}</span>
              <span>
                供应用厂商与标准专家评议
                <AppLink to="/privacy/" navigate={navigate}>
                  信息处理说明
                </AppLink>
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
      </div>
      <RegistrationDialog state={registration} />
      {!registration.open && searchOpen && (
        <SearchDialog
          navigate={navigate}
          onClose={() => setSearchOpen(false)}
        />
      )}
    </>
  );
}
