# Open edX：WP4a 真实平台取样（合成课程/学员）

本目录服务于“智慧教学-数据模型标准”的平台适配研究，不是标准正文、平台认证或符合性声明；不实施 WP4b 契约转换。

**证据等级：真实平台数据（合成课程/学员）。** 已复用Tutor运行容器完成两个run、师生与选退课、视频/CAPA事件、ORA提交及员工重置后重交、评审/覆盖分历史、cohorts，并从平台导出OLX、原生表投影、tracking及固定ERB的离线xAPI/Caliper输出。没有重建部署、没有真实教学效果证据。

当前样本及逐文件来源、版本、收集时间、字节数和SHA256以 [`samples/manifest.json`](samples/manifest.json) 为准；`deployment/deployment.json` 是先前部署阶段的历史检查点，不是当前场景覆盖声明。编号追溯见 [`追溯表.csv`](追溯表.csv)，适配风险和待验证项见 [`发现的标准问题.md`](发现的标准问题.md)。

## 场景阶段1：课程、身份、选课、小组

```sh
bash seed --stage structure
python3 -m unittest discover -s . -p 'test_seed.py' -v
```

`course-template.xml` 为自写合成OLX，含native video、CAPA数值题与staff-assessment ORA2。脚本生成三秒纯蓝色视频，分别导入 `course-v1:SYNTH+WP4A+run01` 和 `run02`。两者为同主题两个开课，不主张它们构成标准不可变课程版本。每个run选入3名学员与1名教师，学员03退选再选入；教师获得course staff及instructor角色，3名学员加入手动cohort“合成小组01”。仅使用 `wp4asynth01`—`04`、`example.invalid` 邮箱、虚构中文显示名；用户口令不可用，不设置固定口令。

脚本在平台已存在合成用户或课程时拒绝再次执行structure阶段；不清空平台、不改动其他课程、不重建容器。不支持在部分失败后自动覆盖导入或继续，需先定位故障。导入和选课通过Open edX原生management command/API完成；不能从课程中存在block推断活动已发生，学习证据见下一阶段。

原生OLX检查发现初始模板的空 `youtube=""` 保留了上游默认YouTube示例ID，而非禁用。已通过CMS原生update/publish清空两个run的youtube_id_1_0，未删除课程或学习状态；模板改为明确空速率映射加source子节点，使新导入只使用合成MP4，并在structure阶段断言禁用YouTube。最终导出中 `youtube_id_1_0=""`，包含合成MP4而非默认YouTube示例ID。脚本化事件不证明访问了任何视频服务。

## 场景阶段2：学习活动、ORA重试、评分历史

```sh
bash seed --stage learning
bash seed --stage revision
```

learning阶段通过Django Client派发原生 `/event` 和CAPA XBlock handler请求：3名学员各产生play/pause/stop视频事件，数值题先答1再答2，各有incorrect、correct两次 `problem_check`。会话由脚本内的 `force_login` 及平台SafeSessionCookie生成，不使用可登录口令、不跳过平台安全会话中间件。最初未包装SafeSessionCookie的请求失败，未形成成功学习活动；已修正，不提交会话或失败原始日志。

这是脚本化请求，不是浏览器真实解码/观看的证据，三秒时间值为合成事件参数。CAPA请求则实际执行平台作答与判分逻辑，不是直接写成绩表。

ORA通过已导入block的 `submissions_actions.submit` 创建初稿及workflow，再通过原生staff assessment API初评1/3、复评3/3。revision阶段调用平台 `reset_student_attempts(..., delete_module=True)`，由ORA的 `clear_student_state` 取消workflow并将旧提交软删除，再通过原生block API重交不同文本；第二份作业获3/3。旧提交底层行与取消记录保留。当前ORA版本源码有受配置/截止/评审状态限制的学习者重交功能，本场景未启用；**不声称整个Open edX缺少重交能力**，本次采用员工重置这一等效流程。

核对时发现 `Submission.objects.count()` 默认排除软删除的初稿（返回1），不能用该manager判断原始提交历史数量；取样必须直接读取原始表以保留两份记录，不能“修复”平台manager或补造历史。

两份提交UUID及文本不同，但同一student_item的attempt_number都为1；不能仅凭该计数合并重置前后两份事实。保留UUID、status、时间和取消记录，尝试身份适配留给WP4b。revision阶段还检查原始表恰有一份活跃初稿，拒绝部分完成/重复的重置。

