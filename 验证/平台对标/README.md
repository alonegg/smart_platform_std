# 智慧教学-数据模型标准：平台源码对标

详细分析见[研究报告：标准初稿可实现性与接入性评估](研究报告-标准初稿可实现性与接入性评估.md)，区分分层覆盖度、工程可实现性、接入前置及尚无实测的教学效果；全部报告统计可由 `tools/report_stats.py --check` 核验。

## 1. 目的与立场

本材料供标准专家及应用厂商检验标准三类数据——课程资源（第6章）、教学过程与学习证据（第7章）、认知诊断（第10章）——及公共与交换要素是否定义完整、可交换、可验证。目标是让第三方应用，尤其AI应用，能够只凭公开标准及其配套契约实现产生、交换和验证，而不是依赖某个平台私有约定。

平台没有的数据不构成放宽标准的理由；矩阵登记补齐责任和进入标准的路径。应区分“平台存在近似数据”“语义对应”“能交换”“通过机器核验”和“真实教学有效”，不得相互替代。

**本材料不是标准正文、不是平台认证、不是符合性声明**。按正文4.4.5，静态源码、合成结构检查及单次演示均不能作为真实平台验证、认知有效性或符合性声明的证据。本目录仅为仓库验证材料，不进入评审网站正文、全文检索及下载文稿；本次未修改站点或文稿构建配置。

## 2. 对象与版本

源码快照登记日期：**2026-11-19（UTC）**。这是本次在本机读取HEAD的日期，不是各上游提交时间，也不是部署时间。提交号来自 `git -C ~/ref/<repo> rev-parse HEAD`；同名分支后续更新不改变本次证据所指快照。

| 平台 | `~/ref/`下仓库 | 实际提交号 |
| --- | --- | --- |
| Open edX | edx-platform | `ccfe30bfdb22d56c0139958c17049840b8176519` |
| Open edX | event-routing-backends | `bae21257a259d17d54d9501af0abdd0c8e002ed8` |
| Open edX | openedx-events | `fc7b38942cc215f2c2aa34f0dd3171c7c5c47d50` |
| Open edX | xblock-lti-consumer | `eba607951f0225db5707e1846c034fe92b8cae1e` |
| Open edX | edx-submissions | `9c9e7c416a127c769b72d2c1b7141de96d20283a` |
| Moodle | moodle | `2d4bafe8548a6d6c01494c862ec3d9749ba6ea84` |

本次仅做源码静态对标，**未部署平台，未执行附录A的T用例**，未确认某插件在实际站点启用。Moodle该快照代码根在 `public/`，未发现 `ltix` 目录。Open edX所引用的外部依赖仅核查上述仓库可见的集成接口，不推定未提供的完整外部实现。标准依据为[当前正文](../../标准/评审稿/智慧教学-数据模型标准.md)，具体条款、平台对应和证据见[CSV矩阵](数据要素对照矩阵.csv)。CSV为UTF-8带BOM，便于Excel读取；未做Excel视觉检查。

## 3. 方法与复现

### 要素来源

<!-- summarize:scope:start -->
矩阵取自正文 **8 张表、166 行要素**，保留原表合并字段，不擅自拆行。

| 来源 | 数据行数 |
| --- | --- |
| 表5-1 核心对象 | 46 |
| 表6-2 Resource版本字段 | 17 |
| 表6-3 RightsRecord成员 | 9 |
| 表7-1 事件公共结构 | 23 |
| 表7-2 最小事件词表 | 24 |
| 表8-1 manifest成员 | 17 |
| 表10-1 CognitiveState字段 | 16 |
| 表10-2 方法登记与批准 | 14 |

类别按业务含义归入课程资源、教学过程与学习证据、认知诊断、公共与交换，而非仅按抽取表所在章节机械分组。
<!-- summarize:scope:end -->

### 各列含义与判定规则

