# 智慧教学-数据模型标准

公开站点：<https://stds.chunlin.ch>。用于应用厂商、标准专家审阅、评议和提出意见。

## 第2轮修订稿预览站

这是受 Cloudflare Access 保护的内部维护预览，不是现行征求意见稿，不部署到默认站点。
`PORTAL_EDITION=r2` 选择 `维护/第2轮修订稿/智慧教学-数据模型标准-修订稿.md`，
固定源提交为 `0ebb33034179adde310f4616fba06365f959337e`；默认版仍使用原受控源与提交。
正文、全文检索及标准 Word/PDF/Markdown 下载均使用修订稿；评议意见汇总表沿用现有文件。
Word 使用 Pandoc 与当前 reference-doc 生成，表格过滤器只补齐相对列宽，防止自动布局越过页边界；PDF 使用 LibreOffice Writer 从该 Word 导出。
默认版仍为 786 个条款单元、56 张表；r2 为 805 个单元、57 张表，19 个分节与附录 A 的 288 格矩阵不变。
预览站顶部始终标明“第2轮修订稿预览，非现行征求意见稿”，不改 `consultation.json`。

内部 `/compare/` 按 `docmodel.py` 的条款单元并排展示两版全文，默认只看 19 项新增和 8 项修改，
可取消“只看改动”查看全部条款。修订编号、Issue 来自修订清单，与 `make_diff.py` 共用解析逻辑；
未关联 Issue 的项明确标注，不虚构链接。对照数据仅进入 r2 页面资源，不进入全文搜索索引或下载文件。
默认版不生成该页、对照数据或导航入口。
构建及测试均强制检查 `wrangler.r2.jsonc` 的 `REQUIRE_ACCESS` 必须为字符串 `"true"`，
同时要求 `PORTAL_EDITION: "r2"` 和 `run_worker_first: true`，否则失败。

### 从零开始本地构建

需要 Node.js 22.12+、npm、Python 3.11+；重新生成 Word 另需 Pandoc。
以下命令从仓库根目录开始；应使用完整 Git 历史，浅克隆先执行 `git fetch --unshallow origin`。

```bash
cd designs/standards-portal
npm ci
PORTAL_EDITION=r2 npm run build
PORTAL_EDITION=r2 npm test
# 等价构建快捷命令：npm run build:r2
# 仅本机静态预览（没有 Access，不可暴露到公网）
npm run preview
# 浏览器检查内部对照筛选与禁用意见页；另一个终端执行
PORTAL_EDITION=r2 PORTAL_TEST_URL=http://127.0.0.1:4311 npm run test:browser -- tests/r2.spec.js
```

切换默认版前必须重新 `npm run build && npm test`，不要部署上一次 r2 的 dist。
默认测试执行所有单元测试；r2 执行同一组正文/搜索/下载检查、修订结构检查和预览安全测试。
仅现有登记写入/征求意见程序测试不在 r2 执行，因为它们的可写业务断言与只读预览相反，仍由默认版完整执行。

### 用户自行创建资源与部署

本任务不部署、不申请 Cloudflare 凭证，也不创建云端资源。由部署者在本机完成授权后执行：

```bash
cd designs/standards-portal  # 若当前已在此目录则省略
npm exec -- wrangler login
npm exec -- wrangler d1 create smart-platform-stds-r2-readers
# 将返回的 database_id 填入 wrangler.r2.jsonc 的占位符，绝不能复制生产数据库 id。
# 在 Cloudflare Zero Trust 后台为 r2.stds.chunlin.ch 单独创建 Self-hosted Access 应用。
# 为内部读者配置 Allow 策略；将 Team Domain 和该应用 AUD 填入配置的 ACCESS_TEAM_DOMAIN/ACCESS_AUD。
# 必须保留 REQUIRE_ACCESS="true"、PORTAL_EDITION="r2"、run_worker_first=true。
npm exec -- wrangler d1 migrations apply smart-platform-stds-r2-readers --remote -c wrangler.r2.jsonc
PORTAL_EDITION=r2 npm run build
PORTAL_EDITION=r2 npm test
npm exec -- wrangler deploy -c wrangler.r2.jsonc
# 后续可用 npm run deploy:r2（构建、测试后使用独立配置部署）。
```

