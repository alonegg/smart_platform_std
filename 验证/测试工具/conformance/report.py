"""中文报告；四值计数与未覆盖边界。"""
import json
from .runner import LABELS


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown(result):
    lines = ["# WP3 符合性测试报告", "", result["evidence_scope"], "", "**跳过不计为通过。**", "", "总体：" + {"passed": "通过", "failed": "不通过", "incomplete": "未完成"}[result["overall"]], "", "| 类别 | 用例 | 观察点 |", "|---|---:|---:|"]
    for status, label in LABELS.items():
        lines.append(f"| {label} | {result['summary']['cases'][status]} | {result['summary']['observations'][status]} |")
    lines += ["", "父项按子用例聚合，不重复计数。"]
    lines += ["", "## 逐用例", "", "| 用例 | 状态 | 承担方 | 交接点 |", "|---|---|---|---|"]
    for case in result["cases"]:
        lines.append("| " + " | ".join(cell(case[k]) for k in ("case_id", "status_label", "bearer", "handoff")) + " |")
    for case in result["cases"]:
        lines += ["", "### " + case["case_id"] + " " + case["title"], "", "理由：" + case["reason"]]
        if case["observations"]:
            lines += ["", "| 观察点 | 预期 | 实际 | 状态 |", "|---|---|---|---|"]
            for obs in case["observations"]:
                lines.append("| " + " | ".join(cell(obs[k]) for k in ("id", "expected", "actual", "status_label")) + " |")
        if case["out_of_tool_scope"]:
            lines += ["", "未覆盖子场景（不计通过）："]
            lines += ["- " + o["scenario"] + "：" + o["reason"] + "（" + o["assumption"] + "）" for o in case["out_of_tool_scope"]]
    return "\n".join(lines) + "\n"


def write(result, json_out, report_out):
    json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    report_out.write_text(markdown(result))