| 列或列组 | 含义与规则 |
| --- | --- |
| 要素编号、数据类别、要素类型、要素名 | 稳定定位抽取行；对象、字段、事件分开。合并字段仍为原表一行，不代表各成员可互换。 |
| 标准条款、标准定义摘要 | 追溯正文与原表；摘要不替代条款原文及条件约束。 |
| OpenEdX对应、Moodle对应 | 具体模型、表字段、事件、API或转换器，并说明与标准的差异。 |
| OpenEdX状态、Moodle状态 | **原生**：模型/字段/事件存在且语义一致；**可派生**：数据已存在，需组合、计算或适配转换；**部分**：有近似物但语义不同或缺关键属性；**缺失**：在核查源码范围内不存储也不产生。不能确定时保守判部分。 |
| OpenEdX依据、Moodle依据 | Open edX路径相对于 `~/ref/`，Moodle路径相对于 `~/ref/moodle/`；必须是真实存在的相对源码文件。缺失项同样给出实际搜索位置和关键词，不将“未找到”解释为整个生态永远没有。 |
| OpenEdX覆盖度、Moodle覆盖度 | 各置于相应依据列之后。**3 原生**对应原生；**2 可适配**：核心事实和关键属性已存在，仅需转换、组合、派生或适配器补元数据，不需新增业务事实或改平台模型（可派生一律为2）；**1 弱对应**：缺关键属性、语义不一致或仅覆盖部分活动类型，需扩展或应用新增事实；**0 缺失**对应缺失。部分项逐条判1或2，不确定判1，对应列末尾以 `〔覆盖度2：理由〕` 或 `〔覆盖度1：缺…〕` 记录。 |
| 缺失时补齐方 | 两平台均原生时为**无需补齐**；否则从**平台适配器**（已有数据转换/派生）、**平台扩展开发**（改平台或插件产生新数据）、**校级公共服务**（A.3/A.8规定的权威公共职责）、**接入应用**（含AI，按Profile产生）、**学校管理**（人工登记、审定、批准）选择；多选用中文分号。多个角色是协作责任，不是任意择一即可替代。 |
| 补齐路径(标准条款) | 写明事件、接口服务组、交换包类型、能力登记、AI任务契约、认知写入等具体路径及条款；待D2事项在此标记，不降低正文业务条件。 |
| AI应用接入关系 | **AI读取输入**：限任务获准输入；**AI写入提议**：拟入正式记录者仅为待确认提议；**AI写入认知记录**：P-DIA及方法准入限制；**AI禁止写入**：括号限定的确认、发布、归档、授权或伪造等操作；**不直接涉及**：本要素没有直接AI任务关系。可多选并附条款。即时帮助等直接输出由括号说明，不能误当作认知写入或正式发布。 |
| 标准定义充分性 | **充分**：含义、取值域或受控词表来源、必填/条件及校验规则已规定；明确交D2的契约可判充分并标待D2。**需补样例**：定义清楚，但边界判定需合法/非法样例。**歧义**：有多种合理解释或条文冲突。**定义缺失**：实现所需的语义、取值域、产生方或校验未规定。平台缺失本身不是后两者的判据。 |
| 意见建议 | 充分时必须为空；其余按 `【条款号】问题：…；建议：…` 填写，可作为按条款评议的草案。 |

充分性和治理五列仅依据正文与已经填写的平台列判断。证据路径存在只验证了引用可定位，不证明功能实际运行、完整覆盖或标准符合性。校验脚本检查格式、枚举、一致性和关键权限边界，不能代替专家的实质判断。

覆盖度仅细分静态适配距离，不改原四值状态及治理结论。已有内容的确定快照、标准身份映射、Schema版本等可由适配器补元数据；已经丢失的历史、审批决定、目标关联、授权及证据作用不能补造。仅字段判为可适配，不表示其所属完整对象也可适配。覆盖度与补齐方不是一一映射：治理列还涵盖目标契约的公共登记及人工审批责任。本步仅完成细分与描述统计，分层假设的详细研究报告另行开展。

### 复现命令

以下从仓库根目录运行，仅使用Python标准库。除明确指定 `--write` 外，汇总及校验不写矩阵。