预览域名为 <https://r2.stds.chunlin.ch>，Worker `smart-platform-stds-r2`，D1 `smart-platform-stds-r2-readers`，
限流 namespace 独立；数据库 id、Access Team Domain 和 r2 应用 AUD 必须由部署者填写。
Access 应用策略决定内部读者范围；Worker 仍核验签名、issuer、audience 与有效期，不只信任邮箱头。
管理端还额外要求 `ADMIN_EMAIL`，普通获准预览用户不会因此获得管理权限。
所有路径（包括下载、JS、robots、API、错误响应）均经过 Worker；r2 未开启 Access 时拒绝服务，
未通过 JWT 校验时拒绝访问，不因无索引标识而放松鉴权。

r2 的 robots 为全站 `Disallow: /`，所有 Worker 响应及静态 `_headers` 含 `X-Robots-Tag: noindex`，
全部预渲染页面（含 404、管理页）含 noindex meta。响应禁止共享缓存。
意见页面无表单、提交按钮禁用；Worker 在数据库分发前拒绝所有业务 API，登记与定时清理也停用，
不连接生产数据库。独立 D1 及迁移保留以保持部署结构独立，不代表预览允许收集数据。
本机 `npm run preview` 仅用于静态界面检查，不验证线上 Access；上线后须分别核对匿名请求拒绝、
获准用户可读、普通读者不能管理、意见 POST 拒绝，以及 noindex、下载与 `/version.json`。

**r2 若将来转为公开征求意见稿，必须去掉 `/compare/` 和预览标识，并按 `AGENTS.md` 重新检查，
重新选定受控正文、下载、检索与程序信息后再发布；不得仅关闭 Access 将本预览站公开。**

### 重新生成预览下载文稿

在仓库根目录执行，保留当前 Word 参考文档的样式；只新增生成物，不修改修订稿正文：

```bash
pandoc 维护/第2轮修订稿/智慧教学-数据模型标准-修订稿.md --reference-doc=标准/评审稿/智慧教学-数据模型标准.docx --lua-filter=designs/standards-portal/scripts/r2-table-widths.lua -o 维护/第2轮修订稿/智慧教学-数据模型标准-修订稿.docx
# 需安装 LibreOffice Writer（仅安装 core 无法载入 Word）与 Noto 中文字体。
libreoffice -env:UserInstallation=file://$HOME/.cache/lo-r2-preview --headless --convert-to pdf --outdir 维护/第2轮修订稿 维护/第2轮修订稿/智慧教学-数据模型标准-修订稿.docx
pdffonts 维护/第2轮修订稿/智慧教学-数据模型标准-修订稿.pdf
```

重新生成后应核对正文和 57 张表的完整性、中文字体及分页，而不仅检查文件是否存在。
若本机不能生成并验证 PDF，必须显式从 r2 下载清单移除 PDF 并说明原因，不得回退到默认版 PDF。

## 主站版本入口

<https://stds.chunlin.ch> 的版本选择栏提供第 1 轮征求意见稿和第 2 轮修订稿。
第 1 轮继续使用根路径、原有深链接、意见、登记及管理功能。第 2 轮位于 `/v2/`，
其正文、检索和下载使用独立的公开评议稿。第二版仅提供阅读与邮件评议。

从门户目录运行 `npm run build:primary` 会构建并组装两个版本。运行 `npm run deploy`
会构建并部署主站。两个版本通过同一 Worker 版本一起发布，`/v2/` 保留只读路由。
版本入口不包含条文差异、编制过程或历次意见采纳记录。

## 第2轮修订稿公开阅读站

<https://stdsv2.chunlin.ch> 使用 `npm run deploy:r2-public` 发布。该版本使用 `维护/第2轮修订稿/公开评议/` 中单独固定提交的公开评议文稿。
公开提供阅读、检索、同源 Word/PDF/Markdown 及三份 draft 工程材料。附录 C 和下载页提供邮件评议入口。构建不生成内部对照数据或管理页。
只读 Worker 仅绑定静态资源，无 D1 或定时任务。Cloudflare Access 的免登录策略仅适用于此域名。
发布前运行 `python3 -B 维护/第2轮修订稿/公开评议/check_public_review.py` 检查文档、字段表和原子用例。
发布后应从无登录状态核对正文、附件、检索及已移除的路径。

## 默认站点发布开关

