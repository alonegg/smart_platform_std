# WP2 参考校级公共服务

服务于《智慧教学-数据模型标准》的候选验证包。供 WP3 测试工具、WP5 AI 样例通过 Python 库或本地 JSON HTTP 接口调用，使用合成数据演示“授权—事件—回执—评分责任链—方法准入”。

**证据范围仅“合成样例通过”**（4.4.5.2）：不是认证、D2 冻结、真实平台数据通过、独立应用接替、真实教务归档或教学效果证据。参考服务/夹具不计作两个独立应用。

## 范围与承担边界

按附录 A.8 表 A.11 选择以下职责的本地子集；不是对条款组全部要求作出符合性声明。

| 条款组 | 本包承担 | 未承担/局限 |
|---|---|---|
| 7-A/7-C：7.2.1、7.2.8、7.6 | WP1 input/stored 信封校验，event_id/received_at/auth_context 赋值，摘要、去重/冲突隔离、乱序追加和双排序 | 不验证全部外部业务关系、xAPI/Caliper 转换或所有事件的先决条件 |
| 7-B：7.5 | 提议/人员确认/更正追加，教务接收模拟与 registrar_status 派生，组员快照 | 无正式分数/量尺字段和真实教务数值核对，无 T20 全证据复核 |
| 8-B：8.7 | 可查询回执、durability、school_received/school_registered | source_persisted 由源应用确认；无生产级故障恢复/可靠队列 |
| 8-C：8.8 | 本地事实/传输/重复/冲突/拒收对账，撤权与通知记录，确认时检查授课有效期 | 无应送集合、跨应用完整对账、外部缓存/任务撤权与到期主动推送调度 |
| 9-A：9.8.2、9.8.3 c)、9.8.5 | 应用登记和 active/suspended/revoked 目录；未登记/退出实例不能取令牌或回传 | 不核验 CapabilityRegistration 的真实批准/能力一致性，不提供公开目录/名单发放 API，不模拟全部到期状态 |
| 9-B：8.6.3—8.6.6、9.2 | 模拟 HMAC 令牌、人员委托/会话、scope、授权有效期、jti 防重放、密钥轮换 | 不是正式 OAuth2/统一身份认证，不处理真实账号/密钥托管 |
| 10-B：10.13.3、10.13.6 | 方法登记/批准及变更历史；用途、人群、后果等级、时间准入 | 无真实模型阈值、离线证明、方法停用外部传播或教学效果验证 |
| 11-A：11.5.2、11.5.3 | 实例域稳定假名及解析；跨实例/退出/撤权后拒绝 | 不实施统一假名过渡方案或学校隐私审查 |
| 11-D：11.10 审计部分 | 追加式本地日志、只读查询、哈希链与篡改检测 | 无日志外送、外部锚、审计/系统管理员分离；不承担 11.11—11.14 安全评估 |

范围的实际编号与选择规则在 [scope.json](scope.json)，逐项结果见 [追溯表.csv](追溯表.csv)。例如 **OBJ-042 是 ApplicationInstance**，OBJ-044 为 AccessGrant；不使用对象名代替编号。部分字段只做结构/引用快照校验，标记 partial；assumption 不是正式符合性。

## 安装与测试

Python 3.11+；依赖完全复用 WP1 锁定包（业务实现仅标准库，契约校验用 jsonschema 及其既有依赖）。从仓库根执行：

```sh
python3 -m pip install -r 验证/契约/requirements.txt
```

**一条测试命令**：

```sh
python3 -m unittest discover -s 验证/参考公共服务/tests -v
```

测试也可由 pytest 收集。`tools/check_trace.py` 为只读校验器，已纳入 unittest；范围内每个编号须存在于矩阵、追溯表及其指向的实际输出文件。测试临时数据库位于本包临时子目录并自动清理，不写回 fixtures/Schema/追溯表。

## 启动

```sh
python3 验证/参考公共服务/server.py --port 8700 --bootstrap
```

可增加 `--db 验证/参考公共服务/synthetic.sqlite`。默认 `:memory:`；只绑定 `127.0.0.1`。`--bootstrap` 在启动时输出本次合成管理员令牌；不带该参数不打印令牌。所有凭证仅用于隔离合成测试，禁止接入真实身份/个人数据。服务重启会重新生成管理员令牌和服务 secret；CLI 不承诺跨重启重新生成相同假名，需稳定 secret 的测试使用库构造函数注入。