```bash
# 仅初始化时使用！会覆盖CSV，已填写后不要运行：
# python3 -B 验证/平台对标/tools/extract_elements.py

# 输出由CSV实时计算的Markdown统计片段：
python3 -B 验证/平台对标/tools/summarize.py
# CSV变更后更新README标记区；随后进行逐字一致性检查：
python3 -B 验证/平台对标/tools/summarize.py --write
python3 -B 验证/平台对标/tools/summarize.py --check

# 行数、BOM、编号、平台状态/覆盖度/真实路径、治理枚举与非目标列不变：
python3 -B 验证/平台对标/tools/validate_openedx.py
# 本目录全部单元测试（含汇总、治理及原双平台校验）：
python3 -B -m unittest discover -s 验证/平台对标/tools -p 'test_*.py' -v
```

矩阵默认校验使用 `--changed-platform 覆盖度`，依赖上述源码快照及仓库外覆盖度填写前备份 `~/backup/数据要素对照矩阵.覆盖度填写前.csv`。其他机器须提供对应文件，或用 `--ref-root`、`--baseline` 指定位置；不能随意用当前CSV充作历史基线。历史填写步骤可通过 `--changed-platform OpenEdX`、`Moodle` 或 `治理` 配合对应的历史矩阵与基线复验，保留对未添加覆盖度列的历史快照支持。汇总本身只依赖当前CSV，不依赖源码目录和外部备份。

README统计由 `summarize.py` 维护下列标记区及第5节。标记区外只写方法和计划，不手抄统计数字；`--check` 会拒绝过期、缺失或重复的统计段落。

## 4. 结果

<!-- summarize:results:start -->
### 覆盖度细分（源码静态对标，不是符合率）

均值按各行等权的0–3分算术平均计算，保留两位小数；合并字段不拆分，不按业务重要性加权。覆盖度2表示适配所需的核心事实已存在，不表示已经实现适配、获准接入或通过T用例。

| 数据类别 | 平台 | 0 缺失 | 1 弱对应 | 2 可适配 | 3 原生 | 合计 | 平均覆盖度 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 课程资源 | OpenEdX | 12 | 23 | 7 | 2 | 44 | 0.98 |
| 课程资源 | Moodle | 6 | 29 | 7 | 2 | 44 | 1.11 |
| 教学过程与学习证据 | OpenEdX | 14 | 38 | 6 | 0 | 58 | 0.86 |
| 教学过程与学习证据 | Moodle | 6 | 48 | 4 | 0 | 58 | 0.97 |
| 认知诊断 | OpenEdX | 27 | 7 | 1 | 0 | 35 | 0.26 |
| 认知诊断 | Moodle | 4 | 30 | 1 | 0 | 35 | 0.91 |
| 公共与交换 | OpenEdX | 9 | 17 | 3 | 0 | 29 | 0.79 |
| 公共与交换 | Moodle | 3 | 22 | 4 | 0 | 29 | 1.03 |
| 全部类别 | OpenEdX | 62 | 85 | 17 | 2 | 166 | 0.75 |
| 全部类别 | Moodle | 19 | 129 | 16 | 2 | 166 | 1.01 |

#### 代表要素

每个类别、平台、分值按CSV行序列举至多三个要素；不足时如实列出全部，不跨类别凑数。分值2的逐项适配理由及分值1的关键缺口见CSV对应列末尾；分值0的搜索范围见依据列。

