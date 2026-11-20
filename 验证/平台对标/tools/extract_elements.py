#!/usr/bin/env python3
"""从当前评审稿的指定表格生成平台对标骨架；合并字段保持原表一行。

运行：python3 验证/平台对标/tools/extract_elements.py
输出会覆盖已有矩阵（包括人工填写列），请在填写后另存或先备份。
表 10-2 的中文内容名保持原文，不推定未规定的字段标识；
表 10-1 的派生状态保留原表语义，不视为记录的持久化字段。
"""

import csv
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "标准/评审稿/智慧教学-数据模型标准.md"
OUTPUT = Path(__file__).resolve().parents[1] / "数据要素对照矩阵.csv"
HEADERS = [
    "要素编号", "数据类别", "要素类型", "要素名", "标准条款", "标准定义摘要",
    "OpenEdX对应", "OpenEdX状态", "OpenEdX依据", "Moodle对应", "Moodle状态",
    "Moodle依据", "缺失时补齐方", "补齐路径(标准条款)", "AI应用接入关系",
    "标准定义充分性", "意见建议",
]
TABLES = [
    ("5-1", "核心对象总览", "OBJ", "", "5.1.8", "object_type", "含义"),
    ("6-2", "Resource 版本字段", "FLD-RES", "Resource", "6.2.1", "字段", "说明"),
    ("6-3", "RightsRecord 成员", "FLD-RGT", "RightsRecord", "6.3.1", "成员", "内容"),
    ("7-1", "事件公共结构的适用条件与约束", "FLD-EVT", "LearningEvent", "7.2", "字段", "约束"),
    ("7-2", "最小事件词表", "EVT", "", "7.3.1", "事件", "必要业务语义"),
    ("8-1", "manifest 成员", "FLD-MAN", "manifest", "8.2.5", "成员", "说明"),
    ("10-1", "CognitiveState 最小字段", "FLD-COG", "CognitiveState", "10.3.1", "字段", "语义"),
    ("10-2", "MethodRegistration 与 MethodApproval 登记内容", "FLD-MTH", "", "10.8.2", "内容", "要求"),
]
RESOURCE_OBJECTS = {
    "Course", "CourseVersion", "ProgramVersion", "LearningUnit", "LearningActivity",
    "LearningObjective", "Framework", "KnowledgePoint", "Competency", "ProgramAlignment",
    "Resource", "Segment", "RightsRecord", "AssessmentItem", "AssessmentPlan",
    "AssessmentAdjustment", "Rubric", "RubricCriterion",
}
COGNITIVE_OBJECTS = {
    "Scale", "CognitiveState", "MethodRegistration", "MethodApproval", "LearningRecommendation",
}
PROCESS_OBJECTS = {
    "TaskAttempt", "LearnerGroup", "LearningEvent", "ProcessArtifact", "Submission",
    "HelpRecord", "Feedback", "GradeDecision", "PeerReview", "ObservationRecord", "EvidenceLink",
}


def cells(line):
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip()[1:-1])]


def extract_table(lines, number, title):
    caption = f"表 {number} {title}"
    positions = [i for i, line in enumerate(lines) if line.strip() == caption]
    if len(positions) != 1:
        raise ValueError(f"{caption}: 应有且仅有一个表标题，实际 {len(positions)}")
    start = positions[0] + 1
    while start < len(lines) and not lines[start].strip():
        start += 1
    block = []
    while start < len(lines) and lines[start].strip().startswith("|"):
        block.append(cells(lines[start]))
        start += 1
    if len(block) < 3 or not all(re.fullmatch(r":?-{3,}:?", c) for c in block[1]):
        raise ValueError(f"{caption}: 缺少表头、分隔行或数据行")
    header = block[0]
    if any(len(row) != len(header) for row in block[2:]):
        raise ValueError(f"{caption}: 数据列数与表头不符")
    return [dict(zip(header, row)) for row in block[2:]]


def category(number, name):
    if number.startswith("6-") or (number == "5-1" and name in RESOURCE_OBJECTS):
        return "课程资源"
    if number.startswith("7-") or (number == "5-1" and name in PROCESS_OBJECTS):
        return "教学过程与学习证据"
    if number.startswith("10-") or (number == "5-1" and name in COGNITIVE_OBJECTS):
        return "认知诊断"
    return "公共与交换"


def build_rows(markdown):
    rows, counts = [], []
    for number, title, code, prefix, clause, name_column, meaning_column in TABLES:
        source_rows = extract_table(markdown.splitlines(), number, title)
        counts.append((number, len(source_rows)))
        for index, source in enumerate(source_rows, 1):
            name = source[name_column].replace("`", "")
            owner = source["对象"] if number == "10-2" else prefix
            if owner:
                name = "、".join(f"{owner}.{part}" for part in name.split("、"))
            summary = source[meaning_column]
            if len(summary) > 120:
                summary = summary[:119] + "…"
            reference = f"{clause}（表 {number}）"
            if number == "5-1":
                reference += f"；定义条款：{source['定义条款']}"
            rows.append([
                f"{code}-{index:03d}", category(number, name),
                "对象" if code == "OBJ" else "事件" if code == "EVT" else "字段",
                name, reference, summary,
            ] + [""] * (len(HEADERS) - 6))
    return rows, counts


def main():
    rows, counts = build_rows(SOURCE.read_text(encoding="utf-8"))
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(HEADERS)
        writer.writerows(rows)
    for number, count in counts:
        print(f"表 {number}: {count} 行")
    print(f"CSV 数据行: {len(rows)}；含表头: {len(rows) + 1} 行")


if __name__ == "__main__":
    main()
