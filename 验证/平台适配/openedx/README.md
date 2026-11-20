# Open edX：WP4a 运行环境检查点（未完成场景取样）

本目录服务于“智慧教学-数据模型标准”的平台适配研究，不是标准正文、平台认证或符合性声明；不实施 WP4b 契约转换。

**当前为分阶段交付，尚未完成最终导出。** 已复用运行容器执行课程、身份、选课、小组及学习评分活动；这些是实际平台中的合成场景，但已保存的 `deployment/` 仍仅为部署元数据，最终证据需由后续样本导出和测试支持。

## 场景阶段1：课程、身份、选课、小组

```sh
bash seed --stage structure
python3 -m unittest discover -s . -p 'test_seed.py' -v
```

`course-template.xml` 为自写合成OLX，含native video、CAPA数值题与staff-assessment ORA2。脚本生成三秒纯蓝色视频，分别导入 `course-v1:SYNTH+WP4A+run01` 和 `run02`。两者为同主题两个开课，不主张它们构成标准不可变课程版本。每个run选入3名学员与1名教师，学员03退选再选入；教师获得course staff及instructor角色，3名学员加入手动cohort“合成小组01”。仅使用 `wp4asynth01`—`04`、`example.invalid` 邮箱、虚构中文显示名；用户口令不可用，不设置固定口令。

脚本在平台已存在合成用户或课程时拒绝再次执行structure阶段；不清空平台、不改动其他课程、不重建容器。不支持在部分失败后自动覆盖导入或继续，需先定位故障。导入和选课通过Open edX原生management command/API完成；尚未执行浏览器播放、答题或ORA学习者流程，不能从课程中存在block推断这些活动已发生。

## 场景阶段2：学习活动、ORA重试、评分历史

```sh
bash seed --stage learning
bash seed --stage revision
```

learning阶段通过Django Client派发原生 `/event` 和CAPA XBlock handler请求：3名学员各产生play/pause/stop视频事件，数值题先答1再答2，各有incorrect、correct两次 `problem_check`。会话由脚本内的 `force_login` 及平台SafeSessionCookie生成，不使用可登录口令、不跳过平台安全会话中间件。最初未包装SafeSessionCookie的请求失败，未形成成功学习活动；已修正，不提交会话或失败原始日志。

这是脚本化请求，不是浏览器真实解码/观看的证据，三秒时间值为合成事件参数。CAPA请求则实际执行平台作答与判分逻辑，不是直接写成绩表。

ORA通过已导入block的 `submissions_actions.submit` 创建初稿及workflow，再通过原生staff assessment API初评1/3、复评3/3。revision阶段调用平台 `reset_student_attempts(..., delete_module=True)`，由ORA的 `clear_student_state` 取消workflow并将旧提交软删除，再通过原生block API重交不同文本；第二份作业获3/3。旧提交底层行与取消记录保留。当前ORA版本源码有受配置/截止/评审状态限制的学习者重交功能，本场景未启用；**不声称整个Open edX缺少重交能力**，本次采用员工重置这一等效流程。

核对时发现 `Submission.objects.count()` 默认排除软删除的初稿（返回1），不能用该manager判断原始提交历史数量；取样必须直接读取原始表以保留两份记录，不能“修复”平台manager或补造历史。

此外用原生成绩工厂计算持久化成绩，并调用 `PersistentSubsectionGradeOverride.update_or_create_override` 将学员01的subsection覆盖分从2/4改为3.5/4，保留两条历史及教师归属。它是平台分数覆盖历史，不自动等同标准正式更正决定/审批链。learning及revision阶段分别在已有学习状态/分数覆盖时拒绝重复；中途失败后不自动覆盖已有记录。

## 版本与差异

机器可读结果及全部依赖镜像摘要见 [`deployment/deployment.json`](deployment/deployment.json)。收集器只读取选定的镜像字段、版本和 VCS 元数据，不导出容器环境变量。