| 数据类别 | 平台 | 覆盖度 | 代表要素 |
| --- | --- | --- | --- |
| 课程资源 | OpenEdX | 2 | `OBJ-004` Course、`OBJ-013` LearningUnit、`OBJ-014` LearningActivity |
| 课程资源 | OpenEdX | 0 | `OBJ-011` ProgramVersion、`OBJ-019` ProgramAlignment、`FLD-RES-005` Resource.contributors |
| 课程资源 | OpenEdX | 1 | `OBJ-005` CourseVersion、`OBJ-015` LearningObjective、`OBJ-016` Framework |
| 课程资源 | Moodle | 2 | `OBJ-013` LearningUnit、`OBJ-016` Framework、`OBJ-018` Competency |
| 课程资源 | Moodle | 0 | `FLD-RES-009` Resource.educational_use、`FLD-RGT-002` RightsRecord.rights_holders[]、`FLD-RGT-003` RightsRecord.rights_basis |
| 课程资源 | Moodle | 1 | `OBJ-004` Course、`OBJ-005` CourseVersion、`OBJ-011` ProgramVersion |
| 教学过程与学习证据 | OpenEdX | 2 | `FLD-EVT-002` LearningEvent.event_type、LearningEvent.event_type_version、`FLD-EVT-003` LearningEvent.event_class、`FLD-EVT-005` LearningEvent.source_instance |
| 教学过程与学习证据 | OpenEdX | 0 | `OBJ-036` ObservationRecord、`FLD-EVT-004` LearningEvent.profile_id、LearningEvent.profile_version、`FLD-EVT-007` LearningEvent.entry_mode |
| 教学过程与学习证据 | OpenEdX | 1 | `OBJ-009` TaskAttempt、`OBJ-012` LearnerGroup、`OBJ-029` LearningEvent |
| 教学过程与学习证据 | Moodle | 2 | `FLD-EVT-002` LearningEvent.event_type、LearningEvent.event_type_version、`FLD-EVT-003` LearningEvent.event_class、`FLD-EVT-005` LearningEvent.source_instance |
| 教学过程与学习证据 | Moodle | 0 | `FLD-EVT-004` LearningEvent.profile_id、LearningEvent.profile_version、`FLD-EVT-012` LearningEvent.teaching_assignment_ref、`FLD-EVT-017` LearningEvent.entry_evidence_refs |
| 教学过程与学习证据 | Moodle | 1 | `OBJ-009` TaskAttempt、`OBJ-012` LearnerGroup、`OBJ-029` LearningEvent |
| 认知诊断 | OpenEdX | 2 | `FLD-COG-002` CognitiveState.learner_ref、CognitiveState.enrollment_id（仅1项，全部列出） |
| 认知诊断 | OpenEdX | 0 | `OBJ-037` CognitiveState、`OBJ-039` LearningRecommendation、`OBJ-040` MethodRegistration |
| 认知诊断 | OpenEdX | 1 | `OBJ-028` Scale、`FLD-COG-003` CognitiveState.target_ref、`FLD-COG-007` CognitiveState.value、CognitiveState.scale_ref |
| 认知诊断 | Moodle | 2 | `OBJ-028` Scale（仅1项，全部列出） |
| 认知诊断 | Moodle | 0 | `FLD-COG-014` CognitiveState.use_purposes、CognitiveState.consequence_level、CognitiveState.access_policy_ref、`FLD-COG-015` CognitiveState.validity、`FLD-MTH-009` MethodApproval.用途级别 |
| 认知诊断 | Moodle | 1 | `OBJ-037` CognitiveState、`OBJ-039` LearningRecommendation、`OBJ-040` MethodRegistration |
| 公共与交换 | OpenEdX | 2 | `OBJ-001` Person、`FLD-MAN-005` manifest.export_task_id、`FLD-MAN-009` manifest.files |
| 公共与交换 | OpenEdX | 0 | `OBJ-008` EnrollmentRound、`OBJ-046` DataClassification、`FLD-MAN-001` manifest.package_id |
| 公共与交换 | OpenEdX | 1 | `OBJ-002` Organization、`OBJ-003` AcademicSession、`OBJ-006` Offering |
| 公共与交换 | Moodle | 2 | `OBJ-001` Person、`FLD-MAN-003` manifest.schema_version、`FLD-MAN-005` manifest.export_task_id |
| 公共与交换 | Moodle | 0 | `OBJ-008` EnrollmentRound、`FLD-MAN-004` manifest.profile_id、manifest.profile_version、`FLD-MAN-012` manifest.portability_level |
| 公共与交换 | Moodle | 1 | `OBJ-002` Organization、`OBJ-003` AcademicSession、`OBJ-006` Offering |

### 两平台状态交叉统计

行轴为Open edX，列轴为Moodle；单元格表示同一要素的状态组合。边际合计可用于读取各平台状态分布。

#### 课程资源

| Open edX ＼ Moodle | 原生 | 可派生 | 部分 | 缺失 | 合计 |
| --- | --- | --- | --- | --- | --- |
| 原生 | 2 | 0 | 0 | 0 | 2 |
| 可派生 | 0 | 1 | 0 | 0 | 1 |
| 部分 | 0 | 0 | 29 | 0 | 29 |
| 缺失 | 0 | 0 | 6 | 6 | 12 |
| 合计 | 2 | 1 | 35 | 6 | 44 |

