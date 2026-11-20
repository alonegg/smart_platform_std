# WP1 候选契约包

## 目的与证据范围

服务于《智慧教学-数据模型标准》的首批可机器校验、可复现候选契约，供WP2公共服务、WP3测试工具、WP4适配器和WP5 AI应用引用。仅使用合成数据；所有标识、姓名、许可、授权、摘要和服务实例示例均不代表真实数据。

**证据范围只有“合成样例通过”。** 不构成D2冻结、认证、真实平台数据通过、互操作试点通过或教学效果证据。标准正文、平台对标矩阵与网站均未修改。未冻结的成员、结构和候选子集登记在[临时假设](临时假设.md)，待负责人评议的问题见[发现的标准问题](发现的标准问题.md)。

## 范围与目录

- 正文表5-1的46类对象词表（不是DESIGN中的旧计数）；表7-2的24个事件词表、逐事件定义及正反例。
- 首批27个对象Schema：Person、Organization、AcademicSession、Course、CourseVersion、Offering、Enrollment、EnrollmentRound、TeachingAssignment、ApplicationInstance、AccessGrant、Resource、Segment、RightsRecord、LearningActivity、AssessmentPlan、AssessmentAdjustment、TaskAttempt、Submission、ProcessArtifact、GradeDecision、Feedback、PeerReview、CognitiveState、EvidenceLink、MethodRegistration、MethodApproval。
- LearningEvent由公共信封及24份逐事件定义承载，不另造独立业务对象；计划所称GradeProposal以GradeDecision的proposed表达。
- input/stored/exchange三阶段信封；manifest、业务receipt、独立交付的export-receipt；公共词表、SHA-256摘要候选向量。
- `scope.json`列首批目标与148个要素编号；`追溯表.csv`逐项登记矩阵全部166个编号，其中18项依赖对象为out_of_scope且逐项说明理由，不用范围外状态规避首批覆盖。
- `tools/validate.py`做离线结构与本地语义校验；`tools/check_trace.py`只读检查范围、追溯、文件及条款/要素注释；`tests/`自动发现fixture并检验覆盖和复现。

追溯列为element_id、条款、输出文件（仓库根相对路径，以分号分隔）、状态、理由。状态covered表示条文明示约束已有对应候选产出；assumption表示还受H条目的线格式/子集选择约束；out_of_scope仅用于未实现的依赖对象。以上状态均不是正式符合性结论。

## 运行

Python 3.11+；先安装锁定依赖：`python3 -m pip install -r 验证/契约/requirements.txt`。

从仓库根用一条命令运行全部测试：

```sh
python3 -m pytest 验证/契约 -q
```

其他入口：

```sh
python3 验证/契约/tools/check_trace.py
python3 验证/契约/tools/validate.py 验证/契约/fixtures/valid/event/event-submission.submitted.json
python3 验证/契约/tools/validate.py 验证/契约/fixtures/invalid/event/event-T25-client-auth-context.json
python3 验证/契约/tools/validate.py 验证/契约/fixtures/valid/Resource/Resource-minimal.json --related 验证/契约/fixtures/valid/RightsRecord/RightsRecord-minimal.json
```

CLI接受普通instance或fixture包装；普通事件默认input，可用`--stage stored|exchange`及`--target <对象名|event|manifest|receipt|export-receipt|引用定义名>`。Fixture的stage用于复现其声明阶段。普通manifest以package_id/package_type识别；回执以receipt_id识别，含manifest_sha256者为export-receipt。所有Schema通过本地referencing.Registry解析，不联网。

Resource可用重复`--related <RightsRecord文件>`或fixture顶层`related_instances`数组同时提供权利档案。仅同object_id、同version_id的档案参与contributors/license投影比较；否则rights-projection明确skipped。关联档案本身须通过结构和本地语义校验，不会反向覆盖档案。

## 供其他工作包引用的约定

### 版本与稳定名称

- JSON Schema为Draft 2020-12。
- `$id`基址固定为`https://example.edu/smart-teaching/contracts/0.1.0-candidate/`，加契约目录内相对路径，如`schema/common.schema.json`。
- 包版本及`schema_version`为`0.1.0-candidate`（H-06）；Profile使用profile_id/profile_version成对声明，不能与内容version_id混为一项。
- 本候选版本承诺保留以下`$defs`名称及既有引用语义；新增定义不改写旧定义，破坏性变更须另发候选版本并明确迁移，不代表标准已冻结：

```text
Identifier VersionId ObjectType Timestamp Sha256 ByteLength ProfileDecl
LifecycleStatus ReviewStatus IndependentRef EmbeddedRef RecordRef
NonVersionedRef ObjectRef MissingReasons AuthContext ExternalId Extensions
IndependentBase RecordBase NonVersionedBase EmbeddedBase EmbeddedInRecordRef
```

### 四类引用与记录owner例外

ObjectRef必含object_type，根据词表中的版本化分类判别：