此外用原生成绩工厂计算持久化成绩，并调用 `PersistentSubsectionGradeOverride.update_or_create_override` 将学员01的subsection覆盖分从2/4改为3.5/4，保留两条历史及教师归属。它是平台分数覆盖历史，不自动等同标准正式更正决定/审批链。learning及revision阶段分别在已有学习状态/分数覆盖时拒绝重复；中途失败后不自动覆盖已有记录。

## 版本与差异

机器可读结果及全部依赖镜像摘要见 [`deployment/deployment.json`](deployment/deployment.json)。收集器只读取选定的镜像字段、版本和 VCS 元数据，不导出容器环境变量。

| 组件 | 本次运行值 | 相对源码快照 |
| --- | --- | --- |
| Tutor | 23.0.0；`e29ec3e0a9d66131fffb21bef5adc00ac799d712` | 固定 main 提交；非22.0.4回退 |
| edx-platform | `d3a86602dcf70bbf4f7925727bcc50ff10e51109` | 与目标 `ccfe30bfdb22d56c0139958c17049840b8176519` 不同；未进行逐文件兼容性分析 |
| edx-event-routing-backends | 10.1.0；`bae21257a259d17d54d9501af0abdd0c8e002ed8` | 与目标提交一致；实际运行离线转换，缺口见下文 |
| edx-submissions | 4.0.2；提交未知 | wheel 无 VCS 元数据，不能断言等同目标 `9c9e7c416a127c769b72d2c1b7141de96d20283a` |
| ORA2 | 7.1.3；提交未知 | 已执行提交、员工重置及评审；不以版本冒充提交证据 |
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

本机部署检查：`tutor local launch -I --skip-build` 返回0，LMS根路径HTTP 200。Studio根路径301至 `/home/`，未登录跟随至HTTP 401；课程导入/导出后续已由原生management command完成，不依赖HTTP检查推断。未验证教师浏览器登录或Studio交互，未做浏览器视觉检查。

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

已检查容器中 `common/djangoapps/util/storage.py`：缺少该legacy键会明确回退到 `STORAGES['default']['BACKEND']`。这不是工作目录未激活；迁移和后续导入、CAPA/ORA及成绩工厂操作均在该配置下完成，不修改上游共享配置压制警告。导出另有上游runtime.user_id、GridOut.contentType弃用警告，非宿主环境未加载。

部署已恢复成功，没有走官方示例OLX的降级回退，也没有把上游fixture假装成运行平台导出。

## 导出与复跑保护

```sh
# 复用运行部署，不重建或重复造数
bash export                          # 默认新建 .runtime/exports-*，不写已提交文件
bash export --output .runtime/new-export
# 仅在samples不存在或为空时显式建立样本；已有样本会拒绝，不提供强制覆盖
bash export --update-samples
python3 -m unittest discover -s . -p 'test_*.py' -v
bash -n deploy.sh tutor.sh seed export teardown
git diff --check
```

宿主采集脚本仅用Python 3.11+标准库，无新增宿主依赖；平台API/ERB使用镜像内依赖。默认写入忽略的本地临时目录，非空目录/普通文件均拒绝，异常保留失败输出，不覆盖或自动续写。第一次CMS导出报 `fs.errors.CreateFailed: root path '.../run01' does not exist`；原生命令需要现有目标目录，脚本现先创建全新目录再导出，未为此重建服务。

export_runtime.py在LMS shell执行只读SQL，以SYNTH/WP4A course_id及显式关联子查询限制范围。auth_user只投影4名合成身份必要字段，profile只取user_id/name；不读取密码值、不导出会话/令牌表。JSON递归去除password/secret/token/session/cookie/CSRF等键，tracking另去除IP/agent，投影见export-policy.json。submissions直接查原始表，保留D行，不能换用默认manager。

关联导出曾因submissions的32位UUID与ORA保存的带连字符UUID直接比较而得到空评审集；已在关联条件归一化两端UUID并检查必需证据表非空，没有更改表内原值或补造评审。选课history_id是随机UUID，必须按history_date排序，不按主键字典序判断先后；management command事件中的字符串user_id="None"保留为平台无当前用户上下文，不冒充合成师生。

tracking.jsonl来自 `/openedx/data/logs/tracking.log` 中合成课程/用户的原生JSON记录；**保留原生事件名/业务载荷，但因字段删除和JSON重编码，不是原文件逐字节副本**，也不是标准事件。匿名学习者标识/提交UUID是合成关系引用，不作为登录令牌使用。不要提交.runtime中的原始tracking、完整Tutor配置或部署日志。