#### 教学过程与学习证据

| Open edX ＼ Moodle | 原生 | 可派生 | 部分 | 缺失 | 合计 |
| --- | --- | --- | --- | --- | --- |
| 原生 | 0 | 0 | 0 | 0 | 0 |
| 可派生 | 0 | 1 | 1 | 0 | 2 |
| 部分 | 0 | 0 | 42 | 0 | 42 |
| 缺失 | 0 | 0 | 8 | 6 | 14 |
| 合计 | 0 | 1 | 51 | 6 | 58 |

#### 认知诊断

| Open edX ＼ Moodle | 原生 | 可派生 | 部分 | 缺失 | 合计 |
| --- | --- | --- | --- | --- | --- |
| 原生 | 0 | 0 | 0 | 0 | 0 |
| 可派生 | 0 | 0 | 0 | 0 | 0 |
| 部分 | 0 | 0 | 8 | 0 | 8 |
| 缺失 | 0 | 0 | 23 | 4 | 27 |
| 合计 | 0 | 0 | 31 | 4 | 35 |

#### 公共与交换

| Open edX ＼ Moodle | 原生 | 可派生 | 部分 | 缺失 | 合计 |
| --- | --- | --- | --- | --- | --- |
| 原生 | 0 | 0 | 0 | 0 | 0 |
| 可派生 | 0 | 2 | 0 | 0 | 2 |
| 部分 | 0 | 0 | 18 | 0 | 18 |
| 缺失 | 0 | 0 | 6 | 3 | 9 |
| 合计 | 0 | 2 | 24 | 3 | 29 |

#### 全部类别

| Open edX ＼ Moodle | 原生 | 可派生 | 部分 | 缺失 | 合计 |
| --- | --- | --- | --- | --- | --- |
| 原生 | 2 | 0 | 0 | 0 | 2 |
| 可派生 | 0 | 4 | 1 | 0 | 5 |
| 部分 | 0 | 0 | 97 | 0 | 97 |
| 缺失 | 0 | 0 | 43 | 19 | 62 |
| 合计 | 2 | 4 | 141 | 19 | 166 |

### 两平台都缺失的要素（19项）

| 编号 | 名称 |
| --- | --- |
| OBJ-008 | EnrollmentRound |
| FLD-RES-009 | Resource.educational_use |
| FLD-RGT-002 | RightsRecord.rights_holders[] |
| FLD-RGT-003 | RightsRecord.rights_basis |
| FLD-RGT-006 | RightsRecord.permitted_uses[] |
| FLD-RGT-007 | RightsRecord.third_party_components[] |
| FLD-RGT-009 | RightsRecord.review |
| FLD-EVT-004 | LearningEvent.profile_id、LearningEvent.profile_version |
| FLD-EVT-012 | LearningEvent.teaching_assignment_ref |
| FLD-EVT-017 | LearningEvent.entry_evidence_refs |
| FLD-EVT-018 | LearningEvent.attested_at |
| FLD-EVT-023 | LearningEvent.payload_hash |
| EVT-009 | attendance.recorded |
| FLD-MAN-004 | manifest.profile_id、manifest.profile_version |
| FLD-MAN-012 | manifest.portability_level |
| FLD-COG-014 | CognitiveState.use_purposes、CognitiveState.consequence_level、CognitiveState.access_policy_ref |
| FLD-COG-015 | CognitiveState.validity |
| FLD-MTH-009 | MethodApproval.用途级别 |
| FLD-MTH-010 | MethodApproval.获准使用用途 |

缺失是当前源码对标范围内的结论，不是生态内所有插件均不可能实现。应按矩阵责任和路径补齐，而不是删除标准约束。

### 补齐方统计

多选分别计数，不相加作为要素总数。

| 补齐方 | 要素行数 |
| --- | --- |
| 无需补齐 | 2 |
| 平台适配器 | 136 |
| 平台扩展开发 | 43 |
| 校级公共服务 | 106 |
| 接入应用 | 145 |
| 学校管理 | 67 |

