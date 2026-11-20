# WP4a：Moodle 真实平台取样

## 目的、范围与证据等级

为“智慧教学-数据模型标准”保留可复现的原生平台数据，供后续 WP4b 研究。
**证据等级：真实平台数据（合成课程/学员）**。数据由运行中的 Moodle 经 CLI 调用平台
API、模块逻辑与题目引擎产生，不是手写数据库 fixture，不是认证或符合性声明，
不证明真实教学有效性。这里没有标准契约对象转换、标准事件映射输出或符合性测试结论。

全部课程、学员、教师、提交、答题及媒体均为合成；没有真实个人信息。
数据库仅监听 Compose 内网，Web 绑定 `127.0.0.1:8087`，邮件发送禁用。

## 实际运行版本和镜像

| 项目 | 实测值 |
|---|---|
| Moodle 源码提交 | `2d4bafe8548a6d6c01494c862ec3d9749ba6ea84` |
| Moodle release / version | `6.0dev (Build: 20261117)` / `2026111700.00` |
| PHP | `8.3.36` |
| PostgreSQL | `17.12 (Debian 17.12-1.pgdg13+1)` |
| Web 镜像 | `mirror.gcr.io/moodlehq/moodle-php-apache:8.3` |
| Web digest | `sha256:1db7b6ed013fcb5268095b5e28c410ba9117d38d9b6a324c100c48fcbe69745e` |
| DB 镜像 | `mirror.gcr.io/library/postgres:17` |
| DB digest | `sha256:b60e90042aa6b8dbecd58e224b3e36114dbf8ad754465264c2476ad58a86e45c` |

与平台对标 README 的源码快照**无源码版本差异**：直接下载上述固定提交的源码归档，
代码根为 `public/`；不改 Moodle 源码，仅在源码根放置本目录的运行配置 `config.php`。
`platform.json` 是运行 PHP/数据库查询结果；提交号由固定源码 URL 登记，非运行中 Git 检测。
完整镜像名称、ID、RepoDigests 由 `docker inspect` 采集，见 `samples/manifest.json`。
默认镜像同时固定 digest，`deploy.sh` 可用 `IMAGE_REGISTRY` 切换镜像仓库，或用
`PHP_IMAGE` / `DB_IMAGE` 指定完整镜像引用。直接 `docker compose` 使用 compose 中的默认镜像；
如需切换，所有命令应保持同一组环境变量。

### 部署问题与解决

初次 Docker Hub 返回 `429 Too Many Requests`，ECR 返回 `Data limit exceeded`，当时回退为
官方示例。本次改用 `mirror.gcr.io` 完成部署，已移除旧示例，不再混用证据等级。
最初使用 PostgreSQL 16.16，被安装检查拒绝：

```text
version 17 is required and you are running 16.16
```

因此使用 PostgreSQL 17，而非绕过版本检查；原 16 卷不复用。
造数调试中，上游 question 测试 helper 依赖 PHPUnit，故改用真实 `save_question` API；
测验加题后调用平台 `recompute_quiz_sumgrades`；分组生成器传分组 idnumber。
失败的造数事务均自动回滚，数据库序列号可能留空洞，不按 ID 连续性判断记录遗漏。

## 复现

需要 Docker Engine / Compose、Python 3.11+、curl、tar、openssl、ripgrep、ffmpeg（含 libx264）。
Python **只用标准库，无第三方依赖**，不需要依赖锁文件。PHP 来自固定镜像。
从本目录执行：

```sh
./deploy.sh
./seed
./export                         # 输出新的临时目录，不改 samples/
./export --output /path/to/new-empty-directory
python3 -m unittest discover -s . -p 'test_*.py' -v
```

`deploy.sh` 运行数据库安装 CLI，已安装时跳过安装；站点管理员口令运行时随机生成且不落库外明文。
数据库口令在忽略的 `.runtime/db.env`，首次生成权限 0600，不提交。不要用 `bash -x` 运行部署脚本。
生成器通过 `core\session\manager::set_user` 设置合成操作用户，以 CLI 身份执行，
不需要人工登录或手工点击。重复 `seed` 会拒绝已有场景，防止叠加记录；它仅会重建忽略的合成视频。

```sh
./teardown                       # 停容器和项目网络，保留卷
./deploy.sh                      # 重新启动已有数据
./teardown --volumes             # 显式删除本 Compose 项目的 DB17 和数据卷
./deploy.sh && ./seed             # 全新数据库重建场景（ID/时间不要求相同）
```

当前交付的两个容器保持运行。首次错误部署遗留的 DB16 卷不由当前 compose 管理，不会自动删除。

### 更新样本与覆盖保护

默认导出先在忽略的 `.runtime/export-*` 暂存，再复制到新临时目录；不会回写已提交文件。
`--output` 指向非空目录会失败；即使 `--update-samples` 也**拒绝覆盖非空 samples**。
显式更新需先由维护者将原 samples 归档到仓库外持久目录并清空目标，再执行
`./export --update-samples`，审阅差异后另行提交。测试覆盖非空目录拒绝和内容不变。
备份有生成时间、随机备份 ID，复跑不要求二进制相同；每次输出各自的摘要与收集时间。

## 场景与核对结果