| 组件 | 本次运行值 | 相对源码快照 |
| --- | --- | --- |
| Tutor | 23.0.0；`e29ec3e0a9d66131fffb21bef5adc00ac799d712` | 固定 main 提交；非22.0.4回退 |
| edx-platform | `d3a86602dcf70bbf4f7925727bcc50ff10e51109` | 与目标 `ccfe30bfdb22d56c0139958c17049840b8176519` 不同；未进行逐文件兼容性分析 |
| edx-event-routing-backends | 10.1.0；`bae21257a259d17d54d9501af0abdd0c8e002ed8` | 与目标提交一致；已安装并迁移，**未验证事件转换** |
| edx-submissions | 4.0.2；提交未知 | wheel 无 VCS 元数据，不能断言等同目标 `9c9e7c416a127c769b72d2c1b7141de96d20283a` |
| ORA2 | 7.1.3；提交未知 | 尚未执行提交/评审 |
| openedx-events | 11.2.0；提交未知 | 不以发行版本冒充源码提交证据 |
| Python / Django | 3.12.13 / 5.2.19 | 容器内实际读取 |
| MySQL / MongoDB | 8.4.13 / 7.0.48 | Tutor依赖服务 |
| Redis / Caddy / Meilisearch | 7.4.12 / 2.11.9 / 1.36.0 | Tutor依赖服务 |

基础镜像为 `overhangio/openedx:23.0.0-main@sha256:4c02292ee576964472f92be4b8b78972202af2dde57d095114d1fea13ad99a2f`。原镜像没有安装 `edx-event-routing-backends`（检查了正确发行包名称，而不只是缺少 `event-routing-backends` 这个名字）。因此用 `image.Dockerfile` 创建本地衍生镜像 `wp4a-openedx:bae21257`，安装目标提交及固定版本的新增依赖；没有改 edx-platform 源码。部署使用本地镜像实际摘要，而非可移动tag；关闭build provenance以避免仅attestation时间变化造成新索引摘要。衍生镜像没有发布，元数据中的本地摘要不代表远程仓库存在可拉取的同名镜像。该镜像构建尚非离线、逐字节可复现构建。

## 复现部署

前提：Docker/Compose、Git、Python 3.11+、venv 和可访问的镜像/Python/Git源；Docker本机端口80/443应空闲。该配置仅供本地合成测试，HTTP、禁用SMTP、无MFE插件，不适用于生产部署。

```sh
cd 验证/平台适配/openedx
bash deploy.sh
bash tutor.sh local status
python3 collect_versions.py
# 或指定不存在/空目录；非空目录会被拒绝，不会覆盖已有元数据
python3 collect_versions.py --output .runtime/another-version-collection
python3 -m unittest discover -s . -p 'test_deployment.py' -v
# 仅停止Open edX；不删数据、不影响Moodle
bash teardown
```

`IMAGE_REGISTRY` 可替换 MySQL/MongoDB/Redis/Caddy 的镜像源，默认 `mirror.gcr.io`；保持相同镜像内容摘要。基础 Open edX、permissions 和 Meilisearch 也固定摘要。Tutor 安装固定 Git 提交，但其工具链传递依赖尚未生成完整锁文件。

`tutor.sh` 将 Tutor 配置、插件目录及数据库绑定目录限定在忽略的 `.runtime/`。Tutor首次运行生成随机部署口令；部署日志可能包含 Tutor 回显的敏感命令，**只能保留在被忽略的本机 `.runtime/`，不得复制或提交原始日志/完整 config.yml/Compose 环境**。脚本不创建真实人员账号。重跑部署不写 `deployment/` 或未来的 `samples/`；版本收集默认写 `.runtime/versions-*`，显式输出仍拒绝覆盖非空目录。`deployment/` 是本次保存的部署证据，不是教学样本。

本机检查：`tutor local launch -I --skip-build` 返回0，LMS根路径HTTP 200。Studio根路径301至 `/home/`，未登录跟随至HTTP 401；尚未验证教师登录或Studio交互，不能据此声称课程导入可用。未做浏览器视觉检查。

## 部署故障与恢复

