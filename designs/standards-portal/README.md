# 智慧教学-数据模型标准

公开站点：<https://stds.chunlin.ch>。用于应用厂商、标准专家审阅、评议和提出意见。

## 编辑原则与内容来源

项目根目录 `AGENTS.md` 定义读者与编辑原则。页面应使首次阅读者独立理解当前条文、适用范围、技术依据、验证条件和待决事项。
正文、搜索及下载文件使用 `标准/评审稿/智慧教学-数据模型标准.md`，Word 与其同步生成；附录 C 是评议指引，附录 E 是学校待决事项。
页面不展示本文件与前序稿的对应关系、旧编号、修订沿革或历轮意见采纳记录。编制历史保留在 Git 和维护记录。
资源内容版本、历史引用、兼容策略、外部标准规格版本及标准发布治理属于技术要求，应按条文保留。

网站采用 baoyu-design 方法形成的学术编辑式界面，预渲染 26 个公开页面及 1 个受保护管理页面，正文含 19 个分节。
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
npm exec -- wrangler d1 migrations apply smart-platform-stds-readers --local --persist-to ../../temp/registration-local
npm run dev:worker
npm run test:browser
```

浏览器检查使用独立 headless Chrome，默认访问 `http://127.0.0.1:4320`；可设置 `PORTAL_TEST_URL=https://stds.chunlin.ch` 检查公网。
构建验证受控源文件，生成正文、全文索引、下载和校验清单，再用 Vite 与 React SSR 生成静态页面。
阅读和下载支持无 JavaScript 访问；搜索、角色切换和筛选在浏览器执行。普通阅读不要求登录。首次访问主动显示登记弹窗，读者可选择暂不登记；登记成功后使用 HttpOnly 不透明会话 Cookie 关联本人记录，不在浏览器持久保存姓名或邮箱。

内容检查覆盖：受控 hash、章节、锚点、288 个矩阵值、下载字节、技术字段搜索、页面/索引的沿革清理、旧下载残留，以及条款引用、真实 Markdown 表格、统一能力代码、外部登记索引、操作子用例和待决前置节点。
矩阵核验明确列出三处受控 C→M 调整，并要求其余 285 格不变；文稿检查还覆盖重复回执状态、T20-F/L/E 与九组联合场景的用例引用。静态条文检查不表示这些业务场景已经执行通过。
浏览器检查覆盖：厂商/专家路径、全文保真、搜索/深链接/历史导航、9 类 Profile、待决筛选、手机导航、评议链接与无障碍自动检查。

## 更新正文与 Word

1. 审阅并提交 `标准/评审稿/` 的 Markdown 与 Word。
2. 将 `scripts/content.mjs` 的 `sourceCommit` 更新到包含该文稿的确切提交，保持同一份当前源文件；引用路径和预期结构随必要修改。
3. 通过内容与浏览器检查，再提交网站修改并走 PR。
4. 合并后构建、部署并核对公网内容。

```bash
pandoc 标准/评审稿/智慧教学-数据模型标准.md --reference-doc=标准/评审稿/智慧教学-数据模型标准.docx -o temp/standard-review.docx
cp temp/standard-review.docx 标准/评审稿/智慧教学-数据模型标准.docx
pandoc 标准/评审稿/评议意见表.md -o 标准/评审稿/评议意见表.docx
```

正式标准的发布和修订按正文治理要求执行。网页编辑不改变征求意见稿性质或代表学校已经完成审定、实现与验收。
编制流程及与正式受控发布的区别见仓库 `维护/标准编制与复现.md`；生成 Word 时保留当前参考文档的 A4、中文字体和样式，并核对全部内容及渲染。

## Cloudflare 部署与回读

独立 Worker：`smart-platform-stds`；Custom Domain：`stds.chunlin.ch`。
凭据通过环境或 Wrangler 身份提供；不写入代码。

```bash
npm run build
npm exec -- wrangler d1 migrations apply smart-platform-stds-readers --remote
npm exec -- wrangler deploy --dry-run
npm exec -- wrangler deploy
```

部署后核对 `/version.json` 的内容与代码提交、全部静态页和当前附件字节、旧下载 404 与浏览器行为。
控制面 hash 保存在机器清单中，评审界面不显示 Git/PR 沿革。
生成目录、依赖和临时 SSR 构建包不提交。代码按仓库 Apache-2.0 使用；文稿与第三方材料遵循仓库授权说明。

## 阅读登记与管理端

首次访问（含章节深链接）会主动弹出“阅读者登记”；已登记浏览器不重复弹出表单，可从顶部“阅读登记”管理。姓名、单位或身份、参与角色为基本项，专业方向和邮箱选填。登记说明确认、境外处理确认和允许联系均默认不勾选。

登记通过同源 Worker API 写入独立 D1 `smart-platform-stds-readers`。不透明 Cookie 的 SHA-256 用于关联记录；API 校验 Origin、字段长度、角色、邮箱与说明版本，并限流。数据库写入成功后再精确回读；失败不返回成功状态。重复创建幂等，修改和撤回限于本人会话。

信息处理说明在 `/privacy/`；组织方和联系方式配置在 `src/registration-policy.json`。登记有效期 180 天，到期从可用名单立即移除，每日任务在 24 小时内删除主记录。已阅状态必须由本人明确确认，与页面访问分开；不建立指纹或完整浏览轨迹。此处不验证登记者真实身份，也不把 GitHub 意见自动认定为该人的提交。

管理页：<https://stds.chunlin.ch/admin/>。Cloudflare Access 使用现有邮箱 OTP，并仅允许 `alone@swufe.edu.cn`；Worker 另外验证 Access JWT 的签名、issuer、audience、有效期与允许邮箱。名单支持搜索、分页、CSV 导出及按请求删除。CSV 导出防止公式注入。管理响应和本人会话响应均不缓存。

Cloudflare Access 应用的配置单独存在于 Cloudflare 控制面，`wrangler.jsonc` 保存受众和域名供后端校验，不包含登录凭据。全新账户部署前需先建立等价的独立 Access 应用和允许邮箱策略。不要把数据 Cookie 或 Access Token 写进仓库、链接或日志。

本地 Node API 测试使用内存 SQLite 与真实 RSA 签名；浏览器登记测试使用本地真实 D1。生产验收只用显著标注的合成记录，并在测试后按其会话撤回、精确核对删除，不清空其他人的记录。未经用户操作不发送实际邮箱验证码，邮箱 OTP 的真实收取与登录应单独验收。

Wrangler 已在项目中锁定版本。开发命令中的 `--infer-origin-from-routes=false` 保留真实 localhost Origin，使同源校验和 HTTPS Cookie 检查与生产保持一致；不应降低兼容日期或移除后端校验来通过本地检查。
