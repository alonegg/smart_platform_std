"""8.11、A.8；OBJ-029；只读校验参考公共服务范围与逐要素追溯。"""
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
MATRIX = REPO / "验证/平台对标/数据要素对照矩阵.csv"


def check(scope_path=ROOT / "scope.json", trace_path=ROOT / "追溯表.csv", matrix_path=MATRIX):
    errors = []
    scope = json.loads(Path(scope_path).read_text(encoding="utf-8"))
    elements = scope["element_ids"]
    if not elements or len(set(elements)) != len(elements):
        errors.append("scope must contain unique, nonempty element_ids")
    with Path(matrix_path).open(encoding="utf-8-sig", newline="") as f:
        known = {r["要素编号"] for r in csv.DictReader(f)}
    with Path(trace_path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["element_id", "条款", "输出文件", "状态", "理由"]:
            errors.append("trace column names/order do not match contract")
        rows = list(reader)
    ids = [r.get("element_id", "") for r in rows]
    if len(set(ids)) != len(ids):
        errors.append("duplicate trace element_id")
    for element in sorted(set(elements) - set(ids)):
        errors.append("missing trace: " + element)
    for element in sorted(set(ids) - set(elements)):
        errors.append("outside scope: " + element)
    for element in sorted((set(elements) | set(ids)) - known):
        errors.append("unknown matrix element: " + element)
    for row in rows:
        element = row.get("element_id", "")
        if not all(row.get(k) for k in ("条款", "输出文件", "状态", "理由")):
            errors.append("incomplete trace: " + element)
        if row.get("状态") not in ("covered", "assumption", "partial"):
            errors.append("invalid status: " + element)
        for filename in row.get("输出文件", "").split(";"):
            path = (REPO / filename).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file():
                errors.append("missing or outside package output: " + filename)
            elif element not in path.read_text(encoding="utf-8"):
                errors.append(f"element absent in output: {element}: {filename}")
    return errors, len(elements), len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path, default=ROOT / "scope.json")
    parser.add_argument("--trace", type=Path, default=ROOT / "追溯表.csv")
    args = parser.parse_args()
    try:
        errors, elements, rows = check(args.scope, args.trace)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("FAIL: " + str(error))
        return 1
    if errors:
        print("\n".join("FAIL: " + error for error in errors))
        return 1
    print(f"PASS: {elements} scoped elements, {rows} trace rows; matrix IDs, files and annotations verified (synthetic scope only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
