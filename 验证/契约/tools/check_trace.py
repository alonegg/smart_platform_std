"""只读核验首批范围、矩阵追溯、文件存在性及条款/要素注释。"""
import csv
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
OBJECTS = """Person Organization AcademicSession Course CourseVersion Offering Enrollment
EnrollmentRound TeachingAssignment ApplicationInstance AccessGrant Resource Segment RightsRecord
LearningActivity AssessmentPlan AssessmentAdjustment TaskAttempt Submission ProcessArtifact
GradeDecision Feedback PeerReview CognitiveState EvidenceLink MethodRegistration MethodApproval""".split()
PREFIXES = ("FLD-RES-", "FLD-RGT-", "FLD-EVT-", "FLD-MAN-", "FLD-COG-", "FLD-MTH-")
CLAUSE = re.compile(r"(?<![\w.])(?:[A-D]\.\d+(?:\.\d+)*|\d+(?:\.\d+)+)(?![\w.])")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def baseline(repo=REPO):
    with (repo / "验证/平台对标/数据要素对照矩阵.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    matrix = {row["要素编号"]: row for row in rows}
    expected = {key for key, row in matrix.items()
                if key.startswith(PREFIXES + ("EVT-",))
                or (key.startswith("OBJ-") and row["要素名"] in [*OBJECTS, "LearningEvent"])}
    return matrix, expected


def check_trace(root=ROOT, repo=REPO):
    errors = []
    matrix, expected = baseline(repo)
    standard = (repo / "标准/评审稿/智慧教学-数据模型标准.md").read_text(encoding="utf-8")
    clauses = set(re.findall(r"(?m)^\s*(?:#{1,6}\s+)?(\d+(?:\.\d+)+|[A-D]\.\d+(?:\.\d+)*)(?=\s)", standard))
    def check_clauses(value, location):
        values = value if isinstance(value, list) else [value]
        if not values:
            errors.append(f"{location}: 条款列表为空")
        for item in values:
            if not isinstance(item, str):
                errors.append(f"{location}: 条款必须为字符串")
                continue
            tokens = CLAUSE.findall(item)
            if not tokens or any(token not in clauses for token in tokens):
                errors.append(f"{location}: 无效条款 {item}")
    scope = load(root / "scope.json")
    listed = scope.get("element_ids", [])
    if set(listed) != expected or len(listed) != len(set(listed)):
        errors.append(f"scope首批要素不一致: missing={sorted(expected-set(listed))}, extra={sorted(set(listed)-expected)}")
    events = load(root / "vocab/event_types.json")["values"]
    if set(scope.get("objects", [])) != set(OBJECTS) or set(scope.get("events", [])) != {e["event_type"] for e in events}:
        errors.append("scope首批对象/事件清单不完整")
    if set(scope.get("exchange_targets", [])) != {"manifest", "receipt", "export-receipt"}:
        errors.append("scope交换目标清单不完整")
    with (root / "追溯表.csv").open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not {"element_id", "条款", "输出文件", "状态", "理由"} <= set(reader.fieldnames or []):
            errors.append("追溯表列不完整")
        trace = list(reader)
    ids = [r.get("element_id") for r in trace]
    if len(ids) != len(set(ids)):
        errors.append("追溯表要素编号重复")
    if set(ids) != set(matrix):
        errors.append("追溯表未逐项登记矩阵全部要素及范围外理由")
    traced_files = {}
    prefix = "验证/契约/"
    for row in trace:
        key = row.get("element_id", "")
        if key not in matrix:
            errors.append(f"追溯表无效要素: {key}")
        status = row.get("状态")
        if status not in {"covered", "assumption", "out_of_scope"}:
            errors.append(f"{key}: 无效状态")
        if key in expected and status == "out_of_scope":
            errors.append(f"{key}: 首批要素不能标范围外")
        if status == "out_of_scope" and not row.get("理由", "").strip():
            errors.append(f"{key}: 范围外缺少理由")
        check_clauses(row.get("条款", ""), key)
        paths = row.get("输出文件", "").split(";") if row.get("输出文件") else []
        if status in {"covered", "assumption"} and not paths:
            errors.append(f"{key}: 缺少输出文件")
        traced_files[key] = set(paths)
        for path in paths:
            relative = Path(path.removeprefix(prefix))
            if not path.startswith(prefix) or relative.is_absolute() or ".." in relative.parts or not (root / relative).is_file():
                errors.append(f"{key}: 输出文件不存在或越界 {path}")
    annotations = 0
    files = sorted(p for folder in ["schema", "events", "fixtures"] for p in (root / folder).rglob("*.json"))
    for path in files:
        document = load(path)
        location = prefix + str(path.relative_to(root))
        meta = document.get("fixture", document)
        clause_key = "clauses" if "fixture" in document or path.parent.name == "events" else "x-clause"
        element_key = "elements" if clause_key == "clauses" else "x-elements"
        if not meta.get(clause_key) or not meta.get(element_key):
            errors.append(f"{location}: 缺少根条款或要素注释")
        for node in walk(document):
            for key in ["clauses", "x-clause"]:
                if key in node:
                    check_clauses(node[key], location)
            for key in ["elements", "x-elements"]:
                if key in node:
                    if not isinstance(node[key], list):
                        errors.append(f"{location}: 要素列表格式错误")
                        continue
                    for element in node[key]:
                        annotations += 1
                        if element not in matrix:
                            errors.append(f"{location}: 无效矩阵要素 {element}")
                        elif location not in traced_files.get(element, set()):
                            errors.append(f"{location}: 注释要素未追溯到本文件 {element}")
    return {"result": "failed" if errors else "passed", "scope_elements": len(expected),
            "matrix_elements": len(matrix), "trace_rows": len(trace), "documents": len(files),
            "annotations": annotations, "errors": sorted(set(errors))}


def main():
    try:
        result = check_trace()
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result = {"result": "failed", "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["result"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
