"""只读校验 WP5 合成用例注记与矩阵编号、追溯表的一致性。"""

import ast
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def check_trace():
    with (ROOT.parent / "平台对标" / "数据要素对照矩阵.csv").open(encoding="utf-8-sig", newline="") as matrix:
        valid_ids = {row["要素编号"] for row in csv.DictReader(matrix)}
    with (ROOT / "追溯表.csv").open(encoding="utf-8", newline="") as trace:
        rows = list(csv.DictReader(trace))
    ids = {row["element_id"] for row in rows}
    assert len(ids) == len(rows), "duplicate trace IDs"
    assert ids <= valid_ids, f"unknown element IDs: {ids - valid_ids}"
    for row in rows:
        assert row["clauses"].strip(), f"missing clauses: {row}"
        paths = row["outputs"].split(";")
        assert "test_integration.py" in paths and all((ROOT / p).is_file() for p in paths), row

    annotated = set()
    cases = ast.parse((ROOT / "test_integration.py").read_text(encoding="utf-8"))
    for case in cases.body:
        if isinstance(case, ast.FunctionDef) and case.name.startswith("test_"):
            clauses, separator, names = (ast.get_docstring(case) or "").partition("|")
            case_ids = set(names.split())
            assert clauses.strip() and separator and case_ids, f"missing trace annotation: {case.name}"
            assert case_ids <= ids, f"{case.name} is missing IDs: {case_ids - ids}"
            annotated |= case_ids
    assert ids == annotated, f"trace rows without tests: {ids - annotated}"
    return len(ids)


if __name__ == "__main__":
    print(f"WP5 trace OK: {check_trace()} element IDs")