### AI接入关系统计

多选分别计数。AI禁止写入针对括号列明的操作，与同一行允许获准提议不矛盾。

| AI关系 | 要素行数 |
| --- | --- |
| AI读取输入 | 160 |
| AI写入提议 | 58 |
| AI写入认知记录 | 30 |
| AI禁止写入 | 88 |
| 不直接涉及 | 2 |

### 标准定义充分性统计

| 数据类别 | 充分 | 需补样例 | 歧义 | 定义缺失 | 合计 |
| --- | --- | --- | --- | --- | --- |
| 课程资源 | 38 | 5 | 1 | 0 | 44 |
| 教学过程与学习证据 | 47 | 11 | 0 | 0 | 58 |
| 认知诊断 | 29 | 6 | 0 | 0 | 35 |
| 公共与交换 | 25 | 4 | 0 | 0 | 29 |
| 合计 | 139 | 26 | 1 | 0 | 166 |
<!-- summarize:results:end -->

<!-- summarize:findings:start -->
## 5. 主要发现

### a) 平台不是标准语义的基线

在166行中，Open edX原生2项、部分97项；Moodle原生2项、部分141项。应准确表述为两平台均以‘部分’为主，而非‘几乎全部’都部分。认知诊断中，Open edX缺失27项、部分8项；Moodle缺失4项、部分31项。

代表性要素为`OBJ-005` CourseVersion、`OBJ-006` Offering、`OBJ-008` EnrollmentRound、`OBJ-037` CognitiveState、`OBJ-040` MethodRegistration、`OBJ-041` MethodApproval。Open edX的course run不能直接等同课程版本与开课的分离模型；Moodle虽有能力证据、分析模型及版本，仍不等于标准认知状态和用途批准。标准必须自带对象、事件和验证定义，不能以任一平台为基线。

### b) 语义有规可循，机器契约仍是前置

166项中判‘充分’139项，其中补齐路径标注‘待D2’139项。即本矩阵的‘充分’项全部仍有D2契约交付前置。‘待D2’表示按正文交付安排仍需冻结结构/适用性契约，不表示每项都同时缺少Schema、逐事件定义、词表和夹具，也不是对D2实际发布物的独立盘点。

据此，当前AI应用‘有规可循’在语义层成立，在跨应用机器可校验层尚不成立；D2契约是接入的关键前置。如`FLD-EVT-002` LearningEvent.event_type、LearningEvent.event_type_version、`FLD-EVT-004` LearningEvent.profile_id、LearningEvent.profile_version、`FLD-EVT-020` LearningEvent.payload、`FLD-MTH-011` MethodApproval.适用范围，应按正文4.1.2、5.4、7.3.3、8.11及E12发布同版本Schema、逐事件定义、词表和正反夹具。不能用平台私有字段补写未冻结的公共契约。

### c) 校级公共职责不得下放给平台或AI自行决定

矩阵有106项列入‘校级公共服务’补齐责任；这是多选涉及行数，不是独立服务数量。代表性要素包括`FLD-EVT-001` LearningEvent.event_id、`OBJ-001` Person、`FLD-EVT-021` LearningEvent.received_at、`FLD-EVT-022` LearningEvent.auth_context、`FLD-MAN-017` manifest.export_receipt_id、`EVT-003` permission.revoked、`OBJ-041` MethodApproval。

按A.3/A.8，首次受理event_id、标识映射与成对学习者假名、学校接收/登记回执、撤权传播和方法准入权威校验由校级公共服务承担。平台及应用仍负责源事实、源端保存、适配与本地撤权；学校管理负责人工审定和批准。厂商可受托建设公共服务，但不能因此以普通平台或AI应用身份自行生成权威决定。

### d) AI接入按操作而非按对象整体放权

允许任务获准读取输入的范围涉及160项，例如`OBJ-020` Resource、`OBJ-030` ProcessArtifact、`OBJ-037` CognitiveState；不代表可读取全量数据或默认外发，仍受最小化、授权及外发网关控制。

