# 智慧教学 · 标准阅读室

公开站点：<https://stds.chunlin.ch>。网站通过 baoyu-design 方法设计，采用暖白与深青色的学术编辑式界面。

## 内容和版本

正文来自 PR #26 合并提交 `6cf3410bfd9249f2a5c3eed707ab69527a21420e` 中的
`标准/chunlin@1106/未来智慧教学平台数据资产层标准_chunlin@1106.md`。
当前内容是 **chunlin@1106 征求意见稿**，不是已正式审定发布的校级标准。

首页导读和专题用于组织阅读；完整标准条文按原文生成。第 1—12 章及规范性附录 A/B、资料性附录 C/D/E
均有独立 URL。S0—S7 是旧版编号，对应新版第 5—12 章，不使用旧版 59 条作为新版数量。
Profile 专题按单个 Profile 显示原表和共同要求，不代替多能力适用声明、C 项判断与学校审核。
实施阶段未标注为已完成，待决事项保持待决，v0.1 下载资料明确标为背景和资料性附件。

构建器仅复制明确列出的公开文稿与附件，不读取校内材料、原始文档、申报项目或私有归档仓库。
正文、在线元数据与下载文件的 SHA-256 可通过 `/version.json` 核对；内容基线与网站代码提交分别记录。

## 本地运行

需要 Node.js 22.12+ 和 npm。依赖版本锁定在 `package-lock.json`。

```bash
cd designs/standards-portal
npm ci
npm run build
npm run preview -- --port 4312
```

构建先核对 Markdown 与合并基线一致，再提取章节、Profile、32 组适用要求、6 个阶段、30 项待决事项，
生成下载文件及全文索引；随后用 Vite 构建并以 React SSR 预渲染 25 个页面。
无 JavaScript 也能从目录阅读完整正文和下载文件；搜索、角色切换及专题筛选在浏览器运行。
搜索索引按需加载，没有登录、追踪脚本、分析 Cookie 或后台采集。

首次执行 `npm run dev` 前也需先执行一次 `npm run build`，以生成受控内容。

## 验证

```bash
npm test
npm run test:browser
```

内容检查覆盖：源文件校验值、章节和事项完整性、288 个矩阵值与原表一致、稳定锚点、静态正文和附件字节一致。
Playwright 使用独立 headless Chrome，检查搜索/角色路径/深链接/浏览历史、9 类 Profile、筛选、正文全文保真、移动布局及 axe 检查。
需要本机 Chrome；也可修改 `playwright.config.js` 的 `channel` 使用已安装的 Playwright Chromium。

浏览器检查默认访问 `http://127.0.0.1:4312`，可设置 `PORTAL_TEST_URL=https://stds.chunlin.ch` 复跑公网检查。
自动检查的通过范围不等同于本标准所规定的真实系统互操作、安全测评或教学效果验证。

## Cloudflare 部署

独立 Worker 名称为 `smart-platform-stds`。`wrangler.jsonc` 配置 Workers Static Assets 与 `stds.chunlin.ch` Custom Domain；
不启用额外的 workers.dev 或 Preview URL。凭据由环境变量或 Wrangler 身份提供，不放入源码。

```bash
npm run build
wrangler deploy --dry-run
wrangler deploy
```

部署后核对 HTTPS、`/version.json` 的 `sourceCommit` / `siteCommit`、全部静态路由、附件 SHA-256、真实 404 与浏览器行为。
`dist/`、`node_modules/`、临时 SSR 包和生成内容不提交；可从版本库及锁文件复现。

## 后续同步

1. 审阅并合并新的标准 PR。
2. 显式更新 `scripts/content.mjs` 的 `sourcePath`、`sourceCommit` 以及元数据；不要仅改页面版本文字。
3. 如文档结构变化，更新提取规则与预期数量，核对条文性质、规范性/资料性附录和待决事项。
4. 构建、验证、提交、部署后重新核对公开回读。

网站阅读地址和条款锚点尽量保持稳定；原稿变化导致条号变化时应保留版本说明与迁移入口。

## 授权

代码按仓库 Apache-2.0 使用；文稿及图件遵循仓库授权说明。第三方标准只保留引用，不分发其正文。
