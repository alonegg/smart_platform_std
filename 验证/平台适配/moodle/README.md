# WP4a Moodle 平台取样（部署受阻，官方示例降级交付）

## 目的与证据边界

本目录服务于“智慧教学-数据模型标准”的取样工作，不做 WP4b 契约转换，不发明标准。
**本次未部署成功；不是“真实平台数据（合成课程/学员）”证据，不是认证或符合性声明。**
按任务允许的失败回退路径，只交付上游官方测试仓库的无用户合成课程备份。
未伪造数据库表 JSON、日志、用户数据或评分历史；没有用空数组冒充真实导出。
完整 Docker 部署、场景造数和数据库导出仍未完成，本目录不能视为 WP4a 完整验收通过。

## 版本与差异

| 项目 | 实际情况 |
|---|---|
| 对标源码提交 | `2d4bafe8548a6d6c01494c862ec3d9749ba6ea84` |
| 已下载源码版本 | `6.0dev (Build: 20261117)`，`2026111700.00`，代码根 `public/` |
| 实际部署版本 / 提交 | 无；不得把源码版本当作运行版本 |
| 计划 PHP 镜像 | `moodlehq/moodle-php-apache:8.3`；拉取失败，digest 未取得 |
| 尝试的替代标签 | `moodlehq/moodle-php-apache:8.3-bookworm`；同样失败，未验证标签存在 |
| DB 镜像探测 | `public.ecr.aws/docker/library/postgres:16`；失败，digest 未取得 |
| PHP / DB 运行版本 | 未运行，未知；标签不是实测版本 |
| 官方示例备份内部版本 | `5.2dev (Build: 20260109)`，`2026010900` |
| 备份原始生成时间 | Unix `1768413472`；与 manifest 的收集时间分列 |
| 备份平台提交 | 上游文件未记录，未知；不能等同承载 fixture 的源码提交 |

示例来自上述固定提交的
`public/mod/subsection/tests/fixtures/subsections_with_descriptions.mbz`。
这是上游测试用课程 `Subsections course`，不是本次 CLI 备份。
内部含 label、subsection、url、wiki、glossary；无 users.xml，users 设置为 0，files.xml 为空。
检查了归档全部文本：未见姓名/邮箱/账号记录，选课 password 字段仅为空或 `$@NULL@$`；无实际口令。
保留原始包字节，不改写其版本、站点元数据或时间。上游许可证见 Moodle 项目的 COPYING.txt（GPL）。

## 失败记录与环境诊断

2026-11-20 UTC，本机 Docker client/server `29.9.2`，compose `v5.6.1`，daemon 正常。

```text
$ docker pull moodlehq/moodle-php-apache:8.3
Error response from daemon: unknown: failed to resolve reference "docker.io/moodlehq/moodle-php-apache:8.3": unexpected status from HEAD request to https://registry-1.docker.io/v2/moodlehq/moodle-php-apache/manifests/8.3: 429 Too Many Requests
$ docker pull moodlehq/moodle-php-apache:8.3-bookworm
Error response from daemon: unknown: failed to resolve reference "docker.io/moodlehq/moodle-php-apache:8.3-bookworm": unexpected status from HEAD request to https://registry-1.docker.io/v2/moodlehq/moodle-php-apache/manifests/8.3-bookworm: 429 Too Many Requests
$ docker pull public.ecr.aws/docker/library/postgres:16
Error response from daemon: error from registry: Data limit exceeded
```

检查了环境：Docker context 为 `default`，`docker image ls` 为空；无 `~/.docker` 配置目录，
环境变量名中无 docker/proxy/registry 项。不是工作目录虚拟环境未加载造成的命令缺失。
没有继续重试共享限额，也未请求新密钥、修改 daemon 配置或尝试绕过限额。
GitHub 固定提交源码下载成功，故从同一源码中取官方备份 fixture。

## 复现与检查

Python 3.11+，只用标准库，**无第三方 Python 依赖，故无需依赖锁文件**。
从本目录执行：

```sh
./deploy.sh                  # 仅重现镜像拉取门禁，失败记录在忽略的 .runtime/；非完整部署器
./seed                       # 明确退出 2；没有实现或冒充已执行的造数
./export                     # 下载固定提交的官方 fixture，默认输出到新临时目录
./export --output /path/to/new-empty-directory
# 只有显式指定才以 samples 为目标；即使显式指定也拒绝覆盖非空目录
./export --update-samples
# 可离线输入已下载的同一官方文件，不会覆盖输入
./export --source /path/to/subsections_with_descriptions.mbz
./teardown                   # 本次没有创建任何容器/卷/网络，不做全局清理
python3 -m unittest discover -s . -p 'test_*.py' -v
```

已提交 samples 后执行 `--update-samples` 会拒绝覆盖。建议使用默认临时目录比较 sha256；
收集时间会改变，但不会回写仓库。manifest 是取样来源清单，不是标准交换 manifest。
测试检查 SHA256、体积、版本、无用户/无文件备份、空/损坏输入拒绝、非空目录拒绝覆盖。

## 样本和场景

`samples/upstream-subsections-no-users.mbz`：8177 字节；来源 URL、收集时间、SHA256、
原备份平台版本和覆盖范围见 `samples/manifest.json`。总量远低于 20MB。

| 请求场景 | 状态 |
|---|---|
| 无用户课程备份 | 仅官方示例，非本机导出 |
| 两个开课 / 两个版本 | 未执行，不把两个 course id 自行解释为标准版本 |
| ≥3 学员 + 教师、选课和退选 | 未执行 |
| ffmpeg 合成视频及查看 | 未执行 |
| quiz 作答和评分 | 未执行 |
| assign reopen 两次提交、小组作业 | 未执行 |
| 教师评分后改分、grade_grades_history | 未执行 |
| groups / groupings / 成员 | 未执行 |
| 含用户备份及所有数据库表 JSON | 未取得 |

后续须在可拉取镜像的环境完成官方 moodle-docker 的固定提交部署、运行时版本/digest 采集、
独立场景生成器、SQL 原始导出、含/不含用户的 CLI 备份与验收；本次脚本没有这些成功路径。