## Python 库（WP3、WP5）

在 `sys.path` 中加入本目录后 `from service import Service`。构造函数支持 database、admin_token、secret、audience、clock、max_revocation_delay、manual_scopes、received_stages、confirmation_roles、identifier_policy、population_match、registrar_statuses、receiver_field_policy、hash_serializer。参数均是合成候选配置，不能绕过 WP1 校验。

每个公开业务方法的第一个实参是 bearer 字符串。返回 JSON 可序列化 dict，检查 `status`；事件拒收/冲突返回通过 WP1 receipt 校验的可查询回执，其他业务拒绝返回 `status=rejected` 和原因。所有结果均审计。每次写操作使用新签发的令牌；同一 jti 不能用于第二次写入，即使之前业务拒绝也应另取令牌。

以下最小示例从仓库根运行，原始 fixture 不改写：

```python
import json
from pathlib import Path
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "验证/参考公共服务")
from service import Service, ref

base = Path("验证/契约/fixtures/valid")
def fixture(kind, name=None):
    return json.loads((base / kind / (name or f"{kind}-minimal.json")).read_text())["instance"]

service = Service()
admin = service.admin_token  # 只用于本地合成测试的模拟管理员
app = fixture("ApplicationInstance")
assert service.register_application(admin, app)["status"] == "accepted"
grant = fixture("AccessGrant")
grant["access_mode"] = "delegated"
grant["subject_ref"] = {"object_type": "Person", "object_id": "https://example.edu/person/1"}
grant["scopes"] = ["events.write", "events.read"]
now = datetime.now(timezone.utc)
grant["valid_from"] = (now - timedelta(minutes=1)).isoformat()
grant["valid_until"] = (now + timedelta(hours=1)).isoformat()
assert service.issue_grant(admin, grant)["status"] == "accepted"
token = service.issue_token(admin, ref(grant))["token"]
event = fixture("event", "event-submission.submitted.json")
event["source_instance"] = app["object_id"]
receipt = service.accept_event(token, event)
assert receipt["status"] == "accepted"
assert service.get_receipt(token, receipt["receipt_id"]) == receipt
service.db.close()
```

WP3 应分别校验业务状态、事实数、回执阶段、授权与审计，而不是只看 HTTP。WP5 将服务凭证限制为 grade.propose/所需最小读取权限；人工确认须另用人员 delegated/user_session，不能给 client_credentials 增加 grade.confirm。`propose_grade` 可携带经 WP1 校验的 learner_ref、Submission、具体方法/来源版本引用；独立关系的候选性见 S-06。

## HTTP 调用

完整手写 [OpenAPI 3.1](openapi.yaml) 使用 WP1 Schema `$id` 外部引用，不复制其定义。运行时仍离线调用 WP1 校验器，不联网获取 `$id`。全部 29 个公开方法各映射一个 HTTP 操作；`tests/test_http.py` 检查 operationId/路由与 Service 方法集合一致。

请求头：`Authorization: Bearer <token>`，POST 使用 `Content-Type: application/json`。除 `POST /events` 的请求体直接为 input 事件外，POST 使用方法参数名组成对象（如 `{"grant": ...}`、`{"decision": ...}`），GET 用查询参数。路径 `{id}` 为百分号编码的完整标识；撤权路径 body 使用 `version_id`（默认 v1）及可选 basis。GET `/grades?instance=...&formal=false` 查询完整历史。

HTTP 200 只说明业务请求已处理，仍可能返回 rejected/conflict；格式错误用 400、未知路由用 404，并返回 JSON 拒绝体及审计。事件端点的格式错误也生成可按 receipt_id 查询的 rejected 回执。无效/无法鉴别凭证的拒收回执仅管理员可查询，防止匿名泄漏；已鉴别实例的拒收回执可由该实例查询。

最小 HTTP 链路：启动时复制合成管理员令牌到本地环境变量 `WP2_ADMIN_TOKEN`，在上面库示例相同的 app/grant/event 合成对象基础上使用：

