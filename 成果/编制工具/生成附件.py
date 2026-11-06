"""Generate reviewable companion data and a synthetic reference example."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger(__name__)


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def extract_table(text: str, start: str, end: str) -> list[list[str]]:
    section = text.split(start, 1)[1].split(end, 1)[0]
    rows = []
    for line in section.splitlines():
        if line.startswith("|") and not re.match(r"^\|[\s:|-]+$", line):
            rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def diagram() -> None:
    path = ROOT / "图件" / "三层架构.png"
    path.parent.mkdir(exist_ok=True)
    im = Image.new("RGB", (1800, 1360), "#f7f9fc")
    draw = ImageDraw.Draw(im)
    font_path = "/System/Library/Fonts/STHeiti Light.ttc"
    bold_path = "/System/Library/Fonts/STHeiti Medium.ttc"

    def text(x: int, y: int, s: str, size: int = 35, color: str = "#24344d", bold: bool = False) -> None:
        font = ImageFont.truetype(bold_path if bold else font_path, size)
        draw.text((x, y), s, font=font, fill=color)

    def box(rect: tuple[int, int, int, int], fill: str, outline: str = "#d9e1ed") -> None:
        draw.rounded_rectangle(rect, radius=20, fill=fill, outline=outline, width=2)

    text(65, 42, "未来智慧教学平台 · 三层架构", 54, bold=True)
    text(65, 112, "课程与学习证据持续积累，应用按统一标准读写", 31, "#5c6d82")
    box((60, 180, 1740, 390), "#e6eefb")
    text(95, 207, "第三层  应用层", 42, "#244f87", True)
    text(95, 272, "备课与建课    课堂教学    自主学习    测评反馈    AI 学伴    教学改进", 36)
    text(95, 330, "可替换处理服务：ASR / OCR、分段、翻译、出题、认知分析", 32)
    text(210, 421, "↑ 授权读取资源、证据与状态", 32, "#244f87")
    text(960, 421, "↓ 回传产物、过程与评价", 32, "#244f87")
    box((60, 480, 1740, 940), "#e9f4f1", "#b9d8cc")
    text(95, 510, "第二层  数据资产层", 42, "#246653", True)
    cards = [(95, 580, 610, 790), (643, 580, 1158, 790), (1191, 580, 1706, 790)]
    labels = [
        ("课程资源", "大纲 · 目标 · 课件 · 题目", "视频片段 · 知识 / 能力框架"),
        ("教学过程资源与数据", "事件 · 作答 · 作品 · 帮助", "反馈 · 评分确认 · 过程证据"),
        ("学生认知状态", "理解 · 技能 · 误解 · 建议", "证据 · 方法 · 不确定性"),
    ]
    for rect, lines in zip(cards, labels):
        box(rect, "#ffffff", "#c8dfd6")
        text(rect[0] + 22, 606, lines[0], 34, "#246653", True)
        text(rect[0] + 22, 667, lines[1], 28)
        text(rect[0] + 22, 719, lines[2], 27)
    text(95, 821, "共同能力：统一标识与版本 · 对象关系 · 交换接口 · 权限与生命周期", 34)
    text(95, 880, "S0 总则｜S1 资源｜S2 过程｜S3 交换｜S4 接入｜S5 认知｜S6 安全｜S7 验证", 29)
    text(230, 974, "↑ 素材、存储引用、运行状态", 32, "#776038")
    text(1000, 974, "↓ 计算、存储与保护策略", 32, "#776038")
    box((60, 1035, 1740, 1220), "#f3eee3", "#e0d4bc")
    text(95, 1062, "第一层  基础设施层", 42, "#776038", True)
    text(95, 1133, "智慧教室与采集    校园网络    CPU / GPU    运行环境    存储    备份与恢复", 35)
    text(65, 1252, "外部权威系统：身份、机构、课程目录、学期与选退课；安全和治理贯穿三层。", 29)
    text(65, 1300, "研究设计稿 v0.1  ·  2026-10-23", 25, "#657589")
    im.save(path)


def dictionary() -> None:
    # Each row specifies a field, not a production schema or an implemented API.
    rows: list[list[str]] = []

    def add(obj: str, clause: str, spec: str) -> None:
        for line in spec.strip().splitlines():
            field, kind, required, meaning, rule = line.split("|", 4)
            rows.append([obj, field, kind, required, meaning, rule, clause])

    add("CommonObject", "S0-01—S0-06", """