| 分类 | 定义 | 版本规则 |
|---|---|---|
| 独立版本化 | IndependentRef | object_id及具体version_id必填 |
| 随所属版本固定 | EmbeddedRef | object_id及指向独立版本的owner_ref必填，自身不带version_id |
| 不可变记录 | RecordRef | object_id必填；version_id可省略，出现时必须等于object_id |
| 非版本化 | NonVersionedRef | object_id必填，禁止version_id |
| EvidenceLink记录owner例外（H-20） | EmbeddedInRecordRef | owner_ref为RecordRef，owner的object_type必须出现且是不可变记录；自身不造版本 |

五种示例：

```json
{"object_type":"Resource","object_id":"https://example.edu/resource/1","version_id":"v1"}
```
```json
{"object_type":"Segment","object_id":"segment-1","owner_ref":{"object_type":"Resource","object_id":"https://example.edu/resource/1","version_id":"v1"}}
```
```json
{"object_type":"Submission","object_id":"https://example.edu/submission/1","version_id":"https://example.edu/submission/1"}
```
```json
{"object_type":"Person","object_id":"https://example.edu/person/1"}
```
```json
{"object_type":"EvidenceLink","object_id":"link-1","owner_ref":{"object_type":"CognitiveState","object_id":"https://example.edu/cognitivestate/1"}}
```

EmbeddedInRecordRef只扩展EvidenceLink的记录所属引用；原EmbeddedRef仍只接受独立版本owner。5.1.3(a)的正文边界问题尚待裁定。

VersionId拒收latest/current/head三个字面别名（H-02），不声称能识别全部学校别名，也不按版本字面排序。通用引用不注册as_of，出现即拒收（H-15）；CognitiveState.as_of是表10-1明示的独立字段，不属于引用成员。

单目标字段可按定义省略object_type；多目标ObjectRef必须携带。例如在objects目录内：

```json
{"allOf":[{"$ref":"../common.schema.json#/$defs/NonVersionedRef"}],"properties":{"object_type":{"const":"Person"}},"x-target-types":["Person"]}
```

### 阶段、规则与输出

input拒收客户端event_id/received_at/auth_context；stored要求三字段及payload_hash；exchange要求事件ID、接收时间和摘要，认证上下文可选。grade.confirmed不能由AI产生，也不能采用仅client_credentials；grade.corrected仅staff，grade.archived仅system。AI允许产生的帮助、讨论或认知事件仍受其逐事件定义与能力/方法用途授权约束，不得因此调用确认、正式发布、导出或授权接口。

规则ID采用H-14的`R-域-三位数字`，如R-REF-001；Schema注释使用x-rule-id/x-clause/x-elements，候选选择带x-assumption。错误取最近规则标识，未标注回退SCHEMA-keyword；hint优先采用报错Schema位置及最近祖先的x-hint，reason保留jsonschema原文。WP2是尚未执行的权威核验标识，不是标准规则编号。

输出格式：

```json
{"result":"failed","checks":[{"check":"structure","result":"failed","errors":[{"rule_id":"R-STAGE-001","pointer":"/auth_context","reason":"…","hint":"…"}]}]}
```

总体result为passed/failed；单项检查可passed/failed/skipped。CLI成功退出0，失败退出1。跳过不等于该项通过。输出不含运行时间戳；测试确保重跑前后git status及契约文件字节不变。

## 局限与未执行核验

- 字段只取正文概念的最低候选子集；Organization、AcademicSession仅公共字段，不发明名称和学期日期。其他依赖类型只有引用类别，不表示实现了其完整Schema。
- 引用结构和目标类型本地校验；存在性、权限、实际修读/授课/调整关系、证据资格、撤回时限、当前方法准入、量尺值域及验证覆盖需WP2权威服务，明确skipped。24个逐事件定义均已提供，不再把缺定义当作skipped成功。
- Resource文件类以H-19必填file_based布尔标记判别；学校许可采用H-18的SPDX单标识或school:学校域:注册代码。学校代码实际注册、国家分类适用条件、BCP47/IANA登记、存储控制、上游署名与许可兼容不能凭静态字符串证明。
- CognitiveState未知/证据不足时value须显式null且有/value缺失原因；有效性及使用限制是派生状态，不写回原记录。AccessGrant撤销/过期状态同理。
- Segment只有提供source_duration_ms才检查源时长，缺少时skipped。
- manifest和导出回执仅检查声明的结构及本地一致性；没有实施归档生成/解包、实际字节摘要核验、百分号路径全规则、确定性压缩、全对象引用闭包、包类型内容权限、独立恢复、签名、学校受控回执登记或真实平台往返。这些不得据空合成清单宣布通过。
- 业务receipt只验证阶段/持久化边界的声明一致性，不实现可靠队列、状态机、权限或重试服务。
- H-11摘要实现可通过payload_hash的serializer参数替换；向量仅针对当前候选规范化，不是认证、签名、原始数值词法保留或跨语言正式符合性证据。
- 未执行真实平台接入、AI实际调用、真实试点、教学效果评估或正式T用例全套验收；这些属于后续工作包。无公开部署。