```python
import os
from urllib.request import Request, urlopen
from urllib.parse import quote

admin = os.environ["WP2_ADMIN_TOKEN"]
def request(method, path, token, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = Request("http://127.0.0.1:8700" + path, data=data, method=method,
                  headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urlopen(req) as response:
        return json.load(response)

assert request("POST", "/applications", admin, {"application": app})["status"] == "accepted"
assert request("POST", "/grants", admin, {"grant": grant})["status"] == "accepted"
token = request("POST", "/tokens", admin, {"grant_ref": ref(grant)})["token"]
receipt = request("POST", "/events", token, event)
assert receipt["status"] == "accepted"
assert request("GET", "/receipts/" + quote(receipt["receipt_id"], safe=""), token) == receipt
```

管理员路由：applications 三个操作、grants 签发/订阅/撤销、tokens、teaching-assignments、methods 登记/批准/状态、grades/registrar-receipts、audit 查询/校验。其余按 Service 的具体 scope 校验；所有路由及参数见 OpenAPI。

## 用例 → 测试方法

表内均为 `tests/` 下的方法；以 `_positive_` 与 `_reject_` 区分正反。反向方法中的成功操作用于建立前置与验证原事实未被覆盖，既有断言保留。

| 用例 | 正向方法 | 拒绝方法 |
|---|---|---|
| T05 | `test_T05_positive_same_digest_duplicate`、`test_T05_positive_http_accept_query_receipt` | `test_T05_reject_conflict_and_repair` |
| T06 | `test_T06_positive_append_late` | `test_T06_reject_invalid_order` |
| T07（公共服务） | `test_T07_positive_receipt_stages_and_empty_reconcile` | `test_T07_reject_receipt_scope_and_reconcile` |
| T08-P | `test_T08_P_positive_proposal_not_formal` | `test_T08_P_reject_mutation_and_missing_object`、`test_T08_P_reject_invalid_group_snapshot` |
| T08-C | `test_T08_C_positive_personnel_confirmation` | `test_T08_C_reject_teacher_and_service_boundaries`、`test_T08_C_reject_http_client_credentials_confirmation` |
| T08-A | `test_T08_A_positive_exact_acceptance_archives` | `test_T08_A_reject_unconfirmed_or_wrong_receipt` |
| T08-R | `test_T08_R_positive_append_keeps_predecessor` | `test_T08_R_reject_overwrite_and_old_receipt_replay` |
| T10 | `test_T10_positive_current_approval_and_history` | `test_T10_reject_runtime_outside_approval`、`test_T10_reject_ai_output_without_approval` |
| T11 | `test_T11_positive_tokens_and_instance_pseudonyms` | `test_T11_reject_token_boundaries`、`test_T11_reject_pseudonym_isolation_exit`、`test_T11_reject_directory_and_revocation_notifications` |
| T25 | `test_T25_positive_stored_credential_trace` | `test_T25_reject_receiver_fields_and_trace`、`test_T25_reject_http_forged_fields_and_bad_json` |

另有 AccessGrant、审计篡改、文件库重开、空/错误输入与追溯脚本正反测试。拒收辅助断言检查最后一条审计；事件拒收/冲突另检查回执可查询且通过 WP1 receipt 校验。

## 与工作计划的差异、登记与局限

参见 main 上的[可执行验证体系工作计划](../工作计划-可执行验证体系.md)。计划列出的 fastapi/uvicorn 在本包按任务要求替换为 stdlib `http.server.ThreadingHTTPServer`，HTTP 客户端测试用 urllib；不新增依赖。共享 SQLite 连接由 RLock 串行化全部 Service 操作，不声称生产吞吐性能。

计划建议统一假设登记于契约包；本任务禁止修改契约，因此 [S-01—S-10](临时假设.md) 在本目录登记，对照 main 的 H-xx/WP0/WP6 条目沿用口径。新增部分仅列为“建议补登到 验证/契约/临时假设.md 的条目”，没有替维护机构冻结。五项问题按评议表单字段登记在[发现的标准问题.md](发现的标准问题.md)，区分标准待决与 WP1 契约建议。

默认内存库只保证进程内事实；文件库事务重开仅是合成持久化检查，不是断电/灾备证明。审计哈希链无外部锚，不能抵抗管理员重算或尾部截断；CLI 无 TLS/限流/安全身份体系，只供回环隔离实验。没有真实学校授权、隐私批准、模型验证或生产密钥。除所列职责子集外，不承担完整主数据、导出/恢复、知识/量尺规则、正式成绩计算、审计外送或完整安全控制。