OLX由 `./manage.py cms export course-v1:SYNTH+WP4A+runNN <new-directory>` 实际生成，再用tarfile归档；含课程、策略和合成媒体，不含学习者状态。未执行重新导入/还原验证。

## ERB配置、输出与实际缺口

运行LMS没有配置向外部LRS/Caliper服务发消息。导出只在Django override_settings中临时启用XAPI_EVENTS_ENABLED和CALIPER_EVENTS_ENABLED，并将两种EVENT_LOGGING_ENABLED设False；逐行使用原生parse_json_event、XApiProcessor/CaliperProcessor.transform_event处理去敏感tracking，Caliper再用CaliperEnvelopeProcessor(LMS_ROOT_URL)生成envelope。未发起LRS传送、未永久改Tutor配置、未实现本标准契约转换。

99条输入中，xAPI成功转换76条（76条JSONL），Caliper成功转换37条（37个envelope）。erb-report.json列出所有不支持类型、空输出和失败行号/异常，可逐项对账。ORA create_submission/staff_assess等没有对应registry转换器，未人工改写补齐。

**xAPI有6条显式失败**：problem_check所需referer/context.referer为空，原生错误 `ValueError: Could not get value for context.referer in event "problem_check"`。已核对未投影的原始六条相应字段也为空，排除只是去敏感投影造成的解释；未事后补造referer。同期edx.grades.problem.submitted等可转换，不意味着problem_check输出已补回。Caliper本次没有异常，但仍有不支持类型。这些仅证明固定ERB对此输入的处理，不是全事件覆盖或协议/标准认证。

## 样本清单与覆盖

逐文件库存/字节数见manifest；共39个文件（38份证据/元数据加manifest），约253 KiB，低于20MB。

| 文件或文件族 | 内容与覆盖 |
| --- | --- |
| run01.tar.gz、run02.tar.gz | 两个run原生OLX、视频/CAPA/ORA2、3秒合成MP4 |
| auth_user、auth_userprofile、student_courseaccessrole及history JSON | 4名合成师生，每run教师角色与历史 |
| student_courseenrollment及history JSON | 8条当前活跃选课、20条历史；学员03每run退选/重选 |
| tracking.jsonl | 99条原生记录投影；各3条play/pause/stop、6条problem_check、ORA/选课/评分事件 |
| xapi.jsonl、caliper.jsonl、erb-report.json | ERB离线输出及配置/计数/不支持类型/6条xAPI错误 |
| courseware_studentmodule及history JSON | 3名学员CAPA当前1/1、两次尝试；6条错/对历史、ORA当前UUID |
| submissions_studentitem/submission/score/scoresummary JSON | 两个UUID，D初稿/A重交、attempt_number均1；8条score含reset |
| assessment_*、workflow_* JSON | 3次评审、rubric/parts、2个workflow和1条取消 |
| grades_persistent*、grades_historical*、grades_visibleblocks JSON | 3名学员持久化成绩；2→3.5/4的两条覆盖历史 |
| course_groups_* JSON | 两个cohort，各3名成员及关联；未创建teams |
| platform.json、export-policy.json、manifest.json | 当前版本/镜像摘要、范围投影、来源/hash/时间/场景库存 |

追溯表17行、16个矩阵既有编号、9类场景，仅追溯本次范围，不覆盖整个矩阵。视频、CAPA、ORA与改分活动发生在run01；run02提供第二开课、师生选退课与cohort证据，不声称两个run均有相同学习活动。

## 未验证或不能声称的事项

- 无浏览器视觉/真实播放、观看时长、Studio交互或备份还原验证；脚本化请求不能证明这些体验。
- 未启用学习者自助重交，采用员工重置替代；不声称平台缺少全部重交能力。
- 未创建teams/团队提交，未实测成员退出/迁移；cohort当前关系不等于事件形成时成员快照。
- 无正式成绩发布/更正授权决定链、跨平台统一尝试/不可变课程版本、学校事件Profile或关键提交证据库回执。
- 无LRS发送/接收、全事件转换或标准符合性证明；不能省略错误后宣称全覆盖。
- 合成测试不能作为真实师生行为或真实教学效果。

复跑检查发现：启用默认build attestation时，再次构建同内容镜像会产生新的索引摘要，原容器仍报告旧摘要，但本机镜像检查已无法解析该旧摘要，导致版本收集失败（`No such image`）。已关闭该attestation并让Tutor配置使用实际本地摘要，强制平台容器与可检查镜像一致；不通过查询可移动tag来伪造旧容器的digest。