发布开关：`wrangler.jsonc` 的 `PUBLICATION_PAUSED` 设为 `"true"` 时，Worker 统一返回暂停说明；当前为 `"false"`（正常发布），正文、附件、搜索数据、前端资源、阅读登记和管理页面均经过该入口，避免从深链接继续读取已暂停的内容。普通请求返回 HTTP 503、`Retry-After` 和 `no-store`；`robots.txt` 返回全站暂停抓取规则。暂停页面无需 JavaScript，也不加载原站点资源。受控文稿与既有登记数据保留，原有到期清理任务继续运行。

恢复发布须明确将 `wrangler.jsonc` 的 `PUBLICATION_PAUSED` 改为 `"false"`，核对选定的受控评审稿，执行构建、测试和部署，再验收公网阅读、检索、下载及登记功能。`run_worker_first: true` 保证所有静态资源也受发布开关控制；不应通过跳过 Worker 恢复访问。

## 编辑原则与内容来源

项目根目录 `AGENTS.md` 定义读者与编辑原则。页面应使首次阅读者独立理解当前条文、适用范围、技术依据、验证条件和待决事项。
正文、搜索及下载文件使用 `标准/评审稿/智慧教学-数据模型标准.md`，Word 与其同步生成；附录 C 是评议指引，附录 E 是学校待决事项。
页面不展示本文件与前序稿的对应关系、旧编号、修订沿革或历轮意见采纳记录。编制历史保留在 Git 和维护记录。
资源内容版本、历史引用、兼容策略、外部标准规格版本及标准发布治理属于技术要求，应按条文保留。

网站采用 baoyu-design 方法形成的学术编辑式界面，预渲染 29 个公开页面及 1 个受保护管理页面，正文含 19 个分节。
首页分别提供应用厂商与标准专家阅读路径；“厂商速读”（/quickstart/）按所选 Profile 合并附录 A 矩阵，列出 M/C/O 条款组。
征求意见程序信息（轮次、截止日期、起草单位、联系人、评议类别、处理结论）集中在 `src/consultation.json`，顶部状态条、意见表单和管理端均读取该文件。

意见渠道：
- 站内表单 `/comment/`：每条编号条文（如 5.1.3）带锚点 `#clause-5-1-3` 与“意见”入口，自动带入条款和章节；不需要账号或登记，默认不公开，提交后返回意见编号（如 R1-0001），本浏览器可查看已提交意见及其处理结论。
- “意见处理情况” `/responses/`：只列出已给出处理结论的意见；从不公开提议人、单位和邮箱，提议方未勾选公开时只显示编制组撰写的摘要。
- GitHub Issue 表单（`.github/ISSUE_TEMPLATE/review-comment.yml`）和邮件为辅助渠道。

5 个下载文件为标准 Word/PDF/Markdown 和评议意见汇总表 Word/Markdown；构建器清理其专用生成目录，防止未列入当前清单的文件残留。
不读取或发布校内材料、私有归档和未选定附件。

## 本地运行与验证

需要 Node.js 22.12+、npm。依赖由锁文件固定。制作 Word 文稿另需 Pandoc。

```bash
cd designs/standards-portal
npm ci
npm run build
npm test
npm exec -- wrangler d1 migrations apply smart-platform-stds-readers --local --persist-to ../../temp/registration-local  # 含 0002_comments
npm run dev:worker
npm run test:browser
```