object_id|string|必填|稳定对象标识|不按名称合并；不得重复
object_type|string|必填|对象类型|注册词表
version_id|string|必填|对象内容版本|被引用的发布版本不可静默覆盖
schema_version|string|必填|结构版本|与内容版本分开
source_system|string|必填|产生记录的系统|登记的来源身份
source_id|string|必填|来源系统标识|与来源系统组合唯一
created_at|date-time|必填|创建时间|RFC3339 带时区
created_by|string|必填|创建主体|按服务身份或人员权限核验
rights_ref|string|必填|内容权利引用|可解析权利档案
access_policy_ref|string|必填|访问策略引用|对象范围和用途明确
classification_ref|string|必填|分类分级记录引用|不得以资产域代替安全等级
lifecycle_status|enum|必填|生命周期状态|draft/published/withdrawn/archived
review_status|enum|必填|审核状态|pending/approved/not_applicable
supersedes|object_ref/null|条件|被修订对象版本|新对象可为空；更正需关联
"""
    )
    add("ResourceVersion", "S1-02—S1-03", """
title|string|必填|资源名称|显示名称不充当标识
resource_type|string|必填|资源类型|对齐校内词表及分类代码
language|string|必填|内容语言|语言代码
representation_kind|enum|必填|内容表示形式|editable_source/reading_copy/runtime_package/media_derivative
media_type|string|必填|文件媒体类型|与实际字节匹配
byte_length|integer|文件必填|文件字节长度|非负整数
content_hash|string|文件必填|SHA-256|64 位十六进制；只证明字节一致
storage_ref|string|文件必填|受控存储引用|临时 URL 不作唯一长期引用
target_refs|array<object_ref>|适用时|目标或知识点|引用目标版本
derived_from|array<object_ref>|派生时|来源资源|不可只指向 latest
"""
    )
    add("TeachingEvent", "S2-02—S2-06", """
event_id|string|必填|校内事件标识|唯一
schema_version|string|必填|事件结构版本|校内信封非 xAPI 原始 Statement
profile_version|string|必填|事件语义版本|与词表一起冻结
source_system|string|必填|事件来源|服务端鉴别
source_event_id|string|必填|源事件标识|与 source_system 组成幂等键
actor_ref|string|必填|事件行为主体|去标识引用；角色不自报授权
offering_id|string|必填|开课场景|课程发布等非开课事件在对应 Profile 另定
enrollment_id|string/null|学习者事件必填|修读关联|不得跨修读混合
action|string|必填|校内动作词表|映射到标准 verb 时保留语义
object_ref|object_ref|必填|事件对象|object_id 与 version_id
occurred_at|date-time|必填|源端发生时间|带时区
received_at|date-time|接收后必填|接收时间|接收端生成
context|object|必填|场景与帮助条件|按活动 Profile
payload_hash|string|必填|源业务载荷 hash|不含 received_at；相同键不同 hash 为冲突
artifact_refs|array<object_ref>|作品事件必填|过程作品|按授权可解析
"""
    )
    add("Submission", "S2-01、S2-05", """
attempt_id|string|必填|任务尝试|与修读和任务关联
enrollment_id|string|必填|修读标识|不得只存学生编号
activity_ref|object_ref|必填|任务及版本|锁定当时内容与规则
artifact_refs|array<object_ref>|必填|作答作品|正式提交至少一个有效作品
submission_status|enum|必填|提交状态|draft/submitted/withdrawn/corrected
receipt_id|string|提交后必填|持久化回执|说明可靠保存边界
help_refs|array<object_ref>|必填|帮助记录|已知无帮助用空数组；缺失另说明
"""
    )
    add("CognitiveState", "S5-03—S5-12", """