最初执行 `bash tutor.sh local launch -I --skip-build` 失败，去除口令后的原始错误片段：

```text
ERROR 2005 (HY000): Unknown MySQL server host 'mysql' (-2)
[10/10] Waiting for MySQL service (this may take a while)...
MySQL initialisation error
Error: Command failed with status 1
```

随后检查实际容器日志与目录权限，发现初始配置错误地让 permissions 服务使用 MySQL 镜像：

```text
/usr/local/bin/setowners.sh: line 2: setowner: command not found
mysqld: Can't create/write to file '/var/lib/mysql/is_writable' (OS errno 13 - Permission denied)
[ERROR] [MY-010460] [Server] --initialize specified but the data directory exists and is not writable. Aborting.
```

当时宿主目录为root所有、0755，而Tutor指定MySQL进程用户999，故数据库写权限错误有直接证据。改为官方 `overhangio/openedx-permissions:23.0.0-main` 后，permissions正常退出0，MySQL运行，初始化和后续迁移完成。没有更改Compose项目名、数据库口令或删除数据库来绕过问题。最初DNS报错与重启状态的精确时序未采集，不能把DNS层因果链称为已完全证实；不存在已验证的“项目名不一致”结论。

初始配置另有警告：

```text
Warning: RUN_MEILISEARCH=false, but MEILISEARCH_URL is still set to its default value "http://meilisearch:7700".
```

这不是环境未加载，而是禁用内部服务却仍引用内部URL的配置缺陷；已改为启动Meilisearch，未假定存在外部服务。首次插件缺失提示通过显式 `PLUGINS=[]` 消除；当前不用MFE/indigo。

迁移还反复输出以下上游存储回退警告：

```text
Key BLOCK_STRUCTURES_SETTINGS 'STORAGE_CLASS' not found in storage settings {'COURSE_PUBLISH_TASK_DELAY': 30, 'TASK_DEFAULT_RETRY_DELAY': 30, 'TASK_MAX_RETRIES': 5}.Using default storage path.
```

已检查容器中 `common/djangoapps/util/storage.py`：缺少该legacy键会明确回退到 `STORAGES['default']['BACKEND']`。这不是工作目录未激活；迁移在该回退下完成。尚未实测课程block structure读写，需在造数阶段继续验证；本次不修改上游共享存储配置压制警告。

部署已恢复成功，因此尚未走官方示例OLX的降级回退，也没有把上游fixture假装成运行平台导出。

## 待完成的第2步内容

1. 已完成：合成OLX课程（视频/CAPA/ORA2）、平台导入两个run、3名学员和教师、选退课、cohort；最终原生导出仍待后续阶段。
2. 已执行：原生视频事件、`problem_check`、ORA提交与员工重置后重交、评审与分数覆盖历史；待最终导出测试。不能把这些脚本化原生API能力推断成全部学习者界面能力。
3. 实现 `seed` / `export`，保留每个run的原生OLX导出、tracking JSONL、原生表投影，以及目标event-routing-backends生成的xAPI/Caliper；检查配置、丢弃/不支持事件与转换错误。
4. 新建 `samples/manifest.json`、矩阵编号追溯表、按Issue模板字段记录的可能标准问题及 `test_samples.py`；覆盖合成身份、无敏感字段、SHA256、总体积<20MB、正常/空/错误输入、非覆盖输出及声明范围无遗漏。
5. 取得上述样本并验证后才提升为“真实平台数据（合成课程/学员）”；当前没有新的实测标准问题结论。

本检查点不含上述尚未实现文件的空壳，也不把部署元数据单元测试当作场景/样本验收。

复跑检查发现：启用默认build attestation时，再次构建同内容镜像会产生新的索引摘要，原容器仍报告旧摘要，但本机镜像检查已无法解析该旧摘要，导致版本收集失败（`No such image`）。已关闭该attestation并让Tutor配置使用实际本地摘要，强制平台容器与可检查镜像一致；不通过查询可移动tag来伪造旧容器的digest。