浏览器检查使用独立 headless Chrome，默认访问 `http://127.0.0.1:4320`；可设置 `PORTAL_TEST_URL=https://stds.chunlin.ch` 检查公网。
构建验证受控源文件，生成正文、全文索引、下载和校验清单，再用 Vite 与 React SSR 生成静态页面。
阅读和下载支持无 JavaScript 访问；搜索、角色切换和筛选在浏览器执行。普通阅读和提交意见均不要求登录或登记。首次访问只在页面顶部显示可关闭的登记提示，不弹窗打断阅读；登记成功后使用 HttpOnly 不透明会话 Cookie 关联本人记录，不在浏览器持久保存姓名或邮箱。

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
# PDF：LibreOffice 无界面模式在 macOS 上不会回退到系统中文字体，需把 Noto CJK 放入独立用户配置的 fonts 目录
mkdir -p /tmp/lo-profile/user/fonts && cp ~/Library/Fonts/NotoSerifCJKsc-{Regular,Bold}.otf /tmp/lo-profile/user/fonts/
soffice -env:UserInstallation=file:///tmp/lo-profile --headless --convert-to pdf --outdir temp 标准/评审稿/智慧教学-数据模型标准.docx
cp temp/智慧教学-数据模型标准.pdf 标准/评审稿/
pdffonts 标准/评审稿/智慧教学-数据模型标准.pdf | grep NotoSerifCJK   # 必须命中，否则中文缺字
```

正式标准的发布和修订按正文治理要求执行。网页编辑不改变征求意见稿性质或代表学校已经完成审定、实现与验收。
编制流程及与正式受控发布的区别见仓库 `维护/标准编制与复现.md`；生成 Word 时保留当前参考文档的 A4、中文字体和样式，并核对全部内容及渲染。

## Cloudflare 部署与回读

独立 Worker：`smart-platform-stds`；Custom Domain：`stds.chunlin.ch`。
凭据通过环境或 Wrangler 身份提供；不写入代码。

```bash
npm run build:primary
npm exec -- wrangler d1 migrations apply smart-platform-stds-readers --remote
npm exec -- wrangler deploy --dry-run
npm exec -- wrangler deploy
```

部署后核对 `/version.json` 的内容与代码提交、全部静态页和当前附件字节、旧下载 404 与浏览器行为。
控制面 hash 保存在机器清单中，评审界面不显示 Git/PR 沿革。
生成目录、依赖和临时 SSR 构建包不提交。代码按仓库 Apache-2.0 使用；文稿与第三方材料遵循仓库授权说明。

## 阅读登记、意见与管理端

首次访问在页面顶部显示可关闭的登记提示（本会话内关闭后不再出现）；读者点击后才打开“阅读者登记”，也可从顶部“阅读登记”管理。姓名、单位或身份、参与角色为基本项，专业方向和邮箱选填。登记说明确认和允许联系均默认不勾选。

登记通过同源 Worker API 写入独立 D1 `smart-platform-stds-readers`。不透明 Cookie 的 SHA-256 用于关联记录；API 校验 Origin、字段长度、角色、邮箱与说明版本，并限流。数据库写入成功后再精确回读；失败不返回成功状态。重复创建幂等，修改和撤回限于本人会话。

意见写入同一 D1 的 `review_comments` 表（迁移 `0002_comments.sql`），使用同一限流与 Origin 校验；会话 Cookie 仅用于“本浏览器提交的意见”列表。管理端“评议意见”页签支持按结论、身份、类别筛选，填写处理结论、理由和公开摘要，并导出意见汇总表 CSV。

信息处理说明在 `/privacy/`（登记与意见信息处理说明）；组织方和联系方式配置在 `src/registration-policy.json`。登记有效期 180 天，到期从可用名单立即移除，每日任务在 24 小时内删除主记录。已阅状态必须由本人明确确认，与页面访问分开；不建立指纹或完整浏览轨迹。此处不验证登记者真实身份，也不把 GitHub 意见自动认定为该人的提交。

管理页：<https://stds.chunlin.ch/admin/>。Cloudflare Access 使用现有邮箱 OTP，并仅允许 `alone@swufe.edu.cn`；Worker 另外验证 Access JWT 的签名、issuer、audience、有效期与允许邮箱。名单支持搜索、分页、CSV 导出及按请求删除。CSV 导出防止公式注入。管理响应和本人会话响应均不缓存。

Cloudflare Access 应用的配置单独存在于 Cloudflare 控制面，`wrangler.jsonc` 保存受众和域名供后端校验，不包含登录凭据。全新账户部署前需先建立等价的独立 Access 应用和允许邮箱策略。不要把数据 Cookie 或 Access Token 写进仓库、链接或日志。

本地 Node API 测试使用内存 SQLite 与真实 RSA 签名；浏览器登记测试使用本地真实 D1。生产验收只用显著标注的合成记录，并在测试后按其会话撤回、精确核对删除，不清空其他人的记录。未经用户操作不发送实际邮箱验证码，邮箱 OTP 的真实收取与登录应单独验收。

Wrangler 已在项目中锁定版本。开发命令中的 `--infer-origin-from-routes=false` 保留真实 localhost Origin，使同源校验和 HTTPS Cookie 检查与生产保持一致；不应降低兼容日期或移除后端校验来通过本地检查。