state_id|string|必填|认知记录标识|与 object_id 对应
version_id|string|必填|认知版本|追加修订
learner_ref|string|必填|学习者引用|受控去标识标识
enrollment_id|string|必填|修读范围|跨课聚合需显式规则
target_ref|object_ref|必填|学习目标或能力|包括版本及可选 CASE 映射
dimension|enum|必填|评价维度|conceptual_understanding/procedural_skill/transfer/misconception 等
origin_type|enum|必填|状态来源|observation/model_inference/teacher_judgment/self_report
status|enum|必填|证据和有效状态|unknown/insufficient_evidence/estimated/reviewed/stale/invalidated
value|number/string/null|条件|状态值|未知或证据不足必须为空
scale_ref|object_ref/null|有值必填|量尺|不可混同正确率和概率
uncertainty|object|必填|不确定性|无可靠估计使用 not_estimated
evidence_refs|array<object>|必填|证据与作用|估计或复核必须有依据；unknown 可空
method_ref|object_ref/null|实际推断或判断有值时必填|方法版本|算法、规则或人工规程
context|object|必填|任务条件|帮助、独立性及相关限制
evidence_window|object|必填|证据覆盖时间|start/end 带时区
as_of|date-time|必填|状态形成时间|不等于证据发生时间
valid_until|date-time|必填|需重新确认时间|到期标记 stale
review|object/null|复核时必填|人工复核记录|主体、时间、意见
supersedes|object_ref/null|更正时必填|前一状态|保留历史关系
purpose|string|必填|允许用途|不自动用于正式成绩或资格决定
access_policy_ref|string|必填|访问策略|本人及获授权教师等
"""
    )
    add("LearningRecommendation", "S5-10", """
