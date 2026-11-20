import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BENCHMARK = ROOT / "验证/平台对标"
PROPOSALS = "修订条文建议.md"
PROFILE_DOC = "最小可行Profile组合.md"
ASSUMPTIONS = HERE / "临时假设.md"
BLOCKERS = {"E12", "E13", "E14", "E22", "E23a", "E26"}
SUBDECISIONS = {"E23a", "E23b", "E23c"}
DECISION = r"E\d{2}[a-c]?"
CLAUSE = r"(?:\d+|[A-E])(?:\.\d+)*"


def read(path):
    return path.read_text(encoding="utf-8")


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def unique(values, label, errors):
    duplicates = {value for value, count in Counter(values).items() if count > 1}
    if duplicates:
        errors.append(f"{label}重复：{', '.join(sorted(duplicates))}")
    return set(values)


def main():
    errors = []
    standard = read(ROOT / "标准/评审稿/智慧教学-数据模型标准.md")
    clauses = set(re.findall(rf"^(?:#+ )?({CLAUSE})(?= )", standard, re.M))
    tables = set(re.findall(r"^表 ([\dA-E]+[-.]\d+) ", standard, re.M))
    profiles = set(re.findall(r"^\| (P-[A-Z]+) \|", standard, re.M))
    cases = set(re.findall(r"^\| (T\d{2})(?= )", standard, re.M))
    cases.update(re.findall(r"^\| (T\d{2}-[A-Z]+) \|", standard, re.M))
    official_decisions = set(re.findall(r"^\| (E\d{2}) \|", standard, re.M))
    documented_subdecisions = set(re.findall(r"^\| (E23[a-c]) ", standard, re.M))
    if documented_subdecisions != SUBDECISIONS:
        errors.append("附录 E.3 分项与 WP0 范围不一致")
    expected_decisions = official_decisions | documented_subdecisions
    matrix = {
        row["要素编号"]
        for row in csv_rows(BENCHMARK / "数据要素对照矩阵.csv")
    }

    sections = re.split(r"^## Issue #(\d+) — .+$", read(HERE / PROPOSALS), flags=re.M)
    issue_numbers = unique(sections[1::2], "Issue", errors)
    if issue_numbers != {str(n) for n in range(39, 48)}:
        errors.append("建议章节必须恰好覆盖 #39–#47")

    by_issue = defaultdict(set)
    for issue, body in zip(sections[1::2], sections[2::2]):
        for heading in ("条款", "要素", "影响的表与 Profile", "原文", "建议条文", "理由"):
            if not re.search(rf"^- {heading}(?:（[^）]+）)?：\s*\S", body, re.M):
                errors.append(f"#{issue} 缺少{heading}")
        refs = re.search(r"^- 条款：(.+)$", body, re.M)
        ids = re.search(r"^- 要素：(.+)$", body, re.M)
        impact = re.search(r"^- 影响的表与 Profile：(.+)$", body, re.M)
        references = set(refs[1].split("、")) if refs else set()
        elements = set(ids[1].split("、")) if ids else set()
        by_issue[issue] = elements
        if not references or references - clauses:
            errors.append(f"#{issue} 条款缺失或无效：{sorted(references - clauses)}")
        if not elements or elements - matrix:
            errors.append(f"#{issue} 要素缺失或无效：{sorted(elements - matrix)}")
        impact_tables = set(re.findall(r"表 ([\dA-E]+[-.]\d+)", impact[1] if impact else ""))
        impact_profiles = set(re.findall(r"P-[A-Z]+", impact[1] if impact else ""))
        if not impact_tables or not impact_profiles or impact_tables - tables or impact_profiles - profiles:
            errors.append(f"#{issue} 表或 Profile 缺失或无效")

    rows = csv_rows(HERE / "追溯表.csv")
    element_ids = unique([row["要素编号"] for row in rows], "追溯要素", errors)
    traced = defaultdict(set)
    for row in rows:
        element, issue = row["要素编号"], row["Issue"]
        refs = set(row["条款"].split(";"))
        destinations = set(row["产出文件"].split(";"))
        if element not in matrix or refs - clauses:
            errors.append(f"{element} 追溯条款或要素无效：{sorted(refs - clauses)}")
        if any(not path or not (HERE / path).is_file() for path in destinations):
            errors.append(f"{element} 产出文件不存在")
        if issue:
            traced[issue].add(element)
            if PROPOSALS not in destinations:
                errors.append(f"{element} 未追溯到修订条文建议")
        elif PROFILE_DOC not in destinations:
            errors.append(f"{element} 未追溯到 Profile 组合建议")
    if traced != by_issue:
        errors.append("Issue 逐项要素与追溯表不一致")

    schedule = read(HERE / "待决事项排期.md")
    decisions = unique(re.findall(rf"^\| ({DECISION}) \|", schedule, re.M), "排期编号", errors)
    if decisions != expected_decisions:
        errors.append(f"排期缺失 {sorted(expected_decisions - decisions)}；额外 {sorted(decisions - expected_decisions)}")
    flagged = set(re.findall(rf"^\| ({DECISION}) \|[^\n]*\| \*\*阻塞\*\*", schedule, re.M))
    if flagged != BLOCKERS:
        errors.append(f"阻塞项不符：{sorted(flagged)}")
    assumption_ids = set(re.findall(DECISION, read(ASSUMPTIONS)))
    if assumption_ids - expected_decisions or BLOCKERS - assumption_ids:
        errors.append("临时假设编号无效或未覆盖计划阻塞项")

    profile_text = read(HERE / PROFILE_DOC)
    profile_refs = set(re.findall(r"\bP-[A-Z]+\b", profile_text))
    case_refs = set(re.findall(r"\bT\d{2}(?:-[A-Z]+)?\b", profile_text))
    expected_profiles = {"P-COM", "P-SUB", "P-GRD", "P-AI", "P-DIA"}
    selected_cases = {
        "T01", "T02", "T05", "T06", "T07", "T08-P", "T08-C", "T08-A", "T08-R",
        "T09", "T10", "T11", "T14", "T23", "T25",
    }
    if not expected_profiles <= profile_refs <= profiles:
        errors.append("组合建议缺少首批 Profile 或引用了无效 Profile")
    if not selected_cases <= case_refs <= cases:
        errors.append(f"组合建议缺少首批用例或引用了无效用例：{sorted(case_refs - cases)}")

    if errors:
        raise SystemExit("\n".join(errors))
    print(f"通过：{len(issue_numbers)} 个 Issue；{len(element_ids)} 个矩阵要素及产出引用。")
    print(f"通过：{len(official_decisions)} 项待决事项、{len(documented_subdecisions)} 个 E23 分项、{len(flagged)} 个计划阻塞项。")
    print(f"通过：{len(expected_profiles)} 个首批 Profile、{len(selected_cases)} 个选测/离线用例引用。")
    print("证据范围：仅文稿静态核验；合成业务场景及真实平台验证未执行。")


if __name__ == "__main__":
    main()