| 场景 | 实际数据 / 证据 |
|---|---|
| 两个开课 | `SYNTH-OPEN-01` 与 `SYNTH-OPEN-02`，当前 course ID 8、9；同一教学主题的两个独立空间，**不是两个不可变课程版本**。第二空间仅造师生选课，活动集中在第一空间 |
| 师生与选课 | 学员01–03、教师04，共4名合成用户；两个空间各4条选课，共8条，教师各有 editingteacher 角色 |
| 状态变更 | 学员03在开课01经 `update_user_enrol` 暂停后恢复；同一选课有2条 `user_enrolment_updated`，当前恢复 active。日志本身不保留旧/新状态值，不能单靠导出还原状态序列 |
| 视频查看 | ffmpeg 生成3秒蓝色视频 `synthetic.mp4`，以 resource 储存；3位学员各调用 `resource_view`，产生3条查看日志。备份内含视频，可按 files.contenthash 校验 |
| quiz | 简答题 `1+1=?`，三位学员均提交 `2`，3条 finished attempt，sumgrades=1，各得100分 |
| assign 重开重交 | 个人作业手动 reopen；学员01两次 submitted，attemptnumber=0、1（Moodle 从0编号），提交文本不同，第一次 latest=0，第二次 latest=1 |
| 教师改分 | 个人作业第一次60分；重交后70分，再改为85分；grade_grades_history 保留60、70、85，当前85。评分者为教师04 |
| 小组作业 | 1个 group、1个 grouping、3名成员；grouping关联小组；teamsubmission=1，组提交 userid=0/groupid=4；评分传播给三名成员，60改85 |

全部上述证据由离线测试检查，不将 Moodle 原生事件直接认作标准事件。
矩阵要素追溯见 `追溯表.csv`；本次范围由 `export.py:SCENARIO_ELEMENTS` 声明，
测试逐场景检查追溯项无遗漏、无多项、无重复、编号存在于正式矩阵、文件存在。
这里的“无遗漏”指本次 WP4a 取样范围，不是整个矩阵或 WP4b 首批契约全覆盖。

## 样本清单与来源

41个数据/元数据文件加1个 manifest，约270KB（精确体积与逐文件SHA256见 manifest）。

| 类别 | 文件 |
|---|---|
| 课程备份 | `course-users.mbz`、`course-no-users.mbz` |
| 原生日志 | `logstore_standard_log.json`（124条） |
| 成绩与历史 | `grade_items.json`、`grade_grades.json`、`grade_grades_history.json`（38条）、`grade_items_history.json` |
| 作业 | `assign.json`、`assign_submission.json`（6条，含组/成员占位记录）、`assign_grades.json`、`assignsubmission_onlinetext.json`、`assign_plugin_config.json` |
| 测验/题目/响应 | `quiz.json`、`quiz_slots.json`、`quiz_attempts.json`、`quiz_grades.json`、`question.json`、`question_versions.json`、`question_bank_entries.json`、`question_references.json`、`question_answers.json`、`question_usages.json`、`question_attempts.json`、`question_attempt_steps.json`、`question_attempt_step_data.json` |
| 课程/资源 | `course.json`、`course_modules.json`、`resource.json`、`files.json` |
| 师生/选课/小组 | `user.json`、`user_enrolments.json`、`enrol.json`、`role.json`、`role_assignments.json`、`context.json`、`groups.json`、`groups_members.json`、`groupings.json`、`groupings_groups.json` |
| 来源元数据 | `platform.json`、`export_policy.json`、`manifest.json` |

含用户备份实际调用当前快照的 `admin/cli/backup.php`（位于源码根，不在 public 下），
启用 users/logs/grade_histories；无用户备份调用同一个 `backup_controller`，显式 users=false。
两包均为开课01；开课02数据在表导出中。未执行备份还原验证，不能据此主张可往返恢复。
表 JSON 由 Moodle 数据库 API 按 id 排序导出，是平台原字段；除明确安全投影外不改值。
manifest 是取样来源清单，不是标准交换 manifest；时间为本次 UTC 收集时间，备份内部另有生成时间。

## 隐私与局限

- `user.json` 只保留 `id,username,firstname,lastname,email,auth,suspended,deleted,idnumber`，不含密码哈希、令牌、会话或手机号。除4名造数用户，还含合成管理员及 Moodle 内建 guest；guest 的 `root@localhost` 是本机默认值，非真实邮箱，其余邮箱均为 `example.invalid`。
- 仅导出白名单表，不导出 sessions、user_password_history、外部令牌或站点配置。各表列名含 password/secret/token 的列均剔除（本次为 quiz.password、enrol.password），安全投影记于 `export_policy.json`。其内容只是被排除列名，不含这些列的值。
- `includeuserpasswordsinbackup=false`；测试逐个检查两个归档内 XML，禁止非空口令/令牌/会话字段，含用户包实际只有4名合成师生，不含密码字段。`files.contenthash` 是资源内容摘要，不是凭据。
- 所有日志 origin=cli；视频“查看”仅说明调用了真实资源查看逻辑，不证明浏览器播放、观看时长、完播率或 `media.progressed`。未做视觉检查。
- 成绩历史不自动等同标准评分确认、更正审批或归档链；小组当前成员不自动等同事发时成员快照。详见 `发现的标准问题.md`。
- 这是单实例、单次合成场景，不代表生产规模、安全审计、性能、学生认知效果或标准符合性。此目录的脚本应仅用于隔离的合成站点，不能直接对生产库全表导出。