learner_ref|string|必填|建议接收者|授权范围内
target_ref|object_ref|必填|学习目标|可解析目标版本
state_ref|object_ref|必填|依据状态|保留形成建议时版本
action_type|string|必填|学习行动|复习/解释/练习/指导等
activity_ref|object_ref|必填|建议活动|任务可运行或人工可执行
rationale|string|必填|可理解的理由|说明证据和局限
expires_at|date-time|必填|建议有效期|过期重审
feedback_ref|object_ref/null|反馈后|学生或教师反馈|不把接受建议当作有效学习
"""
    )
    save_csv(ROOT / "附件" / "核心字段字典.csv", ["对象", "字段", "类型", "必填性", "含义", "约束与空值语义", "对应条款"], rows)


def samples() -> None:
    sample_root = ROOT / "样例"
    sample_root.mkdir(exist_ok=True)
    pack = sample_root / "教学复用包"
    (pack / "assets").mkdir(parents=True, exist_ok=True)
    (pack / "objects").mkdir(exist_ok=True)
    (pack / "relations").mkdir(exist_ok=True)
    (pack / "rights").mkdir(exist_ok=True)
    (pack / "assets" / "讲义.md").write_text("# 合成教学材料\n\n边际变化与平均变化是不同概念。本文件仅用于验证资源引用和字节校验，不构成真实课程。\n", encoding="utf-8")

    def obj(identifier: str, typ: str, fields: dict[str, Any]) -> dict[str, Any]:
        return {"object_id": identifier, "object_type": typ, "version_id": "v1", "schema_version": "0.1.0", "source_system": "synthetic-author", "source_id": identifier, "created_at": "2026-10-23T09:00:00+08:00", "created_by": "synthetic-author", "rights_ref": "rights-demo", "access_policy_ref": "policy-teaching", "classification_ref": "classification-demo", "lifecycle_status": "published", "review_status": "not_applicable", "supersedes": None, **fields}

    def ref(identifier: str) -> dict[str, str]:
        return {"object_id": identifier, "version_id": "v1"}

    handout = pack / "assets" / "讲义.md"
    resource = obj("resource-demo", "ResourceVersion", {"title": "边际与平均量说明", "resource_type": "handout", "language": "zh-CN", "representation_kind": "editable_source", "media_type": "text/markdown", "byte_length": handout.stat().st_size, "content_hash": hashlib.sha256(handout.read_bytes()).hexdigest(), "storage_ref": "assets/讲义.md", "target_refs": [ref("target-demo")], "derived_from": []})
    target = obj("target-demo", "LearningObjective", {"title": "能够解释边际量与平均量的区别"})
    activity = obj("activity-demo", "ActivityVersion", {"title": "解释任务", "prompt": "用自己的语言解释两种量的差异，并给出例子。", "target_refs": [ref("target-demo")], "resource_refs": [ref("resource-demo")], "ai_help_policy": "hints_allowed_and_recorded"})
    course = obj("course-demo", "CourseVersion", {"title": "合成课程", "unit_refs": [ref("unit-demo")], "target_refs": [ref("target-demo")], "scope_note": "仅演示一个单元，非真实完整学分课程"})
    unit = obj("unit-demo", "LearningUnit", {"title": "概念区分", "activity_refs": [ref("activity-demo")], "resource_refs": [ref("resource-demo")]})
    objects = [course, unit, target, resource, activity]
    for item in objects:
        save_json(pack / "objects" / (item["object_id"] + ".json"), item)
    save_json(pack / "relations" / "relations.json", [{"from": ref("activity-demo"), "type": "assesses", "to": ref("target-demo"), "review_status": "not_applicable", "synthetic": True}])
    save_json(pack / "rights" / "rights.json", {"rights_id": "rights-demo", "classification_id": "classification-demo", "policy_id": "policy-teaching", "synthetic": True, "rights_statement": "本样例为合成说明材料；不包含真实学生记录。", "allowed_use": ["review", "local_validation"]})
    manifest_files = [{"path": str(p.relative_to(pack)), "byte_length": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(pack.rglob("*")) if p.is_file() and p.name != "manifest.json"]
    manifest = {"package_id": "synthetic-teaching-demo", "schema_version": "0.1.0", "profile": "teaching", "profile_version": "0.1.0", "synthetic": True, "export_scope": "one_synthetic_unit", "exported_at": "2026-10-23T09:00:00+08:00", "portability_level": "content_available", "objects": [ref(x["object_id"]) for x in objects], "files": manifest_files, "dependencies": [], "mapping_losses": [], "note": "学校说明性包，不是 Common Cartridge 包；未做独立应用运行认证。"}
    save_json(pack / "manifest.json", manifest)

    evidence = obj("evidence-demo", "ProcessArtifact", {"access_policy_ref": "policy-private", "content": "合成作答：将平均量的变动直接解释为边际量。", "learner_ref": "learner-synthetic-001", "enrollment_id": "enrollment-demo", "activity_ref": ref("activity-demo"), "help_level": "hint", "synthetic": True})
    method = obj("method-demo", "AssessmentMethod", {"title": "人工示例判断规程", "limitations": "仅展示字段；没有测量校准与效果验证。"})
    scale = obj("scale-demo", "AssessmentScale", {"values": ["needs_clarification", "can_explain", "can_transfer"], "note": "说明性量尺；非经验证的跨课程能力等级。"})
    state = obj("state-demo", "CognitiveState", {"access_policy_ref": "policy-private", "state_id": "state-demo", "learner_ref": "learner-synthetic-001", "enrollment_id": "enrollment-demo", "target_ref": ref("target-demo"), "dimension": "conceptual_understanding", "origin_type": "teacher_judgment", "status": "reviewed", "value": "needs_clarification", "scale_ref": ref("scale-demo"), "uncertainty": {"type": "not_estimated", "explanation": "无统计概率估计；单次提示条件下的作答不能代表稳定掌握。"}, "evidence_refs": [{"object_ref": ref("evidence-demo"), "role": "supports", "note": "仅支持安排进一步解释任务"}], "method_ref": ref("method-demo"), "context": {"help_level": "hint", "independent_performance": False, "synthetic": True}, "evidence_window": {"start": "2026-10-23T09:00:00+08:00", "end": "2026-10-23T09:20:00+08:00"}, "as_of": "2026-10-23T09:21:00+08:00", "valid_until": "2026-10-30T09:21:00+08:00", "review": {"reviewer_ref": "teacher-synthetic", "reviewed_at": "2026-10-23T09:21:00+08:00", "synthetic": True}, "purpose": "learning_support"})
    unknown = {**state, "object_id": "state-unknown", "source_id": "state-unknown", "state_id": "state-unknown", "status": "insufficient_evidence", "value": None, "scale_ref": None, "evidence_refs": [], "method_ref": None, "review": None, "origin_type": "model_inference"}
    event_core = {"event_id": "event-demo", "schema_version": "0.1.0", "profile_version": "0.1.0", "source_system": "synthetic-app", "source_event_id": "source-event-demo", "actor_ref": "learner-synthetic-001", "offering_id": "offering-demo", "enrollment_id": "enrollment-demo", "action": "submission.submitted", "object_ref": ref("submission-demo"), "occurred_at": "2026-10-23T09:20:00+08:00", "context": {"synthetic": True}, "artifact_refs": [ref("evidence-demo")]}
    event = {**event_core, "received_at": "2026-10-23T09:20:01+08:00", "payload_hash": hashlib.sha256(json.dumps(event_core, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()}
    submission = obj("submission-demo", "Submission", {"access_policy_ref": "policy-private", "attempt_id": "attempt-demo", "enrollment_id": "enrollment-demo", "activity_ref": ref("activity-demo"), "artifact_refs": [ref("evidence-demo")], "submission_status": "submitted", "receipt_id": "receipt-synthetic", "help_refs": [ref("help-demo")]})
    helper = obj("help-demo", "HelpRecord", {"access_policy_ref": "policy-private", "help_level": "hint", "text": "请先分别给出两个概念的定义。", "synthetic": True})
    recommendation = obj("recommendation-demo", "LearningRecommendation", {"access_policy_ref": "policy-private", "learner_ref": "learner-synthetic-001", "target_ref": ref("target-demo"), "state_ref": ref("state-demo"), "action_type": "explain", "activity_ref": ref("activity-demo"), "rationale": "再次独立解释，补足现有单次提示作答的证据。", "expires_at": "2026-10-30T09:21:00+08:00", "feedback_ref": None})
    save_json(sample_root / "三类数据关联示例.json", {"synthetic": True, "status": "illustrative_not_production_schema", "authority_context": {"offering_id": "offering-demo", "enrollment_id": "enrollment-demo", "learner_ref": "learner-synthetic-001", "access_policies": ["policy-teaching", "policy-private"]}, "objects": objects + [evidence, helper, submission, method, scale, state, unknown, recommendation], "events": [event], "notice": "合成记录，非真实评分、认知模型或教学效果证据。"})


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    research = (ROOT / "03_标准研究与采用说明.md").read_text(encoding="utf-8")
    for title, start, end in [
        ("国际标准采用矩阵.csv", "## 三、", "## 四、"),
        ("国内标准采用矩阵.csv", "## 五、", "## 六、"),
        ("官方来源索引.csv", "## 七、", "## 八、"),
    ]:
        rows = extract_table(research, start, end)
        save_csv(ROOT / "附件" / title, rows[0], rows[1:])
    event_text = (ROOT / "02_数据资产层标准体系草案.md").read_text(encoding="utf-8")
    rows = extract_table(event_text, "### S2-03", "### S2-04")
    event_rows = [[row[0], event.strip(), row[2], "S2-03"] for row in rows[1:] for event in row[1].split("、")]
    save_csv(ROOT / "附件" / "最小事件词表.csv", ["类别", "事件", "业务语义", "对应条款"], event_rows)
    original_rows = [{"file": p.name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((ROOT.parent / "原始文档").iterdir()) if p.is_file()]
    save_json(ROOT / "附件" / "原始文件核验.json", original_rows)
    dictionary()
    samples()
    diagram()
    LOG.info("Companion tables, synthetic samples, and architecture diagram generated.")


if __name__ == "__main__":
    main()