列入‘AI写入提议’58项，例如`OBJ-023` AssessmentItem、`OBJ-024` AssessmentPlan、`OBJ-034` GradeDecision、`EVT-018` grade.proposed。拟入正式记录的输出只能是待确认提议，不能自动确认或发布。

列入‘AI写入认知记录’30项，例如`OBJ-037` CognitiveState、`OBJ-038` EvidenceLink、`OBJ-039` LearningRecommendation、`EVT-022` cognition.updated、`EVT-023` recommendation.issued，须声明P-AI与P-DIA并通过10.13的方法、版本、批准范围、用途和有效期校验；不能据此取得正式评分权限。

列入‘AI禁止写入’88项，例如`FLD-EVT-001` LearningEvent.event_id、`FLD-EVT-022` LearningEvent.auth_context、`EVT-019` grade.confirmed、`EVT-020` grade.corrected、`EVT-021` grade.archived。禁止项包括接收端专属赋值、冒充人员生成真实事实以及确认/更正/归档、发布、导出和授权操作；不否认同一对象上的提议权限。

‘不直接涉及’2项。另须避免将`OBJ-032` HelpRecord、`EVT-016` help.provided、`EVT-008` discussion.facilitated误判为一律只能提议：9.5.1 b)、9.5.6允许获准的即时帮助直接呈现，讨论引导还须满足7.3.6 b)，矩阵在括号中说明其边界。

### e) 按条款提交样例与歧义意见

需补样例26项、歧义1项、定义缺失0项。以下为全部需补样例条目；完整‘问题/建议’见CSV的意见建议列。

| 编号 | 要素名 | 评议条款 |
| --- | --- | --- |
| OBJ-005 | CourseVersion | 5.2.1、6.7.2 |
| OBJ-008 | EnrollmentRound | 5.2.2、5.2.6 |
| OBJ-012 | LearnerGroup | 5.2.5、7.1.4 a) |
| OBJ-024 | AssessmentPlan | 6.6.3 j)、6.6.4、7.5.9 |
| OBJ-025 | AssessmentAdjustment | 6.6.10、7.5.8 |
| OBJ-034 | GradeDecision | 7.5.2、7.5.7 |
| OBJ-035 | PeerReview | 7.1.4 b)、7.3.2 |
| OBJ-038 | EvidenceLink | 10.2.1 a)、10.6.5 |
| FLD-RES-005 | Resource.contributors | 6.2.6 |
| FLD-RGT-007 | RightsRecord.third_party_components[] | 6.3.4、6.4.4、8.3.2 |
| FLD-EVT-007 | LearningEvent.entry_mode | 7.2.12 |
| FLD-EVT-008 | LearningEvent.scope_type、LearningEvent.scope_refs | 7.2.2、7.3.4 f) |
| FLD-EVT-014 | LearningEvent.group_ref、LearningEvent.member_refs | 7.1.4 a)、7.2.3 |
| EVT-013 | submission.submitted | 7.3.4 b)、8.7.3 |
| EVT-014 | submission.withdrawn | 7.3.4 i)、7.5.9 |
| EVT-017 | feedback.published | 7.3.4 g)、9.5.1 |
| EVT-019 | grade.confirmed | 7.3.4 d)、9.2.4 |
| FLD-MAN-008 | manifest.objects | 8.2.4 b)、8.2.5 |
| FLD-MAN-013 | manifest.content_inclusions | 8.2.9、8.3.2 |
| FLD-MAN-017 | manifest.export_receipt_id | 8.2.8 |
| FLD-COG-006 | CognitiveState.estimate_status | 10.6.5 |
| FLD-COG-010 | CognitiveState.method_ref | 10.3.3、10.8.4 |
| FLD-COG-012 | CognitiveState.evidence_window、CognitiveState.as_of、CognitiveState.valid_until | 10.3.1、10.13.6 e) |
| FLD-COG-013 | CognitiveState.review、CognitiveState.supersedes | 10.3.2、10.11.4 |
| FLD-MTH-011 | MethodApproval.适用范围 | 10.8.3、10.13.3 |
| FLD-MTH-012 | MethodApproval.批准状态 | 10.8.2、10.13.6 |

**`OBJ-021` Segment（歧义）**

