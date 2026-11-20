# Open edX：WP4a 运行环境检查点（未完成场景取样）

本目录服务于“智慧教学-数据模型标准”的平台适配研究，不是标准正文、平台认证或符合性声明；不实施 WP4b 契约转换。

**本次为中途交接检查点，不能作为第2步全部完成的交付。** 已通过 Tutor local 启动 Open edX、完成数据库迁移并收集容器内版本和镜像元数据。尚未创建合成课程或用户，没有课程导出、学习行为、成绩历史、xAPI/Caliper 样本，不得标为“真实平台数据（合成课程/学员）”。当前证据等级仅为**运行时部署元数据**。

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

1. 编写合成OLX课程（视频/CAPA/ORA2），平台导入两个run；创建至少3名学员、教师及选退课/模式变更、cohort或team。
2. 生成实际视频事件、`problem_check`、ORA提交与可行的重试等效流程、评审与改分历史。不能用自造JSON充当平台事件，也不能把submissions底层API的能力推断成ORA学习者界面支持重交。
3. 实现 `seed` / `export`，保留每个run的原生OLX导出、tracking JSONL、原生表投影，以及目标event-routing-backends生成的xAPI/Caliper；检查配置、丢弃/不支持事件与转换错误。
4. 新建 `samples/manifest.json`、矩阵编号追溯表、按Issue模板字段记录的可能标准问题及 `test_samples.py`；覆盖合成身份、无敏感字段、SHA256、总体积<20MB、正常/空/错误输入、非覆盖输出及声明范围无遗漏。
5. 取得上述样本并验证后才提升为“真实平台数据（合成课程/学员）”；当前没有新的实测标准问题结论。

本检查点不含上述尚未实现文件的空壳，也不把部署元数据单元测试当作场景/样本验收。

复跑检查发现：启用默认build attestation时，再次构建同内容镜像会产生新的索引摘要，原容器仍报告旧摘要，但本机镜像检查已无法解析该旧摘要，导致版本收集失败（`No such image`）。已关闭该attestation并让Tutor配置使用实际本地摘要，强制平台容器与可检查镜像一致；不通过查询可移动tag来伪造旧容器的digest。
