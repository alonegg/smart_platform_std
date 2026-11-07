# 智慧教学 · 标准阅读室

公开站点：<https://stds.chunlin.ch>。用于应用厂商、标准专家审阅、评议和提出意见。

## 编辑原则与内容来源

项目根目录 `AGENTS.md` 定义读者与编辑原则。页面应使首次阅读者独立理解当前条文、适用范围、技术依据、验证条件和待决事项。
正文、搜索及下载文件使用 `标准/评审稿/未来智慧教学平台数据资产层标准.md`，Word 与其同步生成；附录 C 是评议指引，附录 E 是学校待决事项。
页面不展示本文件与前序稿的对应关系、旧编号、修订沿革或历轮意见采纳记录。编制历史保留在 Git 和维护记录。
资源内容版本、历史引用、兼容策略、外部标准规格版本及标准发布治理属于技术要求，应按条文保留。

网站采用 baoyu-design 方法形成的学术编辑式界面，预渲染 25 个页面，正文含 19 个分节。
首页分别提供应用厂商与标准专家阅读路径。章节页的“提出意见”链接打开带条款与意见格式的 GitHub Issue 草稿，意见由访问者自行提交。
4 个下载文件为标准 Word/Markdown 和评议意见表 Word/Markdown；构建器清理其专用生成目录，防止未列入当前清单的文件残留。
不读取或发布校内材料、私有归档和未选定附件。

## 本地运行与验证

需要 Node.js 22.12+、npm。依赖由锁文件固定。制作 Word 文稿另需 Pandoc。

```bash
cd designs/standards-portal
npm ci
npm run build
npm test
npm run preview -- --port 4312
npm run test:browser
```

浏览器检查使用独立 headless Chrome，默认访问 `http://127.0.0.1:4312`；可设置 `PORTAL_TEST_URL=https://stds.chunlin.ch` 检查公网。
构建验证受控源文件，生成正文、全文索引、下载和校验清单，再用 Vite 与 React SSR 生成静态页面。
阅读和下载支持无 JavaScript 访问；搜索、角色切换和筛选在浏览器执行。无登录、分析 Cookie 或后台采集。

内容检查覆盖：受控 hash、章节、锚点、288 个矩阵值、下载字节、技术字段搜索、页面/索引的沿革清理、旧下载残留。
浏览器检查覆盖：厂商/专家路径、全文保真、搜索/深链接/历史导航、9 类 Profile、待决筛选、手机导航、评议链接与无障碍自动检查。

## 更新正文与 Word

1. 审阅并提交 `标准/评审稿/` 的 Markdown 与 Word。
2. 将 `scripts/content.mjs` 的 `sourceCommit` 更新到包含该文稿的确切提交，保持同一份当前源文件；引用路径和预期结构随必要修改。
3. 通过内容与浏览器检查，再提交网站修改并走 PR。
4. 合并后构建、部署并核对公网内容。

```bash
pandoc 标准/评审稿/未来智慧教学平台数据资产层标准.md -o 标准/评审稿/未来智慧教学平台数据资产层标准.docx
pandoc 标准/评审稿/评议意见表.md -o 标准/评审稿/评议意见表.docx
```

正式标准的发布和修订按正文治理要求执行。网页编辑不改变征求意见稿性质或代表学校已经完成审定、实现与验收。

## Cloudflare 部署与回读

独立 Worker：`smart-platform-stds`；Custom Domain：`stds.chunlin.ch`。
凭据通过环境或 Wrangler 身份提供；不写入代码。

```bash
npm run build
wrangler deploy --dry-run
wrangler deploy
```

部署后核对 `/version.json` 的内容与代码提交、全部静态页和当前附件字节、旧下载 404 与浏览器行为。
控制面 hash 保存在机器清单中，评审界面不显示 Git/PR 沿革。
生成目录、依赖和临时 SSR 构建包不提交。代码按仓库 Apache-2.0 使用；文稿与第三方材料遵循仓库授权说明。