【6.4.1、6.4.2】问题：6.4.1对Segment统一要求start_ms、end_ms及源时长约束，而6.4.2同时允许课件页码、文本段落和图像区域等非时间定位。实现者可合理地将时间成员理解为所有Segment必填，也可理解为仅时间定位条件必填，导致非时间片段的交换与校验结果不一致；建议：按定位类型明确条件字段，规定仅音视频时间定位适用start_ms、end_ms及源时长不等式，页码、段落和图像区域分别使用其定位成员，禁止用虚构时间值满足必填，并在D2提供各类型合法及非法样例。

拟通过站内意见表单按对应条款提交上述评议；本次只整理材料，尚未提交意见，也未修改标准正文。不得为适配平台而放宽标准。
<!-- summarize:findings:end -->

## 6. 下一步：动态验证计划（尚未执行）

部署和测试须在学校批准的隔离环境内使用合成数据，固定版本、镜像摘要、依赖、配置及帮助策略。以下为首批增量验证，不是任何Profile的完整验收；完整适用范围按附录A表A.9登记，不适用项必须附理由。

| 阶段 | 工作与边界 | 计划产出 |
| --- | --- | --- |
| 契约与夹具冻结 | 以D2为前置，冻结字段字典、Schema、逐事件定义、词表、适用性、交换包及合法/非法夹具；学校确定Profile、用途、范围、撤权时限与责任主体。未冻结部分标记阻塞，不能私定契约后声称通过标准。 | 可版本化契约包、适用矩阵、预期结果、待决清单及验证入口。 |
| 部署参考环境 | 用Tutor部署Open edX、Docker部署Moodle，选择与源码对标可对应的可运行版本；如需更换源码版本，先刷新对应证据与矩阵。建立课程、版本、开课、修读、任务、量规和合成账号。 | 版本/镜像清单、可复现部署说明、最小课程与账号夹具、权限配置及差异记录。 |
| 最小校级公共服务 | 实现事件接收及首次受理event_id、标识映射/按实例假名、源端与学校分阶段回执及durability、对账与撤权传播；保留认证上下文、去重/冲突与本地缓存失效观察点。方法准入未实现时不得启用认知写入。 | 公共服务接口、事件/映射/回执/撤权日志、持久化与故障观察工具、责任边界说明。 |
| 平台适配与首批执行 | 实现两平台→标准事件/交换包适配器，并提供另一平台读取/导入路径。按A.9及表12-1首批执行T01（标识与版本）、T02（课程包）、T05（重试/冲突/跨协议）、T07（提交故障）、T08（按实际阶段分提议/确认/归档/更正）、T11（越权撤权与假名）、T14（第二应用接替）。 | 输入事件序列、转换代码/损失报告、交换包及回执、每用例精确预期与实际结果、失败复现材料。 |
| 第二应用接替 | 在校级公共服务正常的前提下使原平台不可用，由另一个独立应用读取声明范围内历史资产、布置新任务、产生新提交并回传；按12.10记录缺失、有损与恢复耗时。参考公共服务不计为第二独立应用。 | 双应用交叉验证记录、接替证据包、范围/未覆盖项及修复责任，不外推为任意平台可完全迁移。 |
| AI评分提议样例 | 一个声明P-AI并叠加P-GRD的AI应用，通过9.4任务契约读取指定版本的量规、作品和方案，生成grade.proposed。执行T08-P：服务身份确认被拒、提议不进入正式成绩；如承担LTI AGS，回传分数也只能登记为提议。执行T23：直接/间接提示注入、越权工具、泄露诱导与超量调用，验证不能调用确认、发布、导出或授权接口。 | 任务/模型/提示策略版本、输入输出与Schema检查、提议/拒收回执、对抗测试和限流日志；与教师确认链分开留证。 |

AI样例不输出认知判断，不据此宣称P-DIA已验证。未来扩展认知记录时须先建立MethodRegistration、有效MethodApproval及运行时准入，并补齐A.9对P-DIA的适用用例。模型、提示策略或契约变更后应复测。每阶段均按4.4.5区分静态、合成、动态执行证据及尚未覆盖的业务，不将计划写为既成结果。
